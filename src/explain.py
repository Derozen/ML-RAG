"""Explicabilite descriptive et audit des citations du RAG FOMC.

Usage:
  python src/explain.py --question "..." --reranker colbert
  python src/explain.py --input results/generation/une_reponse.json

N'invente aucun jugement de pertinence : les recouvrements lexicaux ne
constituent PAS une validation semantique de la reponse.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

SOURCE_RE = re.compile(r"\[SOURCE\s+(\d+)\]", re.IGNORECASE)
WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def citation_audit(answer_text: str, passages: list[dict]) -> dict:
    """Valide uniquement l'existence des identifiants de citation."""
    available = {int(p['rank']): p for p in passages}
    found = [int(m.group(1)) for m in SOURCE_RE.finditer(answer_text)]
    distinct = list(dict.fromkeys(found))
    invalid = [n for n in distinct if n not in available]
    valid = [n for n in distinct if n in available]
    return {
        'citations_mentioned': found,
        'valid_citation_ids': valid,
        'invalid_citation_ids': invalid,
        'cited_sources': [
            {'source_number': n, 'chunk_id': available[n]['chunk_id'],
             'document': available[n]['document'], 'pages': available[n]['pages'],
             'source_url': available[n]['source_url']}
            for n in valid
        ],
        'has_valid_citation': bool(valid),
        'all_citation_ids_valid': not invalid,
        'semantic_support_verified': False,
        'note': ('Validite structurelle des citations uniquement : la concordance '
                 'des affirmations avec les extraits reste a verifier humainement '
                 'ou avec un protocole de verification distinct.'),
    }


def lexical_evidence(question: str, passage: str) -> dict:
    """Indicateur descriptif de chevauchement, non une preuve de pertinence."""
    stop = {'the', 'and', 'for', 'what', 'that', 'with', 'from', 'this', 'were',
            'how', 'did', 'does', 'which', 'when', 'into', 'its', 'are', 'was',
            'would', 'could', 'have', 'has', 'been', 'about', 'starting'}
    terms = {w for w in WORD_RE.findall(question.lower()) if len(w) >= 3 and w not in stop}
    words = set(WORD_RE.findall(passage.lower()))
    overlap = sorted(terms & words)
    return {
        'matched_query_terms': overlap,
        'query_term_coverage': round(len(overlap) / len(terms), 4) if terms else None,
        'warning': 'Chevauchement lexical descriptif, PAS explication causale ni preuve de reponse.',
    }


def retrieval_diagnostics(question: str, passages: list[dict]) -> dict:
    """Recalcule les rangs BM25 et E5 a partir des index courants."""
    import numpy as np
    from rag_pipeline import assets
    from common import CONFIG, lexical_tokens, stable_order

    chunks, bm25, vectors, model, ids = assets()
    id_to_pos = {cid: i for i, cid in enumerate(ids)}
    lexical = np.asarray(bm25.get_scores(lexical_tokens(question)), dtype=float)
    query_text = 'query: ' + question
    if len(model.tokenizer.encode(query_text, truncation=False)) > CONFIG['max_model_tokens']:
        raise ValueError('Question trop longue pour E5')
    v = model.encode([query_text], normalize_embeddings=True,
                     convert_to_numpy=True, show_progress_bar=False)[0]
    dense = vectors @ np.asarray(v, dtype=np.float32)
    lex_ids = [ids[i] for i in stable_order(lexical, ids)]
    dense_ids = [ids[i] for i in stable_order(dense, ids)]
    lex_ranks = {cid: rank for rank, cid in enumerate(lex_ids, 1)}
    dense_ranks = {cid: rank for rank, cid in enumerate(dense_ids, 1)}
    # La fusion utilise uniquement les top-20 de chaque recuperateur,
    # comme dans rag_pipeline.retrieve() par defaut.
    k = 20
    constant = CONFIG['rrf_constant']
    rows = []
    for p in passages:
        cid = p['chunk_id']
        if cid not in id_to_pos:
            raise ValueError(f'Chunk introuvable dans les index : {cid}')
        pos = id_to_pos[cid]
        lr = lex_ranks[cid]
        dr = dense_ranks[cid]
        lexical_rrf = 1 / (constant + lr) if lr <= k else 0.0
        dense_rrf = 1 / (constant + dr) if dr <= k else 0.0
        rows.append({
            'rank_after_reranking': p['rank'], 'chunk_id': cid,
            'bm25_score': float(lexical[pos]), 'bm25_rank_full': lr,
            'dense_cosine_score': float(dense[pos]), 'dense_rank_full': dr,
            'rrf_from_bm25_top20': lexical_rrf,
            'rrf_from_dense_top20': dense_rrf,
            'rrf_total_top20': lexical_rrf + dense_rrf,
            'retrieval_score_recorded': p.get('retrieval_score'),
            'rerank_score_recorded': p.get('rerank_score'),
            'retriever': p.get('retriever'), 'reranker': p.get('reranker'),
            'lexical_evidence': lexical_evidence(question, p['text']),
        })
    return {
        'method': 'Scores des index recalcules sans consulter les qrels',
        'rrf_depth': k, 'rrf_constant': constant,
        'score_warning': ('Scores BM25, E5, RRF et ColBERT sur des echelles differentes; '
                          'les valeurs ne sont pas des probabilites.'),
        'colbert_note': ('Le score MaxSim total est rapporte depuis le pipeline; '
                         'aucune attribution par token n est calculee dans cette version.'),
        'passages': rows,
    }


