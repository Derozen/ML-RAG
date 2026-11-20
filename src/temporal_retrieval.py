"""Récupération temporelle expérimentale pour les documents FOMC 2021–2026.

BM25 + E5 + RRF, puis ColBERT. Recherche séparée des décisions et des
justifications, avec indices documentaires. Ne modifie pas le benchmark.
Les indices sont heuristiques et ne certifient pas la pertinence factuelle.
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from functools import lru_cache

import numpy as np

from common import CONFIG, lexical_tokens
from rag_pipeline import assets

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
PERIOD_RE = re.compile(r"202[1-6](?:-(?:0[1-9]|1[0-2]))?\Z")


def plain_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value))
    return "".join(c for c in value if not unicodedata.combining(c)).lower()


def detect_periods(question: str, max_periods: int = 6) -> list[str]:
    """Détecte mois/années explicites, et développe les plages d'années.

    Les intervalles entre deux mois n'incluent que leurs extrémités.
    """
    text = plain_text(question)
    found: set[str] = set()
    occupied: list[tuple[int, int]] = []
    formats = [
        (re.compile(r"\b(202[1-6])-(0[1-9]|1[0-2])\b"),
         lambda m: f"{m.group(1)}-{m.group(2)}"),
        (re.compile(rf"\b({MONTH_RE})\s+(202[1-6])\b"),
         lambda m: f"{m.group(2)}-{MONTHS[m.group(1)]:02d}"),
        (re.compile(rf"\b(202[1-6])\s+({MONTH_RE})\b"),
         lambda m: f"{m.group(1)}-{MONTHS[m.group(2)]:02d}"),
    ]
    for pattern, converter in formats:
        for match in pattern.finditer(text):
            if any(match.start() < end and match.end() > start
                   for start, end in occupied):
                continue
            found.add(converter(match))
            occupied.append(match.span())

    # Identifier d'abord les plages de deux années entières.
    range_re = re.compile(
        r"\b(?:between|from|entre|de)?\s*(202[1-6])\s*"
        r"(?:and|to|et|au|a|jusqu'a|-|–)\s*(202[1-6])\b"
    )
    for match in range_re.finditer(text):
        if any(match.start() < end and match.end() > start
               for start, end in occupied):
            continue
        start, stop = int(match.group(1)), int(match.group(2))
        if start <= stop:
            found.update(str(y) for y in range(start, stop + 1))

    for match in re.finditer(r"\b202[1-6]\b", text):
        if not any(match.start() < end and match.end() > start
                   for start, end in occupied):
            found.add(match.group())

    months_years = {p[:4] for p in found if len(p) == 7}
    periods = sorted(p for p in found
                     if not (len(p) == 4 and p in months_years))
    if len(periods) > max_periods:
        raise ValueError(f"{len(periods)} périodes détectées (maximum {max_periods}).")
    return periods


def meeting_date(chunk: dict) -> str:
    value = chunk.get("meeting_end")
    return str(value.isoformat() if hasattr(value, "isoformat") else value or "")


def in_period(chunk: dict, period: str) -> bool:
    return meeting_date(chunk).startswith(period)


INTENTS = {
    "decision": (
        "FOMC statement Committee decided to raise lower maintain "
        "the target range for the federal funds rate percent"
    ),
    "reasons": (
        "FOMC participants inflation price stability labor market "
        "economic conditions rationale for monetary policy decision"
    ),
}


def intent_query(question: str, period: str, intent: str) -> str:
    return f"{period} {question} {INTENTS[intent]}"


def evidence_features(text: str) -> dict:
    t = re.sub(r"\s+", " ", plain_text(text))
    has_rate = "federal funds" in t and "target range" in t
    decision_phrases = (
        "decided to raise", "decided to lower", "decided to maintain",
        "decided to keep", "raise the target range", "lower the target range",
        "maintain the target range", "target range to", "target range at",
    )
    economics = (
        "inflation", "price stability", "labor market", "employment",
        "supply", "demand", "economic activity", "economic outlook",
    )
    return {
        "has_rate_reference": has_rate,
        "has_decision_evidence": has_rate and any(x in t for x in decision_phrases),
        "economic_term_count": sum(x in t for x in economics),
    }


def evidence_bonus(features: dict, intent: str, text: str = "") -> float:
    """Bonus heuristique hors benchmark, dépendant du type de preuve."""
    t = re.sub(r"\s+", " ", plain_text(text))
    if intent == "decision":
        bonus = (4.0 if features["has_decision_evidence"] else
                 1.0 if features["has_rate_reference"] else 0.0)
        if "the committee decided" in t:
            bonus += 2.0
        if "staff review" in t:
            bonus -= 2.0
        return bonus

    bonus = min(features["economic_term_count"], 4) * 0.45
    if "participants" in t:
        bonus += 1.5
    if "the committee" in t:
        bonus += 1.5
    if "policy stance" in t:
        bonus += 1.0
    if "staff economic outlook" in t:
        bonus -= 2.0
    if "staff review" in t:
        bonus -= 1.0
    return bonus


@lru_cache(maxsize=1)
def colbert_model():
    from rerank import ColBERT
    return ColBERT()


def retrieve_candidates_for_period(
    query, period, pool_size, chunks, bm25, vectors, encoder, ids
):
    eligible = [i for i, c in enumerate(chunks) if in_period(c, period)]
    if not eligible:
        return [], {}

    bm = np.asarray(bm25.get_scores(lexical_tokens(query)), dtype=np.float64)
    query_text = "query: " + query
    if len(encoder.tokenizer.encode(query_text, truncation=False)) > CONFIG["max_model_tokens"]:
        raise ValueError("Question trop longue pour E5.")
    embedding = encoder.encode(
        [query_text], normalize_embeddings=True,
        convert_to_numpy=True, show_progress_bar=False
    )[0]
    dense = vectors @ np.asarray(embedding, dtype=np.float32)
    bm_order = sorted(eligible, key=lambda i: (-float(bm[i]), ids[i]))[:pool_size]
    dense_order = sorted(eligible, key=lambda i: (-float(dense[i]), ids[i]))[:pool_size]
    scores = {}
    for ranking in (bm_order, dense_order):
        for rank, i in enumerate(ranking, 1):
            scores[i] = scores.get(i, 0.0) + 1.0 / (CONFIG["rrf_constant"] + rank)
    return sorted(scores, key=lambda i: (-scores[i], ids[i]))[:pool_size], scores


def rank_intent(query, period, intent, pool_size, chunks, bm25, vectors, encoder, ids):
    from rerank import maxsim
    candidates, rrf = retrieve_candidates_for_period(
        query, period, pool_size, chunks, bm25, vectors, encoder, ids
    )
    if not candidates:
        return []
    model = colbert_model()
    qvec = model.encode([query], True)[0]
    dvecs = model.encode([chunks[i]["search_text"] for i in candidates], False)
    rows = []
    for i, dvec in zip(candidates, dvecs):
        features = evidence_features(chunks[i]["text"])
        colbert_score = float(maxsim(qvec, dvec))
        bonus = evidence_bonus(features, intent, text=chunks[i]["text"])
        rows.append({
            "index": i, "intent": intent, "rrf_score": float(rrf[i]),
            "colbert_score": colbert_score, "intent_bonus": bonus,
            "selection_score": colbert_score + bonus,
            "features": features,
        })
    return sorted(rows, key=lambda r: (-r["selection_score"], ids[r["index"]]))


def retrieve_temporal(
    question: str,
    date_queries: list[dict] | None = None,
    per_date: int = 2,
    pool_size: int = 20,
    max_periods: int = 6,
    max_passages: int = 6,
) -> list[dict]:
    """Sélectionne au plus per_date passages/période, sous un budget global.

    Les rangs sont attribués à la fin. Si aucune date n'est mentionnée,
    retourne [] afin que Streamlit puisse utiliser le RAG classique.
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question vide.")
    if not 1 <= per_date <= pool_size <= 100:
        raise ValueError("Paramètres per_date/pool_size invalides.")
    if not 1 <= max_passages <= 6:
        raise ValueError("Le budget final doit être compris entre 1 et 6 passages.")
    if date_queries is None:
        date_queries = [{"period": p, "query": question}
                        for p in detect_periods(question, max_periods)]
    if not date_queries:
        return []

    prepared, seen = [], set()
    for item in date_queries:
        period = str(item.get("period") or item.get("month") or "")
        if not PERIOD_RE.fullmatch(period):
            raise ValueError(f"Période invalide : {period}")
        if period not in seen:
            prepared.append({"period": period, "question": str(item.get("query") or question)})
            seen.add(period)
    if len(prepared) > max_periods:
        raise ValueError("Trop de périodes sélectionnées.")
    if max_passages < len(prepared):
        raise ValueError("Budget inférieur au nombre de périodes.")

    chunks, bm25, vectors, encoder, ids = assets()
    grouped = []
    for item in prepared:
        period, base = item["period"], item["question"]
        rankings = {
            intent: rank_intent(
                intent_query(base, period, intent), period, intent,
                pool_size, chunks, bm25, vectors, encoder, ids
            )
            for intent in ("decision", "reasons")
        }
        chosen, used = [], set()
        for intent in ("decision", "reasons"):
            if len(chosen) >= per_date:
                break
            # Préférer une décision explicite, si disponible dans le pool.
            candidates = rankings[intent]
            if intent == "decision":
                explicit = [r for r in candidates if r["features"]["has_decision_evidence"]]
                if explicit:
                    candidates = explicit
            for row in candidates:
                if row["index"] not in used:
                    chosen.append(row)
                    used.add(row["index"])
                    break
        remaining = sorted(
            rankings["decision"] + rankings["reasons"],
            key=lambda r: (-r["selection_score"], ids[r["index"]])
        )
        for row in remaining:
            if len(chosen) >= per_date:
                break
            if row["index"] not in used:
                chosen.append(row)
                used.add(row["index"])
        grouped.append({"period": period, "rows": chosen})

    # Round-robin : un passage par période, puis un deuxième, etc.
    selected, used_indices = [], set()
    for position in range(per_date):
        for group in grouped:
            if len(selected) >= max_passages:
                break
            if position < len(group["rows"]):
                row = group["rows"][position]
                if row["index"] not in used_indices:
                    selected.append((group["period"], row))
                    used_indices.add(row["index"])
        if len(selected) >= max_passages:
            break

    results = []
    for period, row in selected:
        chunk = chunks[row["index"]]
        start = chunk.get("page_start")
        end = chunk.get("page_end", start)
        pages = chunk.get("pages")
        if pages is None:
            pages = list(range(start, end + 1)) if isinstance(start, int) and isinstance(end, int) else []
        url = str(chunk.get("source_url") or "")
        if url and start:
            url = url.split("#")[0] + f"#page={start}"
        results.append({
            "rank": len(results) + 1,
            "chunk_id": chunk["chunk_id"], "text": chunk["text"],
            "document": chunk["filename"], "meeting_end": chunk.get("meeting_end"),
            "target_period": period,
            "target_month": period if len(period) == 7 else None,
            "evidence_intent": row["intent"],
            "evidence_features": row["features"],
            "pages": pages, "source_url": url,
            "retrieval_score": row["rrf_score"],
            "rerank_score": row["colbert_score"],
            "selection_score": row["selection_score"],
            "retriever": "temporal_intent_rrf", "reranker": "colbert",
        })
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", required=True)
    parser.add_argument("--per-date", type=int, default=2)
    parser.add_argument("--pool-size", type=int, default=20)
    parser.add_argument("--max-passages", type=int, default=6)
    args = parser.parse_args()
    print("PERIODES :", detect_periods(args.question))
    passages = retrieve_temporal(
        args.question, per_date=args.per_date,
        pool_size=args.pool_size, max_passages=args.max_passages,
    )
    print("PASSAGES :", len(passages))
    for p in passages:
        print("\n" + "=" * 60)
        for k in ("rank", "target_period", "evidence_intent", "document", "chunk_id", "evidence_features", "retrieval_score", "rerank_score", "selection_score"):
            print(k.upper(), ":", p.get(k))
        print("EXTRAIT :", p["text"][:1200])
