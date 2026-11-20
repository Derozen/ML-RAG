# Comparaison des contextes finaux de 6 passages

Chaque méthode retient 6 chunks parmi les mêmes 20 candidats. Les annotations portent sur les pages ; la couverture ne prouve pas la présence de la réponse dans le chunk.

| Recherche | Reranker | Couverture pages du contexte | nDCG pages @6 | Toutes les pages attendues |
|---|---|---:|---:|---:|
| bm25 | none | 0.381 | 0.257 | 0.276 |
| bm25 | bm25 | 0.381 | 0.257 | 0.276 |
| bm25 | colbert | 0.501 | 0.397 | 0.393 |
| bm25 | cross_encoder | 0.469 | 0.325 | 0.352 |
| dense | none | 0.388 | 0.270 | 0.269 |
| dense | bm25 | 0.420 | 0.294 | 0.297 |
| dense | colbert | 0.494 | 0.381 | 0.372 |
| dense | cross_encoder | 0.466 | 0.346 | 0.359 |
| hybrid_rrf | none | 0.447 | 0.302 | 0.338 |
| hybrid_rrf | bm25 | 0.381 | 0.257 | 0.276 |
| hybrid_rrf | colbert | 0.527 | 0.401 | 0.400 |
| hybrid_rrf | cross_encoder | 0.483 | 0.340 | 0.379 |

Les scores décrivent les annotations silver fournies. Les passages non jugés ne sont pas nécessairement non pertinents. Les anciens temps de reclassement concernent le calcul des 20 candidats ; sélectionner 6 passages ne supprime pas ce coût.
