# État du plan de finalisation

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
