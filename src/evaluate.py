"""Comparer les classements de chunks par projection sur les pages silver annotées."""
from collections import defaultdict
import argparse
import csv
import math
from statistics import mean
import numpy as np
from common import ROOT, CONFIG, METHODS, RERANKERS, questions, read_json, read_jsonl, write_json, write_jsonl, write_csv, digest, log
from align_references import project_pages

METRICS = ('recall_at_5', 'recall_at_10', 'recall_at_20', 'ndcg_at_10', 'mrr_at_10', 'pool_page_recall')


def metrics(ids, relevance):
    if len(ids) != len(set(ids)):
        raise ValueError('Classement dupliqué')
    relevant = {pid for pid, grade in relevance.items() if grade > 0}
    if not relevant:
        raise ValueError('Question sans référence pertinente')
    result = {f'recall_at_{k}': len(set(ids[:k]) & relevant) / len(relevant) for k in (5, 10, 20)}
    def dcg(grades):
        return sum((2**g - 1) / math.log2(rank + 1) for rank, g in enumerate(grades, 1))
    ideal = dcg(sorted(relevance.values(), reverse=True)[:10])
    result['ndcg_at_10'] = dcg([relevance.get(pid, 0) for pid in ids[:10]]) / ideal
    first = next((rank for rank, pid in enumerate(ids[:10], 1) if pid in relevant), None)
    result['mrr_at_10'] = 1 / first if first else 0.0
    return result


