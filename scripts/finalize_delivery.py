"""Assemble current status, error tables and a self-contained local delivery.

No model inference or modification of frozen data, code, weights or indexes.
"""
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
from statistics import mean
import sys
from urllib.parse import unquote
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from common import digest, write_json, write_csv
from protocol import verify


def load_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))


def error_analysis(out):
    source=ROOT/'results/audit_project/error_analysis.csv'
    rows=load_csv(source)
    assert len(rows)==1020 and len({r['question_id'] for r in rows})==85
    counts=defaultdict(Counter)
    types=defaultdict(list)
    for r in rows:
        counts[r['retrieval'],r['reranker']][r['category']]+=1
        types[r['retrieval'],r['reranker'],r['question_type']].append(r)
    summary=[]
    for (m,rr),c in counts.items():
        assert sum(c.values())==85
        summary.append(dict(retrieval=m,reranker=rr,questions=85,
            no_annotated_page=c['aucune_page_annotee'],partial_coverage=c['couverture_partielle'],
            all_annotated_pages=c['toutes_pages_annotees']))
    write_csv(out/'error_categories_dev.csv',summary)
    typed=[]
    for (m,rr,t),group in types.items():
        typed.append(dict(retrieval=m,reranker=rr,question_type=t,questions=len(group),
            context_page_recall=mean(float(r['context_page_recall']) for r in group),
            ndcg_pages_at_6=mean(float(r['ndcg_pages_at_6']) for r in group)))
    existing={(r['retrieval'],r['reranker'],r['question_type']):r for r in load_csv(ROOT/'results/audit_project/scores_by_question_type.csv')}
    for row in typed:
        ref=existing[row['retrieval'],row['reranker'],row['question_type']]
        assert int(ref['questions'])==row['questions']
        assert abs(float(ref['ndcg_pages_at_6'])-row['ndcg_pages_at_6'])<1e-12
        assert abs(float(ref['context_page_recall'])-row['context_page_recall'])<1e-12
    write_csv(out/'scores_by_type_dev_verified.csv',typed)
    lines=['# Analyse des erreurs consolidée — 85 questions de développement','',
        'Les 1 020 observations correspondent aux mêmes 85 questions dans 12 configurations. '
        'Les catégories mesurent les références de pages silver, sans attribuer automatiquement une cause sémantique.','',
        '| Recherche | Reranker | Aucune page annotée | Couverture partielle | Toutes les pages annotées |',
        '|---|---|---:|---:|---:|']
    for r in summary:
        lines.append(f"| {r['retrieval']} | {r['reranker']} | {r['no_annotated_page']} | {r['partial_coverage']} | {r['all_annotated_pages']} |")
    lines+=['','## Résultats par type : système RRF + ColBERT','',
        '| Type | Effectif | Couverture moyenne | nDCG pages@6 |','|---|---:|---:|---:|']
    for r in typed:
        if (r['retrieval'],r['reranker'])==('hybrid_rrf','colbert'):
            lines.append(f"| {r['question_type']} | {r['questions']} | {r['context_page_recall']:.3f} | {r['ndcg_pages_at_6']:.3f} |")
    lines+=['','Les moyennes sont recalculées sur les observations individuelles et concordent avec les tableaux existants à 10⁻¹². Le groupe multi-document ne comporte que trois questions : aucune généralisation robuste ne repose sur ce seul effectif.','',
        '## Trois cas relus dans les PDF','',
        '- **FOMC_004** : un chunk de la bonne réunion contient une réponse, mais sa page manque aux qrels. Un zéro silver ne prouve pas une absence de réponse.',
        '- **FOMC_035** : ColBERT promeut un passage pertinent de janvier 2022, malgré une baisse du score silver. La génération reste partielle et cite aussi des réunions ultérieures.',
        '- **FOMC_064** : une preuve déjà présente dans le contexte passe du quatrième au premier chunk ; la page passe du rang 7 au rang 1. L’amélioration de nDCG ne signifie pas ici découverte d’une nouvelle preuve.','',
        '[Textes, identifiants de chunks, classements et citations vérifiées](../audit_project/ANALYSE_QUALITATIVE_DEV.md). Les trois cas sont sélectionnés pour expliquer les mécanismes ; leur fréquence n’est pas une estimation du taux d’erreur.','',
        'Deux références supplémentaires sont proposées dans `data/evaluation/audit/dev_qrels_proposals.trec`, sans modification des qrels historiques ni recalcul opportuniste des scores. Les pages non jugées comptent zéro dans les métriques, sans preuve de non-pertinence.']
    (out/'ANALYSE_ERREURS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def link_audit(paths):
    broken=[];checked=0
    for path in paths:
        path=path.resolve()
        text=path.read_text(encoding='utf-8-sig')
        text=re.sub(r'```[\s\S]*?```','',text)
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text):
            target=unquote(target.strip().strip('<>'))
            if re.match(r'^[a-zA-Z]+://',target) or target.startswith('#'): continue
            target=target.split('#',1)[0]
            if not target: continue
            checked+=1
            if not (path.parent/target).resolve().exists():
                broken.append(dict(document=path.relative_to(ROOT).as_posix(),target=target))
    return dict(checked_local_links=checked,broken_links=broken)


