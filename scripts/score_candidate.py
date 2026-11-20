"""Isolated, explicitly provisional evaluation of assistant-proposed holdout qrels.

No annotation is promoted to human-approved and no frozen input is modified.
Retrieval and reranking receive only question text, never gold answers or qrels.
"""
import argparse
import gc
import math
import os
from pathlib import Path
import sys
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
os.environ.setdefault('HF_HUB_OFFLINE', '1')
import numpy as np
from common import (CONFIG, METHODS, RERANKERS, digest, read_jsonl, write_json,
                    write_jsonl, write_csv, lexical_tokens, stable_order, log)
from build_indexes import load_indexes, load_dense_encoder
from retrieve import rrf
from rerank import ColBERT, CrossEncoder, maxsim
from align_references import project_pages
from protocol import verify


def context_metrics(pages, relevance, budget):
    positives = {p for p, g in relevance.items() if g > 0}
    assert positives and len(pages) == len(set(pages))
    gain = lambda grades: sum((2**g-1)/math.log2(i+1) for i, g in enumerate(grades, 1))
    ideal = gain(sorted(relevance.values(), reverse=True)[:budget])
    first = next((i for i,p in enumerate(pages[:budget], 1) if p in positives), None)
    return dict(context_page_recall=len(set(pages)&positives)/len(positives),
                all_reference_pages_found=int(positives <= set(pages)),
                ndcg_pages_at_budget=gain([relevance.get(p,0) for p in pages[:budget]])/ideal,
                mrr_pages_at_budget=1/first if first else 0.)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--provisional', action='store_true', required=True)
    args = parser.parse_args()
    verify()
    candidate = ROOT/'data/holdout_candidate'
    inputs = [candidate/'queries_20.jsonl', candidate/'assistant_review/completed_proposal/qrels_PAGES_proposed.trec',
              ROOT/'data/evaluation/chunk_pages.jsonl', ROOT/'protocol/frozen_pipeline_20261120.json', Path(__file__)]
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in inputs}
    out = ROOT/'results/candidate_provisional'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out.mkdir(parents=True, exist_ok=False)
    write_json(out/'run.json', dict(status='running_provisional', final_independent_test=False,
        human_approved=False, input_sha256=hashes, selected_before_scoring='hybrid_rrf + colbert',
        candidates=20, output_budgets=[5,6], generation_evaluated=False))
    queries = [{'id':q['question_id'], 'question':q['question']} for q in read_jsonl(inputs[0])]
    assert len(queries)==20 and len({q['id'] for q in queries})==20
    # Questions-only checkpoint is written before loading judgments.
    write_jsonl(out/'questions_only.jsonl', queries)
    chunks, bm25, vectors = load_indexes()
    ids = [c['chunk_id'] for c in chunks]
    by_id = {c['chunk_id']:c for c in chunks}
    indices = {cid:i for i,cid in enumerate(ids)}
    encoder = load_dense_encoder()
    pools, rankings, records = {}, {}, []
    for q in queries:
        text = q['question']
        assert len(encoder.tokenizer.encode('query: '+text, truncation=False)) <= CONFIG['max_model_tokens']
        lexical = np.asarray(bm25.get_scores(lexical_tokens(text)))
        vec = encoder.encode(['query: '+text], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)[0]
        dense = vectors @ vec
        orders = {'bm25':[ids[i] for i in stable_order(lexical,ids)[:20]],
                  'dense':[ids[i] for i in stable_order(dense,ids)[:20]]}
        orders['hybrid_rrf'] = rrf([orders['bm25'],orders['dense']], CONFIG['rrf_constant'])[0][:20]
        for method, order in orders.items():
            assert len(order)==len(set(order))==20
            pools[q['id'],method] = order
            rankings[q['id'],method,'none'] = order
        log('Récupération '+q['id'])
    del encoder
    gc.collect()
    for rr in RERANKERS:
        log('Reclassement '+rr)
        model = ColBERT() if rr=='colbert' else CrossEncoder() if rr=='cross_encoder' else None
        if rr=='colbert':
            union = sorted({cid for order in pools.values() for cid in order})
            embedded = dict(zip(union, model.encode([by_id[c]['search_text'] for c in union],False)))
        for q in queries:
            if rr=='colbert': qvec = model.encode([q['question']],True)[0]
            if rr=='bm25': lexical = bm25.get_scores(lexical_tokens(q['question']))
            for method in METHODS:
                before = pools[q['id'],method]
                scores = ([maxsim(qvec,embedded[c]) for c in before] if rr=='colbert' else
                          model.score(q['question'],[by_id[c]['search_text'] for c in before]) if rr=='cross_encoder' else
                          [lexical[indices[c]] for c in before])
                assert len(scores)==20 and np.isfinite(scores).all()
                after = [before[i] for i in stable_order(scores,before)]
                assert set(after)==set(before)
                if method==rr=='bm25': assert after==before
                rankings[q['id'],method,rr] = after
            log(rr+' '+q['id'])
        if rr=='colbert': del embedded
        del model
        gc.collect()
    for (qid,method,rr), order in rankings.items():
        records.append(dict(question_id=qid,retrieval=method,reranker=rr,chunk_ids=order))
    assert len(records)==240
    write_jsonl(out/'rankings.jsonl',records)
    # Evaluation-only inputs are first read here, after all model rankings are fixed.
    qrels = defaultdict(dict)
    for line in inputs[1].read_text(encoding='utf-8-sig').splitlines():
        if line.strip():
            qid, _, page, grade = line.split()
            assert page not in qrels[qid] and int(grade) in (0,1,2)
            qrels[qid][page] = int(grade)
    assert set(qrels)=={q['id'] for q in queries} and sum(map(len,qrels.values()))==294
    mapping = {r['chunk_id']:r['page_ids'] for r in read_jsonl(inputs[2])}
    rows, contexts, summaries = [], [], []
    for rec in records:
        for budget in (5,6):
            selected = rec['chunk_ids'][:budget]
            pages = project_pages(selected,mapping)
            scores = context_metrics(pages,qrels[rec['question_id']],budget)
            rows.append(dict(question_id=rec['question_id'],retrieval=rec['retrieval'],reranker=rec['reranker'],budget=budget,**scores))
            contexts.append(dict(question_id=rec['question_id'],retrieval=rec['retrieval'],reranker=rec['reranker'],budget=budget,chunk_ids=selected,page_ids=pages))
    keys = ('context_page_recall','all_reference_pages_found','ndcg_pages_at_budget','mrr_pages_at_budget')
    for budget in (5,6):
        for method in METHODS:
            for rr in ('none',)+RERANKERS:
                group = [r for r in rows if (r['budget'],r['retrieval'],r['reranker'])==(budget,method,rr)]
                assert len(group)==20
                summaries.append(dict(budget=budget,retrieval=method,reranker=rr,questions=20,**{k:mean(r[k] for r in group) for k in keys}))
    write_csv(out/'metrics_per_question.csv',rows)
    write_csv(out/'comparison.csv',summaries)
    write_jsonl(out/'contexts.jsonl',contexts)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    six = [r for r in summaries if r['budget']==6]
    fig, ax = plt.subplots(figsize=(10,6),layout='constrained')
    bars = ax.barh([r['retrieval']+' + '+r['reranker'] for r in six],[r['ndcg_pages_at_budget'] for r in six])
    ax.bar_label(bars,fmt='%.3f',padding=3)
    ax.set(xlim=(0,1.05),xlabel='nDCG pages@6 — 6 chunks en sortie',title='PROVISOIRE : 20 questions, qrels proposés par assistant')
    ax.invert_yaxis()
    fig.savefig(out/'comparison.png',dpi=170)
    plt.close(fig)
    selected = next(r for r in six if r['retrieval']=='hybrid_rrf' and r['reranker']=='colbert')
    lines = ['# Évaluation provisoire du lot candidat de 20 questions','',
        '**Ce calcul ne constitue pas un test final indépendant validé.** Les 294 grades sont des propositions de l’assistant ; les validations humaines et sémantiques restent absentes. Le lot est désormais exposé aux scores. Aucun réglage n’est effectué à partir de ceux-ci.','',
        'Les modèles figés reçoivent seulement le texte des questions, avec les mêmes index et paramètres. Chaque reranker conserve les 20 candidats de son récupérateur ; 5 et 6 chunks sont évalués séparément. Les qrels sont chargés après fixation des classements.','',
        '## Budget principal : six chunks','',
        '| Recherche | Reranker | Couverture | Toutes les références | nDCG pages@6 | MRR pages@6 |',
        '|---|---|---:|---:|---:|---:|']
    for r in six:
        lines.append(f"| {r['retrieval']} | {r['reranker']} | {r['context_page_recall']:.3f} | {r['all_reference_pages_found']:.3f} | {r['ndcg_pages_at_budget']:.3f} | {r['mrr_pages_at_budget']:.3f} |")
    lines += ['',f"Système choisi avant cette mesure : **RRF + ColBERT**, nDCG pages@6 provisoire **{selected['ndcg_pages_at_budget']:.3f}**. Le meilleur score observé après calcul ne remplace pas automatiquement ce choix.",'',
        '![Comparaison provisoire](comparison.png)','',
        '## Limites et suite','',
        'Les pages non annotées comptent zéro sans preuve de non-pertinence. Les références sont des pages et ne prouvent pas la présence de la réponse dans le chunk. Les 20 questions sont peu nombreuses et certaines partagent des sources. Aucune supériorité statistique ou qualité de génération n’est établie.','',
        'Restent : validation indépendante des grades, nouveauté sémantique et réponses ; correction versionnée de la génération partielle et des citations hors réunion ; évaluation de réponses générées ; contrôle du paquet de reproduction sur un autre environnement. Si le système est corrigé à partir de ce lot, préparer une nouvelle confirmation indépendante.','',
        'Reproduction : `.\\.venv\\Scripts\\python.exe scripts/score_candidate.py --provisional`. Chaque exécution crée un dossier distinct. Les 145 questions, leurs résultats et les grilles humaines sont préservés.']
    (out/'RAPPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert all(digest(ROOT/p)==sha for p,sha in hashes.items())
    verify()
    write_json(out/'run.json',dict(status='completed_provisional',final_independent_test=False,human_approved=False,
        input_sha256=hashes,questions=20,configurations=12,contexts=480,candidates=20,budgets=[5,6],
        selected_before_scoring='hybrid_rrf + colbert',generation_evaluated=False,
        source_inputs_unchanged=True,output_sha256={p.name:digest(p) for p in out.iterdir() if p.name!='run.json'}))
    log('Résultats provisoires : '+str(out))


if __name__=='__main__':
    main()
