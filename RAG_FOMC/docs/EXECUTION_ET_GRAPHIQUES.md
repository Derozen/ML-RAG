# Exécuter la comparaison et voir les graphiques

Le corpus, les index et les 200 questions validées sont déjà préparés sur ce poste. Ne pas relancer l’extraction, le découpage ou l’indexation pour simplement reproduire la comparaison : changer les chunks invaliderait les liens de preuve.

## 1. Ouvrir le terminal PowerShell de VS Code

Menu **Terminal → Nouveau terminal**, puis :

```powershell
cd C:\Users\LENOVO\Desktop\VS_Codex\RAG_FOMC
$env:HF_HUB_OFFLINE = "1"
```

Les commandes emploient directement le Python du projet : aucune activation du venv n’est nécessaire. Le modèle est déjà disponible dans le cache local. Le chargement initial peut prendre plusieurs minutes sur ce poste, même sans téléchargement.

## 2. Vérifier le code (facultatif avant chaque reproduction)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

Attendre la fin et le message `OK`. Ces tests contrôlent le pipeline et les annotations ; ils ne remplacent pas la comparaison réelle.

## 3. Exécuter le développement, puis le test

```powershell
.\.venv\Scripts\python.exe run.py compare --split dev --output results/mon_execution/dev
```

Attendre la fin, puis :

```powershell
.\.venv\Scripts\python.exe run.py compare --split test --output results/mon_execution/test
```

Chaque commande exécute BM25, Dense E5 et Hybride RRF sur le même index, avec trois répétitions. Les paramètres sont ceux figés dans les métadonnées de l’index. Aucun ajustement ne doit être fait en fonction des scores du test.

Si un dossier contient déjà des résultats, utiliser un nouveau nom, par exemple `results/mon_execution_02/dev` et `results/mon_execution_02/test`. Le refus d’écrasement préserve les expériences précédentes. Exécuter les deux lots l’un après l’autre et limiter les autres calculs si les latences doivent être étudiées.

## 4. Produire les graphiques de cette exécution

```powershell
.\.venv\Scripts\python.exe scripts/plot_comparison.py --results results/mon_execution/dev
.\.venv\Scripts\python.exe scripts/plot_comparison.py --results results/mon_execution/test
```

Matplotlib est déjà installé sur ce poste. Pour un nouvel environnement, la dépendance optionnelle s’installe via `python -m pip install -e ".[plots]"` avec le Python de cet environnement et une connexion disponible. Il n’est pas nécessaire de réinstaller quoi que ce soit pour cette exécution.

Le script lit les sorties enregistrées, vérifie l’empreinte du fichier de questions et ne recharge pas E5. Il peut être relancé pour actualiser les mêmes figures. Si une autre version de questions a servi au benchmark, préciser `--questions CHEMIN_DU_FICHIER_ORIGINAL`.

## 5. Ouvrir les résultats

Dans l’explorateur de fichiers VS Code, ouvrir `results/mon_execution/test/plots/` :

- `01_scores_globaux.png` : rappel, MRR et proportion de questions dont toutes les preuves sont retrouvées à k=20.
- `02_preuves_par_type.png` : résultats pour les factuelles, reformulations, explicatives et comparatives.
- `03_scores_selon_k.png` : rappel et preuves complètes à k=1,5,10,20.

Les fichiers SVG correspondants permettent un export vectoriel pour le mémoire. Les chiffres des courbes sont aussi exportés dans `scores_selon_k.csv`.

Dans `results/mon_execution/test/`, consulter également :

- `summary.csv` : moyennes par méthode et par type.
- `metrics_per_question.csv` : résultats individuels.
- `rankings.csv` ou `rankings.jsonl` : passages effectivement récupérés ; le JSONL contient le texte.
- `paired_comparisons.csv` : intervalles exploratoires des différences entre méthodes.
- `unanswerable_review.jsonl` : candidats des questions sans réponse.
- `run.json` : configuration, versions et empreintes permettant la reproduction.

Les figures montrent la récupération de preuves annotées, pas la qualité de réponses produites par un LLM. Les questions sans réponse sont exclues des scores de pertinence ; leur abstention n’est pas implémentée. Les moyennes des graphiques donnent le même poids à chaque question : voir aussi l’analyse par famille dans le rapport initial. Les intervalles de différences sont dans le CSV apparié et ne sont pas représentés comme des barres d’erreur des moyennes.

## Voir immédiatement les résultats déjà calculés

Les résultats existants sont dans `results/comparison_200_v1/`. Les figures peuvent être générées sans refaire le benchmark :

```powershell
.\.venv\Scripts\python.exe scripts/plot_comparison.py --results results/comparison_200_v1/test
```

Le fichier `scripts/report_comparison_200.py` concerne spécifiquement cette expérience initiale ; il ne résume pas automatiquement un dossier `mon_execution`. Utiliser le script de figures ci-dessus pour toute nouvelle exécution.