def main():
    queries = questions()
    qmap = {q['id']: q['question'] for q in queries}
    labels = {q['question_id']: q for q in read_jsonl(ROOT / 'data/evaluation/queries_145.jsonl')}
    audit = read_json(ROOT / 'data/evaluation/alignment_report.json')
    for path, key in [('data/processed/chunks.jsonl', 'chunks_sha256'),
                      ('data/processed/paragraphs.jsonl', 'paragraphs_sha256'),
                      ('data/evaluation/queries_145.jsonl', 'questions_sha256'),
                      ('data/evaluation/silver_qrels_PAGES.trec', 'source_qrels_sha256'),
                      ('data/evaluation/page_qrels.tsv', 'page_qrels_sha256'),
                      ('data/evaluation/chunk_pages.jsonl', 'mapping_sha256')]:
        if digest(ROOT / path) != audit[key]:
            raise ValueError(f'Audit des pages périmé: {path}')
    qrels = defaultdict(dict)
    with (ROOT / 'data/evaluation/page_qrels.tsv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            qrels[row['question_id']][row['page_id']] = int(row['relevance'])
    mapping = {r['chunk_id']: r['page_ids'] for r in read_jsonl(ROOT / 'data/evaluation/chunk_pages.jsonl')}
    source = ROOT / 'results/retrieval/rankings.jsonl'
    retrieval_run = read_json(ROOT / 'results/retrieval/run.json')
    if retrieval_run['rankings_sha256'] != digest(source) or retrieval_run['questions_sha256'] != audit['questions_sha256']:
        raise ValueError('Récupération périmée ou modifiée')
    rankings = defaultdict(list)
    times = {}
    for row in read_jsonl(source):
        rankings[(row['question_id'], row['method'], 'none')].append(row)
    for row in read_jsonl(ROOT / 'results/retrieval/timings.jsonl'):
        times[(row['question_id'], row['method'], 'none')] = dict(retrieval_seconds=row['seconds'], reranking_seconds=0.0)
    for reranker in RERANKERS:
        run = read_json(ROOT / f'results/reranking/{reranker}_run.json')
        path = ROOT / f'results/reranking/{reranker}.jsonl'
        if run['input_rankings_sha256'] != digest(source) or run['output_sha256'] != digest(path) or run['config'] != CONFIG:
            raise ValueError('Reranking périmé ou modifié')
        for row in read_jsonl(path):
            rankings[(row['question_id'], row['retrieval'], reranker)].append(row)
        for row in read_jsonl(ROOT / f'results/reranking/{reranker}_timings.jsonl'):
            times[(row['question_id'], row['retrieval'], reranker)] = dict(
                retrieval_seconds=times[(row['question_id'], row['retrieval'], 'none')]['retrieval_seconds'],
                reranking_seconds=row['seconds'])
    expected = {(qid, method, rr) for qid in qmap for method in METHODS for rr in ('none',) + RERANKERS}
    if set(rankings) != expected or set(times) != expected or set(qrels) != set(qmap):
        raise ValueError('Configurations/questions incomplètes ou inattendues')
    rows, projected = [], []
    ranklists = {}
    for qid in qmap:
        for method in METHODS:
            initial = [r['chunk_id'] for r in sorted(rankings[qid, method, 'none'], key=lambda r: r['rank'])]
            if len(initial) != CONFIG['top_k'] or len(set(initial)) != CONFIG['top_k']:
                raise ValueError('20 candidats uniques requis')
            pool_pages = set(project_pages(initial, mapping))
            positives = {pid for pid, grade in qrels[qid].items() if grade > 0}
            pool_recall = len(pool_pages & positives) / len(positives)
            oracle = sorted(pool_pages, key=lambda pid: (-qrels[qid].get(pid, 0), pid))
            ceiling = metrics(oracle, qrels[qid])['ndcg_at_10']
            for reranker in ('none',) + RERANKERS:
                ordered = sorted(rankings[qid, method, reranker], key=lambda r: r['rank'])
                if [r['rank'] for r in ordered] != list(range(1, CONFIG['top_k'] + 1)):
                    raise ValueError('Rangs de chunks invalides')
                ids = [r['chunk_id'] for r in ordered]
                if len(ids) != len(initial) or set(ids) != set(initial):
                    raise ValueError('Le pool de chunks a changé')
                if method == 'bm25' and reranker == 'bm25' and ids != initial:
                    raise ValueError('Contrôle BM25 incohérent')
                pages = project_pages(ids, mapping)
                if set(pages) != pool_pages:
                    raise ValueError('Le pool de pages a changé')
                scores = metrics(pages, qrels[qid])
                if scores['ndcg_at_10'] > ceiling + 1e-12:
                    raise ValueError('Score supérieur au plafond des pages candidates')
                elapsed = times[qid, method, reranker]
                rows.append(dict(question_id=qid, retrieval=method, reranker=reranker,
                    question_type=labels[qid].get('question_type', ''), topic=labels[qid].get('topic', ''),
                    source_split=labels[qid].get('split', ''), evaluation_unit='page',
                    **scores, pool_page_recall=pool_recall, candidate_pages=len(pages),
                    oracle_ndcg_at_10=ceiling, **elapsed, total_seconds=sum(elapsed.values())))
                projected.append(dict(question_id=qid, retrieval=method, reranker=reranker,
                                      chunk_ids=ids, page_ids=pages))
                ranklists[qid, method, reranker] = pages
    summary = []
    for method in METHODS:
        for reranker in ('none',) + RERANKERS:
            group = [r for r in rows if r['retrieval'] == method and r['reranker'] == reranker]
            summary.append(dict(configuration=method if reranker == 'none' else method + ' + ' + reranker,
                retrieval=method, reranker=reranker, questions=len(group), evaluation_unit='page',
                **{key: mean(r[key] for r in group) for key in METRICS},
                oracle_ndcg_at_10=mean(r['oracle_ndcg_at_10'] for r in group),
                candidate_pages_mean=mean(r['candidate_pages'] for r in group),
                retrieval_median_ms=float(np.median([r['retrieval_seconds'] for r in group]) * 1000),
                reranking_median_ms=float(np.median([r['reranking_seconds'] for r in group]) * 1000),
                total_median_ms=float(np.median([r['total_seconds'] for r in group]) * 1000),
                total_p95_ms=float(np.percentile([r['total_seconds'] for r in group], 95) * 1000)))
    lookup = {(r['question_id'], r['retrieval'], r['reranker']): r for r in rows}
    changes = []
    for method in METHODS:
        for reranker in RERANKERS:
            for metric in ('ndcg_at_10', 'mrr_at_10', 'recall_at_20', 'pool_page_recall'):
                delta = [lookup[qid, method, reranker][metric] - lookup[qid, method, 'none'][metric] for qid in qmap]
                changes.append(dict(retrieval=method, reranker=reranker, metric=metric, mean_delta=mean(delta),
                    improved=sum(v > 1e-12 for v in delta), tied=sum(abs(v) <= 1e-12 for v in delta),
                    worse=sum(v < -1e-12 for v in delta)))
    cases = []
    for method in METHODS:
        for reranker in ('colbert', 'cross_encoder'):
            ordered = sorted(qmap, key=lambda qid: lookup[qid, method, reranker]['ndcg_at_10'] - lookup[qid, method, 'none']['ndcg_at_10'])
            for kind, qid in [('largest_loss', ordered[0]), ('largest_gain', ordered[-1])]:
                cases.append(dict(kind=kind, question_id=qid, question=qmap[qid], retrieval=method, reranker=reranker,
                    reference_pages=qrels[qid], before=ranklists[qid, method, 'none'], after=ranklists[qid, method, reranker],
                    before_ndcg=lookup[qid, method, 'none']['ndcg_at_10'], after_ndcg=lookup[qid, method, reranker]['ndcg_at_10']))
    write_csv(ROOT / 'results/comparison.csv', summary)
    write_csv(ROOT / 'results/metrics_per_question.csv', rows)
    write_csv(ROOT / 'results/paired_changes.csv', changes)
    write_jsonl(ROOT / 'results/page_rankings.jsonl', projected)
    write_jsonl(ROOT / 'results/cases.jsonl', cases)
    write_json(ROOT / 'results/verification.json', dict(questions=len(queries), configurations=12,
        question_configuration_checks=len(rows), corpus_documents=audit['corpus_documents'],
        candidate_chunks_unchanged=True, candidate_pages_unchanged=True, pool_page_recall_invariant=True,
        bm25_control_identical=True,
        candidate_pools_exceeding_20_pages=sum(r['reranker']=='none' and r['candidate_pages']>20 for r in rows),
        candidate_pages_min=min(r['candidate_pages'] for r in rows),
        candidate_pages_max=max(r['candidate_pages'] for r in rows),
        evaluation_unit='unique PDF page', qrels_quality='silver',
        questions_sha256=audit['questions_sha256'], source_qrels_sha256=audit['source_qrels_sha256'],
        chunks_sha256=audit['chunks_sha256'], split='all',
        projection='First occurrence of page in chunk ranking; physical page order within each chunk; deduplicated.',
        note='Recall@20 counts up to 20 unique pages, not 20 chunks; it need not be invariant if a pool contains more than 20 pages.'))
    make_plots(summary)
    make_report(summary, changes, cases, audit)
    evaluate_contexts(projected, mapping, qrels)
    log(f'Évaluation pages terminée: {len(queries)} questions, 12 configurations, {len(rows)} contrôles')


def evaluate_contexts(projected, mapping, qrels):
    """Evaluate 5 and 6 selected chunks, not 5/6 pages or the entire candidate pool."""
    from common import CONTEXT_K
    for budget in (5, CONTEXT_K):
        output = ROOT / f'results/context_top{budget}'
        detailed = []
        contexts = []
        for row in projected:
            qid = row['question_id']
            ids = row['chunk_ids'][:budget]
            if len(ids) != budget or len(set(ids)) != budget:
                raise ValueError('Budget final de contexte non respecté')
            pages = project_pages(ids, mapping)
            relevant = qrels[qid]
            positives = {p for p,g in relevant.items() if g>0}
            def ndcg_at(k):
                gain=lambda grades:sum((2**g-1)/math.log2(i+1) for i,g in enumerate(grades,1))
                return gain([relevant.get(p,0) for p in pages[:k]])/gain(sorted(relevant.values(),reverse=True)[:k])
            first=next((i for i,p in enumerate(pages[:budget],1) if p in positives),None)
            detailed.append(dict(question_id=qid,retrieval=row['retrieval'],reranker=row['reranker'],
                final_chunks=budget,selected_pages=len(pages),
                context_page_recall=len(set(pages)&positives)/len(positives),
                all_reference_pages_found=int(positives<=set(pages)),
                ndcg_pages_at_5=ndcg_at(5),ndcg_pages_at_6=ndcg_at(6),
                mrr_pages_at_budget=1/first if first else 0.0))
            contexts.append(dict(question_id=qid,retrieval=row['retrieval'],reranker=row['reranker'],
                                 chunk_ids=ids,page_ids=pages))
        summary=[]
        keys=('context_page_recall','all_reference_pages_found','ndcg_pages_at_5','ndcg_pages_at_6','mrr_pages_at_budget')
        for method in METHODS:
            for reranker in ('none',)+RERANKERS:
                group=[r for r in detailed if r['retrieval']==method and r['reranker']==reranker]
                summary.append(dict(retrieval=method,reranker=reranker,questions=len(group),final_chunks=budget,
                                    **{key:mean(r[key] for r in group) for key in keys}))
        write_csv(output/'comparison.csv',summary)
        write_csv(output/'metrics_per_question.csv',detailed)
        write_jsonl(output/'contexts.jsonl',contexts)
        import matplotlib.pyplot as plt
        fig, ax=plt.subplots(figsize=(10,6),layout='constrained')
        ax.barh([r['retrieval']+' + '+r['reranker'] for r in summary],
                [r['ndcg_pages_at_6'] for r in summary],color='#22856a')
        ax.set(xlim=(0,1),xlabel='nDCG pages @6',title=f'Contexte final : {budget} chunks après reclassement de 20 candidats')
        ax.invert_yaxis()
        fig.savefig(output/'comparison.png',dpi=160)
        plt.close(fig)
        lines=[f'# Comparaison des contextes finaux de {budget} passages','',
               f'Chaque méthode retient {budget} chunks parmi les mêmes {CONFIG["top_k"]} candidats. Les annotations portent sur les pages ; la couverture ne prouve pas la présence de la réponse dans le chunk.', '',
               '| Recherche | Reranker | Couverture pages du contexte | nDCG pages @6 | Toutes les pages attendues |',
               '|---|---|---:|---:|---:|']
        for r in summary:
            lines.append(f"| {r['retrieval']} | {r['reranker']} | {r['context_page_recall']:.3f} | {r['ndcg_pages_at_6']:.3f} | {r['all_reference_pages_found']:.3f} |")
        lines += ['', 'Les scores décrivent les annotations silver fournies. Les passages non jugés ne sont pas nécessairement non pertinents. Les anciens temps de reclassement concernent le calcul des 20 candidats ; sélectionner 6 passages ne supprime pas ce coût.', '']
        (output/'RAPPORT.md').write_text('\n'.join(lines),encoding='utf-8')
        write_json(output/'verification.json',dict(questions=len(questions()),configurations=12,
            contexts=len(contexts),final_chunks=budget,candidates=CONFIG['top_k'],
            source_rankings_sha256=digest(ROOT/'results/retrieval/rankings.jsonl'),
            qrels_sha256=digest(ROOT/'data/evaluation/page_qrels.tsv')))


def make_plots(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    output = ROOT / 'results/plots'
    output.mkdir(exist_ok=True)
    baseline = [r for r in summary if r['reranker'] == 'none']
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6), layout='constrained')
    for ax, key, title in zip(axes, ('recall_at_20', 'ndcg_at_10', 'mrr_at_10'), ('Recall pages @20', 'nDCG pages @10', 'MRR pages @10')):
        bars = ax.bar(['BM25', 'Dense E5', 'RRF'], [r[key] for r in baseline], color=['#2469a6', '#dc8128', '#22856a'])
        ax.bar_label(bars, fmt='%.3f', padding=3)
        ax.set(title=title, ylim=(0, 1.1))
        ax.grid(axis='y', alpha=.18)
        ax.set_axisbelow(True)
    fig.suptitle(f"Récupération - {CONFIG['questions']} questions - références silver de pages")
    fig.savefig(output / '01_retrieval.png', dpi=180)
    plt.close(fig)
    matrix = np.array([[next(r['ndcg_at_10'] for r in summary if r['retrieval'] == method and r['reranker'] == rr)
                        for rr in ('none',) + RERANKERS] for method in METHODS])
    fig, ax = plt.subplots(figsize=(9, 4.8), layout='constrained')
    im = ax.imshow(matrix, vmin=0, vmax=1, cmap='YlGnBu', aspect='auto')
    ax.set_xticks(range(4), ['Initial', 'BM25', 'ColBERT', 'Cross-encoder'])
    ax.set_yticks(range(3), ['BM25', 'Dense E5', 'RRF'])
    ax.set(xlabel='Reranking des mêmes 20 chunks par ligne', ylabel='Récupération initiale',
           title=f"nDCG pages @10 - {CONFIG['questions']} questions - qrels silver")
    for i in range(3):
        for j in range(4):
            ax.text(j, i, f'{matrix[i,j]:.3f}', ha='center', va='center', fontweight='bold', color='white' if matrix[i,j] > .65 else '#152e48')
    fig.colorbar(im, ax=ax, label='nDCG@10 moyen sur les pages uniques')
    fig.savefig(output / '02_reranking_ndcg.png', dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 5.6), layout='constrained')
    ax.barh([r['configuration'] for r in summary], [r['total_median_ms'] for r in summary], color='#2469a6')
    ax.set(xlabel='Temps total médian par question (ms, échelle logarithmique)',
           title='Durées CPU exploratoires - chargements et préencodage ColBERT exclus', xscale='log')
    ax.invert_yaxis()
    fig.savefig(output / '03_latency.png', dpi=180)
    plt.close(fig)


