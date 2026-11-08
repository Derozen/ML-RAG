"""Re-score frozen v1 rankings using assistant-reviewed v2 qrels, explicitly exploratory."""
from collections import defaultdict
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import shutil
import sys
from statistics import mean

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rag_fomc.common import read_jsonl, write_csv, write_json, write_jsonl, sha256
from rag_fomc.evaluation import retrieval_metrics
from rag_fomc.comparison import paired_intervals
from rag_fomc.retrieval import METHODS

def main():
    revision=ROOT/'evaluation/revision_v2'
    path=revision/'questions_consolidated.jsonl'
    questions=read_jsonl(path)
    original=read_jsonl(ROOT/'evaluation/questions.jsonl')
    annotation=json.loads((revision/'annotations.json').read_text(encoding='utf-8'))
    assert sha256(path)==annotation['questions_sha256']
    assert sha256(ROOT/'evaluation/questions.jsonl')==annotation['original_questions_sha256']
    assert sha256(ROOT/'data/processed/chunks.jsonl')==annotation['chunks_sha256']
    assert all(q['validated'] is False for q in questions), 'Do not imply renewed human approval.'
    assert [(q['qid'],q['question'],q['split'],q['family_id']) for q in questions]==[(q['qid'],q['question'],q['split'],q['family_id']) for q in original]
    base=ROOT/'results/comparison_200_v2_rescored'
    if base.exists(): raise ValueError('Output already exists; preserve revision results.')
    deltas=[]; all_k=[]
    for split in ('dev','test'):
        source=ROOT/f'results/comparison_200_v1/{split}'; out=base/split
        run=json.loads((source/'run.json').read_text(encoding='utf-8'))
        assert run['questions_sha256']==annotation['original_questions_sha256']
        assert run['chunks_sha256']==annotation['chunks_sha256']
        rankings=read_jsonl(source/'rankings.jsonl')
        by=defaultdict(list)
        for r in rankings: by[(r['qid'],r['method'])].append(r)
        selected=[q for q in questions if q['split']==split]
        metrics=[]; k=run['config']['top_k']
        for q in selected:
            if not q['answerable']: continue
            for method in METHODS:
                ranked=sorted(by[(q['qid'],method)],key=lambda r:r['rank'])
                assert len(ranked)==k
                metrics.append(dict(qid=q['qid'],method=method,type=q['type'],split=split,k=k,
                               **retrieval_metrics([r['chunk_id'] for r in ranked],q['evidence'],k)))
        summary=[]
        for method in METHODS:
            for kind in ['ALL']+sorted({q['type'] for q in selected}):
                group=[m for m in metrics if m['method']==method and (kind=='ALL' or m['type']==kind)]
                row=dict(method=method,type=kind,k=k,answerable_questions=len(group),
                         **{name:mean(m[name] for m in group) if group else None for name in ('recall','mrr','evidence_coverage','all_evidence')})
                summary.append(row)
        out.mkdir(parents=True)
        write_csv(out/'summary.csv',summary,list(summary[0]))
        write_csv(out/'metrics_per_question.csv',metrics,list(metrics[0]))
        intervals=paired_intervals(metrics,selected,run['config']['seed'])
        write_csv(out/'paired_comparisons.csv',intervals,list(intervals[0]))
        # Copies make the plot utility work without loading a retriever; hashes prove unchanged rankings.
        shutil.copyfile(source/'rankings.jsonl',out/'rankings.jsonl')
        assert sha256(source/'rankings.jsonl')==sha256(out/'rankings.jsonl')
        with (source/'summary.csv').open(encoding='utf-8-sig',newline='') as f:
            old={(r['method'],r['type']):r for r in csv.DictReader(f)}
        for r in summary:
            if r['type']=='ALL':
                for name in ('recall','mrr','evidence_coverage','all_evidence'):
                    prior=float(old[(r['method'],'ALL')][name]); current=r[name]
                    deltas.append(dict(split=split,method=r['method'],metric=name,v1=prior,v2=current,delta=current-prior))
        for method in METHODS:
            for cutoff in (1,5,10,20):
                per_question=[]; families=defaultdict(list)
                for q in selected:
                    if not q['answerable']: continue
                    ids=[r['chunk_id'] for r in sorted(by[(q['qid'],method)],key=lambda r:r['rank'])]
                    m=retrieval_metrics(ids,q['evidence'],cutoff)
                    per_question.append(m); families[q['family_id']].append(m)
                for agg in ('question','family'):
                    group=per_question if agg=='question' else [{name:mean(m[name] for m in g) for name in g[0]} for g in families.values()]
                    all_k.append(dict(split=split,method=method,k=cutoff,aggregation=agg,n=len(group),
                                      **{name:mean(m[name] for m in group) for name in group[0]}))
        write_json(out/'run.json',dict(run,created_at_utc=datetime.now(timezone.utc).isoformat(),
            questions_sha256=sha256(path),annotations_sha256=sha256(revision/'annotations.json'),
            evaluation_status='exploratory_assistant_revised_annotations_pending_independent_review',
            evaluation_mode='rescore_frozen_rankings_no_retrieval_no_new_timing',
            questions_path=str(path),source_run_json_sha256=sha256(source/'run.json'),
            source_rankings_sha256=sha256(source/'rankings.jsonl'),
            warning='Revised analysis of an already observed test, not independent confirmation. New qrels have not been validated by user.'))
    write_csv(base/'v1_vs_v2.csv',deltas,list(deltas[0]))
    write_csv(base/'metrics_by_k_and_family.csv',all_k,list(all_k[0]))
    lines=['# Révision des preuves et recalcul de la comparaison',
           '\n**Analyse exploratoire : ajouts relus par l’assistant, validation indépendante encore attendue.**',
           '\nLes 200 questions, leurs réponses, lots et familles sont inchangés. Les preuves alternatives sont ajoutées aux mêmes groupes. Les classements v1 sont réutilisés à l’identique : aucune recherche, aucun réglage ni nouvelle mesure de vitesse. Les anciennes annotations et sorties restent en place.',
           f"\n{annotation['questions_with_added_chunks']} questions reçoivent au moins un chunk supplémentaire ; {annotation['source_variants']} variantes de source contrôlées dans les paragraphes, chunks et sur {annotation['physical_pdf_pages_checked']} pages physiques PDF.",
           '\n## Lot test : avant / après\n',
           '| Méthode | Recall v1 | Recall v2 | MRR v1 | MRR v2 | Complétude v1 | Complétude v2 |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for method in METHODS:
        d={r['metric']:r for r in deltas if r['split']=='test' and r['method']==method}
        lines.append(f"| {method} | {d['recall']['v1']:.3f} | {d['recall']['v2']:.3f} | {d['mrr']['v1']:.3f} | {d['mrr']['v2']:.3f} | {d['all_evidence']['v1']:.3f} | {d['all_evidence']['v2']:.3f} |")
    lines += ['\n## Interprétation\n',
              'La complétude et le MRR peuvent augmenter avec des preuves acceptées supplémentaires sans aucun changement du moteur. Le Recall par chunks peut diminuer parce que son dénominateur augmente. Les scores entre versions ne constituent donc pas un gain d’algorithme.',
              '\nLe critère principal proposé pour la suite est la complétude des groupes à budget de candidats fixé ; la couverture partielle et le MRR restent complémentaires. Ce choix ne constitue pas une présélection indépendante du test historique.',
              '\nLes bootstrap restent exploratoires, groupés par famille, sans prise en compte complète des réunions partagées ni de l’incertitude d’annotation. Aucune conclusion de vitesse ou d’abstention ne peut être tirée.',
              '\n## Relecture à poursuivre\n',
              '[Questions et citations](../../evaluation/revision_v2/RELECTURE.md) · [Pool aveugle](../../evaluation/revision_v2/pool_blind.jsonl) · [Décisions et motifs](../../evaluation/revision_v2/candidate_decisions.jsonl).',
              f"\nPool total : {annotation['pool_unique_pairs']} couples question/passage ; états : {json.dumps(annotation['pool_decisions'],ensure_ascii=False)}. Les passages non acceptés restent non jugés ou à examiner ; ils ne sont pas étiquetés automatiquement comme non pertinents.",
              '\nUne recherche dans les documents sources dépasse le seul pool, mais ne garantit pas l’exhaustivité sémantique des annotations. Les 40 questions explicatives conservent leurs preuves et bénéficient uniquement de correspondances littérales/normalisées sûres. Les 10 questions sans réponse gardent leurs motifs initiaux ; elles nécessitent une revue d’absence à part.',
              '\nNe pas remplacer le fichier validé v1 ni déclarer ces ajouts validés humainement sans revue. Après validation, une nouvelle expérience de confirmation indépendante sera nécessaire pour évaluer des changements conçus à partir de ces résultats.']
    (base/'RAPPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines[:13]))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8'); main()
