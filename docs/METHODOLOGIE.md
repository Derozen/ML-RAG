# Méthodologie du RAG FOMC

Cette description est reprise dans le [rapport consolidé](RAPPORT_PROJET.md).
Les [références scientifiques](REFERENCES.md) et la
[revue de conformité](CONFORMITE_ECC.md) complètent les principes et leurs limites.

## Objectif et protocole

Le système recherche des preuves dans les minutes et statements officiels du FOMC, les reclasse et produit éventuellement une réponse avec citations grâce à un LLM local. La comparaison distingue la récupération, le reranking, la sélection du contexte et la génération. Une bonne récupération ne prouve pas qu’une réponse générée est correcte.

Le corpus de recherche est partagé par les méthodes. Les questions et leurs annotations ne sont jamais injectées dans les passages. Les récupérateurs et rerankers lisent le texte de la question ; les qrels servent aux audits et à l’évaluation. Les modèles sont préentraînés et ne sont pas ajustés localement : aucun jeu d’entraînement supervisé local n’était requis. Les 145 questions constituent l’évaluation exploratoire ; les 85 questions dev sont le sous-ensemble d’analyse détaillée. Les autres questions déjà consultées ne sont pas présentées comme indépendantes. Le gel par empreintes précède la création du nouveau jeu candidat, non scoré avant validation humaine. Un test dont les résultats ont déjà guidé des choix ne redevient pas indépendant après un changement d’étiquette.

## Prétraitement et analyse exploratoire

Les PDF sont extraits en respectant l’ordre des colonnes et les lignes à plusieurs polices. Les montants, fractions, dates et négations sont conservés. Les passages ont au plus 400 tokens de corps, avec chevauchement de 60 tokens et une entrée complète sous la limite du modèle. Le chevauchement réduit la perte d’information aux frontières, mais crée des passages qui partagent du texte.

Chaque chunk conserve son document, sa date, ses paragraphes et la contribution en caractères de chaque page physique. L’inventaire du contenu, les empreintes des fichiers et les longueurs sont contrôlés. Toutes les pages à contribution positive restent dans la provenance ; une contribution faible ne devient pas une preuve de pertinence.

`audit_project.py` produit les distributions par année, longueur de chunk et type de question, les contrôles de valeurs vides et d’identifiants dupliqués, ainsi que les recouvrements de pages annotées entre les étiquettes de lots. Un corpus partagé entre questions est normal pour la recherche documentaire ; le risque vient notamment du réglage des méthodes sur les questions utilisées ensuite pour annoncer un résultat final.

## Récupération : trois méthodes

### BM25 : référence lexicale

BM25 additionne les contributions des termes de la question. Pour chaque terme, son IDF mesure sa rareté dans le corpus. Sa fréquence dans le passage est saturée et corrigée par la longueur du passage :

`score(q,d) = somme_t IDF(t) × f(t,d)(k1+1) / [f(t,d) + k1(1−b+b×|d|/longueur_moyenne)]`.

Le projet utilise `rank-bm25`, k1=1,5 et b=0,75. Les IDF et la longueur moyenne proviennent de l’ensemble du corpus, y compris lors du reclassement d’un sous-ensemble. La méthode convient aux dates, montants et termes exacts, mais peut manquer des formulations sémantiquement proches sans mots communs.

### Recherche dense E5

`intfloat/e5-small-v2` encode la question avec le préfixe `query:` et le passage avec `passage:`. Les vecteurs de 384 dimensions sont normalisés. Le score est leur produit scalaire, équivalent au cosinus lorsque les normes valent 1. La recherche est exacte sur les mêmes identifiants de chunks que BM25. Elle peut rapprocher des reformulations, mais un sujet similaire ne garantit pas la bonne réunion ni la bonne valeur numérique.

### Fusion hybride RRF

RRF combine les rangs des listes BM25 et E5 : `RRF(d) = somme_m 1/(60 + rang_m(d))`. Un document absent d’une liste ne reçoit aucune contribution de cette liste. La fusion évite d’additionner des scores BM25 et cosinus qui n’ont pas la même échelle. Les deux listes sont tronquées à 20, puis la fusion fournit 20 candidats. L’étude de profondeur `compare_rrf_depth.py` est une expérience distincte ; ses résultats ne constituent pas un test indépendant si les mêmes questions servent à sélectionner la profondeur.

## Reranking et sélection finale

Le reranker attribue de nouveaux scores aux **20 mêmes candidats**, puis le système conserve les **6 meilleurs passages**, ou 5 si ce budget est choisi. Le reranking n’effectue pas une nouvelle recherche dans tout le corpus. Sélectionner 6 sorties ne signifie pas que seuls 6 candidats ont été scorés.

- **BM25** : reclassement lexical avec les statistiques globales. Appliqué à son propre classement, il constitue un contrôle d’identité.
- **ColBERT** : l’encodeur BERT et sa projection apprise représentent chaque token dans un espace de 96 dimensions. Le score MaxSim est `s(q,d) = somme_i max_j cos(q_i,d_j)`. Les marqueurs de rôle, la normalisation et le masquage des tokens documentaires suivent l’adaptateur du checkpoint. Le modèle utilise jusqu’à 64 tokens de question et 512 de document, sans expansion de requête. Les représentations documentaires peuvent être précalculées.
- **Cross-encoder** : `cross-encoder/ms-marco-MiniLM-L6-v2` lit conjointement la paire question/passage et produit un logit de pertinence. Ce score n’est pas présenté comme une probabilité calibrée. La limite est de 512 tokens ; le document est tronqué si nécessaire. Chaque paire doit être évaluée conjointement, d’où un coût différent du bi-encodeur.

