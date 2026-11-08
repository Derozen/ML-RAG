"""Plot an existing compare run. No retrieval is rerun and no scores are invented."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from rag_fomc.evaluation import retrieval_metrics

METHODS = ('bm25', 'dense', 'hybrid_rrf')
LABELS = ('BM25', 'Dense E5', 'Hybride RRF')
COLORS = ('#2563a6', '#d97820', '#218766')

def read_jsonl(path):
    return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True, help='One completed dev or test run directory')
    parser.add_argument('--questions', type=Path, default=ROOT/'evaluation/questions.jsonl')
    parser.add_argument('--output', type=Path, help='Default: RESULTS/plots')
    args = parser.parse_args()
    folder=args.results.resolve(); out=args.output or folder/'plots'
    run=json.loads((folder/'run.json').read_text(encoding='utf-8'))
    import hashlib
    if hashlib.sha256(args.questions.read_bytes()).hexdigest()!=run['questions_sha256']:
        parser.error('Le fichier de questions ne correspond pas à celui de cette expérience.')
    with (folder/'summary.csv').open(encoding='utf-8-sig', newline='') as f:
        summary=list(csv.DictReader(f))
    questions=[q for q in read_jsonl(args.questions) if q['split']==run['split'] and q['answerable']]
    n=len(questions); k=run['config']['top_k']
    revision_note=('\nAnnotations révisées par l’assistant - résultats provisoires'
                   if run.get('evaluation_status','').startswith('exploratory') else '')
    out.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':10, 'axes.spines.top':False, 'axes.spines.right':False})
    def save(fig,name):
        fig.savefig(out/f'{name}.png',dpi=180,bbox_inches='tight')
        fig.savefig(out/f'{name}.svg',bbox_inches='tight')
        plt.close(fig)

    overall={r['method']:r for r in summary if r['type']=='ALL'}
    fig, axes=plt.subplots(1,3,figsize=(12,4.8),layout='constrained')
    for ax,metric,title in zip(axes,('recall','mrr','all_evidence'),
                               (f'Rappel des passages @{k}',f'MRR @{k}',f'Toutes les preuves @{k}')):
        vals=[float(overall[m][metric]) for m in METHODS]
        bars=ax.bar(LABELS,vals,color=COLORS,width=.65)
        ax.set_ylim(0,1.12); ax.set_yticks(np.arange(0,1.01,.2)); ax.set_title(title)
        ax.bar_label(bars,labels=[f'{v:.3f}' for v in vals],padding=4)
        ax.tick_params(axis='x',labelrotation=15); ax.grid(axis='y',alpha=.18); ax.set_axisbelow(True)
    fig.suptitle(f'Comparaison de récupération — {run["split"]} — {n} questions répondables'+revision_note)
    fig.supxlabel('Moyennes par question • scores compris entre 0 et 1 • plus élevé = meilleur')
    save(fig,'01_scores_globaux')

    kinds=('factual','paraphrase','explanatory','comparative')
    names=('Factuelles','Reformulations','Explicatives','Comparatives')
    lookup={(r['method'],r['type']):r for r in summary}
    matrix=np.array([[float(lookup[(m,t)]['all_evidence']) for t in kinds] for m in METHODS])
    counts=[int(lookup[('bm25',t)]['answerable_questions']) for t in kinds]
    fig,ax=plt.subplots(figsize=(9,4.6),layout='constrained')
    im=ax.imshow(matrix,vmin=0,vmax=1,cmap='YlGnBu',aspect='auto')
    ax.set_xticks(range(4),[f'{name}\n(n={count})' for name,count in zip(names,counts)])
    ax.set_yticks(range(3),LABELS)
    for i in range(3):
        for j in range(4):
            ax.text(j,i,f'{matrix[i,j]:.1%}',ha='center',va='center',
                    color='white' if matrix[i,j]>.65 else '#172b40',fontweight='bold')
    ax.set_title(f'Questions dont toutes les preuves sont retrouvées @{k} — {run["split"]}'+revision_note,pad=15)
    fig.colorbar(im,ax=ax,label='Proportion de questions')
    save(fig,'02_preuves_par_type')

    rankings=defaultdict(list)
    for r in read_jsonl(folder/'rankings.jsonl'): rankings[(r['qid'],r['method'])].append(r)
    ks=[v for v in (1,5,10,20) if v<=k]
    fig,axes=plt.subplots(1,2,figsize=(10,4.8),layout='constrained')
    exported=[]
    for m,label,color in zip(METHODS,LABELS,COLORS):
        values=[]
        for cutoff in ks:
            metrics=[]
            for q in questions:
                ranked=sorted(rankings[(q['qid'],m)],key=lambda r:r['rank'])
                metrics.append(retrieval_metrics([r['chunk_id'] for r in ranked],q['evidence'],cutoff))
            row=dict(method=m,k=cutoff,**{name:float(np.mean([v[name] for v in metrics])) for name in metrics[0]})
            values.append(row); exported.append(row)
        for ax,metric,title in zip(axes,('recall','all_evidence'),('Rappel des passages','Toutes les preuves')):
            ax.plot(ks,[r[metric] for r in values],marker='o',label=label,color=color)
            ax.set(title=title,xlabel='Nombre de passages récupérés (k)',ylim=(0,1.05),xticks=ks)
            ax.grid(alpha=.2); ax.legend(loc='lower right')
    fig.suptitle(f'Effet du nombre de passages — {run["split"]} — {n} questions répondables'+revision_note)
    save(fig,'03_scores_selon_k')
    with (out/'scores_selon_k.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(exported[0])); writer.writeheader(); writer.writerows(exported)
    (out/'README.md').write_text(
        '# Figures de comparaison\n\n'
        'PNG pour lecture directe ; SVG pour export dans le mémoire. Valeurs issues de cette expérience uniquement.\n\n'
        '- `01_scores_globaux` : rappel, MRR et proportion de questions avec toutes les preuves.\n'
        '- `02_preuves_par_type` : preuves complètes par catégorie de question.\n'
        '- `03_scores_selon_k` : évolution lorsque le nombre de candidats augmente.\n\n'
        'Les 10 questions sans réponse ne sont pas incluses dans ces métriques de pertinence. '
        'Les moyennes sont par question ; les reformulations ne sont pas indépendantes. '
        'Ces graphiques n’affichent pas d’intervalles de confiance : consulter `../paired_comparisons.csv` pour les différences appariées. '
        'Aucun graphique de vitesse n’est produit : les mesures initiales ont été réalisées avec deux lots concurrents.\n',encoding='utf-8')
    print(f'3 figures PNG et SVG : {out}')

if __name__=='__main__': main()
