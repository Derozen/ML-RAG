
"""Validation des références silver au niveau des pages PDF FOMC.

Ne transforme pas les jugements de pages en jugements de chunks.
Vérifie la provenance réelle des chunks et conserve tous les qrels.
"""

from collections import Counter
import math
import re

from common import (
    ROOT,
    questions,
    read_json,
    read_jsonl,
    write_json,
    write_jsonl,
    write_csv,
    digest,
    log,
)


# ============================================================
# 1. LECTURE ET VALIDATION DES QRELS
# ============================================================

def parse_page_qrels(text, question_ids, manifest):
    """Lit les qrels TREC et valide les références aux PDF."""

    documents = {d["filename"]: d for d in manifest}

    if len(documents) != len(manifest):
        raise ValueError("Noms de documents dupliqués")

    judgments = {}

    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue

        fields = line.split()

        if len(fields) != 4:
            raise ValueError(
                f"Qrels ligne {line_number}: quatre champs attendus"
            )

        qid, iteration, page_id, raw_grade = fields

        match = re.fullmatch(
            r"(.+\.pdf)#p([1-9][0-9]*)",
            page_id,
        )

        if qid not in question_ids or not match:
            raise ValueError(
                f"Question ou page inconnue ligne {line_number}"
            )

        if iteration != "0":
            raise ValueError(
                f"Champ iteration invalide ligne {line_number}"
            )

        filename = match.group(1)
        page = int(match.group(2))

        if filename not in documents:
            raise ValueError(
                f"Document absent du corpus : {filename}"
            )

        if page > documents[filename]["pages"]:
            raise ValueError(
                f"Page inexistante : {page_id}"
            )

        try:
            grade = int(raw_grade)
        except ValueError as exc:
            raise ValueError(
                f"Grade invalide ligne {line_number}"
            ) from exc

        if grade not in (0, 1, 2):
            raise ValueError(
                f"Grade hors échelle 0/1/2 : {grade}"
            )

        key = (qid, page_id)

        if key in judgments:
            raise ValueError(
                f"Jugement dupliqué : {key}"
            )

        judgments[key] = grade

    covered = {
        qid
        for (qid, _), grade in judgments.items()
        if grade > 0
    }

    if covered != set(question_ids):
        raise ValueError(
            "Certaines questions n'ont aucune page "
            "pertinente annotée"
        )

    return judgments


# ============================================================
# 2. VALIDATION DES CONTRIBUTIONS PAR PAGE
# ============================================================