def make_report(summary, changes, cases, audit):
    best = max(summary, key=lambda r: r['ndcg_at_10'])
    pdf_paths = {d['filename']: d['path'].replace('\\', '/')
                 for d in read_json(ROOT / 'data/processed/manifest.json')}
    lines = [f"# Comparaison FOMC - {CONFIG['questions']} questions et qrels silver de pages", '',
        'Ce rapport conserve le classement complet des 20 candidats pour le diagnostic. La sortie finale est limitée à 6 passages (ou 5). Voir [le rapport des contextes top-6](context_top6/RAPPORT.md) pour les performances des passages effectivement retenus.', '',
        f"Les {audit['questions']} questions et {audit['judgments']} jugements fournis sont utilisés sans changement. Les grades d’origine sont conservés : {audit['grade_counts']}. Toutes les pages annotées existent dans les PDF et sont représentées dans les chunks indexés. Ce contrôle vérifie les fichiers et numéros de pages ; il ne constitue pas une validation humaine de leur pertinence sémantique.", '',
        f"Le corpus analysé comprend {audit['corpus_documents']} PDF et {audit['corpus_chunks']} chunks. Les index documentaires ont été reconstruits après nettoyage, puis la récupération et le reranking recalculés. Aucun entraînement local. Les étiquettes dev/test/validation sont conservées comme métadonnées ; toutes les questions sont évaluées ensemble.", '',
        '## Protocole et unité de mesure', '',
        'BM25, E5 et RRF récupèrent chacun 20 chunks. BM25, ColBERT et le cross-encoder reclassent exactement ces mêmes candidats. Le contrôle BM25 → BM25 conserve le classement initial.', '',
        'Les qrels désignent des pages PDF, pas des chunks. Un chunk est relié aux pages physiques de ses paragraphes. Les pages sont parcourues dans l’ordre des chunks ; à l’intérieur d’un chunk multipage, elles suivent l’ordre physique. Chaque page est conservée à sa première apparition uniquement. Cette règle déterministe traite les pages du même chunk comme un groupe ordonné par numéro, sans utiliser les qrels. Elle peut influencer les métriques aux coupures de rang.', '',
        'Recall@5/10/20 porte sur les premières pages uniques ; nDCG@10 utilise les grades silver et le gain 2^grade−1 ; MRR@10 utilise la première page annotée pertinente. Le classement idéal nDCG utilise tous les qrels de la question. La couverture du pool (pool_page_recall) mesure les pages pertinentes présentes dans l’ensemble des 20 chunks. Cette couverture est invariante après reranking. Recall@20 peut varier si ces 20 chunks couvrent plus de 20 pages uniques.', '',
        '## Résultats moyens', '',
        '| Configuration | Recall pages @20 | nDCG pages @10 | MRR pages @10 | Couverture du pool | Temps total médian (ms) |',
        '|---|---:|---:|---:|---:|---:|']
    for row in summary:
        lines.append(f"| {row['configuration']} | {row['recall_at_20']:.3f} | {row['ndcg_at_10']:.3f} | {row['mrr_at_10']:.3f} | {row['pool_page_recall']:.3f} | {row['total_median_ms']:.1f} |")
    lines += ['', f"Le meilleur nDCG@10 observé est **{best['configuration']} : {best['ndcg_at_10']:.3f}**. Cette conclusion concerne ces questions, ces jugements silver, cette projection en pages et ces checkpoints.", '',
        '## Effet du reranking sur le nDCG@10', '',
        '| Configuration | Écart moyen | Questions améliorées | Inchangées | Dégradées |',
        '|---|---:|---:|---:|---:|']
    for row in changes:
        if row['metric'] == 'ndcg_at_10':
            lines.append(f"| {row['retrieval']} + {row['reranker']} | {row['mean_delta']:+.3f} | {row['improved']} | {row['tied']} | {row['worse']} |")
    notes = read_json(ROOT / 'results/reranking/colbert_run.json')['model_notes']
    lines += ['', '## Modèles, temps et limites', '',
        'E5 : intfloat/e5-small-v2 ; ColBERT : answerdotai/answerai-colbert-small-v1, encodeur BERT et projection apprise à 96 dimensions, marqueurs de rôle et somme MaxSim ; cross-encoder : cross-encoder/ms-marco-MiniLM-L6-v2. Les révisions et paramètres sont figés dans src/common.py. BM25 utilise les statistiques du corpus complet, y compris lors du reranking.', '',
        f"Les temps correspondent à un passage CPU après échauffement, sans chargement des modèles. Le préencodage documentaire ColBERT prend {notes['document_preencoding_seconds']:.1f} secondes et est exclu des durées en ligne. Les temps restent exploratoires.", '',
        'Une page pertinente peut contenir plusieurs passages sans rapport avec la question : retrouver un chunk de cette page ne prouve pas que ce chunk contient la réponse. L’évaluation de pages est donc moins précise qu’une annotation de passages. Aucun grade de chunk n’a été inféré des qrels de pages. Les pages non jugées sont comptées zéro pour les métriques, sans preuve de non-pertinence. Les annotations silver peuvent être incomplètes ou erronées ; une revue humaine ciblée reste possible dans les PDF.', '',
        'Le jeu unique permet une comparaison descriptive à paramètres fixés, sans confirmation indépendante après optimisation. Les nouveaux scores portent sur une autre unité de mesure et ne doivent pas être comparés directement aux anciens scores de chunks.', '',
        '## Fichiers utiles', '',
        '- comparison.csv : les 12 configurations.',
        '- metrics_per_question.csv : scores et métadonnées de toutes les questions.',
        '- page_rankings.jsonl : listes de chunks et pages uniques pour chaque configuration.',
        '- paired_changes.csv : gains, égalités et pertes par question.',
        '- cases.jsonl : exemples avant/après.',
        '- ../data/evaluation/silver_qrels_PAGES.trec : jugements originaux.',
        '- ../data/evaluation/chunk_pages.jsonl : provenance chunk → pages.',
        '- verification.json : vérifications et empreintes des entrées.', '', '## Exemples avant et après', '']
    for case in cases:
        lines += [f"### {case['question_id']} - {case['retrieval']} + {case['reranker']} ({case['kind']})", '',
            case['question'], '', f"nDCG@10 : {case['before_ndcg']:.3f} → {case['after_ndcg']:.3f}.", '',
            '| Page silver | Grade | Rang initial | Rang après |', '|---|---:|---:|---:|']
        for pid, grade in sorted(case['reference_pages'].items()):
            before = case['before'].index(pid) + 1 if pid in case['before'] else 'Absente'
            after = case['after'].index(pid) + 1 if pid in case['after'] else 'Absente'
            filename, page = pid.rsplit('#p', 1)
            link = f"[{pid}](../{pdf_paths[filename]}#page={page})"
            lines.append(f'| {link} | {grade} | {before} | {after} |')
        lines.append('')
    (ROOT / 'results/RAPPORT.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')




