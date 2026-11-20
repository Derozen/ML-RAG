
"""Audit heuristique généraliste des affirmations FOMC (2021-2026).

Vérifications :
- Concordance des sections avec le plan de génération
- Validité des identifiants des sources
- Cohérence temporelle
- Correspondance des fourchettes de taux
- Indices de décisions monétaires
- Indices économiques
- Avertissements institutionnels

Aucun appel à un modèle externe.

IMPORTANT :
Les contrôles sont heuristiques. Ils ne prouvent pas
l'implication sémantique des passages cités.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


# ============================================================
# 1. CONFIGURATION
# ============================================================

DECISION_TERMS = (
    "target range",
    "federal funds",
    "committee decided",
    "decided to raise",
    "decided to lower",
    "decided to maintain",
    "policy action",
    "monetary policy",
)

ECONOMIC_TERMS = (
    "inflation",
    "price stability",
    "labor market",
    "employment",
    "demand",
    "supply",
    "economic activity",
    "economic outlook",
)

RANGE_RE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)"
    r"\s*(?:to|through|[-–—])\s*"
    r"(\d+(?:\.\d+)?)\s*(?:percent|%)",
    flags=re.IGNORECASE,
)


# ============================================================
# 2. NORMALISATION DES TEXTES
# ============================================================

def normalize(value: str) -> str:
    """Normalise les textes et les fractions de taux."""

    text = str(value)

    fractions = (
        ("¼", 0.25),
        ("½", 0.50),
        ("¾", 0.75),
    )

    for symbol, amount in fractions:
        text = re.sub(
            rf"(\d+)\s*{re.escape(symbol)}",
            lambda match, amount=amount: str(
                int(match.group(1)) + amount
            ),
            text,
        )

        text = text.replace(
            symbol,
            str(amount),
        )

    # Gérer les fractions transformées en forme Unicode.
    text = unicodedata.normalize("NFKC", text)

    fraction_patterns = (
        (r"1\s*[⁄/]\s*4", 0.25),
        (r"1\s*[⁄/]\s*2", 0.50),
        (r"3\s*[⁄/]\s*4", 0.75),
    )

    for pattern, amount in fraction_patterns:

        text = re.sub(
            rf"(?<!\d)(\d+)\s*{pattern}",
            lambda match, amount=amount: str(
                int(match.group(1)) + amount
            ),
            text,
        )

        text = re.sub(
            rf"(?<![\d.]){pattern}",
            str(amount),
            text,
        )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip().lower()


# ============================================================
# 3. EXTRACTION DES FOURCHETTES DE TAUX
# ============================================================

def ranges(
    text: str,
) -> list[tuple[float, float]]:
    """Extrait les fourchettes de taux présentes dans le texte."""

    normalized = normalize(text)

    values = []

    for match in RANGE_RE.finditer(normalized):

        rate_range = (
            round(float(match.group(1)), 3),
            round(float(match.group(2)), 3),
        )

        if rate_range not in values:
            values.append(rate_range)

    return values


def same_range(
    first: tuple,
    second: tuple,
    tolerance: float = 0.011,
) -> bool:
    """Compare deux fourchettes avec une petite tolérance."""

    return (
        len(first) == 2
        and len(second) == 2
        and all(
            abs(a - b) <= tolerance
            for a, b in zip(first, second)
        )
    )


# ============================================================
# 4. METADONNEES TEMPORELLES
# ============================================================

def date_of(passage: dict) -> str:
    """Retourne la date de réunion enregistrée."""

    value = passage.get("meeting_end")

    if value is None:
        return ""

    if hasattr(value, "isoformat"):
        value = value.isoformat()

    return str(value).strip()


def belongs_to_period(
    passage: dict,
    period: str,
) -> bool:
    """Vérifie une année YYYY ou un mois YYYY-MM."""

    return date_of(passage).startswith(str(period))


# ============================================================
# 5. CONSTRUCTION DU PLAN
# ============================================================

def resolve_plan(
    structured: dict,
    periods: list[str],
    question: str = "",
    plan: dict | None = None,
) -> dict:
    """Reconstruit le plan correspondant à la génération.

    La question doit être celle qui a réellement été
    transmise à generate_with_coverage().
    """

    if plan is None:
        from coverage_guard import build_sections

        plan = build_sections(
            periods,
            question,
        )

    if not isinstance(plan, dict):
        raise ValueError(
            "Le plan de génération doit être un dictionnaire."
        )

    sections = structured.get("sections", {})

    expected_keys = set(plan)
    generated_keys = set(sections)

    if expected_keys != generated_keys:
        missing = sorted(
            expected_keys - generated_keys
        )

        unexpected = sorted(
            generated_keys - expected_keys
        )

        raise ValueError(
            "Le plan de l'audit ne correspond pas "
            "à celui de la génération.\n"
            f"Sections manquantes : {missing}\n"
            f"Sections inattendues : {unexpected}\n"
            "Transmets la question originale ou le plan "
            "utilisé pendant la génération."
        )

    return plan


# ============================================================
# 6. AUDIT DES PREUVES
# ============================================================

def audit_evidence(
    structured: dict,
    passages: list[dict],
    periods: list[str] | None = None,
    plan: dict | None = None,
    question: str = "",
) -> dict:
    """Audite les affirmations et leurs passages cités.

    Validation structurelle, temporelle et lexicale.
    Ne réalise pas de vérification NLI.
    """

    if (
        not isinstance(structured, dict)
        or not isinstance(
            structured.get("sections"),
            dict,
        )
    ):
        raise ValueError(
            "Le JSON doit contenir un objet 'sections'."
        )

    periods = periods or []

    source_map = {}

    for passage in passages:

        source_id = passage.get("rank")

        if (
            type(source_id) is not int
            or source_id in source_map
        ):
            raise ValueError(
                "Identifiants de passages "
                "invalides ou dupliqués."
            )

        source_map[source_id] = passage

    plan = resolve_plan(
        structured=structured,
        periods=periods,
        question=question,
        plan=plan,
    )

    details = {}

    for key, spec in plan.items():

        item = structured["sections"].get(
            key,
            {},
        )

        if not isinstance(item, dict):
            item = {}

        raw_claim = item.get("claim", "")

        claim = (
            raw_claim
            if isinstance(raw_claim, str)
            else ""
        )

        raw_ids = item.get(
            "source_ids",
            [],
        )

        ids = []
        errors = []
        warnings = []

        # ----------------------------------------------------
        # Vérification des identifiants
        # ----------------------------------------------------

        if not isinstance(raw_ids, list):
            errors.append(
                "source_ids invalide."
            )
            raw_ids = []

        for source_id in raw_ids:

            if (
                type(source_id) is not int
                or source_id not in source_map
            ):
                errors.append(
                    f"Source inconnue : {source_id!r}"
                )

            elif source_id not in ids:
                ids.append(source_id)

        if not claim.strip():
            errors.append(
                "Affirmation absente."
            )

        if not ids:
            errors.append(
                "Aucune source citée."
            )

        # ----------------------------------------------------
        # Vérification des périodes
        # ----------------------------------------------------

        required_periods = spec.get(
            "periods",
            [],
        )

        for period in required_periods:

            if not any(
                belongs_to_period(
                    source_map[source_id],
                    period,
                )
                for source_id in ids
            ):
                errors.append(
                    f"Période sans citation : {period}"
                )

        if len(required_periods) == 1:

            expected_period = required_periods[0]

            for source_id in ids:

                if not belongs_to_period(
                    source_map[source_id],
                    expected_period,
                ):
                    errors.append(
                        f"SOURCE {source_id} hors période "
                        f"{expected_period}."
                    )

        # ----------------------------------------------------
        # Vérification des fourchettes chiffrées
        # ----------------------------------------------------

        claim_ranges = ranges(claim)

        source_ranges = {}

        for source_id in ids:

            passage_text = source_map[
                source_id
            ].get("text", "")

            source_ranges[source_id] = ranges(
                passage_text
            )

        for claimed_range in claim_ranges:

            supported_by = [
                source_id
                for source_id, detected in source_ranges.items()
                if any(
                    same_range(
                        claimed_range,
                        source_range,
                    )
                    for source_range in detected
                )
            ]

            if not supported_by:
                errors.append(
                    "Fourchette non retrouvée dans les "
                    f"sources citées : {claimed_range}"
                )

        # Attention : une même fourchette chiffrée ne
        # prouve pas à elle seule une décision monétaire.
        # On distingue la valeur du contexte institutionnel.

        # ----------------------------------------------------
        # Indices de décision monétaire
        # ----------------------------------------------------

        lower_claim = normalize(claim)

        decision_claim = any(
            term in lower_claim
            for term in DECISION_TERMS
        )

        if decision_claim:

            decision_sources = [
                source_id
                for source_id in ids
                if any(
                    term in normalize(
                        source_map[source_id].get(
                            "text",
                            "",
                        )
                    )
                    for term in DECISION_TERMS
                )
            ]

            if not decision_sources:
                warnings.append(
                    "Décision monétaire non détectée "
                    "explicitement dans les sources."
                )

        # ----------------------------------------------------
        # Indices économiques
        # ----------------------------------------------------

        economic_claim = any(
            term in lower_claim
            for term in ECONOMIC_TERMS
        )

        if economic_claim:

            economic_sources = [
                source_id
                for source_id in ids
                if any(
                    term in normalize(
                        source_map[source_id].get(
                            "text",
                            "",
                        )
                    )
                    for term in ECONOMIC_TERMS
                )
            ]

            if not economic_sources:
                warnings.append(
                    "Arguments économiques non "
                    "retrouvés lexicalement."
                )

            warnings.append(
                "Les justifications économiques "
                "nécessitent une revue sémantique."
            )

        # ----------------------------------------------------
        # Contrôle des affirmations d'unanimité
        # ----------------------------------------------------

        if (
            "unanimous" in lower_claim
            or "unanimously" in lower_claim
        ):

            warnings.append(
                "Distinguer l'unanimité du Board "
                "of Governors du vote du FOMC."
            )

            # Vérifier uniquement les passages cités.
            dissent_detected = any(
                "voting against this action"
                in normalize(
                    source_map[source_id].get(
                        "text",
                        "",
                    )
                )
                for source_id in ids
            )

            if dissent_detected:
                warnings.append(
                    "Une dissidence figure dans "
                    "les sources citées."
                )

        # ----------------------------------------------------
        # Résultat de la section
        # ----------------------------------------------------

        details[key] = {
            "claim": claim,
            "source_ids": ids,
            "required_periods": required_periods,
            "claimed_ranges": claim_ranges,
            "source_ranges": {
                str(source_id): detected
                for source_id, detected
                in source_ranges.items()
            },
            "issues": list(
                dict.fromkeys(errors)
            ),
            "warnings": list(
                dict.fromkeys(warnings)
            ),
            "heuristic_checks_pass": not errors,
            "semantic_support_verified": False,
            "requires_human_review": True,
        }

    return {
        "sections": details,
        "total_sections": len(details),
        "sections_without_blocking_issues": sum(
            not section["issues"]
            for section in details.values()
        ),
        "sections_with_warnings": sum(
            bool(section["warnings"])
            for section in details.values()
        ),
        "semantic_support_verified": False,
        "conclusion": (
            "Audit structurel et heuristique uniquement. "
            "La fidélité sémantique des affirmations "
            "n'a pas été vérifiée."
        ),
    }


# ============================================================
# 7. EXECUTION DEPUIS LE TERMINAL
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--result",
        default="results/coverage/latest_result.json",
    )

    parser.add_argument(
        "--output",
        default="results/evidence_audit.json",
    )

    args = parser.parse_args()

    result_path = Path(args.result)

    result = json.loads(
        result_path.read_text(
            encoding="utf-8"
        )
    )

    report = audit_evidence(
        structured=result["structured_answer"],
        passages=result["passages"],
        periods=result.get("periods", []),
        question=result.get("question", ""),
        plan=result.get("plan"),
    )

    output_path = Path(args.output)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n" + "=" * 60)
    print("AUDIT DES PREUVES FOMC")
    print("=" * 60)

    for key, section in report["sections"].items():

        status = (
            "CONTROLES HEURISTIQUES OK"
            if not section["issues"]
            else "A VERIFIER"
        )

        print(
            f"\nSECTION : {key} — {status}"
        )

        print(
            "Sources :",
            section["source_ids"],
        )

        print(
            "Périodes requises :",
            section["required_periods"],
        )

        for issue in section["issues"]:
            print(
                "ERREUR :",
                issue,
            )

        for warning in section["warnings"]:
            print(
                "ATTENTION :",
                warning,
            )

    print("\n" + "=" * 60)

    print(
        "Sections sans erreur heuristique :",
        report["sections_without_blocking_issues"],
        "/",
        report["total_sections"],
    )

    print(
        "Sections avec avertissements :",
        report["sections_with_warnings"],
    )

    print(
        "Validation sémantique : NON EFFECTUÉE"
    )

    print(
        "Rapport enregistré :",
        output_path.resolve(),
    )


if __name__ == "__main__":
    main()
