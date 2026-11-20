"""Profil exploratoire, analyse des erreurs et revue des consignes ECC, sans changer les lots."""
from collections import Counter, defaultdict
from itertools import combinations
import csv
from statistics import mean, median
from common import ROOT, read_json, read_jsonl, write_json, write_csv, digest, log


def main():
    output = ROOT/'results/audit_project'
    output.mkdir(parents=True, exist_ok=True)
    chunks = read_jsonl(ROOT/'data/processed/chunks.jsonl')
    docs = read_json(ROOT/'data/processed/manifest.json')
    queries = read_jsonl(ROOT/'data/evaluation/queries_145.jsonl')
    checks = read_json(ROOT/'data/evaluation/alignment_report.json')
    raw_ok = all(digest(ROOT/d['path']) == d['sha256'] for d in docs)
    if not raw_ok:
        raise ValueError('Un PDF ne correspond plus au corpus indexé')
    labels = {q['question_id']:q for q in queries}
    with (ROOT/'data/evaluation/page_qrels.tsv').open(encoding='utf-8-sig') as stream:
        qrels = list(csv.DictReader(stream,delimiter='\t'))
    page_lots = defaultdict(set)
    for row in qrels:
        page_lots[row['page_id']].add(labels[row['question_id']].get('split','unspecified'))
    overlaps = Counter()
    for lots in page_lots.values():
        for pair in combinations(sorted(lots),2):
            overlaps[' / '.join(pair)] += 1
    normalized = defaultdict(list)
    for q in queries:
        normalized[' '.join(q['question'].lower().split())].append(q['question_id'])
    token_counts = [c['token_count'] for c in chunks]
    profile = dict(documents=len(docs),physical_pages=sum(d['pages'] for d in docs),
        chunks=len(chunks),questions=len(queries),qrels=len(qrels),raw_source_hashes_verified=raw_ok,
        document_types=dict(Counter(d['type'] for d in docs)),
        years=dict(sorted(Counter(d['meeting_end'][:4] for d in docs).items())),
        question_types=dict(Counter(q.get('question_type','unknown') for q in queries)),
        source_splits=dict(Counter(q.get('split','unspecified') for q in queries)),
        chunk_tokens=dict(min=min(token_counts),median=median(token_counts),max=max(token_counts),mean=mean(token_counts)),
        empty_chunks=sum(not c['text'].strip() for c in chunks),
        duplicate_chunk_ids=len(chunks)-len({c['chunk_id'] for c in chunks}),
        multipage_chunks=sum(c['page_start']!=c['page_end'] for c in chunks),
        shared_judged_pages_between_source_splits=dict(overlaps),
        exact_duplicate_question_groups=[ids for ids in normalized.values() if len(ids)>1],
        protocol='All 145 questions exploratory; detailed error analysis restricted to supplied dev subset; no existing split claimed independent.',
        warning='Shared corpus pages across query splits are not by themselves training leakage. They indicate dependence to inspect; test results have already been examined.')
    write_json(output/'profile.json',profile)
    with (ROOT/'results/context_top6/metrics_per_question.csv').open(encoding='utf-8-sig') as stream:
        metrics = list(csv.DictReader(stream))
    errors = []
    groups = defaultdict(list)
    for row in metrics:
        q = labels[row['question_id']]
        if q.get('split') != 'dev':
            continue
        coverage=float(row['context_page_recall'])
        category='aucune_page_annotee' if coverage==0 else 'couverture_partielle' if coverage<1 else 'toutes_pages_annotees'
        errors.append(dict(question_id=row['question_id'],question=q['question'],question_type=q.get('question_type',''),
            retrieval=row['retrieval'],reranker=row['reranker'],context_page_recall=coverage,
            ndcg_pages_at_6=float(row['ndcg_pages_at_6']),category=category,
            interpretation='Diagnostic de pages silver; examiner le texte et les PDF avant de conclure à une erreur sémantique.'))
        groups[row['retrieval'],row['reranker'],q.get('question_type','unknown')].append(row)
    write_csv(output/'error_analysis.csv',errors)
    write_csv(output/'scores_by_question_type.csv',[
        dict(retrieval=k[0],reranker=k[1],question_type=k[2],questions=len(rows),
             context_page_recall=mean(float(r['context_page_recall']) for r in rows),
             ndcg_pages_at_6=mean(float(r['ndcg_pages_at_6']) for r in rows)) for k,rows in groups.items()])
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
    axes[0].bar(list(profile['years']),list(profile['years'].values()),color='#2469a6')
    axes[0].set(title='PDF par année',ylabel='Documents')
    axes[1].hist(token_counts,bins=20,color='#22856a')
    axes[1].set(title='Longueur des chunks',xlabel='Tokens E5',ylabel='Chunks')
    axes[2].bar(list(profile['question_types']),list(profile['question_types'].values()),color='#dc8128')
    axes[2].tick_params(axis='x',rotation=25)
    axes[2].set(title='Types de questions',ylabel='Questions')
    fig.savefig(output/'eda.png',dpi=160)
    plt.close(fig)
    status=[
        ('Fondements théoriques','Documentés','docs/METHODOLOGIE.md : BM25, E5, RRF, ColBERT, cross-encoder et métriques.'),
        ('Prétraitement et analyse exploratoire','Présents','Extraction contrôlée, contributions de pages, profile.json et eda.png.'),
        ('Baseline et modèles avancés','Présents','BM25, E5, RRF ; BM25, ColBERT et cross-encoder ; budgets finaux 5 et 6.'),
        ('Prévention des fuites et lots','Protocole exploratoire explicite','Les 145 questions restent exploratoires ; analyse détaillée sur les 85 dev. Aucun entraînement supervisé local. Aucun ancien lot présenté comme indépendant. Nouveau test non scoré préparé après gel, à valider humainement.'),
        ('Interprétabilité / analyse des erreurs','Présente, à commenter','explain.py, audits de citations, error_analysis.csv, scores_by_question_type.csv et exemples du rapport. Pas de preuve automatique de fidélité sémantique.'),
        ('Sources et préparation des données','Traçables','93 PDF officiels, manifestes, empreintes et annotations silver conservées ; leur pertinence reste à revoir humainement.'),
        ('Solution automatisée et démonstration','Application locale présente','Streamlit et Ollama ; commandes dans le README. Un déploiement public et la présence du modèle Ollama sur un autre poste ne sont pas établis.'),
        ('Dépôt Git et reproductibilité','Dépôt local présent, publication à vérifier','requirements.txt complété, tests et commandes. Aucune publication distante effectuée pendant cette revue.'),
        ('Rapport écrit final','Partiel','Méthodologie, résultats et cette revue existent ; assembler et relire le rapport académique complet.'),
        ('Présentation PowerPoint','À préparer / vérifier','Aucun fichier PPTX identifié dans le projet actif pendant la revue.'),
        ('Vidéo et démonstration de 15–20 min','À préparer / vérifier','Aucune vidéo de soutenance identifiée dans le projet actif pendant la revue.'),
    ]
    lines=['# Revue des consignes ECC — 20 novembre 2026','',
           'Référence : capture « Consignes générales / Livrables » fournie par l’utilisateur. Le projet respecte une partie substantielle des exigences techniques, mais ne peut pas encore être déclaré entièrement conforme.', '',
           '| Exigence | Constat | Preuve ou action restante |','|---|---|---|']
    lines += [f'| {a} | {b} | {c} |' for a,b,c in status]
    lines += ['', '## Profil effectivement vérifié','',
              f"{len(docs)} PDF, {profile['physical_pages']} pages, {len(chunks)} chunks, {len(queries)} questions et {len(qrels)} jugements de pages. Empreintes des sources vérifiées. Chunks vides : {profile['empty_chunks']}. Identifiants de chunks dupliqués : {profile['duplicate_chunk_ids']}.", '',
              '## Séparation des données','',
              f"Étiquettes présentes : {profile['source_splits']}. Pages annotées partagées entre lots : {dict(overlaps)}. Ce partage n’est pas une fuite à lui seul : un moteur de recherche peut utiliser le même corpus pour toutes les questions. En revanche, sélectionner des paramètres à partir des scores de test empêche de présenter ce test comme indépendant.", '',
              'Protocole confirmé par l’utilisateur : conserver les 145 questions et résultats comme évaluation exploratoire ; réserver les 85 questions dev aux corrections et à l’analyse détaillée. Les anciens test/validation déjà consultés ne sont pas indépendants. Aucun jeu d’entraînement supervisé local n’était requis car aucun poids d’encodeur, reranker ou LLM n’est ajusté. Les traitements documentaires déterministes et l’index commun sont normaux pour ce corpus de recherche. Les qrels restent exclus des récupérateurs et rerankers. Le gel enregistre les empreintes des codes, des index et des révisions de modèles ; les nouveaux exemples ne doivent pas guider de nouveaux réglages. Une séparation rétroactive ne supprime pas l’examen des résultats passés.', '',
              '## Correction du reranking','',
              'Les modèles reclassent 20 candidats puis sélectionnent 6 passages (5 également disponibles). Le coût de calcul des 20 scores reste nécessaire. Les sorties *_top5.jsonl et *_top6.jsonl, les contextes dans results/context_top5 et context_top6 et l’application respectent cette distinction. Les métriques concernent les pages projetées à partir des passages effectivement sélectionnés.', '',
              '## Reste à finaliser','',
              'Valider humainement les nouvelles questions et qrels avant leur première évaluation, revoir un échantillon des références silver et des erreurs dev, assembler le rapport final, préparer les diapositives et enregistrer la démonstration de 15–20 minutes. La capture indique une remise au 30 novembre ; cette échéance n’a pas été vérifiée auprès de l’établissement.', '']
    (output/'RAPPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    log('Audit ECC, profil exploratoire et analyse des erreurs générés')


if __name__=='__main__':
    main()
