"""Publish the complete proposed page grid, without approving or scoring it.

The last pass uses paragraph outlines and thematic sentence screening, followed
by full-page reading of potential additional positive evidence. Negative grades
remain editorial proposals, not independently verified absence of an answer.
"""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from common import digest
from protocol import verify, LOCK
from rebuild_holdout import canonical
import pymupdf

BASE = ROOT / 'data/holdout_candidate'
PRIOR = BASE / 'assistant_review/round_2'
OUT = BASE / 'assistant_review/completed_proposal'
SOURCE = Path(__file__).with_name('remaining_minutes_decisions.json')


def jl(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]


def csv_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def parse_qrels(path):
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        qid, iteration, pid, g = line.split()
        key = qid, pid
        if key in result or iteration != '0' or g not in ('0', '1', '2'):
            raise ValueError('Invalid or duplicate qrel')
        result[key] = int(g)
    return result


def check_coverage(expected, prior, additions):
    if set(prior) & set(additions):
        raise ValueError('The completion pass may not silently revise a prior judgment')
    if set(prior) | set(additions) != set(expected):
        raise ValueError('Missing or out-of-scope question/page pairs')


def main():
    verify()
    # Refuse to discard any later human work or pair-level semantic decisions.
    grid_path = OUT / 'human_review.csv'
    if grid_path.exists() and any(r['human_grade'].strip() or r['reviewer'].strip()
                                  or r['notes'].strip() for r in csv_rows(grid_path)):
        raise ValueError('Human work exists: archive/version it before regeneration')
    protected = [BASE / n for n in ('human_review.csv', 'semantic_pairs_145.csv',
                 'question_adjudication.csv', 'queries_20.jsonl', 'question_gold.jsonl',
                 'qrels_PAGES_candidate.trec')]
    protected_hashes = {str(p.relative_to(ROOT)): digest(p) for p in protected}
    previous_report = json.loads((PRIOR / 'report.json').read_text(encoding='utf-8'))
    for name, expected_hash in previous_report['files_sha256'].items():
        if digest(PRIOR / name) != expected_hash:
            raise ValueError('Previous annotation artifacts changed: ' + name)
    initial = parse_qrels(BASE / 'qrels_PAGES_candidate.trec')
    prior = parse_qrels(PRIOR / 'qrels_PAGES_editorial_proposed.trec')
    grid = csv_rows(BASE / 'human_review.csv')
    expected = {(r['question_id'], r['page_id']) for r in grid}
    if len(grid) != len(expected):
        raise ValueError('Duplicate rows in source grid')
    paragraphs = defaultdict(list)
    pmap = {}
    for p in jl(ROOT / 'data/processed/paragraphs.jsonl'):
        paragraphs[f"{p['filename']}#p{p['page']}"].append(p)
        pmap[p['paragraph_id']] = p
    manifest = {d['filename']: d for d in json.loads((ROOT / 'data/processed/manifest.json').read_text(encoding='utf-8'))}
    records, additions, opened = [], {}, {}
    raw_quote_checks = 0
    try:
        for d in json.loads(SOURCE.read_text(encoding='utf-8')):
            qid = 'HOLDOUT_V2_' + d['question']
            name = d['document']
            if d['grade'] not in (0, 1, 2) or not d['reason'].strip():
                raise ValueError('Explicit valid grade and reason required')
            if name not in opened:
                if digest(ROOT / manifest[name]['path']) != manifest[name]['sha256']:
                    raise ValueError('Source PDF changed')
                opened[name] = pymupdf.open(ROOT / manifest[name]['path'])
            for pg in d['pages']:
                key = qid, f'{name}#p{pg}'
                if key not in expected or key in prior or key in additions:
                    raise ValueError('Unexpected or duplicate completion decision: ' + str(key))
                page_ps = paragraphs[key[1]]
                if not page_ps:
                    raise ValueError('Missing page text')
                raw = canonical(opened[name][pg - 1].get_text())
                snippets = []
                for pid in d.get('paragraph_ids', []):
                    p = pmap[pid]
                    if p['filename'] != name or p['page'] != pg or canonical(p['text']) not in raw:
                        raise ValueError('Quote not located verbatim on physical page: ' + pid)
                    snippets.append(dict(paragraph_id=pid, quote=p['text'], source_sha256=p['source_sha256']))
                    raw_quote_checks += 1
                if d['grade'] > 0 and not snippets:
                    raise ValueError('A positive needs source-bound quotes')
                additions[key] = d['grade']
                records.append(dict(question_id=qid, page_id=key[1], proposed_grade=d['grade'],
                    reason=d['reason'], snippets=snippets, annotator='assistant_editorial_proposal',
                    review_depth='full_page_targeted_positive_review' if d['grade'] > 0
                                 else 'paragraph_outline_and_thematic_sentence_screening',
                    needs_full_independent_page_review=True,
                    page_text_sha256=hashlib.sha256('\n'.join(p['text'] for p in page_ps).encode()).hexdigest()))
    finally:
        for pdf in opened.values():
            pdf.close()
    check_coverage(expected, prior, additions)
    merged = prior | additions
    for q in jl(BASE / 'question_gold.jsonl'):
        for facet, references in q['facet_page_ids'].items():
            if not any(merged.get((q['question_id'], pid), 0) > 0 for pid in references):
                raise ValueError('Uncovered proposed answer facet: ' + facet)
    OUT.mkdir(parents=True, exist_ok=True)
    # All data below remain review artifacts, never model inputs.
    (OUT / 'decisions_last_pass.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
    (OUT / 'qrels_PAGES_proposed.trec').write_text(''.join(f'{qid} 0 {pid} {g}\n' for (qid, pid), g in sorted(merged.items())), encoding='utf-8')
    initial_evidence = {(r['question_id'], r['page_id']): r for r in jl(BASE / 'evidence_20.jsonl')}
    supplement = {(r['question_id'], r['page_id']): r for r in jl(PRIOR / 'decisions.jsonl')}
    completion = {(r['question_id'], r['page_id']): r for r in records}
    quotes, review = [], []
    for r in grid:
        key = r['question_id'], r['page_id']
        if key in completion:
            decision = completion[key]
            reason = decision['reason']
            snippets = decision['snippets']
            depth = decision['review_depth']
        elif key in supplement:
            decision = supplement[key]
            reason, snippets = decision['reason'], decision['snippets']
            depth = 'prior_supplemental_editorial_review'
        else:
            ev = initial_evidence[key]
            reason = '; '.join(f.get('reason', f['facet']) for f in ev['covered_facets'])
            snippets = [s for f in ev['covered_facets'] for s in f['snippets']]
            depth = 'initial_fragment_based_proposal'
        review.append(dict(question_id=key[0], question=r['question'], page_id=key[1],
                           proposed_grade=merged[key], covered_facets=r['covered_facets'],
                           annotation_status='assistant_proposal_pending_independent_review',
                           human_grade='', reviewer='', notes='',
                           assistant_reason=reason, review_depth=depth,
                           initial_grade=initial.get(key, '')))
        quotes.append(dict(question_id=key[0], page_id=key[1], proposed_grade=merged[key],
                           reason=reason, snippets=snippets, review_depth=depth,
                           independent_human_validation=False))
    write_csv(grid_path, review)
    (OUT / 'evidence_proposed.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in quotes), encoding='utf-8')
    report = dict(status='complete_editorial_preannotation_pending_independent_review',
                  questions=20, in_scope_pairs=len(expected), proposed_judgments=len(merged),
                  remaining_without_proposed_grade=0, positive_proposals=sum(g > 0 for g in merged.values()),
                  grade_counts=dict(Counter(merged.values())), last_pass_pairs=len(additions),
                  last_pass_raw_pdf_quote_checks=raw_quote_checks,
                  full_independent_page_review_completed=False,
                  human_second_review_completed=False, semantic_independence_established=False,
                  qrels_exhaustive=False, retrieval_evaluation_performed=False,
                  ready_for_final_scoring=False,
                  method_limitation='Completion negatives were proposed from structured paragraph outlines '
                                    'and thematic sentence screening, not certified exhaustive full-page reading. '
                                    'All proposals require independent full-page review; no keyword absence rule assigns grades.',
                  frozen_protocol_sha256=digest(LOCK), protected_files_sha256=protected_hashes,
                  inputs_sha256={str(p.relative_to(ROOT)): digest(p) for p in
                                 (SOURCE, Path(__file__), PRIOR / 'report.json',
                                  BASE / 'semantic_review.jsonl', ROOT / 'data/processed/paragraphs.jsonl')})
    summary = f'''# Préannotation des 20 questions — dossier consolidé

**Statut : préannotation proposée complète, validation indépendante à effectuer.**

Les **{len(merged)}/{len(expected)} couples question/page** ont maintenant un grade
proposé. Il ne reste aucun grade proposé vide dans ce dossier :
**{report['positive_proposals']} pages positives** et
**{len(merged)-report['positive_proposals']} pages proposées non pertinentes**.
Les 20 questions et les 38 facettes attendues conservent leurs références positives.
Il s'agit d'une couverture des documents explicitement demandés par les questions,
pas d'une affirmation d'exhaustivité des réponses possibles dans tout le corpus.

## Méthode et limites

Le dernier passage couvre les 175 couples encore ouverts après la deuxième passe.
Un examen structuré des débuts de paragraphes et des phrases thématiques a servi
à proposer les grades négatifs. Les pages susceptibles d'ajouter un soutien
positif ont fait l'objet d'une lecture ciblée de leur texte complet ;
{raw_quote_checks} citations supplémentaires ont été contrôlées dans les PDF physiques.
**Les grades 0 de cette passe ne certifient donc pas une absence de réponse après
lecture humaine exhaustive.** Ils doivent être confirmés sur la page complète.
La présence d'un nom, d'un chiffre ou d'un thème ne suffit pas : date, période,
auteur et résolution doivent correspondre à ce qui est demandé.

Grade 2 : preuve explicite d'au moins une facette nécessaire. Grade 1 : preuve
partielle ou contexte directement utile, sans lui attribuer les éléments manquants.
Grade 0 : proposition de non-pertinence pour la question précise, avec raison.
La frontière entre contexte utile et simple proximité thématique doit être
harmonisée par adjudication, notamment pour la révision 0 → 1 de la question 018.

## Fichiers à utiliser pour la validation

Les [20 dossiers de lecture](../../review_packets/INDEX.md) donnent accès aux pages
et aux anciennes questions proches. Leurs mentions de grades décrivent la première
proposition ; utiliser les grades du présent CSV consolidé pour cette revue.

- **human_review.csv** : grille consolidée de 294 propositions ; renseigner
  `human_grade`, `reviewer`, et `notes` en cas de désaccord. Les colonnes de
  l'assistant ne constituent jamais des jugements humains.
- **evidence_proposed.jsonl** : motifs et citations réunis en un seul fichier.
- **qrels_PAGES_proposed.trec** : qrels proposés pour revue, pas qrels finaux approuvés.
- **decisions_last_pass.jsonl** : trace des 175 décisions de cette passe.
- **report.json** : statut, limites et empreintes permettant de reproduire le dossier.

Le contrôle de la grille consolidée s'exécute depuis la racine du projet :

```powershell
.\\.venv\\Scripts\\python.exe annotation_tools/check_review.py --page-review data/holdout_candidate/assistant_review/completed_proposal/human_review.csv
```

Le code de sortie 2 indique que les jugements humains restent à compléter ; il
ne signale pas un échec du pipeline. Les décisions sur la nouveauté et les réponses
se renseignent dans `data/holdout_candidate/question_adjudication.csv`.

Les fichiers initiaux et les propositions intermédiaires sont conservés comme
historique. Le `validation_report.json` à la racine concerne la proposition initiale ;
le présent `report.json` décrit cette consolidation. Les grilles humaines initiales
ne sont pas remplies automatiquement et ne sont pas écrasées.

## Indépendance et utilisation des résultats

Les 145 anciennes questions restent exploratoires. Les 85 questions de développement
servent aux diagnostics ; les autres questions déjà consultées ne sont pas un test neuf.
Le pipeline est toujours figé : **RRF + ColBERT, 20 candidats puis 6 passages**.
Cette annotation n'utilise aucun résultat de récupération/reranking des 20 questions.
Le modèle local essayé auparavant n'a fourni aucun jugement exploitable utilisé ici.

La revue de nouveauté sémantique reste à confirmer, particulièrement pour 014, 019
et 020. La création des questions et leur revue par le même assistant ne constituent
pas deux annotations indépendantes. Les questions 017/018 restent dans le même lot.
Il ne faut pas annoncer un test final indépendant simplement parce que les grades
proposés sont complets. Aucun entraînement supervisé local n'était nécessaire avec
les modèles préentraînés utilisés ; absence d'entraînement ne signifie pas absence
de risque de fuite lors des choix de paramètres ou de l'évaluation.

Après confirmation des grades, des réponses et de la nouveauté, résoudre les
désaccords et figer une version approuvée. Puis mesurer une seule fois le système
figé en lui transmettant **seulement les questions**, jamais les réponses attendues
ni les extraits. Aucune comparaison finale n'a été lancée sur ce lot.
'''
    (OUT / 'RAPPORT.md').write_text(summary, encoding='utf-8')
    if protected_hashes != {str(p.relative_to(ROOT)): digest(p) for p in protected}:
        raise ValueError('Protected source files changed')
    report['files_sha256'] = {p.name: digest(p) for p in OUT.iterdir() if p.is_file() and p.name != 'report.json'}
    (OUT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    verify()
    print(json.dumps({k: report[k] for k in ('status', 'proposed_judgments', 'positive_proposals',
          'remaining_without_proposed_grade', 'last_pass_raw_pdf_quote_checks', 'ready_for_final_scoring')}, indent=2))


if __name__ == '__main__':
    main()
