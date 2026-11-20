# Concordance avec les consignes ECC

Revue du 20 novembre 2026, à partir de la capture « Consignes générales / Livrables »
fournie par l’utilisateur et des fichiers effectivement disponibles. Une conformité
technique partielle ne constitue pas une validation pédagogique ou une remise finale.

| Consigne | État vérifié | Preuves et écart restant |
|---|---|---|
| Fondements théoriques des méthodes | Présents | [Méthodologie](METHODOLOGIE.md), [références primaires](REFERENCES.md), modèles et paramètres dans le verrou. |
| Prétraitement | Présent | `src/pdf_layout.py`, `src/chunk.py`, `src/align_references.py` ; 1 692 chunks, provenance par paragraphe/page, montants et négations conservés. |
| Analyse exploratoire obligatoire | Présente | `results/audit_project/profile.json`, `eda.png` : 93 PDF, 838 pages, longueurs, types, doublons et valeurs vides. |
| Baseline simple et méthodes avancées | Présentes | BM25, E5 et RRF ; absence de reranking, BM25, ColBERT et cross-encoder. Comparaison des 12 configurations au même budget de six chunks. |
| Graphiques de comparaison demandés | Présents et intégrés au rapport | [Cinq figures PNG/SVG](../results/figures/INDEX.md) : récupération, 12 configurations, gains/pertes, budget 5/6, types sur dev. Données exploratoires explicitement étiquetées. |
| Prévention des fuites ; lots entraînement/validation/test | Adaptation documentée, pas conformité littérale revendiquée | Aucun poids ajusté localement : pas de lot d’entraînement supervisé nécessaire. Les 145 questions déjà consultées sont exploratoires, seules les 85 dev servent aux diagnostics détaillés. Le corpus documentaire partagé est normal pour la recherche. Cette justification doit être présentée à l’évaluateur au regard de la consigne générale de séparation. |
| Évaluation indépendante après choix des paramètres | Non achevée ; mesure provisoire séparée | Code, poids, index et paramètres figés. La mesure des 20 questions sur les 294 grades proposés est conservée dans `results/candidate_provisional/`. Elle ne constitue pas un test final validé : contrôles sémantiques, validation des grades et adjudication des réponses restent requis. |
| Interprétabilité par une méthode adaptée | Analyse d’erreurs documentée | Diagnostic automatique sur 85 dev × 12 configurations, complété par [trois cas relus dans les sources](../results/audit_project/ANALYSE_QUALITATIVE_DEV.md). Cela répond à l’option « analyse détaillée des erreurs » de la capture ; SHAP n’est pas présenté comme obligatoire pour ce moteur. |
| Sources ouvertes et préparation traçable | Présentes ; annotations à confirmer | 93 publications FOMC enregistrées avec URL et empreinte. Les qrels silver de l’utilisateur ne sont pas des jugements officiels certifiés. Deux références dev manquantes sont proposées séparément, sans modifier les scores historiques. |
| Solution automatisée et déployée si possible | Démonstration locale disponible | Streamlit + recherche/reranking + génération optionnelle Ollama. Le contrôle top-6 en ligne est enregistré. Un déploiement public et une évaluation complète des réponses générées ne sont pas établis. |
| Vérification réelle de la génération | Fonctionnement observé, qualité insuffisamment validée | Un démarrage à froid a expiré ; préchargement réussi puis réponse structurée réelle en environ 96 s. La réponse dev est partielle et cite aussi d’autres réunions : contrôle temporel/complétude à corriger dans une version déclarée, sans modifier silencieusement le système figé. |
| Dépôt Git | Dépôt local et origine configurée | URL distante configurée, sans vérification distante de sa synchronisation. Des fichiers de travail restent à intégrer à la version remise ; aucune publication effectuée par cette revue. |
| README installation/exécution/reproduction | Présent, liens actualisés | [README](../README.md), versions et commandes. Le verrou contrôle la reproductibilité du système figé. |
| Code et fichiers nécessaires à la reproduction | Présents localement | Modèles/index/PDF disponibles localement, certains ignorés par Git. Pour un autre poste, vérifier leur disponibilité et les instructions d’obtention ; l’URL du dépôt seule ne fournit pas ces fichiers. |
| Rapport écrit : contexte, objectifs, fondements, méthode, résultats, discussion | Assemblé, version de travail à relire | [RAPPORT_PROJET.md](RAPPORT_PROJET.md) rassemble ces éléments, avec limites explicites et bibliographie. Mise en forme académique et validation finale restent à faire. |
| PowerPoint | Non identifié dans le projet actif | Préparer les diapositives à partir du rapport ; ne pas confondre rapport Markdown et présentation remise. |
| Vidéo et démonstration de 15–20 minutes | Non identifiées dans le projet actif | Enregistrer une présentation avec démonstration réelle ; ne pas inventer une vidéo ni une preuve de fonctionnement non observée. |
| Données accompagnées de sources et traitements | Documentées localement | Manifeste, méthodologie et profils ; compléter le paquet de remise pour un autre poste. |
| Déploiement ou démonstration testable | Démonstration locale prévue dans le README | Vérifier l’application sur le poste de démonstration, les chemins et la disponibilité du modèle ; aucun hébergement public revendiqué. |

## Corrections documentaires et méthodologiques de cette passe

Les vérifications techniques sont détaillées dans
[VERIFICATION_TECHNIQUE.md](VERIFICATION_TECHNIQUE.md). Le recalcul indépendant des
3 480 contextes top-5/top-6 concorde avec les 24 synthèses. Ces contrôles ne constituent
pas le test final indépendant sur le nouveau lot.

1. Le rapport utilise en priorité les résultats des **six chunks finaux**, et distingue
   explicitement le rang des pages du budget de chunks et des anciens résultats @10/@20.
2. Le mot « meilleur » est limité au meilleur score exploratoire observé. L’écart de
   nDCG pages@6 entre RRF + ColBERT (0,4013) et BM25 + ColBERT (0,3971) ne démontre
   pas une supériorité statistique.
3. Les catégories automatiques « aucune page annotée » ne sont plus assimilées à une
   absence de preuve : les cas dev 004 et 035 contiennent des passages répondants
   sur des pages absentes des références silver. Les propositions de correction
   sont séparées dans `data/evaluation/audit/dev_qrels_proposals.trec`.
4. Les 294 propositions du nouveau lot restent distinctes des annotations humaines.
   La dernière passe négative repose sur un examen structuré, non une lecture humaine
   exhaustive : son exhaustivité et son indépendance ne sont pas revendiquées.
5. Le pipeline et les données historiques restent figés. Une mesure provisoire
   des nouvelles questions est lancée séparément, sans réglage des paramètres.
   Ce lot est désormais exposé aux scores : une correction guidée par ceux-ci
   exigera une nouvelle confirmation.

## Ordre de finalisation

Confirmer et adjuger les annotations du nouveau lot ; relire le rapport et sa
présentation des limites ; préparer les diapositives et la vidéo ; vérifier la
démonstration et le paquet de reproduction. La mesure finale du système figé
attend les annotations approuvées. La capture mentionne le 30 novembre : cette
information provient de la capture et n’a pas été confirmée auprès de l’établissement.