# ============================================================
# Évaluation indépendante des 3 récupérateurs, SANS reranking
# ============================================================

def retrieval_only_main():
    """Évalue uniquement les rankings initiaux; n'ouvre aucun résultat de reranking."""
    from pathlib import Path
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    base = ROOT / 'data/evaluation'
    output = ROOT / 'results/retrieval_evaluation'
    output.mkdir(parents=True, exist_ok=True)

    queries = questions()
    query_ids = [q['id'] for q in queries]
    if len(set(query_ids)) != len(query_ids):
        raise ValueError('Identifiants de questions dupliqués')
    labels = {q['question_id']: q for q in read_jsonl(base / 'queries_145.jsonl')}
    audit = read_json(base / 'alignment_report.json')

    checks = [
        ('data/processed/chunks.jsonl', 'chunks_sha256'),
        ('data/processed/paragraphs.jsonl', 'paragraphs_sha256'),
        ('data/evaluation/queries_145.jsonl', 'questions_sha256'),
        ('data/evaluation/silver_qrels_PAGES.trec', 'source_qrels_sha256'),
        ('data/evaluation/page_qrels.tsv', 'page_qrels_sha256'),
        ('data/evaluation/chunk_pages.jsonl', 'mapping_sha256'),
    ]
    for path, key in checks:
        if digest(ROOT / path) != audit[key]:
            raise ValueError(f'Alignement périmé : {path}. Relancer align_references.py')

    qrels = defaultdict(dict)
    with (base / 'page_qrels.tsv').open(encoding='utf-8-sig', newline='') as stream:
        for record in csv.DictReader(stream, delimiter='\t'):
            qid, pid = record['question_id'], record['page_id']
            if pid in qrels[qid]:
                raise ValueError(f'Qrel en doublon : {qid}, {pid}')
            qrels[qid][pid] = int(record['relevance'])
    if set(qrels) != set(query_ids):
        raise ValueError('Questions du jeu et des qrels différentes')

    mapping_rows = read_jsonl(base / 'chunk_pages.jsonl')
    mapping = {r['chunk_id']: r['page_ids'] for r in mapping_rows}
    if len(mapping) != len(mapping_rows):
        raise ValueError('Identifiants chunks dupliqués dans le mapping')

    source = ROOT / 'results/retrieval/rankings.jsonl'
    timing_path = ROOT / 'results/retrieval/timings.jsonl'
    retrieval_run = read_json(ROOT / 'results/retrieval/run.json')
    if (retrieval_run['rankings_sha256'] != digest(source)
            or retrieval_run['questions_sha256'] != audit['questions_sha256']
            or retrieval_run['chunks_sha256'] != audit['chunks_sha256']):
        raise ValueError('Classements périmés : relancer retrieve.py')

    rankings = defaultdict(list)
    for record in read_jsonl(source):
        key = (record['question_id'], record['method'])
        rankings[key].append(record)
    timings = {}
    for record in read_jsonl(timing_path):
        key = (record['question_id'], record['method'])
        if key in timings:
            raise ValueError(f'Temps dupliqué : {key}')
        timings[key] = float(record['seconds'])

    expected = {(qid, method) for qid in query_ids for method in METHODS}
    if set(rankings) != expected or set(timings) != expected:
        raise ValueError('Classements / durées manquants ou supplémentaires')

    detailed, projections = [], []
    for qid in query_ids:
        relevant = qrels[qid]
        for method in METHODS:
            ordered = sorted(rankings[qid, method], key=lambda r: r['rank'])
            ids = [r['chunk_id'] for r in ordered]
            if [r['rank'] for r in ordered] != list(range(1, CONFIG['top_k'] + 1)):
                raise ValueError(f'Rangs invalides : {qid}/{method}')
            if len(ids) != len(set(ids)) or any(cid not in mapping for cid in ids):
                raise ValueError(f'Chunks dupliqués ou sans provenance : {qid}/{method}')
            pages = project_pages(ids, mapping)
            scores = metrics(pages, relevant)
            positive = {pid for pid, grade in relevant.items() if grade > 0}
            pool_page_recall = len(positive & set(pages)) / len(positive)
            oracle = sorted(set(pages), key=lambda pid: (-relevant.get(pid, 0), pid))
            ceiling = metrics(oracle, relevant)['ndcg_at_10']
            if scores['ndcg_at_10'] > ceiling + 1e-12:
                raise ValueError(f'nDCG supérieur à l’oracle : {qid}/{method}')
            detailed.append(dict(
                question_id=qid, retrieval=method, reranker='none',
                question_type=labels[qid].get('question_type', ''),
                topic=labels[qid].get('topic', ''),
                source_split=labels[qid].get('split', ''),
                evaluation_unit='unique_pdf_page', **scores,
                pool_page_recall=pool_page_recall,
                candidate_pages=len(pages), oracle_ndcg_at_10=ceiling,
                retrieval_seconds=timings[qid, method],
            ))
            projections.append(dict(question_id=qid, retrieval=method,
                                    chunk_ids=ids, page_ids=pages))

    summary = []
    for method in METHODS:
        group = [r for r in detailed if r['retrieval'] == method]
        summary.append(dict(
            configuration=method, retrieval=method, reranker='none',
            questions=len(group), evaluation_unit='unique_pdf_page',
            **{metric: mean(r[metric] for r in group) for metric in METRICS},
            oracle_ndcg_at_10=mean(r['oracle_ndcg_at_10'] for r in group),
            candidate_pages_mean=mean(r['candidate_pages'] for r in group),
            retrieval_median_ms=float(np.median([r['retrieval_seconds'] for r in group]) * 1000),
            retrieval_p95_ms=float(np.percentile([r['retrieval_seconds'] for r in group], 95) * 1000),
        ))

    write_csv(output / 'comparison.csv', summary)
    write_csv(output / 'metrics_per_question.csv', detailed)
    write_jsonl(output / 'page_rankings.jsonl', projections)
    write_json(output / 'verification.json', dict(
        questions=len(query_ids), configurations=len(METHODS),
        checks=len(detailed), chunks=audit['corpus_chunks'],
        evaluation_unit='unique PDF page', qrels_quality='silver',
        chunks_sha256=audit['chunks_sha256'],
        rankings_sha256=digest(source),
        note='20 chunks par question et méthode, projetés sur pages uniques. '
             'Une page peut correspondre à une portion minime du chunk. '
             'Les pages non annotées sont notées 0, sans confirmation de non-pertinence.'
    ))

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.5), layout='constrained')
    for ax, key, title in zip(
        axes, ('recall_at_20', 'ndcg_at_10', 'mrr_at_10'),
        ('Recall pages @20', 'nDCG pages @10', 'MRR pages @10')
    ):
        bars = ax.bar([r['retrieval'] for r in summary], [r[key] for r in summary])
        ax.bar_label(bars, fmt='%.3f', padding=3)
        ax.set(title=title, ylim=(0, 1.1))
        ax.grid(axis='y', alpha=.18)
        ax.set_axisbelow(True)
    fig.suptitle(f'Récupération seule : {len(queries)} questions, qrels silver de pages')
    fig.savefig(output / 'retrieval_metrics.png', dpi=180)
    plt.close(fig)

    lines = [
        '# Évaluation de la récupération seule (sans reranking)', '',
        f'Corpus : {audit["corpus_documents"]} PDF, {audit["corpus_chunks"]} chunks.',
        f'Questions : {len(queries)} ; jugements silver : {audit["judgments"]}.',
        'Unité de mesure : pages PDF uniques, obtenues par projection des chunks.',
        'La projection conserve la première apparition de chaque page et '
        'l’ordre physique des pages au sein d’un chunk.', '',
        '| Récupération | Recall@5 | Recall@10 | Recall@20 | nDCG@10 | MRR@10 | Couverture pool | Latence médiane (ms) |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for r in summary:
        lines.append(
            f'| {r["retrieval"]} | {r["recall_at_5"]:.3f} | '
            f'{r["recall_at_10"]:.3f} | {r["recall_at_20"]:.3f} | '
            f'{r["ndcg_at_10"]:.3f} | {r["mrr_at_10"]:.3f} | '
            f'{r["pool_page_recall"]:.3f} | {r["retrieval_median_ms"]:.1f} |'
        )
    lines += [
        '', '## Limites méthodologiques', '',
        '- Les qrels sont des annotations silver de pages, non de chunks.',
        '- Une page pertinente peut être attribuée à un chunk qui en contient très peu de texte.',
        '- Une page non jugée reçoit 0 dans les métriques, sans preuve de non-pertinence.',
        '- Recall@20 porte sur 20 pages uniques, pas nécessairement sur les 20 chunks.',
        '- Ces latences sont exploratoires ; voir les conventions de mesure de retrieve.py.',
        '- Aucun résultat de reranking n’a été utilisé.', ''
    ]
    (output / 'RAPPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    log(f'Évaluation récupération seule terminée : {len(detailed)} question-méthode ; résultats dans {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--retrieval-only', action='store_true',
                        help='Évaluer BM25, E5 et RRF sans aucun reranker')
    args = parser.parse_args()
    if args.retrieval_only:
        retrieval_only_main()
    else:
        main()
