"""Lanceur depuis la racine, utilisable avant installation du paquet."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from rag_fomc.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
