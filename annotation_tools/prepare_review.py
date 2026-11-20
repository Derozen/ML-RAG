"""Prepare complete reading packets without querying any retrieval model."""
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'data/holdout_candidate'


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def main():
    queries = jsonl(BASE / 'queries_20.jsonl')
    gold = {q['question_id']: q for q in jsonl(BASE / 'question_gold.jsonl')}
    semantic = {q['question_id']: q for q in jsonl(BASE / 'semantic_review.jsonl')}
    paragraphs = defaultdict(list)
    for p in jsonl(ROOT / 'data/processed/paragraphs.jsonl'):
        paragraphs[f"{p['filename']}#p{p['page']}"].append(p)
    with (BASE / 'human_review.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    folder = BASE / 'review_packets'
    folder.mkdir(exist_ok=True)
    documents = {d['filename']: ROOT / d['path'] for d in
                 json.loads((ROOT / 'data/processed/manifest.json').read_text(encoding='utf-8'))}
    index = ['# Dossiers de lecture — revue indépendante', '',
             'Ces dossiers contiennent les réponses proposées : ils sont réservés aux annotateurs.',
             'Ils ne sont jamais des entrées du système évalué. Aucune inférence n’est lancée.', '',
             'Lire chaque page, puis renseigner `human_review.csv` : `human_grade` (0/1/2), '
             '`reviewer`, et `notes` (obligatoire en cas de désaccord avec la proposition).',
             '0 = hors réponse ; 1 = élément partiel ou contexte utile ; '
             '2 = preuve explicite d’au moins une facette demandée. Une page peut ne couvrir '
             'qu’une partie d’une question à plusieurs preuves.', '',
             'Lire les 145 anciennes questions avant de conclure sur la nouveauté. '
             'Une similarité lexicale faible ne suffit pas. Comparer aussi les informations '
             'demandées et les réponses, consulter les preuves si nécessaire. '
             'Consigner les paires problématiques dans `semantic_pairs_145.csv`.', '',
             'Renseigner ensuite `question_adjudication.csv` : verdict `distinct`, `overlap` '
             'ou `uncertain`, `old_questions_reviewed` = 145 après lecture, '
             '`answer_verified` et `facets_verified` = yes après vérification, nom du relecteur '
             'et justification. Ne pas cocher ces champs par anticipation.', '',
             'Un désaccord ou une preuve supplémentaire exige une adjudication documentée ; '
             'ne pas modifier silencieusement les propositions initiales. '
             'L’exhaustivité concerne les documents explicitement demandés, pas toutes les '
             'paraphrases possibles dans le corpus. Les 20 questions restent ensemble.', '']
    old = jsonl(ROOT / 'data/evaluation/queries_145.jsonl')
    old_text = ['# Les 145 questions exploratoires à comparer', '',
                'Les réponses et preuves anciennes restent dans les fichiers historiques. '
                'Consulter celles des questions proches avant de statuer.', '']
    for q in old:
        old_text += [f"- **{q['question_id']}** — {q['question']}"]
    (folder / 'old_questions.md').write_text('\n'.join(old_text) + '\n', encoding='utf-8')
    for q in queries:
        qid = q['question_id']
        pages = [r for r in rows if r['question_id'] == qid]
        unresolved = sum(r['proposed_grade'] == '' for r in pages)
        index.append(f"- [{qid}]({qid}.md) — {q['question_type']}, {q['source_scope']} : "
                     f'{len(pages)} pages, dont {unresolved} sans jugement proposé.')
        s = semantic[qid]
        text = [f'# {qid}', '', q['question'], '', '## Réponse proposée à vérifier', '',
                gold[qid]['expected_answer'], '', '## Facettes attendues', '']
        for facet, ids in gold[qid]['facet_page_ids'].items():
            text.append(f"- {facet} : {', '.join(ids)}")
        text += ['', '## Risques de recouvrement avec les anciennes questions', '',
                 s['editorial_review'], '',
                 '**Avis éditorial proposé, à confirmer par le relecteur.**', '',
                 '[Lire les 145 questions](old_questions.md). Les voisins ci-dessous '
                 'sont des pistes, pas une liste exhaustive.', '']
        seen = set()
        for related in s['related_old_questions'] + s['lexical_neighbors']:
            if related['question_id'] not in seen:
                seen.add(related['question_id'])
                text.append(f"- **{related['question_id']}** — {related['question']}")
        text += ['', '## Toutes les pages des documents demandés', '',
                 'Texte issu du prétraitement existant, sans sélection par un modèle. '
                 'En cas de doute de mise en page, ouvrir le PDF physique lié.', '']
        for row in pages:
            pid = row['page_id']
            name, page = pid.rsplit('#p', 1)
            ps = paragraphs[pid]
            if not ps:
                raise ValueError(f'Page sans texte : {pid}')
            grade = row['proposed_grade'] or 'NON JUGÉE'
            pdf_link = Path(os.path.relpath(documents[name], folder)).as_posix()
            text += [f'### {pid}', '', f"Proposition : **{grade}** — facettes : "
                     f"{row['covered_facets'] or 'non déterminées'}.", '',
                     f'[PDF, page physique {page}]({pdf_link}#page={page})', '']
            for p in ps:
                text += [f"**{p['paragraph_id']}**", '', p['text'], '']
        (folder / f'{qid}.md').write_text('\n'.join(text) + '\n', encoding='utf-8')
    (folder / 'INDEX.md').write_text('\n'.join(index) + '\n', encoding='utf-8')
    checklist = BASE / 'question_adjudication.csv'
    fields = ['question_id', 'semantic_verdict', 'old_questions_reviewed',
              'answer_verified', 'facets_verified', 'reviewer', 'rationale']
    # Never overwrite reviewer input, including on repeated preparation.
    if not checklist.exists():
        with checklist.open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows({'question_id': q['question_id']} for q in queries)
    print(f'{len(queries)} reading packets, {len(rows)} question/page pairs. Existing annotations preserved.')


if __name__ == '__main__':
    main()
