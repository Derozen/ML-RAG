"""E5 : résolution de révision, préfixes explicites et contrôle de longueur."""
from __future__ import annotations

import random
import re


def resolved_revision(config):
    if re.fullmatch(r"[a-fA-F0-9]{40}", config.model_revision):
        return config.model_revision
    from huggingface_hub import model_info
    return model_info(config.model_name, revision=config.model_revision).sha


def load_tokenizer(config, revision):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(config.model_name, revision=revision, use_fast=True)


class Encoder:
    def __init__(self, config, revision):
        import numpy as np
        import torch
        from sentence_transformers import SentenceTransformer
        random.seed(config.seed)
        np.random.seed(config.seed)
        torch.manual_seed(config.seed)
        if config.device == "cpu":
            torch.set_num_threads(config.cpu_threads)
        self.model = SentenceTransformer(config.model_name, revision=revision, device=config.device)
        self.config = config
        self.tokenizer = self.model.tokenizer
        self.limit = min(config.max_model_tokens, self.model.max_seq_length,
                         self.tokenizer.model_max_length)

    def encode(self, texts, prefix):
        import numpy as np
        inputs = [prefix + t for t in texts]
        for i, text in enumerate(inputs):
            if len(self.tokenizer.encode(text, add_special_tokens=True, truncation=False)) > self.limit:
                raise ValueError(f"Entrée {i} trop longue : troncature silencieuse interdite")
        vectors = np.asarray(self.model.encode(inputs, batch_size=self.config.batch_size,
                             normalize_embeddings=True, convert_to_numpy=True,
                             show_progress_bar=len(inputs) > 1), dtype=np.float32)
        if vectors.ndim != 2 or not np.isfinite(vectors).all():
            raise ValueError("Matrice de vecteurs invalide")
        if not np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4):
            raise ValueError("Vecteurs non normalisés")
        return vectors