def build_explanation(run: dict, with_scores: bool = True) -> dict:
    if not isinstance(run, dict) or not isinstance(run.get('answer'), str):
        raise ValueError('Le JSON doit contenir une reponse dans le champ answer')
    passages = run.get('passages')
    if not isinstance(passages, list):
        raise ValueError('Le JSON doit contenir une liste passages')
    ranks = [p['rank'] for p in passages]
    if len(ranks) != len(set(ranks)):
        raise ValueError('Numeros SOURCE dupliques')
    question = run.get('question', '')
    if not question:
        raise ValueError('Question absente')
    audit = citation_audit(run['answer'], passages)
    abstained = bool(run.get('abstained', False))
    return {
        'question': question,
        'answer': run['answer'],
        'model': run.get('model'),
        'retrieval': run.get('retrieval'),
        'reranking': run.get('reranking'),
        'abstained_reported': abstained,
        'citation_audit': audit,
        'retrieval_diagnostics': retrieval_diagnostics(question, passages) if with_scores else None,
        'quality_assessment': 'Aucune verification automatique de fidelite semantique ou hallucination',
    }


def markdown_report(explanation: dict) -> str:
    e = explanation
    a = e['citation_audit']
    lines = ['# Audit explicabilite RAG FOMC', '', '## Question', '', e['question'], '',
             '## Reponse generee', '', e['answer'], '', '## Citations', '',
             f"- References reconnues : {a['valid_citation_ids']}",
             f"- References inconnues : {a['invalid_citation_ids']}",
             '- Support semantique : non verifie automatiquement', '']
    for src in a['cited_sources']:
        lines.append(f"- [SOURCE {src['source_number']}] {src['document']} "
                     f"pages {src['pages']} ; chunk {src['chunk_id']} ; {src['source_url']}")
    diag = e.get('retrieval_diagnostics')
    if diag:
        lines.extend(['', '## Scores descriptifs', '',
                      '| Rang | Chunk | BM25 (rang) | E5 (rang) | RRF-20 | Reranker |',
                      '|---:|---|---:|---:|---:|---:|'])
        for p in diag['passages']:
            lines.append(
                f"| {p['rank_after_reranking']} | {p['chunk_id']} | "
                f"{p['bm25_score']:.3f} ({p['bm25_rank_full']}) | "
                f"{p['dense_cosine_score']:.3f} ({p['dense_rank_full']}) | "
                f"{p['rrf_total_top20']:.5f} | {p['rerank_score_recorded']} |"
            )
    lines.extend(['', '## Limites', '',
                  '- La presence d une citation ne prouve pas que la phrase est soutenue par la source.',
                  '- Les scores ne sont pas des probabilites et ne demontrent pas la causalite.',
                  '- Les passages sources sont des donnees non fiables, pas des consignes.',
                  '- Les qrels silver ne sont pas consultes lors de la generation.', ''])
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--question', help='Question libre a envoyer au pipeline RAG')
    source.add_argument('--input', type=Path, help='JSON deja genere par generate.py')
    parser.add_argument('--method', default='hybrid_rrf', choices=['bm25', 'dense', 'hybrid_rrf'])
    parser.add_argument('--reranker', default='colbert', choices=['none', 'bm25', 'colbert', 'cross_encoder'])
    parser.add_argument('--no-scores', action='store_true', help='Ne pas recalculer BM25 et E5')
    parser.add_argument('--output-dir', type=Path, default=Path('results/explanations'))
    args = parser.parse_args()
    if args.input:
        with args.input.open(encoding='utf-8-sig') as f:
            run = json.load(f)
    else:
        from generate import answer
        run = answer(args.question, method=args.method, reranker=args.reranker)
    exp = build_explanation(run, with_scores=not args.no_scores)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / 'explanation.json').write_text(
        json.dumps(exp, indent=2, ensure_ascii=False), encoding='utf-8')
    (args.output_dir / 'explanation.md').write_text(
        markdown_report(exp), encoding='utf-8')
    print('Audit cree :', args.output_dir / 'explanation.json')
    print('Rapport cree :', args.output_dir / 'explanation.md')
    print('Citations inconnues :', exp['citation_audit']['invalid_citation_ids'])
    print('Support semantique des citations : non verifie automatiquement')


if __name__ == '__main__':
    main()