def status_documents():
    folder=ROOT/'results/reproduction'
    folder.mkdir(parents=True,exist_ok=True)
    clean=ROOT/'tmp/reproduction_clean'
    for source,name in ((clean/'install.log','clean_install.log'),(clean/'acquisition.log','network_acquisition.log')):
        if source.exists(): shutil.copy2(source,folder/name)
    def exit_code(name):
        p=clean/name
        return int(p.read_text(encoding='utf-8-sig').strip()) if p.exists() else None
    install_exit=exit_code('install_exit.txt')
    acquisition_exit=exit_code('acquisition_exit.txt')
    write_json(folder/'clean_environment.json',dict(
        status='not_fully_reproduced_in_clean_environment',
        clean_venv_created=(clean/'.venv/pyvenv.cfg').exists(),
        pip_install_exit_code=install_exit,network_acquisition_exit_code=acquisition_exit,
        clean_install_succeeded=install_exit==0,
        network_pdf_acquisition_succeeded=acquisition_exit==0,
        limitation='Dependency installation did not resolve numpy==1.26.4; direct official PDF request was denied by socket permissions. No clean dependency installation or remote acquisition success is claimed.',
        logs=['clean_install.log','network_acquisition.log']))
    p=folder/'run.json'
    run=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    status=run.get('status','not_run')
    steps='\n'.join(f"| {r['name']} | {'Réussi' if r['exit_code']==0 else 'Échec'} | {r['seconds']:.1f} s |" for r in run.get('steps',[]))
    reproduced=status=='passed_with_reused_dependencies'
    text=f'''# Reproduction : protocole et preuves

## Ce qui a réellement été exécuté

État de la reconstruction isolée : **{status}**.
Les 93 PDF exacts sont importés depuis une source locale avec contrôle SHA-256.
L’extraction, l’alignement des références et les index sont reconstruits dans
un dossier distinct. L’interpréteur et les poids préentraînés du poste sont
réutilisés : il ne s’agit pas d’une installation vierge de dépendances.

| Étape exécutée | Résultat | Durée observée |
|---|---|---:|
{steps}

[État machine détaillé](../results/reproduction/run.json) et journaux dans
`results/reproduction/`. Les comparaisons portent sur les paragraphes, chunks,
tokens BM25, identifiants E5 et vecteurs (tolérance absolue 10⁻⁶). Les synthèses
top-5 et top-6 sont comparées exactement aux fichiers de référence.

Un premier essai a révélé l’absence de création de `indexes/dense/` par le
constructeur d’index figé. Son échec est conservé dans `results/reproduction/attempts/`.
Le script de reproduction prépare désormais les dossiers `indexes/dense/` et
`indexes/bm25/` avant de lancer le pipeline, sans changer le code scientifique.

Les métriques utilisent les classements figés copiés après reconstruction des
index. La recherche et le reranking ne sont pas relancés intégralement pour les
145 questions dans cet essai. Les essais Streamlit effectuent, eux, une vraie
recherche sur des questions dev. La génération Ollama n’est pas incluse dans
cette reconstruction ; ses essais antérieurs sont documentés séparément.

## Installation vierge et acquisition distante

Un nouvel environnement virtuel sans accès aux paquets du projet a été créé.
L’installation de `requirements.txt` a échoué : `numpy==1.26.4` n’a pas pu être
résolu depuis cet environnement. Une requête vers un PDF officiel a également
échoué avec une erreur de permission de socket (`WinError 10013`).

[État et codes de sortie](../results/reproduction/clean_environment.json),
[journal pip](../results/reproduction/clean_install.log),
[journal d’acquisition](../results/reproduction/network_acquisition.log).
Ces échecs sont conservés. Aucune installation indépendante réussie ni acquisition
distante complète des 93 PDF n’est revendiquée. L’import local vérifié constitue
le chemin effectivement testé ; le paquet de remise contient les PDF exacts.

## Rejouer sur un autre poste

1. Extraire le paquet de remise, utiliser Python 3.12 et créer un environnement virtuel.
2. Installer `requirements.txt` avec accès aux distributions nécessaires.
3. Acquérir les poids aux révisions figées avec `src/build_indexes.py --download-models`.
4. Vérifier/importer les PDF à l’aide de `scripts/acquire_corpus.py` et du manifeste.
5. Lancer `scripts/reproduce_project.py` avec un dossier de travail neuf et l’interpréteur préparé.
6. Pour recalculer aussi tous les classements, lancer `run.py --from-step retrieve` dans la copie.

Les commandes complètes sont dans le [README](../README.md). Une nouvelle version
de PDF dont l’empreinte diffère est refusée ; les annotations ne doivent pas être
associées silencieusement à un document différent.

## Conclusion du contrôle

{'La reconstruction et les essais de la copie isolée ont réussi avec les dépendances et poids déjà installés.' if reproduced else 'La reconstruction isolée n’est pas encore confirmée comme entièrement réussie ; consulter les étapes et leur journal.'}
Le point « environnement propre » reste **partiellement vérifié**. Il doit être
complété sur un poste disposant d’un accès aux paquets et aux modèles, sans modifier
les résultats de référence pour masquer un écart.
'''
    (ROOT/'docs/REPRODUCTION.md').write_text(text,encoding='utf-8')
    final='''# État du plan de finalisation

## Décisions et preuves

| Action | État | Réalisation et limite |
|---|---|---|
| 1. Clarifier le HOLDOUT | Terminé pour la remise descriptive | Les 294 grades sont acceptés globalement ; les scores des 20 questions restent provisoires. Une confirmation indépendante sera nécessaire pour une conclusion confirmatoire ou une optimisation guidée par ces scores. |
| 2. Mettre à disposition les preuves | Terminé localement | README corrigé, résultats/figures/analyses/traces autorisés par Git, inventaire SHA-256 et ZIP local vérifiés. Aucune publication distante effectuée. |
| 3. Consolider l’analyse des erreurs | Terminé | 1 020 observations dev, 12 configurations, résultats par type recalculés, trois cas qualitatifs et limites des qrels intégrés au rapport. |
| 4. Vérifier la reproduction | Partiel | Import des 93 PDF contrôlé ; reconstruction et essais détaillés dans le journal. L’installation vierge et le téléchargement distant ont échoué ; aucune réussite sur un autre poste revendiquée. |
| 5. Finaliser le rapport technique | Relu et consolidé | Équations, unités pages/chunks, agrégation, tableaux 145/20, interprétation descriptive et limites de génération explicités. Le format de remise académique reste à adapter si exigé. |

## Points d’entrée

- [Décision sur le HOLDOUT](STATUT_HOLDOUT.md).
- [Rapport principal](RAPPORT_PROJET.md).
- [Analyse d’erreurs consolidée](../results/finalization/ANALYSE_ERREURS.md).
- [Reproduction et limites constatées](REPRODUCTION.md).
- [Audit des liens locaux](../results/finalization/link_audit.json).
- [Inventaire du paquet de remise](../results/finalization/delivery_manifest.json).

Le ZIP est créé dans `output/delivery/RAG_FOMC_remise.zip` et contient code,
PDF, index, annotations, rapports, figures et traces. Il ne contient ni l’environnement
Python ni les poids préentraînés. `.gitignore` autorise désormais les preuves ;
cela ne signifie pas qu’un commit ou un envoi distant a été effectué.

## Ce qui reste hors présentation et démonstration

La comparaison descriptive récupération/reranking est livrable avec ses limites.
Pour prétendre à une validation du RAG complet, restent la correction versionnée
et l’évaluation de la génération (réponse partielle, citations hors réunion),
ainsi que la reproduction complète dans un environnement installé indépendamment.
Une future confirmation indépendante n’est pas simulée en renommant le lot déjà consulté.
Les diapositives, la vidéo et les contraintes de format académique sont distinctes.
'''
    (ROOT/'docs/FINALISATION.md').write_text(final,encoding='utf-8')


