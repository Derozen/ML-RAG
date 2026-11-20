# Reproduction : protocole et preuves

## Ce qui a réellement été exécuté

État de la reconstruction isolée : **passed_with_reused_dependencies**.
Les 93 PDF exacts sont importés depuis une source locale avec contrôle SHA-256.
L’extraction, l’alignement des références et les index sont reconstruits dans
un dossier distinct. L’interpréteur et les poids préentraînés du poste sont
réutilisés : il ne s’agit pas d’une installation vierge de dépendances.

| Étape exécutée | Résultat | Durée observée |
|---|---|---:|
| rebuild_corpus_indexes | Réussi | 343.6 s |
| recompute_evaluation | Réussi | 3.8 s |
| unit_tests | Réussi | 3.3 s |
| streamlit_real_checks | Réussi | 46.9 s |

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

La reconstruction et les essais de la copie isolée ont réussi avec les dépendances et poids déjà installés.
Le point « environnement propre » reste **partiellement vérifié**. Il doit être
complété sur un poste disposant d’un accès aux paquets et aux modèles, sans modifier
les résultats de référence pour masquer un écart.
