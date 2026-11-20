# Revue des consignes ECC — 20 novembre 2026

Référence : capture « Consignes générales / Livrables » fournie par l’utilisateur. Le projet respecte une partie substantielle des exigences techniques, mais ne peut pas encore être déclaré entièrement conforme.

| Exigence | Constat | Preuve ou action restante |
|---|---|---|
| Fondements théoriques | Documentés | docs/METHODOLOGIE.md : BM25, E5, RRF, ColBERT, cross-encoder et métriques. |
| Prétraitement et analyse exploratoire | Présents | Extraction contrôlée, contributions de pages, profile.json et eda.png. |
| Baseline et modèles avancés | Présents | BM25, E5, RRF ; BM25, ColBERT et cross-encoder ; budgets finaux 5 et 6. |
| Prévention des fuites et lots | Protocole exploratoire explicite | Les 145 questions restent exploratoires ; analyse détaillée sur les 85 dev. Aucun entraînement supervisé local. Aucun ancien lot présenté comme indépendant. Nouveau test non scoré préparé après gel, à valider humainement. |
| Interprétabilité / analyse des erreurs | Présente, à commenter | explain.py, audits de citations, error_analysis.csv, scores_by_question_type.csv et exemples du rapport. Pas de preuve automatique de fidélité sémantique. |
| Sources et préparation des données | Traçables | 93 PDF officiels, manifestes, empreintes et annotations silver conservées ; leur pertinence reste à revoir humainement. |
| Solution automatisée et démonstration | Application locale présente | Streamlit et Ollama ; commandes dans le README. Un déploiement public et la présence du modèle Ollama sur un autre poste ne sont pas établis. |
| Dépôt Git et reproductibilité | Dépôt local présent, publication à vérifier | requirements.txt complété, tests et commandes. Aucune publication distante effectuée pendant cette revue. |
| Rapport écrit final | Partiel | Méthodologie, résultats et cette revue existent ; assembler et relire le rapport académique complet. |
| Présentation PowerPoint | À préparer / vérifier | Aucun fichier PPTX identifié dans le projet actif pendant la revue. |
| Vidéo et démonstration de 15–20 min | À préparer / vérifier | Aucune vidéo de soutenance identifiée dans le projet actif pendant la revue. |

## Profil effectivement vérifié

93 PDF, 838 pages, 1692 chunks, 145 questions et 279 jugements de pages. Empreintes des sources vérifiées. Chunks vides : 0. Identifiants de chunks dupliqués : 0.

## Séparation des données

Étiquettes présentes : {'test': 30, 'dev': 85, 'validation': 30}. Pages annotées partagées entre lots : {'dev / test': 22, 'dev / validation': 27, 'test / validation': 11}. Ce partage n’est pas une fuite à lui seul : un moteur de recherche peut utiliser le même corpus pour toutes les questions. En revanche, sélectionner des paramètres à partir des scores de test empêche de présenter ce test comme indépendant.

Protocole confirmé par l’utilisateur : conserver les 145 questions et résultats comme évaluation exploratoire ; réserver les 85 questions dev aux corrections et à l’analyse détaillée. Les anciens test/validation déjà consultés ne sont pas indépendants. Aucun jeu d’entraînement supervisé local n’était requis car aucun poids d’encodeur, reranker ou LLM n’est ajusté. Les traitements documentaires déterministes et l’index commun sont normaux pour ce corpus de recherche. Les qrels restent exclus des récupérateurs et rerankers. Le gel enregistre les empreintes des codes, des index et des révisions de modèles ; les nouveaux exemples ne doivent pas guider de nouveaux réglages. Une séparation rétroactive ne supprime pas l’examen des résultats passés.

## Correction du reranking

Les modèles reclassent 20 candidats puis sélectionnent 6 passages (5 également disponibles). Le coût de calcul des 20 scores reste nécessaire. Les sorties *_top5.jsonl et *_top6.jsonl, les contextes dans results/context_top5 et context_top6 et l’application respectent cette distinction. Les métriques concernent les pages projetées à partir des passages effectivement sélectionnés.

## Reste à finaliser

Valider humainement les nouvelles questions et qrels avant leur première évaluation, revoir un échantillon des références silver et des erreurs dev, assembler le rapport final, préparer les diapositives et enregistrer la démonstration de 15–20 minutes. La capture indique une remise au 30 novembre ; cette échéance n’a pas été vérifiée auprès de l’établissement.
