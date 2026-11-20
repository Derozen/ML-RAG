# Comparaison des contextes finaux de 5 passages

Chaque méthode retient 5 chunks parmi les mêmes 20 candidats. Les annotations portent sur les pages ; la couverture ne prouve pas la présence de la réponse dans le chunk.

| Recherche | Reranker | Couverture pages du contexte | nDCG pages @6 | Toutes les pages attendues |
|---|---|---:|---:|---:|
| bm25 | none | 0.341 | 0.251 | 0.241 |
| bm25 | bm25 | 0.341 | 0.251 | 0.241 |
| bm25 | colbert | 0.485 | 0.396 | 0.372 |
| bm25 | cross_encoder | 0.431 | 0.325 | 0.310 |
| dense | none | 0.370 | 0.270 | 0.255 |
| dense | bm25 | 0.394 | 0.293 | 0.276 |
| dense | colbert | 0.474 | 0.381 | 0.345 |
| dense | cross_encoder | 0.440 | 0.345 | 0.331 |
| hybrid_rrf | none | 0.430 | 0.299 | 0.324 |
| hybrid_rrf | bm25 | 0.341 | 0.251 | 0.241 |
| hybrid_rrf | colbert | 0.502 | 0.401 | 0.372 |
| hybrid_rrf | cross_encoder | 0.439 | 0.340 | 0.331 |

Les scores décrivent les annotations silver fournies. Les passages non jugés ne sont pas nécessairement non pertinents. Les anciens temps de reclassement concernent le calcul des 20 candidats ; sélectionner 6 passages ne supprime pas ce coût.
