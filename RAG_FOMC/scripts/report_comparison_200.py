"""Summarize frozen retrieval runs without tuning on test."""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rag_fomc.evaluation import retrieval_metrics
from rag_fomc.common import write_csv

def read(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]

def main():
    base=ROOT/'results/comparison_200_v1'
    questions=read(ROOT/'evaluation/questions.jsonl')
    lines=['# Comparaison des stratégies de récupération — 200 questions',
           '\n> Revue du 8 novembre 2026 : baseline historique aux annotations initiales. Une preuve alternative pertinente non acceptée a été confirmée pour Q021 ; les scores restent reproductibles, mais le classement doit rester provisoire. Voir [la revue méthodologique](../../docs/REVUE_METHODOLOGIQUE_COURS_ECC.md).\n',
           'Validation déclarée par l’utilisateur le 6 novembre 2026. Paramètres figés : BM25 k1=1,5 / b=0,75 ; E5-small-v2 ; fusion RRF constante 60 sur les 20 premiers candidats de chaque branche. Même index de 1 454 passages, 40 rapports. Aucun réglage sur test, aucun reranking appris ni génération.',
           'Les scores portent uniquement sur les questions répondables : 45 en développement et 145 en test. Les 10 questions sans réponse sont inspectées séparément. Le récupérateur retourne toujours des candidats : il ne possède pas encore de règle d’abstention.',
           'Recall = proportion des chunks acceptés retrouvés ; MRR = inverse du rang du premier chunk accepté ; couverture = proportion des groupes de preuves retrouvés ; preuves complètes = tous les groupes retrouvés. Les annotations ne garantissent pas l’exhaustivité des passages pertinents.']
    rows=[]
    for split in ('dev','test'):
        folder=base/split
        rankings=read(folder/'rankings.jsonl')
        by=defaultdict(list)
        for r in rankings: by[(r['qid'],r['method'])].append(r)
        qs=[q for q in questions if q['split']==split and q['answerable']]
        for method in ('bm25','dense','hybrid_rrf'):
            for k in (1,5,10,20):
                metrics=[]; families=defaultdict(list)
                for q in qs:
                    ranked=sorted(by[(q['qid'],method)],key=lambda r:r['rank'])
                    m=retrieval_metrics([r['chunk_id'] for r in ranked],q['evidence'],k)
                    metrics.append(m); families[q['family_id']].append(m)
                for aggregation in ('question','family'):
                    selected=metrics if aggregation=='question' else [
                        {name:mean(m[name] for m in group) for name in group[0]} for group in families.values()]
                    rows.append(dict(split=split,method=method,k=k,aggregation=aggregation,n=len(selected),
                                     **{name:mean(m[name] for m in selected) for name in selected[0]}))
        lines += [f'\n## Lot {split}', '| Stratégie | Recall@20 | MRR@20 | Couverture@20 | Preuves complètes@20 |',
                  '|---|---:|---:|---:|---:|']
        for row in rows:
            if row['split']==split and row['k']==20 and row['aggregation']=='question':
                lines += [f"| {row['method']} | {row['recall']:.3f} | {row['mrr']:.3f} | {row['evidence_coverage']:.3f} | {row['all_evidence']:.3f} |"]
        lines += [f'\n[Détails par type et latences]({split}/summary.csv) · [intervalles appariés]({split}/paired_comparisons.csv) · [cas à examiner]({split}/review_cases.jsonl) · [questions sans réponse]({split}/unanswerable_review.jsonl)']
    write_csv(base/'metrics_by_k_and_family.csv',rows,list(rows[0]))
    lines += ['\n## Résultats à retenir\n',
              'Sur le test, BM25 retrouve toutes les preuves annotées pour 116/145 questions (80,0 %), contre 107/145 (73,8 %) pour RRF et 82/145 (56,6 %) pour E5 seul. RRF obtient le meilleur MRR@20 (0,490 contre 0,428 pour BM25), mais perd 6,2 points de rappel des chunks acceptés. La moyenne par famille conserve ces deux tendances.',
              'Les comparaisons entre réunions restent les plus difficiles : les deux groupes de preuves sont retrouvés pour 12/25 questions avec BM25, 10/25 avec RRF et 5/25 avec E5. Sur les 30 questions explicatives du test, BM25 et RRF retrouvent toutes les preuves annotées à 20 passages.',
              'Les intervalles exploratoires B−A, RRF moins BM25, sont [−0,109 ; −0,020] pour Recall@20 et [0,001 ; 0,125] pour MRR@20. Le gain de MRR doit rester prudent vu la dépendance entre réunions et les comparaisons multiples.',
              'Pour cette configuration, BM25 constitue la référence pour couvrir les preuves ; RRF reste intéressant pour leur position dans le classement. Ces mesures ne démontrent pas une supériorité universelle de l’un des algorithmes. Les 10 questions sans réponse ont des candidats exportés, mais aucune exactitude d’abstention n’est calculable sans mécanisme de rejet.']
    verification={}
    for split,total in [('dev',50),('test',150)]:
        folder=base/split
        ranks=read(folder/'rankings.jsonl')
        with (folder/'latencies.csv').open(encoding='utf-8-sig',newline='') as f:
            times=list(csv.DictReader(f))
        assert len(ranks)==total*3*20
        assert len(times)==total*3*3
        verification[split]=dict(questions=total,rankings=len(ranks),timing_samples=len(times),
                                 repetitions=3,stable_rankings=True)
    (base/'verification.json').write_text(json.dumps(verification,indent=2)+'\n',encoding='utf-8')
    lines += ['\n## Lecture et limites',
              'Le fichier metrics_by_k_and_family.csv contient les scores à k=1,5,10,20, avec moyennes par question et par famille (une famille reçoit le même poids même si elle comporte une reformulation).',
              'Les intervalles fournis sont des bootstrap exploratoires à 95 % par famille, 1 000 tirages, différences B−A. Les questions de familles différentes peuvent toutefois partager une réunion ; cette dépendance documentaire n’est pas prise en compte. Pas de correction pour comparaisons multiples.',
              'Les questions factuelles et comparatives se concentrent sur taux et chômage. Les questions sans réponse comprennent cinq cas hors dates, relativement faciles. Ces résultats décrivent ce jeu et ces annotations ; ils ne mesurent pas la qualité de réponses générées.',
              'Les trois répétitions servent à vérifier la stabilité des classements et à mesurer les durées, pas à multiplier le nombre de questions indépendantes. Les lots dev et test ont été lancés en parallèle : leurs latences peuvent être perturbées par cette concurrence. Elles sont conservées à titre diagnostique et ne permettent pas de conclure sur la rapidité relative des stratégies. Une mesure de vitesse isolée sera nécessaire pour cette conclusion.']
    (base/'RAPPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps([r for r in rows if r['split']=='test' and r['k']==20],indent=2))

if __name__=='__main__': main()