def main():
    verify()
    running=ROOT/'results/reproduction/run.json'
    if running.exists() and json.loads(running.read_text(encoding='utf-8')).get('status')=='running':
        raise RuntimeError('Wait for the reproduction process to finish before packaging its changing logs.')
    out=ROOT/'results/finalization'
    out.mkdir(parents=True,exist_ok=True)
    status_documents()
    error_analysis(out)
    if not (out/'delivery_manifest.json').exists():
        write_json(out/'delivery_manifest.json',dict(status='being_assembled'))
    if not (out/'link_audit.json').exists():
        write_json(out/'link_audit.json',dict(status='being_checked'))
    docs=[ROOT/'README.md',*sorted((ROOT/'docs').glob('*.md')),ROOT/'results/figures/INDEX.md',ROOT/'results/candidate_provisional/INDEX.md',out/'ANALYSE_ERREURS.md']
    links=link_audit(docs)
    write_json(out/'link_audit.json',links)
    if links['broken_links']: raise ValueError(f"Broken documentation links: {links['broken_links']}")
    files=[]
    for folder in ('src','app','scripts','annotation_tools','tests','docs','protocol','data','indexes','results'):
        for path in (ROOT/folder).rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix in ('.pyc','.tmp'): continue
            if 'import_backups' in path.parts or path.name=='delivery_manifest.json': continue
            files.append(path)
    files += [ROOT/n for n in ('README.md','requirements.txt','run.py','.gitignore')]
    inventory={p.relative_to(ROOT).as_posix():dict(sha256=digest(p),bytes=p.stat().st_size) for p in sorted(set(files))}
    write_json(out/'delivery_manifest.json',dict(created_utc=datetime.now(timezone.utc).isoformat(),
        files=inventory,includes_exact_pdf_corpus=True,includes_pretrained_model_weights=False,
        includes_python_environment=False,remote_publication_performed=False))
    package=ROOT/'output/delivery/RAG_FOMC_remise.zip'
    package.parent.mkdir(parents=True,exist_ok=True)
    temporary=package.with_suffix('.pending.zip')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(set(files+[out/'delivery_manifest.json'])):
            z.write(path,'RAG_FOMC/'+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(temporary) as z:
        assert z.testzip() is None
        import hashlib
        for name, info in inventory.items():
            assert hashlib.sha256(z.read('RAG_FOMC/'+name)).hexdigest()==info['sha256'], f'File changed during packaging: {name}'
    temporary.replace(package)
    verify()
    print(f'PASS: {links["checked_local_links"]} liens locaux, 1 020 observations dev consolidées, {len(inventory)} fichiers et ZIP vérifiés. Modèles/environnement Python exclus ; aucune publication distante.')


if __name__=='__main__': main()
