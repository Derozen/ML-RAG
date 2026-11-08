# Contrats de données

Tous les JSON/JSONL sont en UTF-8. Les dates suivent `YYYY-MM-DD`. Les numéros de pages PDF commencent à 1 ; une page HTML inconnue est `null`, jamais une page inventée. Les identifiants de passages ne sont valables qu’avec leur version de découpage et son empreinte.

## Manifeste CSV

| Champ | Convention |
|---|---|
| `doc_id` | `FOMC_` suivi de la date de fin de réunion |
| `meeting_start`, `meeting_end` | Dates ISO de réunion, distinctes de la publication |
| `related_dates` | Dates additionnelles séparées par `;` pour un document commun |
| `published_at` | Date ISO de publication, vide si non établie |
| `html_url`, `pdf_url` | URL officielle HTTPS ; fournir celle du format exploité |
| `local_path` | Chemin relatif dans `data/raw/` |
| `sha256` | Empreinte attendue optionnelle au premier inventaire |
| `status` | `obtained`, `missing`, `review`, `duplicate` |

Ne pas créer une ligne HTML et une ligne PDF à indexer pour le même compte rendu. Conserver la variante de vérification dans `data/raw/` et son URL dans la même ligne. Les fichiers physiques supplémentaires ne sont pas indexés automatiquement. Les lignes `missing`, `review` et `duplicate` restent visibles dans les comptes de statuts mais ne contribuent pas aux passages.

## Paragraphes

`paragraph_id, doc_id, meeting_end, section_id, section, position, page, source_url, text, source_sha256, needs_table_review`.

`position` suit l’ordre d’extraction. `section_id` distingue deux sections portant le même titre. Le texte est nettoyé de façon conservatrice ; l’original reste dans `data/raw/`. Les titres HTML structurent les paragraphes ; les tableaux sont conservés sous forme textuelle et marqués pour revue.

## Passages

`chunk_id, doc_id, meeting_end, section, section_id, paragraph_ids, page_start, page_end, source_url, text, search_text, token_count, model_token_count, section_char_start, section_char_end, section_token_start, section_token_end`.

`text` est une sous-chaîne du texte de section, conservant sa casse et sa ponctuation ; il n’est pas reconstruit à partir des tokens. `search_text` ajoute les métadonnées communes aux trois méthodes. Les offsets de section sont semi-ouverts : début inclus, fin exclue. Les paragraphes concernés sont listés même si le passage n’en utilise qu’une partie. `token_count` mesure le corps, `model_token_count` mesure l’entrée complète avec préfixe E5 et tokens spéciaux.

Les frontières de phrases sont préférées quand elles laissent une progression suffisante. Les très longues phrases sont découpées en fenêtres de tokens. Le dernier passage est conservé. Un titre de section trop long pour réserver le chevauchement provoque une erreur explicite ; il faut alors réviser les métadonnées ou les paramètres.

## Questions annotées

Exemple **structurel fictif**, à ne pas copier comme annotation officielle :

```json
{
  "qid": "Q001",
  "family_id": "decision_comparison_001",
  "question": "A verified English comparison question goes here.",
  "type": "comparative",
  "split": "dev",
  "answerable": true,
  "reference_answer": "Answer verified against both original documents.",
  "validated": true,
  "evidence": [
    {"evidence_id": "meeting_A", "doc_id": "FOMC_2024-09-18", "section": "Decision", "page": null,
     "quote": "EXACT VERIFIED QUOTE A", "chunk_ids": ["FOMC_2024-09-18_C0001"]},
    {"evidence_id": "meeting_B", "doc_id": "FOMC_2024-11-07", "section": "Decision", "page": null,
     "quote": "EXACT VERIFIED QUOTE B", "chunk_ids": ["FOMC_2024-11-07_C0001"]}
  ],
  "absence_reason": null
}
```

Chaque objet doit être compacté sur une seule ligne dans le fichier JSONL. Les types conseillés sont `factual`, `explanatory`, `comparative`, `unanswerable`. `split` accepte uniquement `dev` ou `test`. `family_id` doit être identique pour toutes les reformulations d’une même question. La revue humaine demeure indispensable : les validations automatiques de structure et de citation ne prouvent pas que la preuve implique réellement la réponse.

Un groupe peut ajouter `quotes_by_chunk`, dictionnaire `{ "ID_DU_PASSAGE": "Citation exacte de cette variante" }`, lorsque des passages équivalents emploient des formulations différentes. Les IDs sans variante utilisent `quote`. Chaque citation est contrôlée dans le passage correspondant ; un groupe reste un élément de preuve, quel que soit le nombre de variantes. Une question de type `comparative` doit avoir au moins deux groupes.

Pour une question sans réponse, utiliser `answerable: false`, `evidence: []`, une `absence_reason` vérifiée sur le corpus retenu, et `validated: true` après revue. Elle est exclue des dénominateurs de rappel/MRR et figure dans le rapport séparé.

## Index et intégrité

`vectors.npy` est une matrice `N × D`, normalisée, en float32. La ligne `i` correspond à `chunk_ids.json[i]` et à la ligne `i` de `bm25_tokens.jsonl`. Les IDs sont triés. Le nombre `N` est le nombre de passages, pas celui des rapports.

`metadata.json` enregistre les paramètres, la révision résolue du modèle, les empreintes des passages, du découpage et de chaque artefact, les versions des bibliothèques et le temps de construction. Les fichiers ne sont jamais chargés via pickle. Un changement de contenu, d’ordre ou un artefact incomplet est refusé au rechargement.

## Classements

Le CSV de transfert contient exactement :

```text
qid,method,rank,chunk_id,doc_id,meeting_end,section,score,source_url
```

Les méthodes sont `bm25`, `dense`, `hybrid_rrf`. Les rangs commencent à 1. Les scores des méthodes ont des échelles différentes et ne sont pas comparables directement. Le JSONL complémentaire conserve notamment `text` et `paragraph_ids` pour la vérification des citations et l’étape future de reranking.
