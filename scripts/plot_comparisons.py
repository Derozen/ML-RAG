"""Scientific comparison figures from cached metrics, without model rescoring."""
import csv
import hashlib
import json
from pathlib import Path
from statistics import mean

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/figures'
METHODS = ('bm25', 'dense', 'hybrid_rrf')
RERANKERS = ('none', 'bm25', 'colbert', 'cross_encoder')
LABEL = dict(bm25='BM25', dense='E5 dense', hybrid_rrf='Hybride RRF',
             none='Sans reranking', colbert='ColBERT', cross_encoder='Cross-encoder')
COLORS = dict(none='#667085', bm25='#3975AD', colbert='#168271', cross_encoder='#D17C26')


def read(name):
    with (ROOT / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    sources = ['results/context_top6/comparison.csv', 'results/context_top5/comparison.csv',
               'results/context_top6/metrics_per_question.csv',
               'results/audit_project/scores_by_question_type.csv']
    hashes = {s: sha(ROOT / s) for s in sources}
    top6 = read(sources[0])
    top5 = read(sources[1])
    details = read(sources[2])
    typed = read(sources[3])
    maps = {6: {(r['retrieval'], r['reranker']): r for r in top6},
            5: {(r['retrieval'], r['reranker']): r for r in top5}}
    expected = {(m, r) for m in METHODS for r in RERANKERS}
    for budget in (5, 6):
        assert set(maps[budget]) == expected
        assert all(int(r['questions']) == 145 and int(r['final_chunks']) == budget for r in maps[budget].values())
    groups = {(m, rr): {r['question_id']: r for r in details if r['retrieval'] == m and r['reranker'] == rr}
              for m, rr in expected}
    ids = set(groups[METHODS[0], RERANKERS[0]])
    assert len(ids) == 145 and len(details) == 1740
    for key, g in groups.items():
        assert set(g) == ids
        assert abs(mean(float(r['ndcg_pages_at_6']) for r in g.values())
                   - float(maps[6][key]['ndcg_pages_at_6'])) < 1e-12
    OUT.mkdir(exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'savefig.facecolor': 'white'})
    names = []

    def save(fig, name, caption):
        fig.text(.5, .018, caption, ha='center', va='bottom', fontsize=9, color='#4C5668')
        fig.savefig(OUT / (name + '.png'), dpi=240, bbox_inches='tight')
        fig.savefig(OUT / (name + '.svg'), bbox_inches='tight')
        plt.close(fig)
        names.append(name)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8))
    for ax, field, title in zip(axes,
                              ('context_page_recall', 'ndcg_pages_at_6', 'mrr_pages_at_budget'),
                              ('Couverture des pages du contexte', 'nDCG des 6 premières pages', 'MRR des 6 premières pages')):
        values = [float(maps[6][m, 'none'][field]) for m in METHODS]
        bars = ax.bar([LABEL[m] for m in METHODS], values, color=['#3975AD', '#D17C26', '#168271'], width=.6)
        ax.bar_label(bars, fmt='%.3f', padding=4, fontsize=10)
        ax.set_ylim(0, 1.0)
        ax.set_title(title, fontsize=11)
        ax.grid(axis='y', alpha=.16)
        ax.set_axisbelow(True)
    fig.suptitle('Récupération seule — 145 questions exploratoires, contexte de 6 chunks', fontsize=14, fontweight='bold')
    fig.subplots_adjust(bottom=.19, top=.81, wspace=.3)
    save(fig, '01_recuperation', 'La couverture considère toutes les pages des 6 chunks ; nDCG et MRR sont limités à 6 pages uniques. Plus élevé = meilleur.')

    matrix = np.array([[float(maps[6][m, rr]['ndcg_pages_at_6']) for rr in RERANKERS] for m in METHODS])
    fig, ax = plt.subplots(figsize=(10, 4.8))
    im = ax.imshow(matrix, cmap='YlGnBu', vmin=0, vmax=1, aspect='auto')
    ax.set_xticks(range(4), [LABEL[r] for r in RERANKERS])
    ax.set_yticks(range(3), [LABEL[m] for m in METHODS])
    for i in range(3):
        for j in range(4):
            ax.text(j, i, f'{matrix[i,j]:.3f}', ha='center', va='center', fontsize=13, fontweight='bold')
    fig.colorbar(im, ax=ax, label='nDCG pages@6', fraction=.04, pad=.03)
    ax.set_title('Récupération et reranking : les 12 configurations', pad=18)
    ax.set_xlabel('Reranking des mêmes 20 candidats', labelpad=12)
    ax.set_ylabel('Récupération')
    fig.subplots_adjust(bottom=.23, top=.81, left=.16, right=.9)
    save(fig, '02_reranking', '145 questions exploratoires ; sélection finale de 6 chunks. Les écarts observés ne constituent pas un test statistique indépendant.')

    paired = []
    for m in METHODS:
        for rr in RERANKERS[1:]:
            delta = [float(groups[m, rr][q]['ndcg_pages_at_6']) - float(groups[m, 'none'][q]['ndcg_pages_at_6']) for q in sorted(ids)]
            paired.append(dict(retrieval=m, reranker=rr, questions=145, mean_delta=mean(delta),
                               improved=sum(d > 1e-12 for d in delta), tied=sum(abs(d) <= 1e-12 for d in delta),
                               degraded=sum(d < -1e-12 for d in delta)))
    with (OUT / 'paired_changes_context6.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(paired[0])); w.writeheader(); w.writerows(paired)
    fig, ax = plt.subplots(figsize=(11, 6))
    ys = np.arange(len(paired))
    vals = [p['mean_delta'] for p in paired]
    ax.barh(ys, vals, color=['#168271' if v >= 0 else '#BB5555' for v in vals], height=.68)
    ax.set_yticks(ys, [f"{LABEL[p['retrieval']]} + {LABEL[p['reranker']]}" for p in paired])
    for y, p in zip(ys, paired):
        ax.text(.16, y, f"{p['mean_delta']:+.3f}     {p['improved']} / {p['tied']} / {p['degraded']}", va='center', fontsize=10)
    ax.invert_yaxis()
    ax.axvline(0, color='#667085', lw=.8)
    ax.set_xlim(-.075, .33)
    ax.set_xlabel('Écart moyen de nDCG pages@6 par rapport au même récupérateur sans reranking')
    ax.set_title('Effet du reranking sur les mêmes 145 questions', pad=24)
    ax.text(.16, -.8, 'Écart     améliorées / égales / dégradées', fontsize=9, color='#4C5668')
    ax.grid(axis='x', alpha=.15); ax.set_axisbelow(True)
    fig.subplots_adjust(left=.27, right=.98, bottom=.17, top=.82)
    save(fig, '03_effet_reranking', 'Comparaison appariée descriptive ; 145 questions par ligne. Un changement de score silver ne prouve pas une erreur sémantique.')

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), sharey=True)
    markers = dict(none='o', bm25='s', colbert='D', cross_encoder='^')
    for m, ax in zip(METHODS, axes):
        for rr in RERANKERS:
            values = [float(maps[k][m, rr]['context_page_recall']) for k in (5, 6)]
            ax.plot([5, 6], values, marker=markers[rr], label=LABEL[rr], color=COLORS[rr],
                    linestyle='--' if rr == 'bm25' else '-', linewidth=1.7)
        ax.set_title(LABEL[m]); ax.set_xticks([5, 6]); ax.set_xlim(4.8, 6.2)
        ax.set_ylim(0, 1); ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_xlabel('Chunks sélectionnés après reranking'); ax.grid(alpha=.16)
    axes[0].set_ylabel('Couverture moyenne des pages annotées')
    handles, labels = axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=4, bbox_to_anchor=(.5, .07), frameon=False)
    fig.suptitle('Effet du budget de contexte — 145 questions exploratoires', fontsize=14, fontweight='bold')
    fig.subplots_adjust(bottom=.28, top=.82, wspace=.15)
    save(fig, '04_budget_contexte', 'Même dénominateur de pertinence pour 5 et 6 chunks. Les courbes BM25 et sans reranking se superposent sur le pool BM25.')

    types = ('factual', 'explanatory', 'comparative', 'multi_document')
    type_labels = dict(factual='Factuelles', explanatory='Explicatives', comparative='Comparatives', multi_document='Multi-documents')
    typed_map = {(r['retrieval'], r['reranker'], r['question_type']): r for r in typed}
    configs = [(m, rr) for m in METHODS for rr in ('none', 'colbert')]
    counts = [int(typed_map[METHODS[0], 'none', t]['questions']) for t in types]
    assert sum(counts) == 85
    values = np.array([[float(typed_map[m, rr, t]['ndcg_pages_at_6']) for t in types] for m, rr in configs])
    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(values, vmin=0, vmax=1, cmap='YlGnBu', aspect='auto')
    ax.set_xticks(range(4), [f'{type_labels[t]}\n(n={n})' for t, n in zip(types, counts)])
    ax.set_yticks(range(len(configs)), [LABEL[m]+(' seul' if rr == 'none' else ' + ColBERT') for m, rr in configs])
    for i in range(len(configs)):
        for j in range(4):
            ax.text(j, i, f'{values[i,j]:.3f}', ha='center', va='center', color='white' if values[i,j] > .6 else '#14202D')
    fig.colorbar(im, ax=ax, label='nDCG pages@6', fraction=.04, pad=.03)
    ax.set_title('Analyse par type de question — sous-ensemble dev uniquement', pad=18)
    fig.subplots_adjust(bottom=.18, top=.84, left=.25, right=.9)
    save(fig, '05_types_dev', '85 questions dev ; petits effectifs dans certaines catégories. Ces résultats ne sont pas ceux du nouveau lot candidat.')

    assert hashes == {s: sha(ROOT / s) for s in sources}
    metadata = dict(population='145 exploratory questions; type-specific figure restricted to 85 dev questions',
                    new_holdout_scored=False, input_sha256=hashes,
                    figures=names, points_derived_from_existing_metrics=True,
                    files_sha256={p.name: sha(p) for p in OUT.iterdir() if p.is_file() and p.name != 'provenance.json'})
    (OUT / 'provenance.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    text = ['# Graphiques de la comparaison exploratoire actuelle', '',
            '**Résultats exploratoires des 145 questions ; aucune figure ne provient du test final indépendant.**', '',
            'Ces résultats sont conservés comme référence exploratoire. Le nouveau lot candidat de 20 questions '
            'n’a pas encore de scores validés pour les remplacer. Les anciennes versions à 200 ou 110 questions '
            'ne sont pas représentées ici.', '',
            'Chaque figure est disponible en PNG et SVG. Les valeurs viennent des fichiers CSV existants, '
            'sans nouvelle exécution des modèles. Les empreintes des entrées figurent dans `provenance.json`.', '']
    titles = ['Récupération seule', 'Les 12 configurations de récupération/reranking',
              'Gains et pertes appariés du reranking', 'Budget de cinq ou six chunks', 'Types de questions sur dev']
    for name, title in zip(names, titles):
        text += [f'## {title}', '', f'![{title}]({name}.png)', '', f'[Version SVG]({name}.svg)', '']
    (OUT / 'INDEX.md').write_text('\n'.join(text), encoding='utf-8')
    print('PASS: 5 figures, PNG+SVG, 145 exploratory questions / 85 dev, source metrics unchanged.')


if __name__ == '__main__':
    main()
