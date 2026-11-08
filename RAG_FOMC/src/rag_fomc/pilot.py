"""Pré-annotations liées aux passages réels, à faire relire avant toute évaluation."""
from copy import deepcopy
import json
from pathlib import Path

from .common import read_jsonl, sha256, write_json, write_jsonl


def prepare_pilot(root):
    root = Path(root)
    source = root / "evaluation/pilot_seed.json"
    seeds = json.loads(source.read_text(encoding="utf-8"))
    chunks_path = root / "data/processed/chunks.jsonl"
    chunks = read_jsonl(chunks_path)
    questions = []
    for seed in seeds:
        q = deepcopy(seed)
        q.update(validated=False, annotation_status="draft_pending_independent_review")
        for proof in q["evidence"]:
            matches = [c for c in chunks if c["doc_id"] == proof["doc_id"] and proof["quote"] in c["text"]
                       and (proof.get("page") is None or (c.get("page_start") is not None and
                            c["page_start"] <= proof["page"] <= c["page_end"]))]
            if not matches:
                raise ValueError(f"{q['qid']}/{proof['evidence_id']}: citation introuvable dans le découpage")
            proof["chunk_ids"] = [c["chunk_id"] for c in matches]
            proof["section"] = matches[0]["section"]
            proof["source_url"] = matches[0]["source_url"]
        questions.append(q)
    # Le fichier de questions validées n'est jamais modifié par cette commande.
    write_jsonl(root / "evaluation/pilot_draft.jsonl", questions)
    write_json(root / "evaluation/pilot_draft.metadata.json", {
        "chunks_sha256": sha256(chunks_path), "seed_sha256": sha256(source), "questions": len(questions),
        "status": "draft_pending_independent_review", "reviewers": [],
        "warning": "Références préparées à partir des PDF ; contrôle de citations automatique, seconde revue humaine requise."})
    return questions
