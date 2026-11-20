"""Assemble a source-grounded project report from existing exploratory outputs.

No model inference, tuning, new holdout scoring, or changes to frozen references.
"""
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from protocol import verify, LOCK
from common import digest
sys.path.insert(0, str(ROOT / 'annotation_tools'))
from rebuild_holdout import canonical
import pymupdf


def jl(name):
    return [json.loads(s) for s in (ROOT / name).read_text(encoding='utf-8').splitlines() if s.strip()]


def rows(name):
    with (ROOT / name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def provisional_run():
    completed = []
    for p in (ROOT / 'results/candidate_provisional').glob('*/run.json'):
        data = json.loads(p.read_text(encoding='utf-8'))
        if data.get('status') == 'completed_provisional':
            completed.append(p.parent)
    return sorted(completed)[-1] if completed else None


def approval_notice():
    p = ROOT / 'data/holdout_candidate/assistant_review/completed_proposal/user_approval.json'
    if not p.exists():
        return ''
    return ('## Validation utilisateur enregistrée\n\n'
            'L’utilisateur a accepté globalement les **294 grades proposés**, sans changement de grade. '
            'Les champs de la grille et la trace de cet accord sont enregistrés dans '
            '[user_approval.json](../data/holdout_candidate/assistant_review/completed_proposal/user_approval.json). '
            'Les scores calculés restent numériquement valables pour ces annotations acceptées.\n\n'
            'Cet accord global ne déclare ni une lecture indépendante page par page, ni la revue '
            'sémantique des 145 questions antérieures, ni l’adjudication des réponses et facettes. '
            'Ces décisions restent non renseignées. Le statut de test final indépendant n’est donc '
            'pas établi. Le [statut retenu pour la remise](STATUT_HOLDOUT.md) est une '
            'évaluation complémentaire descriptive, sans conclusion confirmatoire.\n\n')


def technical_report():
    base = ROOT / 'results/delivery_verification'
    def read_optional(name):
        p = base / name
        return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
    app = read_optional('streamlit_with_generation.json')
    checks = {t['name']: t for t in app.get('tests', [])}
    generation = checks.get('real_structured_generation_dev')
    warm = read_optional('ollama_warmup.json')
    http = read_optional('streamlit_http.json')
    metrics = read_optional('metrics_recomputed.json')
    readiness_path = ROOT / 'data/holdout_candidate/assistant_review/completed_proposal/review_readiness.json'
    readiness = json.loads(readiness_path.read_text(encoding='utf-8'))
    lines = ['# Vérifications techniques et statut du test final', '',
             'Les essais ci-dessous portent sur le code figé et des questions dev déjà explorées. '
             'Ils ne constituent pas une nouvelle évaluation indépendante de qualité.', '',
             '| Contrôle | Observation |', '|---|---|',
             '| Tests automatisés | 25 tests de régression réussis pendant cette revue. Ils ne couvrent pas tous les comportements possibles. |',
             f"| Recalcul indépendant des métriques | {metrics.get('status', 'non exécuté')} : {metrics.get('contexts_checked', 0)} contextes, budgets 5/6, 24 synthèses ; tolérance 10⁻¹². |",
             f"| Syntaxe Python | {checks.get('python_syntax', {}).get('files', 0)} fichiers examinés lors de l’essai applicatif. |"]
    labels = dict(streamlit_startup='Démarrage Streamlit par AppTest', empty_question_guard='Question vide',
                  real_classic_rrf_colbert_top6='Recherche réelle RRF + ColBERT, top-6',
                  real_classic_rrf_colbert_top5='Recherche réelle RRF + ColBERT, top-5',
                  real_explainability_panel='Panneau de scores détaillés',
                  temporal_fallback_without_period='Repli du mode temporel en l’absence de période')
    for key, label in labels.items():
        passed = checks.get(key, {}).get('passed', False)
        extra = ' ; identifiants des passages identiques au benchmark existant.' if key.startswith('real_classic') else ''
        lines.append(f"| {label} | {'Réussi' if passed else 'Non confirmé'}{extra} |")
    http_ok = any(t.get('passed') for t in http.get('tests', []) if t['name'] == 'real_streamlit_http_server')
    lines += [f"| Serveur HTTP local réel | {'HTTP 200 sur la page et santé `ok` ; serveur temporaire arrêté après contrôle.' if http_ok else 'Non confirmé.'} |",
              f"| Génération Qwen structurée réelle | {'Réussie sur FOMC_035 (dev), sortie conservée ; justesse sémantique non certifiée.' if generation else 'Pas de réussite confirmée ; voir la limite Ollama ci-dessous.'} |",
              '| Rendu visuel de Streamlit dans tous les navigateurs | Non vérifié. AppTest et HTTP ne remplacent pas une inspection graphique du navigateur. |',
              '| Autres chemins applicatifs | Les modes temporels valides sur plusieurs dates et toutes les configurations en ligne ne sont pas testés exhaustivement. |',
              '| Test final indépendant des 20 questions | **Non exécuté.** Les propositions de qrels ne sont pas encore validées indépendamment. |', '',
              '## Chargement de Qwen et démonstration', '',
              'Un premier essai complet a échoué après le délai de 300 secondes : les '
              'journaux Ollama situaient le blocage pendant le chargement du modèle. '
              'L’application a affiché cette erreur et préservé le précédent résultat. '
              'La trace est conservée dans `results/delivery_verification/attempts/cold_generation_timeout.json`.', '']
    if warm.get('status') == 'passed':
        lines += [f"Un préchargement sans prompt ni génération a ensuite réussi en **{warm['seconds']:.1f} secondes**. "
                  'Il utilise le même modèle et ne change ni poids ni paramètres du pipeline. '
                  'Le démarrage à froid reste une limite opérationnelle : précharger le modèle avant la démonstration.', '']
    if generation:
        lines += ['La chaîne a ensuite été essayée de nouveau avec le modèle chargé. '
                  'Ce succès valide un cas fonctionnel de génération, pas la fidélité de toutes les réponses. '
                  'Les identifiants de citations et les sections structurées ne constituent pas une preuve '
                  'automatique d’implication sémantique.', '',
                  '[Sortie réelle de génération](../results/delivery_verification/real_generation_dev.json)', '']
        lines += ['### Limites observées dans cette réponse', '',
                  'La revue éditoriale de la sortie FOMC_035 constate une réponse **partielle** : '
                  'elle mentionne l’inflation mais omet le marché du travail solide, pourtant '
                  'explicitement présent dans la source 1 de janvier 2022. Elle cite aussi les '
                  'sources 5 et 6, de décembre et juillet 2022. Ces réunions ultérieures ne '
                  'suffisent pas à justifier ce que pensait le Comité en janvier.', '',
                  'Les contrôles retournent des identifiants de citations valides et une '
                  'section structurellement complète, mais **cela ne valide pas la pertinence '
                  'temporelle ni la complétude de la réponse**. Le mode classique ne doit '
                  'pas être présenté comme ayant résolu ces problèmes. Le pipeline figé '
                  'n’a pas été modifié pendant cette vérification.', '',
                  '[Revue et réponse manuelle proposée, distincte de la sortie du modèle]'
                  '(../results/delivery_verification/generation_semantic_review.json)', '',
                  'Une correction des règles de génération ou de citations devra être '
                  'développée sur dev et déclarée comme une nouvelle version. Le verrou '
                  'existant doit rester l’historique du système réellement comparé.', '']
    elif app.get('failure'):
        lines += ['Dernier échec enregistré : `' + app['failure']['message'].replace('|', '/') + '`.', '']
    lines += ['## Pourquoi le test final attend', '',
              f"Le dernier contrôle de la grille consolidée indique **{readiness.get('pending_page_pairs')} "
              'jugements de pages sans grade humain/relecteur** et '
              f"**{readiness.get('completed_question_adjudications')}/20 décisions par question complètes**. "
              'L’accord global de l’utilisateur accepte les grades, sans attester les décisions sémantiques par question. '
              'La recherche par fragments ne prouve ni l’exhaustivité des qrels ni '
              'la nouveauté sémantique par rapport aux 145 anciennes questions.', '',
              'La mesure complémentaire réalisée reste provisoire et ne peut pas être annoncée '
              'comme un test final indépendant validé. Le contrôle conserve donc le statut '
              '`annotation_pending`. Les données historiques, les modèles, paramètres et index restent figés.', '',
              '## Graphiques et reproduction', '',
              '[Les cinq figures de comparaison](../results/figures/INDEX.md) ont été générées en PNG/SVG '
              'et inspectées visuellement. Les figures globales portent sur les 145 questions exploratoires ; '
              'celle par type porte uniquement sur les 85 dev. Elles ne donnent pas les scores du nouveau lot.', '',
              'Les commandes pour reproduire les contrôles et précharger Ollama sont dans le '
              '[README](../README.md). Les résultats JSON et les identifiants des passages examinés sont '
              'conservés dans `results/delivery_verification/`. La vérification du verrou a réussi '
              'avant et après les essais terminés.', '',
              'La conformité complète n’est pas revendiquée : restent la validation indépendante, '
              'la relecture et mise en forme académique du rapport, les diapositives, la vidéo et '
              'la validation du paquet de reproduction sur le poste de présentation. La consigne '
              'générale entraînement/validation/test est adaptée et justifiée pour ce système sans '
              'entraînement supervisé local, pas présentée comme suivie littéralement.', '']
    candidate_run = provisional_run()
    if candidate_run:
        link = '../' + candidate_run.relative_to(ROOT).as_posix() + '/RAPPORT.md'
        lines += ['', '## Mesure provisoire supplémentaire des 20 questions', '',
                  f'[Scores et graphique]({link}) : 12 configurations, budgets 5/6. '
                  'Les grades initialement proposés par l’assistant ont été acceptés globalement par l’utilisateur. '
                  'L’indépendance du lot et la génération ne sont pas validées par ce calcul. '
                  'Le lot a désormais été exposé aux scores ; une correction guidée par ceux-ci '
                  'nécessitera une autre confirmation.', '']
    lines.insert(2, approval_notice())
    lines += ['', '## Reproduction isolée et dossier de remise', '',
              '[Reproduction : exécutions, journaux et limites](REPRODUCTION.md). '
              'Une copie isolée avec poids/dépendances réutilisés ne constitue pas une installation vierge. '
              '[Plan de finalisation et preuves](FINALISATION.md).', '']
    (ROOT / 'docs/VERIFICATION_TECHNIQUE.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    verify()
    source_names = ['data/evaluation/audit/dev_qualitative_cases.json',
                    'results/context_top6/comparison.csv', 'results/context_top6/contexts.jsonl',
                    'results/audit_project/error_analysis.csv', 'results/audit_project/profile.json',
                    'data/evaluation/queries_145.jsonl', 'data/evaluation/silver_qrels_PAGES.trec',
                    'data/processed/chunks.jsonl', 'data/processed/paragraphs.jsonl',
                    'docs/METHODOLOGIE.md', 'docs/REFERENCES.md', 'docs/CONFORMITE_ECC.md',
                    'scripts/build_project_review.py', 'results/figures/provenance.json']
    source_names += [str(p.relative_to(ROOT)).replace('\\', '/') for p in
                     (ROOT / 'results/delivery_verification').glob('*.json')]
    source_names += ['data/holdout_candidate/assistant_review/completed_proposal/review_readiness.json']
    approval_path = ROOT / 'data/holdout_candidate/assistant_review/completed_proposal/user_approval.json'
    if approval_path.exists():
        source_names.append(approval_path.relative_to(ROOT).as_posix())
    candidate_run = provisional_run()
    if candidate_run:
        source_names += [str(p.relative_to(ROOT)).replace('\\', '/') for p in candidate_run.iterdir() if p.is_file()]
    source_names += [p.relative_to(ROOT).as_posix() for p in (
        ROOT/'docs/STATUT_HOLDOUT.md', ROOT/'docs/REPRODUCTION.md', ROOT/'docs/FINALISATION.md',
        ROOT/'results/finalization/error_categories_dev.csv', ROOT/'results/finalization/scores_by_type_dev_verified.csv',
        ROOT/'results/reproduction/run.json', ROOT/'results/reproduction/clean_environment.json') if p.exists()]
    before = {n: digest(ROOT / n) for n in source_names}
    cases = json.loads((ROOT / source_names[0]).read_text(encoding='utf-8'))
    questions = {q['question_id']: q for q in jl('data/evaluation/queries_145.jsonl')}
    chunks = {c['chunk_id']: c for c in jl('data/processed/chunks.jsonl')}
    paragraphs = jl('data/processed/paragraphs.jsonl')
    contexts = {(r['question_id'], r['reranker']): r for r in jl('results/context_top6/contexts.jsonl')
                if r['retrieval'] == 'hybrid_rrf' and r['reranker'] in ('none', 'colbert')}
    metrics = {(r['question_id'], r['reranker']): r for r in rows('results/audit_project/error_analysis.csv')
               if r['retrieval'] == 'hybrid_rrf' and r['reranker'] in ('none', 'colbert')}
    manifest = {d['filename']: d for d in json.loads((ROOT / 'data/processed/manifest.json').read_text(encoding='utf-8'))}
    qrels = set()
    for line in (ROOT / 'data/evaluation/silver_qrels_PAGES.trec').read_text().splitlines():
        qid, _, pid, _ = line.split()
        qrels.add((qid, pid))
    lines = ['# Analyse qualitative de trois cas de développement', '',
             'Sélection intentionnelle de trois cas illustratifs parmi les 85 questions dev, '
             'après consultation des scores. Cette sélection ne mesure pas la fréquence '
             'des erreurs et n’est pas un test indépendant. Revue éditoriale par l’assistant, '
             'citations contrôlées dans les PDF physiques. Aucun score n’est recalculé.', '']
    records, proposals = [], []
    for case in cases:
        qid = case['question_id']
        assert questions[qid]['split'] == 'dev'
        chunk = chunks[case['chunk_id']]
        quote = case['quote']
        assert quote in chunk['text']
        filename, pg = case['page_id'].rsplit('#p', 1)
        source = ROOT / manifest[filename]['path']
        assert digest(source) == manifest[filename]['sha256']
        with pymupdf.open(source) as pdf:
            assert canonical(quote) in canonical(pdf[int(pg)-1].get_text()), qid
        matches = [p for p in paragraphs if p['filename'] == filename and p['page'] == int(pg)
                   and canonical(quote) in canonical(p['text'])]
        assert matches, qid
        ranks = {}
        page_ranks = {}
        for rr in ('none', 'colbert'):
            ctx = contexts[qid, rr]
            ranks[rr] = ctx['chunk_ids'].index(case['chunk_id']) + 1
            page_ranks[rr] = ctx['page_ids'].index(case['page_id']) + 1
        original_reference = (qid, case['page_id']) in qrels
        if case['proposed_new_reference_grade'] is not None:
            assert not original_reference
            proposals.append(f"{qid} 0 {case['page_id']} {case['proposed_new_reference_grade']}")
        record = case | dict(split='dev', chunk_ranks=ranks, page_ranks=page_ranks,
                             original_reference=original_reference,
                             paragraph_ids=[p['paragraph_id'] for p in matches],
                             source_sha256=manifest[filename]['sha256'], raw_pdf_quote_verified=True)
        records.append(record)
        b, a = metrics[qid, 'none'], metrics[qid, 'colbert']
        lines += [f'## {qid}', '', questions[qid]['question'], '',
                  '| Indicateur | RRF | RRF + ColBERT |', '|---|---:|---:|',
                  f"| nDCG pages@6 | {float(b['ndcg_pages_at_6']):.6f} | {float(a['ndcg_pages_at_6']):.6f} |",
                  f"| Couverture des pages du contexte | {float(b['context_page_recall']):.3f} | {float(a['context_page_recall']):.3f} |",
                  f"| Rang du chunk examiné | {ranks['none']} | {ranks['colbert']} |",
                  f"| Rang de sa page parmi les pages uniques | {page_ranks['none']} | {page_ranks['colbert']} |", '',
                  f"Passage : `{case['chunk_id']}` ; page : `{case['page_id']}` ; "
                  f"paragraphes : {', '.join(record['paragraph_ids'])}.", '',
                  '> ' + quote, '', '**Interprétation :** ' + case['diagnosis'], '',
                  f"Page présente dans les qrels historiques : {'oui' if original_reference else 'non'}. "
                  'Les corrections suggérées restent séparées et ne modifient ni les qrels figés ni les anciens scores.', '']
    output = ROOT / 'results/audit_project'
    (output / 'ANALYSE_QUALITATIVE_DEV.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (output / 'qualitative_dev_review.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'data/evaluation/audit/dev_qrels_proposals.trec').write_text('\n'.join(proposals) + '\n', encoding='utf-8')
    summary = rows('results/context_top6/comparison.csv')
    best = max(summary, key=lambda r: float(r['ndcg_pages_at_6']))
    baseline = next(r for r in summary if r['retrieval'] == 'bm25' and r['reranker'] == 'none')
    second = next(r for r in summary if r['retrieval'] == 'bm25' and r['reranker'] == 'colbert')
    profile = json.loads((output / 'profile.json').read_text(encoding='utf-8'))
    table = ['| Récupération | Reranking | Couverture contexte | Toutes références | nDCG pages@6 | MRR pages@6 |',
             '|---|---|---:|---:|---:|---:|']
    for r in summary:
        table.append(f"| {r['retrieval']} | {r['reranker']} | {float(r['context_page_recall']):.3f} | "
                     f"{float(r['all_reference_pages_found']):.3f} | {float(r['ndcg_pages_at_6']):.3f} | {float(r['mrr_pages_at_budget']):.3f} |")
    methods = (ROOT / 'docs/METHODOLOGIE.md').read_text(encoding='utf-8')
    methods = methods[methods.index('## Prétraitement'):methods.index('## Reproduction et livrables')]
    report = f'''# Optimisation et déploiement d’un RAG pour la question-réponse FOMC

Étude comparative des stratégies de récupération et de reranking — rapport de travail consolidé.
**Résultats exploratoires ; confirmation indépendante et validation de la génération non achevées.**

## Quels résultats conserver ?

Les tableaux de récupération et de reranking restent nécessaires : ils constituent
la comparaison exploratoire actuelle, et non les résultats d’un nouveau test final.
La révision des annotations du lot candidat ne produit pas de nouveaux scores.

| Ensemble ou expérience | Place dans ce rapport |
|---|---|
| 145 questions, corpus actuel de 93 PDF et 1 692 chunks | Comparaison exploratoire conservée, avec un contexte de sortie de six chunks. |
| Anciennes versions à 200 ou 110 questions, ou autre découpage | Non reprises dans les tableaux et graphiques ci-dessous. |
| Nouveau lot candidat de 20 questions | Aucun score disponible : annotations et indépendance restent à valider avant l’évaluation. |
| Essais Streamlit et génération sur dev | Vérifications fonctionnelles et analyse qualitative, distinctes du benchmark de récupération. |

Les fichiers de résultats sources sont conservés pour la traçabilité. Les graphiques
remettent en forme les mesures existantes ; ils ne signalent pas une nouvelle
exécution des modèles. Aucun résultat final indépendant ne peut encore les remplacer.

## Résumé

Le projet construit un moteur de recherche de preuves dans les Minutes et Statements
du FOMC, avec production optionnelle de réponses citées par un modèle local. Il compare
trois récupérateurs (BM25, E5 et RRF) et trois reclassements (BM25, ColBERT et
cross-encoder), ainsi que l’absence de reclassement. Sur 145 questions exploratoires,
**RRF + ColBERT** obtient le meilleur nDCG pages@6 observé :
**{float(best['ndcg_pages_at_6']):.3f}**. Son contexte contient en moyenne
**{100*float(best['context_page_recall']):.1f} %** des pages pertinentes annotées.
Cela n’établit ni une supériorité universelle ni la qualité des réponses générées.

## Problématique et objectifs

Les rapports monétaires répètent des formulations tout en modifiant les dates,
chiffres et décisions. Retrouver un passage parlant du bon thème ne suffit donc pas :
il faut la bonne réunion, le bon auteur et la bonne période. Nous cherchons à savoir
quelle combinaison priorise le mieux les preuves sous un budget final de six passages.
Le second objectif est la traçabilité : chaque extrait doit renvoyer au document et
à sa page physique, et chaque résultat à une expérience reproductible.

Le périmètre accompli porte principalement sur la recherche, le reranking et leur
évaluation. Une application locale permet la démonstration. L’évaluation complète
de la fidélité de génération et un déploiement public ne sont pas établis.

Un essai applicatif réel de génération a réussi après préchargement du modèle,
mais sa réponse a été jugée partielle et certaines citations portent sur d’autres
réunions. Le [compte rendu technique](VERIFICATION_TECHNIQUE.md) précise cette
limite : un succès fonctionnel ne doit pas être présenté comme une réponse validée.

## Données et statut expérimental

Le corpus comporte **{profile['documents']} PDF**, dont 46 Minutes et 47 Statements,
**{profile['physical_pages']} pages physiques** et **{profile['chunks']} chunks**.
Les sources sont les publications officielles de la Federal Reserve enregistrées
dans le manifeste, avec URL et empreinte de chaque fichier. Les documents couvrent
2021 à 2026 dans le corpus fourni ; la provenance et les dates ne constituent pas
une vérification indépendante de tout leur contenu.

Les 145 questions comprennent 68 factuelles, 42 explicatives, 31 comparatives et
4 multi-documents. Les 279 qrels silver portent sur des pages, avec 188 grades 2
et 91 grades 1. Ces grades ont été conservés. Leur existence et leur localisation
ont été vérifiées techniquement ; leur exhaustivité sémantique n’est pas acquise.

Les étiquettes historiques sont 85 dev, 30 validation et 30 test. Tous ces résultats
ayant été consultés, **les 145 questions sont exploratoires**. Seules les 85 dev
servent à l’analyse détaillée présentée ici. Aucun encodeur, reranker ou LLM n’est
entraîné ou affiné localement : les poids préentraînés restent fixes. Cela explique
l’absence d’un lot d’entraînement supervisé local, mais ne supprime pas les risques
de sélection de paramètres sur les scores déjà observés.

Le code, les paramètres, modèles et index ont été figés avant la préparation d’un
nouveau lot candidat. Celui-ci compte 20 questions et 294 grades de pages,
dont 78 positifs. Les grades proposés par l’assistant ont été acceptés globalement
par l’utilisateur après le calcul, sans modification. La relecture indépendante
page par page et l’adjudication sémantique des questions/réponses ne sont pas attestées.
Les scores de ce lot restent ceux d’une évaluation complémentaire provisoire.

{methods}
## Comparaison exploratoire actuelle — 145 questions, six chunks en sortie

Le tableau utilise les mêmes 145 questions et qrels historiques pour les 12
configurations. La couverture concerne toutes les pages des six chunks ; nDCG et
MRR sont coupés aux six premières pages uniques. Six chunks peuvent contenir plus
de six pages : ces indicateurs n’ont donc pas exactement le même périmètre.

{chr(10).join(table)}

Le nDCG observé de RRF + ColBERT dépasse celui de BM25 seul de
{float(best['ndcg_pages_at_6'])-float(baseline['ndcg_pages_at_6']):.3f} point.
En revanche, il ne dépasse BM25 + ColBERT que de
{float(best['ndcg_pages_at_6'])-float(second['ndcg_pages_at_6']):.4f} point.
**Cette faible différence n’est pas une preuve de supériorité statistique.**
Aucun test confirmatoire indépendant ni intervalle tenant compte de toutes les
dépendances entre questions n’est présenté. La combinaison retenue constitue un
choix exploratoire figé pour une future confirmation.

Les mesures sur le pool complet de 20 candidats donnent d’autres scores, notamment
un nDCG pages@10 ; ils servent au diagnostic du pool et ne doivent pas être confondus
avec le tableau du contexte de six chunks. Le nombre 20 désigne le pool à reclasser,
pas le nombre de passages transmis au générateur. Les latences après échauffement excluent certains
chargements et préencodages : elles ne démontrent pas la vitesse d’une requête froide
dans l’application, qui peut réencoder les documents ColBERT.

## Graphiques de comparaison

Toutes les figures ci-dessous utilisent les résultats exploratoires existants.
Elles sont disponibles en PNG et en SVG dans [l’index des figures](../results/figures/INDEX.md),
avec les sources et leurs empreintes. Aucune ne représente le test final indépendant.

### Récupération seule

![Comparaison des récupérateurs](../results/figures/01_recuperation.png)

Les trois récupérateurs sont comparés sans reranking. La couverture porte sur
toutes les pages des six chunks ; nDCG et MRR sur six pages uniques.

### Les douze configurations

![Comparaison des rerankers](../results/figures/02_reranking.png)

La matrice compare chaque reranker sur le même pool de vingt candidats de son
récupérateur. Le contrôle BM25 sur son propre classement conserve le score.

### Effet du reranking

![Gains et pertes du reranking](../results/figures/03_effet_reranking.png)

Chaque ligne est comparée au même récupérateur sans reranking, question par
question. Les nombres de questions améliorées, inchangées et dégradées complètent
la moyenne. Ce diagnostic est descriptif et dépend des références silver.

### Budget de contexte

![Couverture selon le budget de contexte](../results/figures/04_budget_contexte.png)

La couverture des pages utilise le même dénominateur pour cinq et six chunks.
Cette figure montre l’effet du budget de sortie, sans prétendre que la sélection
de six passages évite le scoring des vingt candidats.

### Analyse par type sur dev

![Résultats par type sur dev](../results/figures/05_types_dev.png)

L’analyse détaillée porte seulement sur les 85 questions dev, avec les effectifs
affichés. La catégorie multi-documents n’a que trois questions dans ce sous-ensemble :
sa moyenne ne permet pas une conclusion robuste sur toutes les comparaisons documentaires.

## Interprétabilité par analyse des erreurs

Le diagnostic automatique existant comporte 1 020 lignes : 85 questions dev × 12
configurations. Ses catégories décrivent la couverture des pages silver ; ce sont
des indicateurs de tri, pas des causes d’erreurs validées.

La revue de trois cas dans
[ANALYSE_QUALITATIVE_DEV.md](../results/audit_project/ANALYSE_QUALITATIVE_DEV.md)
ajoute les textes effectivement retenus et les citations vérifiées dans les PDF :

- **FOMC_004** : score nul alors qu’un passage de la bonne réunion énonce l’amélioration
  de l’activité et de l’emploi ; une page alternative des Minutes manque aux qrels.
- **FOMC_035** : baisse de couverture silver après ColBERT, mais promotion au rang 1
  d’un passage de janvier 2022 expliquant inflation élevée et travail solide. La perte
  de score n’est pas à elle seule une perte démontrée de capacité à répondre.
- **FOMC_064** : la même preuve passe du quatrième au premier chunk. Sa page passe
  du septième au premier rang des pages uniques ; nDCG@6 passe de 0 à 1, alors que
  la preuve figurait déjà dans les six chunks avant reclassement.

Ces exemples sont sélectionnés pour expliquer les mécanismes, sans prétendre estimer
leur fréquence. Deux nouvelles références sont proposées dans un fichier séparé ;
elles ne modifient pas les annotations figées et aucun score historique n’est réécrit.
L’analyse d’erreurs est ici la méthode d’interprétabilité adaptée à la consigne ECC ;
un graphique SHAP n’est pas requis pour comprendre ces classements documentaires.

## Démonstration et reproductibilité

Le [compte rendu des vérifications techniques](VERIFICATION_TECHNIQUE.md) distingue
les tests automatisés, les essais Streamlit réels, la génération et le statut du
test final indépendant. Le démarrage d’une application ne prouve pas, à lui seul,
que toute la chaîne fonctionne ni que ses réponses sont justes.

L’application Streamlit orchestre recherche, reranking, sélection de cinq ou six
passages et génération optionnelle via Ollama. Elle offre une démonstration locale,
pas un hébergement public certifié. La variante temporelle est exploratoire et
distincte du système classique comparé. Les commandes d’installation et d’exécution
sont dans le [README](../README.md). La présence d’un dépôt Git et d’une URL distante
configurée ne prouve pas que les dernières modifications y ont été publiées.

Le protocole figé vérifie les empreintes des sources, code, paramètres, index et
révisions de modèles. Les tests contrôlent notamment les métriques, l’alignement
des pages, l’identité des candidats avant/après reranking et le budget de contexte.
L’assemblage documentaire utilise les fichiers existants, hors du code figé et sans
nouvelle inférence. Les essais Streamlit et la reconstruction des index ont appelé
les vrais modèles ; leurs traces sont présentées séparément.

## Limites et travaux nécessaires avant la conclusion finale

Les qrels silver sont incomplets dans certains cas observés ; les pages ne jugent
pas directement le contenu de chaque chunk. Les questions partagent des sources et
les scores déjà vus ne sont pas indépendants. Les résultats ne prouvent pas que la
génération est correcte ou que les citations impliquent toutes les affirmations.
La décision de remise est de conserver le lot supplémentaire comme évaluation
descriptive, sans prétendre qu’il constitue un test indépendant validé. La comparaison
actuelle peut être présentée avec ces limites ; une nouvelle confirmation est requise
pour soutenir une conclusion confirmatoire ou valider un réglage guidé par ces scores.
La validation humaine globale est consignée, sans inventer de décisions sémantiques.

Le rapport rassemble contexte, méthode, résultats et discussion. Sa relecture technique
porte sur les équations, les unités, les moyennes, les tables et les limites de génération.
L’[état des cinq actions](FINALISATION.md) et les [preuves de reproduction](REPRODUCTION.md)
précisent ce qui a été exécuté et ce qui demeure limité. Le format académique exigé par
l’établissement, les diapositives et la vidéo de 15–20 minutes sont des livrables distincts.

## Traçabilité des documents de travail

- [Méthodologie détaillée](METHODOLOGIE.md).
- [Tableau de conformité aux consignes](CONFORMITE_ECC.md).
- [Scores exploratoires de sortie top-6](../results/context_top6/comparison.csv).
- [Profil exploratoire et figures](../results/audit_project/RAPPORT.md).
- [Préannotation du lot candidat](../data/holdout_candidate/assistant_review/completed_proposal/RAPPORT.md).
- [Verrou du pipeline](../protocol/frozen_pipeline_20261120.json).

## Références scientifiques

Les [références primaires vérifiées](REFERENCES.md) couvrent BM25, E5, RRF,
ColBERT et le reranking neuronal avec BERT. Elles expliquent les principes ;
les checkpoints et paramètres réellement employés sont ceux du verrou du projet.
La liste et son format bibliographique restent à relire selon les exigences de remise.
'''
    if candidate_run:
        link = '../' + candidate_run.relative_to(ROOT).as_posix() + '/RAPPORT.md'
        report = report.replace('Aucun score disponible : annotations et indépendance restent à valider avant l’évaluation.',
            'Scores provisoires disponibles ; grades acceptés globalement, indépendance non établie.')
        report = report.replace('Aucun résultat final indépendant ne peut encore les remplacer.',
            'Les nouveaux scores provisoires sont présentés séparément et ne remplacent pas ces résultats exploratoires.')
        report = report.replace('les pages complètes. Aucune performance n’a été calculée sur ce nouveau lot.',
            'les pages complètes. Une mesure provisoire est désormais disponible, sans statut de test final validé.')
        section = '\n'.join(['## Évaluation provisoire supplémentaire — 20 questions', '',
            f'[Tableaux, graphique et limites du calcul]({link}). Les 12 configurations sont évaluées '
            'sur les grades proposés puis acceptés globalement par l’utilisateur, aux budgets de cinq et six chunks. '
            'Aucun paramètre du système figé n’est modifié. Cet accord ne démontre pas l’indépendance sémantique.', '',
            '**Le lot est désormais exposé aux scores.** Tout réglage guidé par ces résultats nécessite '
            'une autre confirmation. La qualité des réponses générées reste à évaluer séparément.', '', ''])
        report = report.replace('## Graphiques de comparaison', section + '## Graphiques de comparaison')
        six = [r for r in rows(candidate_run.relative_to(ROOT).as_posix()+'/comparison.csv') if r['budget']=='6']
        values = ['| Recherche | Reranker | Couverture | nDCG pages@6 | MRR pages@6 |',
                  '|---|---|---:|---:|---:|']
        for r in six:
            values.append(f"| {r['retrieval']} | {r['reranker']} | {float(r['context_page_recall']):.3f} | {float(r['ndcg_pages_at_budget']):.3f} | {float(r['mrr_pages_at_budget']):.3f} |")
        extra = '\n'.join(values)+'\n\n'+(
            'Dense E5 + cross-encoder obtient ici le meilleur nDCG observé (0,521), '
            'devant RRF + cross-encoder (0,520). RRF + ColBERT, choisi avant cette mesure, '
            'obtient 0,506 et la meilleure couverture moyenne (55,7 %). Ce changement de '
            'classement entre jeux souligne la dépendance aux questions et annotations ; '
            'aucun changement de modèle ni test statistique confirmatoire ne résulte de ces écarts. '
            'Les deux jeux ne sont pas fusionnés en un prétendu test indépendant de 165 questions.\n\n')
        report = report.replace('## Graphiques de comparaison',extra+'## Graphiques de comparaison')
    typed_path=ROOT/'results/finalization/scores_by_type_dev_verified.csv'
    if typed_path.exists():
        type_lines=['### Résultats vérifiés par type — RRF + ColBERT sur dev','',
            '| Type | Questions | Couverture | nDCG pages@6 |','|---|---:|---:|---:|']
        for r in rows(typed_path.relative_to(ROOT).as_posix()):
            if (r['retrieval'],r['reranker'])==('hybrid_rrf','colbert'):
                type_lines.append(f"| {r['question_type']} | {r['questions']} | {float(r['context_page_recall']):.3f} | {float(r['ndcg_pages_at_6']):.3f} |")
        type_lines += ['', '[Catégories des 1 020 observations et analyse consolidée](../results/finalization/ANALYSE_ERREURS.md). '
            'Les catégories décrivent la couverture silver ; elles ne prouvent pas une cause sémantique.','']
        report=report.replace('## Interprétabilité par analyse des erreurs','\n'.join(type_lines)+'\n## Interprétabilité par analyse des erreurs')
    if approval_notice():
        report = report.replace('## Quels résultats conserver ?', approval_notice() + '## Quels résultats conserver ?')
    (ROOT / 'docs/RAPPORT_PROJET.md').write_text(report, encoding='utf-8')
    technical_report()
    assert before == {n: digest(ROOT / n) for n in source_names}
    (output / 'project_review_provenance.json').write_text(json.dumps(dict(
        source_hashes=before, pipeline_sha256=digest(LOCK), reviewed_dev_questions=[c['question_id'] for c in cases],
        raw_pdf_quote_checks=len(records), source_data_unchanged=True,
        retrieval_models_called=False, new_holdout_scored=False,
        new_reference_proposals_not_applied=True,
        outputs_sha256={str(p.relative_to(ROOT)): digest(p) for p in
                        (ROOT / 'docs/RAPPORT_PROJET.md', output / 'ANALYSE_QUALITATIVE_DEV.md',
                         output / 'qualitative_dev_review.json',
                         ROOT / 'data/evaluation/audit/dev_qrels_proposals.trec')}), indent=2) + '\n', encoding='utf-8')
    verify()
    print('PASS: 3 dev cases, 3 raw-PDF quote checks, 2 unapplied reference proposals; project report assembled; sources unchanged.')


if __name__ == '__main__':
    main()
