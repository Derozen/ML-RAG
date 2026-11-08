"""Interface locale : préparation, recherche et comparaison contrôlée."""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from .common import Config, read_jsonl, write_csv, write_json, write_jsonl


def parser():
    p = argparse.ArgumentParser(description="RAG FOMC — préparation et récupération uniquement")
    p.add_argument("--root", type=Path, default=Path.cwd(), help="Racine du projet")
    p.add_argument("--config", type=Path, default=Path("configs/default.json"))
    commands = p.add_subparsers(dest="command", required=True)
    archive = commands.add_parser("import-archive", help="Importer les rapports et conserver les sources utiles du ZIP")
    archive.add_argument("--archive", type=Path, required=True)
    commands.add_parser("inventory", help="Valider les originaux et le manifeste")
    commands.add_parser("extract", help="Extraire les paragraphes sourcés")
    commands.add_parser("audit", help="Comparer les extractions aux pages PDF et préparer la revue")
    commands.add_parser("chunk", help="Découper avec le tokenizer E5")
    commands.add_parser("index", help="Construire les index dense et lexical")
    commands.add_parser("prepare-pilot", help="Lier les questions pilotes brouillon aux passages réels")
    search = commands.add_parser("retrieve", help="Exporter les candidats des trois stratégies")
    source = search.add_mutually_exclusive_group(required=True)
    source.add_argument("--question")
    source.add_argument("--questions", type=Path)
    search.add_argument("--output", type=Path, default=Path("results/retrieval"))
    benchmark = commands.add_parser("compare", help="Comparer sur des questions annotées et validées")
    benchmark.add_argument("--questions", type=Path, default=Path("evaluation/questions.jsonl"))
    benchmark.add_argument("--split", choices=["dev", "test"], required=True)
    benchmark.add_argument("--output", type=Path, required=True, help="Nouveau dossier pour cette expérience")
    benchmark.add_argument("--repetitions", type=int)
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    for name in ("httpx", "httpx2"):
        logging.getLogger(name).setLevel(logging.WARNING)
    root = args.root.resolve()
    os.environ.setdefault("HF_HOME", str(root / ".cache/huggingface"))
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "30")
    if os.name == "nt":
        # Transport HTTP vérifié sur le poste ; évite le blocage Xet constaté lors de l'intégration.
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    resolve = lambda path: path if path.is_absolute() else root / path
    try:
        if args.command == "prepare-pilot":
            from .pilot import prepare_pilot
            questions = prepare_pilot(root)
            logging.info("%d questions brouillon ; revue indépendante requise", len(questions))
        elif args.command == "import-archive":
            from .archive_import import import_archive
            report = import_archive(resolve(args.archive), root)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif args.command in {"inventory", "extract", "audit", "chunk", "index"}:
            config = Config.load(resolve(args.config))
            if args.command == "inventory":
                from .ingestion import load_manifest
                load_manifest(root)
            elif args.command == "extract":
                from .ingestion import extract
                extract(root, config)
            elif args.command == "audit":
                from .quality import audit_extraction
                report = audit_extraction(root, config)
                print(json.dumps({key: report[key] for key in ("documents", "pages", "paragraphs", "content_conservation_failures")}, indent=2))
            elif args.command == "chunk":
                from .chunking import chunk
                chunk(root, config)
            else:
                from .indexing import build_index
                build_index(root, config)
        else:
            from .retrieval import METHODS, Retriever
            from .evaluation import compare, validate_questions
            output = resolve(args.output)
            if output.exists() and any(output.iterdir()):
                raise ValueError("Le dossier de résultats doit être vide : choisir un nouveau nom d'expérience")
            retriever = Retriever(root)
            if args.command == "compare":
                summary = compare(root, retriever, resolve(args.questions), args.split, output, args.repetitions)
                print(json.dumps([s for s in summary if s["type"] == "ALL"], indent=2, ensure_ascii=False))
            else:
                questions = ([{"qid": "interactive_001", "question": args.question}] if args.question
                             else read_jsonl(resolve(args.questions)))
                validate_questions(questions, retriever.chunks)
                rows, timings = [], []
                for q in questions:
                    for method in METHODS:
                        candidates, seconds, diagnostics = retriever.search(q["question"], method)
                        rows.extend({"qid": q["qid"], **c} for c in candidates)
                        timings.append({"qid": q["qid"], "method": method, "seconds": seconds, **diagnostics})
                write_jsonl(output / "rankings.jsonl", rows)
                write_csv(output / "rankings.csv", rows, ["qid", "method", "rank", "chunk_id", "doc_id",
                          "meeting_end", "section", "score", "source_url"])
                write_json(output / "diagnostics.json", timings)
                write_jsonl(output / "questions.jsonl", questions)
                logging.info("Temps exploratoires : utiliser compare pour un benchmark avec échauffement")
        logging.info("Étape %s terminée", args.command)
        return 0
    except (ValueError, OSError, KeyError, ImportError) as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
