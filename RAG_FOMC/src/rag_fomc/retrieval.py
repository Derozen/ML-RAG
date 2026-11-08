"""BM25, cosinus exact et RRF ; aucune génération ni reranking appris."""
from __future__ import annotations

from collections import defaultdict
import time

import numpy as np

from .common import Config
from .encoding import Encoder
from .indexing import load_index
from .preprocessing import lexical_tokens

METHODS = ("bm25", "dense", "hybrid_rrf")


def stable_top(scores, k):
    if k <= 0:
        raise ValueError("k doit être positif")
    scores = np.asarray(scores)
    if scores.ndim != 1 or not np.isfinite(scores).all():
        raise ValueError("Scores invalides")
    # Les positions correspondent aux IDs triés dans l'index.
    return [(int(i), float(scores[i])) for i in np.argsort(-scores, kind="stable")[:k]]


def reciprocal_rank_fusion(rankings, constant, k):
    if constant <= 0 or k <= 0:
        raise ValueError("Paramètres RRF invalides")
    scores = defaultdict(float)
    for ranking in rankings:
        seen = set()
        for rank, (index, _) in enumerate(ranking, 1):
            if index in seen:
                raise ValueError("Doublon dans une branche RRF")
            seen.add(index)
            scores[index] += 1.0 / (constant + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:k]


class Retriever:
    def __init__(self, root):
        from rank_bm25 import BM25Okapi
        self.metadata, self.chunks, self.vectors, self.tokens = load_index(root)
        self.config = Config(**self.metadata["config"])
        self.bm25 = BM25Okapi(self.tokens, k1=self.config.bm25_k1, b=self.config.bm25_b)
        self.vocabulary = {t for row in self.tokens for t in row}
        self.encoder = Encoder(self.config, self.metadata["model_revision"])

    def _bm25(self, question, k):
        tokens = lexical_tokens(question)
        scores = np.asarray(self.bm25.get_scores(tokens))
        diagnostics = {"no_lexical_match": not bool(set(tokens) & self.vocabulary),
                       "lexical_scores_all_equal": bool(np.all(scores == scores[0]))}
        return stable_top(scores, k), diagnostics

    def _dense(self, question, k):
        query = self.encoder.encode([question], self.config.query_prefix)[0]
        if query.shape[0] != self.vectors.shape[1]:
            raise ValueError("Dimension question/index incompatible")
        return stable_top(self.vectors @ query, k)

    def search(self, question, method, k=None):
        start = time.perf_counter()
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question vide")
        k = self.config.top_k if k is None else k
        if type(k) is not int or k <= 0:
            raise ValueError("k doit être un entier positif")
        k = min(k, len(self.chunks))
        diagnostics = {}
        if method == "bm25":
            ranking, diagnostics = self._bm25(question, k)
        elif method == "dense":
            ranking = self._dense(question, k)
        elif method == "hybrid_rrf":
            lexical, diagnostics = self._bm25(question, k)
            dense = self._dense(question, k)
            ranking = reciprocal_rank_fusion([lexical, dense], self.config.rrf_constant, k)
        else:
            raise ValueError(f"Méthode inconnue : {method}")
        results = [{**self.chunks[i], "method": method, "rank": rank, "score": score}
                   for rank, (i, score) in enumerate(ranking, 1)]
        return results, time.perf_counter() - start, diagnostics
