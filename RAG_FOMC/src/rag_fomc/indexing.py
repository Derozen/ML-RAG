"""Index exact NumPy et corpus BM25 partageant un ordre canonique."""
from __future__ import annotations

import importlib.metadata
import json
import platform
import time
from pathlib import Path

import numpy as np

from .common import read_jsonl, sha256, unique, write_json, write_jsonl
from .encoding import Encoder
from .preprocessing import lexical_tokens

ARTIFACTS = ("vectors.npy", "chunk_ids.json", "bm25_tokens.jsonl")


def build_index(root, config):
    root = Path(root)
    chunks_path = root / "data/processed/chunks.jsonl"
    metadata = json.loads((root / "data/processed/chunking.json").read_text(encoding="utf-8"))
    if sha256(chunks_path) != metadata["chunks_sha256"]:
        raise ValueError("Passages modifiés depuis le découpage")
    if metadata["config"] != json.loads(json.dumps(config.to_dict())):
        raise ValueError("Configuration modifiée : relancer chunk avant index")
    if sha256(root / "data/processed/paragraphs.jsonl") != metadata["paragraphs_sha256"]:
        raise ValueError("Paragraphes modifiés : relancer chunk")
    chunks = sorted(read_jsonl(chunks_path), key=lambda c: c["chunk_id"])
    if not chunks:
        raise ValueError("Impossible d'indexer un corpus vide")
    unique(chunks, "chunk_id")
    start = time.perf_counter()
    encoder = Encoder(config, metadata["resolved_model_revision"])
    vectors = encoder.encode([c["search_text"] for c in chunks], config.passage_prefix)
    tokens = [{"chunk_id": c["chunk_id"], "tokens": lexical_tokens(c["search_text"])} for c in chunks]
    if any(not row["tokens"] for row in tokens):
        raise ValueError("Un passage ne possède aucun token BM25")
    index_dir = root / "indexes"
    index_dir.mkdir(parents=True, exist_ok=True)
    # Métadonnées écrites en dernier : un arrêt partiel sera détecté au chargement.
    with (index_dir / "vectors.npy.tmp").open("wb") as stream:
        np.save(stream, vectors, allow_pickle=False)
    (index_dir / "vectors.npy.tmp").replace(index_dir / "vectors.npy")
    write_json(index_dir / "chunk_ids.json", [c["chunk_id"] for c in chunks])
    write_jsonl(index_dir / "bm25_tokens.jsonl", tokens)
    versions = {name: importlib.metadata.version(name) for name in (
        "numpy", "sentence-transformers", "transformers", "torch", "rank-bm25", "beautifulsoup4", "pymupdf")}
    write_json(index_dir / "metadata.json", {
        "schema_version": 1, "config": config.to_dict(), "model_revision": metadata["resolved_model_revision"],
        "paragraphs_sha256": metadata["paragraphs_sha256"],
        "chunks_sha256": sha256(chunks_path), "chunking_sha256": sha256(root / "data/processed/chunking.json"),
        "lexical_tokenizer": "unicode-financial-v1-no-stopwords", "shape": list(vectors.shape),
        "dtype": str(vectors.dtype), "artifact_sha256": {f: sha256(index_dir / f) for f in ARTIFACTS},
        "build_seconds_including_model_load": time.perf_counter() - start,
        "python": platform.python_version(), "platform": platform.platform(), "versions": versions})


def load_index(root):
    root = Path(root)
    index_dir = root / "indexes"
    metadata = json.loads((index_dir / "metadata.json").read_text(encoding="utf-8"))
    if metadata["schema_version"] != 1:
        raise ValueError("Version d'index non reconnue")
    if sha256(root / "data/processed/chunks.jsonl") != metadata["chunks_sha256"]:
        raise ValueError("Index périmé : passages modifiés")
    if sha256(root / "data/processed/chunking.json") != metadata["chunking_sha256"]:
        raise ValueError("Index périmé : découpage modifié")
    if sha256(root / "data/processed/paragraphs.jsonl") != metadata["paragraphs_sha256"]:
        raise ValueError("Index périmé : paragraphes réextraits ; relancer chunk et index")
    for name in ARTIFACTS:
        if sha256(index_dir / name) != metadata["artifact_sha256"][name]:
            raise ValueError(f"Index corrompu ou incomplet : {name}")
    ids = json.loads((index_dir / "chunk_ids.json").read_text(encoding="utf-8"))
    chunks = sorted(read_jsonl(root / "data/processed/chunks.jsonl"), key=lambda c: c["chunk_id"])
    unique(chunks, "chunk_id")
    tokens = read_jsonl(index_dir / "bm25_tokens.jsonl")
    vectors = np.load(index_dir / "vectors.npy", allow_pickle=False)
    if ids != [c["chunk_id"] for c in chunks] or ids != [r["chunk_id"] for r in tokens]:
        raise ValueError("Correspondance ID/texte/tokens invalide")
    if vectors.ndim != 2 or vectors.shape[0] != len(ids) or list(vectors.shape) != metadata["shape"]:
        raise ValueError("Dimensions de l'index incohérentes")
    if vectors.dtype != np.float32 or not np.isfinite(vectors).all():
        raise ValueError("Vecteurs invalides")
    if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
        raise ValueError("Vecteurs non normalisés")
    return metadata, chunks, vectors, [r["tokens"] for r in tokens]
