"""Configuration figée, fichiers et normalisation partagés par les six étapes."""
from pathlib import Path
import csv
import hashlib
import json
import os
import re
import time
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('HF_HOME', str(ROOT / '.cache/huggingface'))
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
CONFIG = {
    'corpus': '93-fomc-minutes-statements-2021-2026', 'questions': 145,
    'chunk_tokens': 400, 'overlap_tokens': 60, 'max_model_tokens': 512,
    'top_k': 20, 'rrf_constant': 60, 'bm25_k1': 1.5, 'bm25_b': .75,
    'batch_size': 8, 'cpu_threads': 2, 'seed': 42,
    'dense_model': 'intfloat/e5-small-v2',
    'dense_revision': 'ffb93f3bd4047442299a41ebb6fa998a38507c52',
    'colbert_model': 'answerdotai/answerai-colbert-small-v1',
    'colbert_revision': '934fa8bb4ce2284f4c2baa232d81aca4d076fa5e',
    'cross_encoder_model': 'cross-encoder/ms-marco-MiniLM-L6-v2',
    'cross_encoder_revision': '233902d25c440f23af6f7d6e94d2946bac0bee0a',
    'colbert_query_length': 64, 'colbert_document_length': 512,
    'cross_encoder_max_length': 512,
}
METHODS = ('bm25', 'dense', 'hybrid_rrf')
RERANKERS = ('bm25', 'colbert', 'cross_encoder')

# Separate serving budget: changing it does not invalidate document indexes/scores.
CONTEXT_K = 6

def select_context(ranking, context_k=CONTEXT_K):
    """Keep the best 1..6 already-ranked chunks, preserving provenance and scores."""
    if isinstance(context_k, bool) or not isinstance(context_k, int) or not 1 <= context_k <= CONTEXT_K:
        raise ValueError('Le contexte final doit contenir entre 1 et 6 passages (6 par défaut)')
    ids = [row['chunk_id'] for row in ranking]
    if len(ids) != len(set(ids)):
        raise ValueError('Passages dupliqués dans le classement')
    if [row['rank'] for row in ranking] != list(range(1, len(ranking)+1)):
        raise ValueError('Le classement doit être trié par rang avant sélection')
    return [dict(row) for row in ranking[:context_k]]

def log(message):
    print(time.strftime('%H:%M:%S') + ' | ' + str(message), flush=True)

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def write_json(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    tmp.replace(path)

def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def read_jsonl(path):
    return [json.loads(s) for s in Path(path).read_text(encoding='utf-8-sig').splitlines() if s.strip()]

def write_jsonl(path, rows):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        for r in rows: f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    tmp.replace(path)

def write_csv(path, rows, fields=None, delimiter=','):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fields=fields or list(rows[0])
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=delimiter,extrasaction='ignore')
        w.writeheader(); w.writerows(rows)

def normalize_text(text):
    return re.sub(r'\s+',' ',unicodedata.normalize('NFC',text).replace('\u00a0',' ')).strip()

def lexical_tokens(text):
    return re.findall(r"\d+(?:[.,]\d+)*(?:/\d+)?%?|[^\W\d_]+(?:['’][^\W\d_]+)*|[¼½¾⅛⅜⅝⅞]",text.lower(),re.UNICODE)

def questions():
    rows=read_jsonl(ROOT/'data/evaluation/queries_145.jsonl')
    if len(rows)!=CONFIG['questions'] or len({q['question_id'] for q in rows})!=len(rows):
        raise ValueError('145 identifiants uniques requis')
    if any(not q['question'].strip() for q in rows): raise ValueError('Question vide')
    # Keep labels in the original file; only ID and question enter retrieval/reranking.
    return [dict(id=q['question_id'],question=q['question']) for q in rows]

def model_dir(kind):
    if kind=='dense':
        return ROOT/'.cache/huggingface/hub/models--intfloat--e5-small-v2/snapshots'/CONFIG['dense_revision']
    return ROOT/'.cache/models'/CONFIG[kind+'_model'].replace('/','--')/CONFIG[kind+'_revision']

class E5Tokenizer:
    """Même tokenizer WordPiece JSON que HF, utilisable sans charger Torch."""
    model_max_length=512
    def __init__(self):
        from tokenizers import Tokenizer
        self.tokenizer=Tokenizer.from_file(str(model_dir('dense')/'tokenizer.json'))
        self.tokenizer.no_truncation(); self.tokenizer.no_padding()
    def encode(self,text,add_special_tokens=True,**kwargs):
        return self.tokenizer.encode(text,add_special_tokens=add_special_tokens).ids
    def __call__(self,text,add_special_tokens=False,**kwargs):
        encoded=self.tokenizer.encode(text,add_special_tokens=add_special_tokens)
        return {'input_ids':encoded.ids,'offset_mapping':encoded.offsets}

def prepare_torch():
    import torch
    import numpy as np
    import random
    torch.set_num_threads(CONFIG['cpu_threads'])
    torch.manual_seed(CONFIG['seed']); np.random.seed(CONFIG['seed']); random.seed(CONFIG['seed'])
    return torch

def environment():
    import importlib.metadata,platform
    versions={}
    for name in ['numpy','torch','transformers','sentence-transformers','rank-bm25','pymupdf','safetensors']:
        try: versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name]=None
    return {'python':platform.python_version(),'platform':platform.platform(),'versions':versions}

def stable_order(scores, ids):
    import numpy as np
    values=np.asarray(scores)
    if values.ndim!=1 or not np.isfinite(values).all(): raise ValueError('Scores invalides')
    return sorted(range(len(ids)),key=lambda i:(-float(values[i]),ids[i]))
