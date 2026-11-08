"""Configuration et formats traçables, indépendants des modèles."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    corpus_version: str = "fomc-2020-2025-v1"
    model_name: str = "intfloat/e5-small-v2"
    model_revision: str = "main"
    passage_prefix: str = "passage: "
    query_prefix: str = "query: "
    device: str = "cpu"
    cpu_threads: int = 2
    chunk_tokens: int = 400
    overlap_tokens: int = 60
    max_model_tokens: int = 512
    batch_size: int = 32
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    rrf_constant: int = 60
    top_k: int = 20
    repetitions: int = 3
    seed: int = 42
    html_selector: str = "#article"
    pdf_drop_lines: tuple = ()

    def __post_init__(self):
        for name in ("chunk_tokens", "max_model_tokens", "batch_size", "top_k", "repetitions", "cpu_threads"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(f"{name} doit être un entier positif")
        if not 0 <= self.overlap_tokens < self.chunk_tokens:
            raise ValueError("Le chevauchement doit être inférieur à la fenêtre")
        if self.chunk_tokens >= self.max_model_tokens:
            raise ValueError("Réserver des tokens pour préfixe, métadonnées et tokens spéciaux")
        if not math.isfinite(self.bm25_k1) or self.bm25_k1 <= 0 or not 0 <= self.bm25_b <= 1:
            raise ValueError("Paramètres BM25 invalides")
        if self.rrf_constant <= 0:
            raise ValueError("Constante RRF invalide")

    @classmethod
    def load(cls, path):
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self):
        return asdict(self)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_json(path, obj):
    atomic_text(path, json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def read_jsonl(path):
    rows = []
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if line.strip():
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError("Objet JSON attendu")
                rows.append(row)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return rows


def write_jsonl(path, rows):
    atomic_text(path, "".join(json.dumps(x, ensure_ascii=False, allow_nan=False) + "\n" for x in rows))


def write_csv(path, rows, fields):
    import io
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    atomic_text(path, stream.getvalue())


def unique(rows, key):
    values = [r[key] for r in rows]
    if any(not isinstance(v, str) or not v.strip() for v in values) or len(set(values)) != len(values):
        raise ValueError(f"Identifiants {key} absents ou dupliqués")
