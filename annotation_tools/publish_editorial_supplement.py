"""Validate and publish explicit assistant decisions without changing human grids.

This is a versioned supplement to the initial 64 proposed qrels, not a release
of a final independent test set. Page grades are explicit editorial decisions;
no grade is inferred from missing keywords or from a retrieval-model ranking.
"""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from protocol import verify, LOCK
from common import digest
from rebuild_holdout import canonical
import pymupdf

BASE = ROOT / 'data/holdout_candidate'
OUT = BASE / 'assistant_review/round_2'
DECISIONS = Path(__file__).with_name('supplemental_editorial_decisions.json')


def jl(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]


def main():
    verify()
    protected = [BASE / n for n in ('human_review.csv', 'semantic_pairs_145.csv',
                 'question_adjudication.csv', 'queries_20.jsonl', 'question_gold.jsonl',
                 'qrels_PAGES_candidate.trec')]
    before = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    queries = {q['question_id']: q for q in jl(BASE / 'queries_20.jsonl')}
    gold = {q['question_id']: q for q in jl(BASE / 'question_gold.jsonl')}
    ps = {p['paragraph_id']: p for p in jl(ROOT / 'data/processed/paragraphs.jsonl')}
    manifest = {d['filename']: d for d in json.loads((ROOT / 'data/processed/manifest.json').read_text(encoding='utf-8'))}
    with (BASE / 'human_review.csv').open(encoding='utf-8-sig', newline='') as f:
        pages = list(csv.DictReader(f))
    expected = {(p['question_id'], p['page_id']) for p in pages}
    old = {}
    for line in (BASE / 'qrels_PAGES_candidate.trec').read_text().splitlines():
        qid, _, pid, grade = line.split()
        old[qid, pid] = int(grade)
    decisions = json.loads(DECISIONS.read_text(encoding='utf-8'))
    additions = {}
    source_documents = {}
    quote_count = 0
    try:
        for decision in decisions:
            qid = 'HOLDOUT_V2_' + decision['question']
            name = decision['document']
            assert name in queries[qid]['source_documents']
            assert decision['grade'] in (0, 1, 2) and decision['reason'].strip()
            assert set(decision.get('facets', [])) <= set(gold[qid]['facet_page_ids'])
            if decision['grade'] == 2:
                assert decision.get('facets'), 'Strong proof must identify an atomic facet'
            if name not in source_documents:
                source = ROOT / manifest[name]['path']
                assert digest(source) == manifest[name]['sha256']
                source_documents[name] = pymupdf.open(source)
            for page in decision['pages']:
                pid = f'{name}#p{page}'
                key = qid, pid
                assert key in expected and key not in additions, (key, 'duplicate or outside scope')
                if key in old:
                    assert decision.get('previous_grade') == old[key], 'A revision must declare the original grade'
                else:
                    assert 'previous_grade' not in decision, 'Revision has no original grade'
                snippets = []
                raw = canonical(source_documents[name][page - 1].get_text())
                for para_id in decision.get('paragraph_ids', []):
                    p = ps[para_id]
                    assert p['filename'] == name and p['page'] == page
                    assert p['source_sha256'] == manifest[name]['sha256']
                    # Layout extraction may join hyphenated words; canonicalization
                    # removes whitespace/punctuation but never invents lexical content.
                    assert canonical(p['text']) in raw, (qid, pid, para_id)
                    snippets.append(dict(paragraph_id=para_id, quote=p['text'], source_sha256=p['source_sha256']))
                    quote_count += 1
                assert decision['grade'] == 0 or snippets, 'Positive decision needs a source-bound quote'
                page_text = '\n'.join(p['text'] for p in ps.values() if p['filename'] == name and p['page'] == page)
                additions[key] = dict(question_id=qid, page_id=pid, proposed_grade=decision['grade'],
                    reason=decision['reason'], facets=decision.get('facets', []), snippets=snippets,
                    previous_grade=old.get(key),
                    page_text_sha256=hashlib.sha256(page_text.encode()).hexdigest(),
                    annotator='assistant_editorial_proposal', independent_human_validation=False,
                    method='Targeted thematic screening followed by editorial reading of the selected pages; '
                           'all previously unjudged Statement pages examined; remaining Minutes pages unjudged.')
    finally:
        for doc in source_documents.values():
            doc.close()
    merged = old | {key: d['proposed_grade'] for key, d in additions.items()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'decisions.jsonl').write_text(''.join(json.dumps(d, ensure_ascii=False) + '\n' for _, d in sorted(additions.items())), encoding='utf-8')
    (OUT / 'qrels_PAGES_editorial_proposed.trec').write_text(''.join(
        f'{qid} 0 {pid} {grade}\n' for (qid, pid), grade in sorted(merged.items())), encoding='utf-8')
    rows = []
    for p in pages:
        key = p['question_id'], p['page_id']
        rows.append(dict(question_id=key[0], page_id=key[1], initial_grade=p['proposed_grade'],
                         supplemental_grade=additions[key]['proposed_grade'] if key in additions else '',
                         combined_editorial_grade=merged.get(key, ''),
                         reason=additions[key]['reason'] if key in additions else '',
                         status='editorial_proposal_pending_human_review' if key in merged else 'unjudged'))
    with (OUT / 'coverage.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    remaining = len(expected - set(merged))
    revisions = len(set(additions) & set(old))
    new_judgments = len(set(additions) - set(old))
    positives = sum(v > 0 for v in merged.values())
    new_positive = sum(d['proposed_grade'] > 0 for d in additions.values())
    stats = dict(initial_proposed_judgments=len(old), supplemental_proposed_judgments=len(additions),
                 newly_judged_pairs=new_judgments, grade_revisions=revisions,
                 supplemental_positive_pages=new_positive, proposed_judgments_total=len(merged),
                 proposed_positive_pages=positives, grade_counts=dict(Counter(merged.values())),
                 in_scope_pairs=len(expected), remaining_unjudged_pairs=remaining,
                 supplemental_raw_pdf_quote_checks=quote_count,
                 remaining_unjudged_statement_pairs=sum(k[1].startswith('monetary') for k in expected - set(merged)),
                 qrels_exhaustive=False, independent_human_validation=False,
                 semantic_independence_established=False, retrieval_evaluation_performed=False,
                 ready_for_final_scoring=False, annotation_model_outputs_used=0,
                 frozen_protocol_sha256=digest(LOCK), protected_files_sha256=before,
                 decisions_sha256=digest(DECISIONS), publisher_sha256=digest(Path(__file__)))
    assert before == {str(p.relative_to(ROOT)): digest(p) for p in protected}
    text = f'''# Complément de revue éditoriale — lot candidat V2

## Choix méthodologique

Compléter les preuves avant de calculer les scores est préférable : des qrels
incomplets peuvent classer à tort une bonne récupération comme une erreur.
Cette étape est une annotation proposée par l'assistant, pas une seconde lecture
humaine indépendante et pas une mesure de performance du système.

## Travail réalisé

- Lecture des pages de Statements encore non jugées, y compris les notes de mise en œuvre.
- Recherche thématique de passages supplémentaires dans les Minutes, puis lecture
  des pages sélectionnées. Cette recherche ciblée n'est pas une lecture exhaustive
  des Minutes et ne démontre pas l'absence d'autres preuves.
- {len(additions)} décisions supplémentaires proposées : {new_judgments} couples
  nouvellement jugés et {revisions} révision(s) motivée(s), dont {new_positive}
  décisions positives (révisions comprises).
- {quote_count} citations complètes vérifiées directement dans les pages physiques
  des PDF, avec contrôle de l'empreinte des sources.
- {len(merged)} jugements proposés au total, dont {positives} positifs.
- {remaining} couples question/page restent non jugés ; ils ne reçoivent pas de zéro.

## Exemples de corrections

- **005, Minutes de juin 2022, p. 8** : inquiétude explicite concernant le désancrage
  des anticipations ; preuve forte de cette facette, indépendamment du vote de 75 points.
- **014, Minutes de mars et septembre 2023, p. 4** : autres passages établissant la
  qualification du PIB par le staff. La p. 8 de septembre explique le choix de
  formulation du communiqué. Ces pages manquaient aux références initiales.
- **009, communiqué de juin 2022, p. 4** : la hausse du crédit primaire est un
  distracteur, elle ne doit pas être confondue avec le vote sur les federal funds.
- **010, communiqué de mars 2025, p. 1 et 3** : soutien partiel sur le changement du
  runoff ; ces pages seules n'établissent pas le raisonnement personnel de Waller.
- **018, communiqué de septembre 2025, p. 1** : révision proposée de 0 à 1 pour
  harmoniser le traitement du contexte collectif. Ce désaccord reste explicite
  et nécessite une adjudication ; le grade initial n'est pas effacé.

## Fichiers et protection contre les fuites

`decisions.jsonl` conserve les motifs et extraits. `coverage.csv` présente tous
les couples et les lacunes. `qrels_PAGES_editorial_proposed.trec` fusionne les
propositions initiales et supplémentaires pour revue, sans les rendre officielles.
Les grilles humaines, les 20 questions, les réponses proposées et les qrels initiaux
restent inchangés ; le pipeline, les 145 questions exploratoires et leurs scores aussi.
Aucun classement de BM25, E5, RRF ou reranker n'a servi à choisir ces ajouts.

Un essai de préannotation avec le modèle local a été arrêté sans produire de
jugement exploitable. **Aucune sortie de ce modèle n'est utilisée ici.**

## Ce qui reste nécessaire

Compléter les {remaining} couples non jugés et faire confirmer les grades,
les réponses et l'absence d'équivalence sémantique avec les 145 anciennes questions.
Les cas 014, 019 et 020 restent à examiner avec attention. Le fait de changer de
date ou de demander un calcul ne prouve pas à lui seul la nouveauté sémantique.
La construction des questions et leur revue par le même assistant ne constituent
pas deux annotations indépendantes.

Une version approuvée devra ensuite être figée avant une unique mesure du système
sélectionné : **RRF + ColBERT, 20 candidats puis 6 passages**. Les questions seules
seront transmises au système, jamais les réponses ou les extraits de référence.
Les 145 questions restent un jeu exploratoire ; aucun entraînement supervisé local
n'a été réalisé. Ce dossier ne donne pas encore le statut de test final au nouveau lot.
'''
    (OUT / 'RAPPORT.md').write_text(text, encoding='utf-8')
    stats['files_sha256'] = {p.name: digest(p) for p in OUT.iterdir() if p.is_file() and p.name != 'report.json'}
    (OUT / 'report.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    verify()
    print(json.dumps({k: stats[k] for k in ('supplemental_proposed_judgments', 'supplemental_positive_pages',
          'proposed_judgments_total', 'remaining_unjudged_pairs', 'remaining_unjudged_statement_pairs',
          'supplemental_raw_pdf_quote_checks')}, indent=2))


if __name__ == '__main__':
    main()