def validate_page_contributions(chunk, paragraphs_lookup):
    """Valide les contributions de pages d'un chunk."""

    chunk_id = chunk["chunk_id"]

    contributions = chunk.get("page_contributions")

    if not contributions:
        raise ValueError(
            f"Contributions absentes : {chunk_id}"
        )

    pages = chunk.get("pages", [])

    if not pages:
        raise ValueError(
            f"Pages absentes : {chunk_id}"
        )

    if pages != sorted(set(pages)):
        raise ValueError(
            f"Pages non uniques ou non triées : {chunk_id}"
        )

    contribution_pages = [
        entry["page"]
        for entry in contributions
    ]

    if contribution_pages != pages:
        raise ValueError(
            f"Pages/contributions incohérentes : {chunk_id}"
        )

    total_characters = sum(
        entry["characters"]
        for entry in contributions
    )

    if total_characters <= 0:
        raise ValueError(
            f"Chunk sans caractères attribués : {chunk_id}"
        )

    for entry in contributions:
        characters = entry["characters"]
        ratio = entry["ratio"]

        if characters <= 0:
            raise ValueError(
                f"Contribution vide : {chunk_id}"
            )

        expected_ratio = characters / total_characters

        if not math.isclose(
            ratio,
            expected_ratio,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise ValueError(
                f"Ratio incohérent : {chunk_id}"
            )

    paragraph_ids = chunk["paragraph_ids"]

    if not paragraph_ids:
        raise ValueError(
            f"Chunk sans paragraphe : {chunk_id}"
        )

    if len(paragraph_ids) != len(set(paragraph_ids)):
        raise ValueError(
            f"Paragraphes dupliqués : {chunk_id}"
        )

    actual_pages = set()

    paragraph_counts = chunk.get(
        "paragraph_characters", {}
    )

    if set(paragraph_counts) != set(paragraph_ids):
        raise ValueError(
            f"Contributions des paragraphes incohérentes : "
            f"{chunk_id}"
        )

    page_totals = Counter()

    for paragraph_id in paragraph_ids:
        if paragraph_id not in paragraphs_lookup:
            raise ValueError(
                f"Paragraphe introuvable : {paragraph_id}"
            )

        paragraph = paragraphs_lookup[paragraph_id]

        if paragraph["filename"] != chunk["filename"]:
            raise ValueError(
                f"Document incohérent : {chunk_id}"
            )

        if paragraph["doc_id"] != chunk["doc_id"]:
            raise ValueError(
                f"Identifiant document incohérent : {chunk_id}"
            )

        if paragraph["section_id"] != chunk["section_id"]:
            raise ValueError(
                f"Section incohérente : {chunk_id}"
            )

        count = paragraph_counts[paragraph_id]

        if not isinstance(count, int) or count <= 0:
            raise ValueError(
                f"Contribution de paragraphe invalide : {chunk_id}"
            )

        actual_pages.add(paragraph["page"])
        page_totals[paragraph["page"]] += count

    if actual_pages != set(pages):
        raise ValueError(
            f"Pages réelles différentes des pages déclarées : "
            f"{chunk_id}"
        )

    declared_totals = {
        entry["page"]: entry["characters"]
        for entry in contributions
    }

    if dict(page_totals) != declared_totals:
        raise ValueError(
            f"Sommes par page incohérentes : {chunk_id}"
        )

    if chunk["page_start"] != min(pages):
        raise ValueError(
            f"Page de début incorrecte : {chunk_id}"
        )

    if chunk["page_end"] != max(pages):
        raise ValueError(
            f"Page de fin incorrecte : {chunk_id}"
        )

    if chunk.get("multipage") != (len(pages) > 1):
        raise ValueError(
            f"Indicateur multipage incorrect : {chunk_id}"
        )

    return contributions


# ============================================================
# 3. ASSOCIATION CHUNKS VERS PAGES
# ============================================================

def make_chunk_pages(chunks, paragraphs):
    """Construit le mapping des chunks vers leurs pages PDF.

    Toutes les pages ayant une contribution positive sont
    conservées. Aucun seuil de pertinence n'est appliqué.
    """

    lookup = {
        p["paragraph_id"]: p
        for p in paragraphs
    }

    if len(lookup) != len(paragraphs):
        raise ValueError(
            "Identifiants de paragraphes dupliqués"
        )

    result = {}

    for chunk in chunks:
        chunk_id = chunk["chunk_id"]

        if chunk_id in result:
            raise ValueError(
                f"Identifiant de chunk dupliqué : {chunk_id}"
            )

        validate_page_contributions(
            chunk,
            lookup,
        )

        result[chunk_id] = [
            f"{chunk['filename']}#p{page}"
            for page in chunk["pages"]
        ]

    return result


# ============================================================
# 4. PROJECTION DES CLASSEMENTS SUR LES PAGES
# ============================================================

def project_pages(chunk_ids, mapping):
    """Projette un classement de chunks sur les pages uniques.

    Les pages suivent l'ordre des chunks récupérés.
    Au sein d'un chunk, elles suivent l'ordre physique.

    Les doublons de pages sont supprimés.
    """

    seen = set()
    pages = []

    for chunk_id in chunk_ids:
        if chunk_id not in mapping:
            raise ValueError(
                f"Chunk absent du mapping : {chunk_id}"
            )

        for page_id in mapping[chunk_id]:
            if page_id not in seen:
                seen.add(page_id)
                pages.append(page_id)

    return pages


# ============================================================
# 5. AUDIT DU CORPUS ET DES QRELS
# ============================================================

def main():

    base = ROOT / "data/evaluation"

    queries = questions()

    manifest = read_json(
        ROOT / "data/processed/manifest.json"
    )

    chunks = read_jsonl(
        ROOT / "data/processed/chunks.jsonl"
    )

    paragraphs = read_jsonl(
        ROOT / "data/processed/paragraphs.jsonl"
    )

    # Contrôle des sources originales.
    for document in manifest:
        source = ROOT / document["path"]

        if not source.exists():
            raise FileNotFoundError(
                f"PDF introuvable : {source}"
            )

        if digest(source) != document["sha256"]:
            raise ValueError(
                f"PDF modifié depuis le découpage : "
                f"{document['filename']}"
            )

    # Lecture sans modification des qrels silver.
    qrels_path = base / "silver_qrels_PAGES.trec"

    judgments = parse_page_qrels(
        qrels_path.read_text(encoding="utf-8-sig"),
        {q["id"] for q in queries},
        manifest,
    )

    # Vérification de provenance de tous les chunks.
    mapping = make_chunk_pages(
        chunks,
        paragraphs,
    )

    available_pages = {
        page_id
        for page_ids in mapping.values()
        for page_id in page_ids
    }

    relevant_pages = {
        page_id
        for (_, page_id), grade in judgments.items()
        if grade > 0
    }

    missing_pages = sorted(
        relevant_pages - available_pages
    )

    if missing_pages:
        raise ValueError(
            "Pages annotées absentes de l'index : "
            f"{missing_pages}"
        )

    # Statistiques de provenance.
    multipage_chunks = [
        c for c in chunks
        if c["multipage"]
    ]

    minority_chunks = [
        c for c in multipage_chunks
        if min(
            entry["ratio"]
            for entry in c["page_contributions"]
        ) < 0.05
    ]

    # Contrôle des pages du corpus.
    documents = {
        d["filename"]: d
        for d in manifest
    }

    for page_id in available_pages:
        filename, page_number = page_id.rsplit("#p", 1)

        if filename not in documents:
            raise ValueError(
                f"Document inconnu dans le mapping : {filename}"
            )

        page_number = int(page_number)

        if not (
            1 <= page_number <= documents[filename]["pages"]
        ):
            raise ValueError(
                f"Page invalide dans le mapping : {page_id}"
            )

    # ========================================================
    # 6. EXPORT DES RÉFÉRENCES
    # ========================================================

    write_csv(
        base / "page_qrels.tsv",
        [
            {
                "question_id": qid,
                "page_id": page_id,
                "relevance": grade,
            }
            for (qid, page_id), grade
            in sorted(judgments.items())
        ],
        delimiter="\t",
    )

    # Format conservé pour evaluate.py.
    write_jsonl(
        base / "chunk_pages.jsonl",
        [
            {
                "chunk_id": chunk_id,
                "page_ids": page_ids,
            }
            for chunk_id, page_ids
            in sorted(mapping.items())
        ],
    )

    # ========================================================
    # 7. RAPPORT D'AUDIT
    # ========================================================

    report = {
        "questions": len(queries),
        "judgments": len(judgments),

        "judged_pages": len({
            page for _, page in judgments
        }),

        "judged_documents": len({
            page.split("#p")[0]
            for _, page in judgments
        }),

        "grade_counts": dict(
            Counter(judgments.values())
        ),

        "corpus_documents": len(manifest),
        "corpus_paragraphs": len(paragraphs),
        "corpus_chunks": len(mapping),

        "indexed_pages": len(available_pages),

        "multipage_chunks": len(multipage_chunks),

        "multipage_with_minor_page_under_5_percent": (
            len(minority_chunks)
        ),

        "missing_relevant_pages": missing_pages,

        "source_pdfs_sha256_verified": True,

        "questions_sha256": digest(
            base / "queries_145.jsonl"
        ),

        "source_qrels_sha256": digest(
            qrels_path
        ),

        "page_qrels_sha256": digest(
            base / "page_qrels.tsv"
        ),

        "mapping_sha256": digest(
            base / "chunk_pages.jsonl"
        ),

        "chunks_sha256": digest(
            ROOT / "data/processed/chunks.jsonl"
        ),

        "paragraphs_sha256": digest(
            ROOT / "data/processed/paragraphs.jsonl"
        ),

        "status": (
            "Silver page judgments preserved. "
            "Page existence and chunk provenance verified. "
            "Semantic relevance not manually re-annotated."
        ),

        "evaluation_unit": "unique PDF page",

        "mapping_policy": (
            "All pages with positive character contribution "
            "are retained. No relevance inferred for chunks."
        ),

        "split_policy": (
            "All questions evaluated together; "
            "original split labels remain metadata."
        ),
    }

    write_json(
        base / "alignment_report.json",
        report,
    )

    log(
        f"Qrels validés : {len(queries)} questions, "
        f"{len(judgments)} jugements"
    )

    log(
        f"Corpus : {len(mapping)} chunks, "
        f"{len(available_pages)} pages indexées"
    )

    log(
        f"Chunks multipages : {len(multipage_chunks)}"
    )

    log(
        "Chunks avec une contribution de page "
        f"inférieure à 5 % : {len(minority_chunks)}"
    )

    log(
        "Alignement validé : aucun jugement "
        "de chunk inventé"
    )


if __name__ == "__main__":
    main()