Les révisions sont figées dans `common.py`. Les rangs et les scores complets sont conservés pour les contrôles ; les fichiers `*_top5.jsonl` et `*_top6.jsonl` contiennent les sorties retenues. Les expériences de contexte comparent tous les classements avec le même budget final, y compris les classements sans reranking.

## Génération et variante temporelle

Le chemin classique fournit les 5 ou 6 passages à Ollama, avec leurs identifiants de sources. L’utilisateur doit installer le modèle local indiqué dans l’application. Les contrôles de citations vérifient les identifiants et certaines contraintes structurelles ; ils ne démontrent pas automatiquement que chaque affirmation découle du texte cité.

Le module temporel est une variante exploratoire : il détecte les périodes demandées, recherche des preuves par période et ajoute des heuristiques de décision ou de justification. Il est plafonné à 6 passages au total. Cette politique ajoute des règles au pipeline classique ; elle ne doit pas être présentée comme le même système que celui mesuré dans le benchmark standard. Le mode utilisé est affiché dans l’application.

## Évaluation et interprétation

### Définitions exactes et agrégation

Pour une question q, R(q) est l’ensemble des pages annotées de grade strictement
positif. P@K(q) désigne les K premières pages uniques du classement, et C_B(q)
les pages de tous les B chunks sélectionnés, avec B = 5 ou 6.

- `Recall@K(q) = |P@K(q) ∩ R(q)| / |R(q)|`.
- `Couverture_contexte_B(q) = |C_B(q) ∩ R(q)| / |R(q)|`.
- `Toutes_références_B(q) = 1` si `R(q) ⊆ C_B(q)`, sinon 0.
- `DCG@K(q) = somme_{r=1..K} (2^grade(page_r) − 1) / log2(r+1)` ;
  `nDCG@K(q) = DCG@K(q) / IDCG@K(q)`, avec l’idéal trié sur tous les grades.
- `RR@K(q) = 1/r` pour le premier rang positif `r ≤ K`, sinon 0 ;
  `MRR@K = moyenne_q RR@K(q)`.

Tous les tableaux agrègent par moyenne **par question**, sans pondération par
nombre de pages. Les questions possèdent au moins une référence positive :
aucun dénominateur nul n’est traité comme un échec de récupération. Les jeux
actuels n’évaluent donc pas une politique d’abstention sur des questions sans réponse.
Dans le tableau top-6, nDCG et MRR sont tronqués à six pages uniques, alors que
la couverture parcourt toutes les pages de six chunks. Dans le tableau top-5,
les colonnes nDCG@5 et nDCG@6 restent deux coupures distinctes ; MRR utilise le
budget de cinq pages. Les métriques du pool complet ne sont pas substituées à celles du contexte.

Les 279 annotations silver portent sur des pages, avec grades 1 et 2. Les grades sont conservés. Les pages des chunks sont dédoublonnées dans leur ordre d’apparition, avec ordre physique à l’intérieur d’un chunk multipage. Cette convention impose un ordre aux pages d’un même chunk et doit être indiquée dans le rapport.

- **Recall@K** : proportion des pages pertinentes annotées présentes parmi les K premières pages uniques.
- **nDCG@K** : gain `2^grade−1`, décote `log2(rang+1)`, division par le classement idéal calculé sur tous les qrels de la question.
- **MRR@K** : inverse du premier rang pertinent jusqu’à K, sinon zéro, moyenné sur les questions.
- **Couverture du contexte final** : proportion des pages annotées présentes dans les 5 ou 6 chunks effectivement sélectionnés, sans assimiler le budget de chunks au nombre de pages.
- **Couverture du pool** : même mesure sur tous les 20 candidats ; elle est invariante après reclassement à pool fixe.

Une page pertinente peut correspondre à une petite portion du chunk, sans que la phrase répondant à la question soit présente. Les qrels de pages ne sont donc pas des jugements de chunks. Une page non annotée est notée zéro pour les métriques, sans preuve de non-pertinence. Les résultats silver nécessitent une interprétation prudente et une revue humaine ciblée.

L’analyse des erreurs distingue les contextes sans page annotée, partiellement couverts ou couvrant toutes les pages annotées. Elle est ventilée par méthode et type de question. Les classements avant/après et les diagnostics lexicaux aident à examiner les cas ; une perte de score peut aussi révéler une annotation incomplète. Le texte des PDF doit être lu avant d’attribuer une cause.

Les latences sont exploratoires : chargements, préencodage ColBERT et coût partagé de requête sont rapportés séparément lorsque disponibles. Les durées du benchmark ne sont pas celles d’une requête froide dans l’application, où les documents ColBERT peuvent être réencodés. Aucun gain de vitesse lié à la seule sélection top-6 n’est revendiqué.

## Reproduction et livrables

Le README décrit l’installation, les commandes, la démonstration locale et les fichiers de résultats. Le rapport technique est consolidé ; les cinq actions sont suivies dans [FINALISATION.md](FINALISATION.md), avec les preuves et limites de [reproduction](REPRODUCTION.md). Les diapositives, le format académique demandé et la vidéo de 15–20 minutes sont des livrables distincts. L’existence d’une application locale ne prouve pas un déploiement public.
