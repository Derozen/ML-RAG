"""Freeze/verify the experimental pipeline before preparing or scoring new questions."""
import argparse
from datetime import datetime, timezone
import json
import urllib.request
from common import ROOT, CONFIG, CONTEXT_K, RERANKERS, model_dir, digest, environment, read_json, write_json

LOCK = ROOT/'protocol/frozen_pipeline_20261120.json'


def code_files():
    return sorted([*ROOT.glob('src/*.py'),*ROOT.glob('app/*.py'),ROOT/'run.py',ROOT/'requirements.txt'])


def ollama_models():
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=3) as response:
            return {m['name']:m['digest'] for m in json.load(response)['models']}
    except (OSError, ValueError):
        return {}


def freeze():
    if LOCK.exists():
        raise ValueError('Le protocole est déjà figé. Vérifier la version au lieu de la réécrire.')
    paths=code_files()+[ROOT/p for p in (
        'data/evaluation/queries_145.jsonl','data/evaluation/silver_qrels_PAGES.trec',
        'data/processed/chunks.jsonl','data/processed/paragraphs.jsonl',
        'indexes/dense/vectors.npy','indexes/dense/chunk_ids.json','indexes/bm25/tokens.jsonl')]
    for kind in ('dense','colbert','cross_encoder'):
        paths += [p for p in model_dir(kind).rglob('*') if p.is_file() and p.suffix in ('.json','.safetensors','.txt') and 'download_parts' not in p.parts]
    write_json(LOCK,dict(created_utc=datetime.now(timezone.utc).isoformat(),
        historical_evaluation='145 exploratory questions; dev subset for detailed diagnostics; no existing split is independent.',
        selected_system=dict(mode='classic',retrieval='hybrid_rrf',reranker='colbert',candidates=CONFIG['top_k'],context_k=CONTEXT_K),
        config=CONFIG,environment=environment(),ollama_digests=ollama_models(),
        files={str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in paths},
        code_paths=[str(p.relative_to(ROOT)).replace('\\','/') for p in code_files()],
        new_test_policy='Prepare and validate new questions after this lock; do not score until annotations are approved. Any subsequent tuning invalidates use of that set as a fresh confirmatory test.'))
    print('Protocole figé:',LOCK)


def verify():
    lock=read_json(LOCK)
    if set(lock['code_paths'])!={str(p.relative_to(ROOT)).replace('\\','/') for p in code_files()}:
        raise ValueError('La liste des fichiers de code a changé depuis le gel')
    changed=[name for name,sha in lock['files'].items() if not (ROOT/name).exists() or digest(ROOT/name)!=sha]
    if changed:
        raise ValueError(f'Gel invalidé par des modifications: {changed}')
    live=ollama_models()
    if live and lock['ollama_digests'].get('qwen2.5:3b')!=live.get('qwen2.5:3b'):
        raise ValueError('Le modèle Ollama a changé depuis le gel')
    print('Gel vérifié: code, paramètres, données historiques, index et poids identiques.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('freeze','verify'))
    args=parser.parse_args()
    freeze() if args.action=='freeze' else verify()
