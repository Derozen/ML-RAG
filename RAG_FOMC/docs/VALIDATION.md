# Validation technique — 5 novembre 2026

**Après intégration du ZIP : 34 tests exécutés, 34 réussis, aucun test ignoré.** L’aide de l’interface en ligne de commande a été vérifiée. Le lot initial de 25 tests est complété par les régressions de l’import et de la mise en page.

## Contrôles sur les données fournies

- Import de 93 PDF avec SHA256 ; sélection de 40 Minutes, huit par année de 2021 à 2025.
- Confirmation des dates à partir des titres ou premières pages, y compris les réunions à cheval sur deux mois.
- Extraction de 563 pages en 6 080 paragraphes.
- Audit de conservation des multiensembles de tokens sur chaque page, après retrait des en-têtes : aucune perte ou duplication détectée.
- Aucun caractère Unicode de remplacement détecté.
- Inspection visuelle de pages à deux colonnes de janvier 2021 et à une colonne de septembre 2024.
- Inspection visuelle de pages de décisions de janvier 2021, septembre 2024 et novembre 2024, dont des fractions de taux et les votes contre.

Les césures de fin de ligne sont conservées lorsqu’une correction certaine n’est pas disponible. La conservation des tokens ne prouve pas, à elle seule, l’exactitude de l’ordre sémantique ou des tableaux. Les extraits automatiques destinés à la revue sont dans `data/processed/review_samples.md`.

Environnement des contrôles : Python 3.12.7, NumPy 1.26.4, BeautifulSoup 4.15.0, rank-bm25 0.2.2, PyMuPDF 1.28.2. Sentence Transformers 5.7.0, Transformers 5.22.1 et PyTorch 2.15.0 sont installés dans l’environnement local. Celui-ci réutilise certains paquets système. Les versions critiques sont conservées dans `requirements-tested.txt` ; les instructions du README permettent une installation isolée.

## Découpage avec le tokenizer E5 réel

Révision utilisée : `ffb93f3bd4047442299a41ebb6fa998a38507c52`.

- 1 454 passages couvrent les 40 documents.
- Taille du contenu : minimum 33, médiane 376, maximum 400 tokens.
- Entrée complète maximale, préfixe et métadonnées compris : 433 tokens pour une limite de 512.
- Les douze citations des dix questions brouillon sont présentes dans les paragraphes des pages indiquées et ont été liées aux passages.

Les fichiers `chunks.jsonl`, `chunking.json`, `pilot_draft.jsonl` et `pilot_draft.metadata.json` conservent les paramètres et liens. Les questions restent à l’état brouillon.

## Vectorisation et récupération sur le corpus réel

Les poids E5 ont été téléchargés et vérifiés contre le SHA256 officiel : `45bfa60070649aae2244fbc9d508537779b93b6f353c17b0f95ceccb1c5116c1` pour 133 466 304 octets. Le transport standard rencontrant des interruptions, le téléchargement de secours par blocs a permis de compléter le fichier avant son activation.

La vectorisation réelle a produit une matrice **1 454 × 384**, en float32. Tous les vecteurs sont finis et normalisés ; l’écart maximal observé de norme à 1 est d’environ **1,19 × 10⁻⁷**. Le rechargement a vérifié les empreintes et la correspondance IDs/textes/tokens/vecteurs.

Un essai de récupération a ensuite été exécuté **hors ligne**, avec le véritable E5, sur dix questions brouillon portant sur trois réunions, en recherchant dans les quarante rapports. Les trois moteurs ont produit **600 lignes de classement** : dix questions × trois méthodes × vingt candidats.

Les contrôles ont vérifié : IDs connus, sources identiques à celles des passages, scores finis et décroissants, rangs 1 à 20, absence de doublons par liste et cohérence numérique de chaque score RRF avec les rangs des deux branches.

Les sorties se trouvent dans `results/pilot_retrieval_v1/`, avec `preview.md` pour inspection et `verification.json` pour le détail des contrôles. Ces résultats sont un essai technique ; aucun Recall, MRR ou classement de supériorité n’a été calculé sur les pré-annotations non validées. Les temps exploratoires ne remplacent pas le benchmark prévu par `compare`.

Les contrôles portent sur :

- Conservation des chiffres, fractions et négations lors du nettoyage.
- Couverture des tokens, chevauchement, conservation du dernier passage et déterminisme du découpage.
- Séparation des documents et sections, offsets et provenance des paragraphes.
- Extraction HTML sans navigation et extraction PDF avec numéro de page ; rejet d’une page vide.
- Tri stable des scores égaux, contrôle des scores invalides, formule et unicité de RRF.
- Recall, MRR, couverture partielle et alternatives de preuves, respect du seuil K.
- Chargement des index, détection de corruption et de paragraphes réextraits.
- Rejet des preuves inconnues, questions non validées et familles réparties entre dev/test.
- Citations différentes pour des passages équivalents et direction des différences bootstrap.
- Benchmark complet, exports et séparation des questions sans réponse, avec BM25 réel et encodeur synthétique.

Les tests créent leurs fixtures dans un dossier temporaire et n’ajoutent aucun faux document au corpus de recherche.

**Limites :** le test unitaire de bout en bout utilise un tokenizer et un encodeur artificiels ; il complète l’essai réel décrit ci-dessus. Les pré-annotations du pilote restent à relire indépendamment. Les scores d’évaluation définitifs attendent des annotations validées et le protocole dev/test. La variante MiniLM est configurable, mais ses poids et sa récupération n’ont pas été exécutés dans cette validation.
