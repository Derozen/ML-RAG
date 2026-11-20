# Références scientifiques et techniques

Métadonnées et liens vérifiés le 20 novembre 2026. Ces publications expliquent les
principes ; les détails des checkpoints et de l’adaptateur effectivement utilisés
restent définis par le code et le verrou du projet. Les scores publiés par les
auteurs ne sont pas des résultats de notre corpus FOMC.

| Méthode | Source primaire | Rôle dans le rapport |
|---|---|---|
| BM25 | Robertson, S. et Zaragoza, H. (2009). [The Probabilistic Relevance Framework: BM25 and Beyond](https://doi.org/10.1561/1500000019). Foundations and Trends in Information Retrieval, 4(1–2), 1–174. | Fondements de la recherche probabiliste et du classement lexical. |
| E5 | Wang, L. et al. (2022 ; version révisée 2024). [Text Embeddings by Weakly-Supervised Contrastive Pre-training](https://arxiv.org/abs/2212.03533). | Famille d’embeddings E5 et préentraînement contrastif. |
| RRF | Cormack, G. V., Clarke, C. L. A. et Büttcher, S. (2009). [Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods](https://cormack.uwaterloo.ca/cormack/cormacksigir09-rrf.pdf). SIGIR. | Fusion des classements par réciproques des rangs. |
| ColBERT | Khattab, O. et Zaharia, M. (2020). [ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT](https://arxiv.org/abs/2004.12832). | Encodage séparé et interaction tardive fine entre tokens. |
| Reranking BERT | Nogueira, R. et Cho, K. (2019 ; version révisée 2020). [Passage Re-ranking with BERT](https://arxiv.org/abs/1901.04085). | Principe du reclassement neuronal des paires question/passage ; pas une identification du checkpoint MiniLM à BERT original. |

Pour reproduire exactement l’expérience, consulter
[le verrou des modèles et paramètres](../protocol/frozen_pipeline_20261120.json)
et [la méthodologie de l’implémentation](METHODOLOGIE.md). Les versions des modèles
E5, AnswerAI ColBERT et MiniLM du projet ne sont pas interchangeables avec les
modèles de tous les articles cités.

Les sources documentaires FOMC sont listées avec URL et empreinte dans
`data/processed/manifest.json`. Les questions et jugements silver fournis par
l’utilisateur ne sont pas assimilés à une collection officielle de référence
validée par la Federal Reserve.
