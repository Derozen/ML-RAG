# Jeu proposé de 200 questions

**Mise à jour du 6 novembre 2026 :** l’utilisateur a déclaré avoir vérifié le jeu et a autorisé les tests. Une copie validée est enregistrée dans `questions.jsonl`, avec la provenance dans `annotations.json`. Les fichiers portant le suffixe `_draft` restent les propositions originales. La comparaison exécutée est disponible dans [le rapport](../results/comparison_200_v1/RAPPORT.md). Les indications de revue ci-dessous décrivent le processus de préparation et restent utiles pour toute nouvelle version.

Commencer par [la version de relecture](questions_200_review.md). Chaque entrée présente la question, une réponse extractive, ses citations et les liens vers les pages physiques des PDF. Les questions sont en anglais, comme le corpus et le modèle E5 utilisé. Les césures PDF restent dans les citations afin de conserver leur correspondance exacte avec les passages.

| Type | Nombre |
|---|---:|
| Factuelle | 80 |
| Reformulation | 40 |
| Explicative | 40 |
| Comparative entre réunions | 30 |
| Sans réponse dans le corpus | 10 |

Les fichiers `dev_50_draft.jsonl` et `test_150_draft.jsonl` contiennent les deux lots. Les preuves de développement proviennent des deuxième et sixième réunions de chaque année ; celles de test, des six autres réunions. Aucune famille de reformulations ni aucun document utilisé comme preuve n'est partagé entre les lots. Tous les documents restent néanmoins accessibles à tous les récupérateurs dans le même index : il ne s'agit pas de retirer les documents de test de l'index.

Le script `scripts/prepare_questions_200.py` reconstruit les fichiers et le rapport `questions_200_audit.json`. Il vérifie les citations dans les paragraphes, les chunks et les pages originales des PDF. Pour le contrôle PDF, la normalisation conserve lettres et chiffres et ignore ponctuation, espaces et césures ; les citations des chunks sont contrôlées exactement. Les 220 groupes de preuves portent sur 116 pages distinctes. Les passages acceptés sont ceux contenant la citation choisie : les jugements de pertinence ne sont pas encore exhaustifs.

Les réponses proposées sont volontairement extractives. Les questions factuelles et comparatives privilégient les taux directeurs et le chômage pour une comparaison contrôlée ; les questions explicatives diversifient les thèmes (inflation, emploi, réserves, repo, marchés, croissance, commerce et bilan). Ce jeu ne doit pas être présenté comme représentatif de toutes les questions financières possibles. Les reformulations ne sont pas des observations statistiques indépendantes : agréger aussi les résultats par famille lors de l'analyse.

Avant l'évaluation finale, un lecteur indépendant doit vérifier clarté, adéquation de la réponse, suffisance des preuves et passages pertinents supplémentaires. Pour les questions sans réponse, vérifier l'absence à l'échelle du corpus, et pas seulement l'échec d'un récupérateur. Les cases du document Markdown servent à cette revue ; elles ne modifient pas automatiquement les annotations JSONL. Conserver une trace du lecteur, de la date et des corrections avant promotion dans `questions.jsonl`. Tous les objets restent `validated: false` ; le fichier de questions validées et le pilote initial ne sont pas remplacés.

Ne pas ajuster les paramètres de récupération sur le lot test. Finaliser les annotations et figer leurs empreintes avant les mesures définitives. Aucun score de récupération n'a été calculé sur ces propositions.
