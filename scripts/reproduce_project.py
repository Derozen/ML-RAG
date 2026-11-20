"""Rebuild corpus/indexes in an isolated copy, then evaluate and test Streamlit.

Defaults to the selected interpreter. Reusing an installed interpreter and local
model files is recorded explicitly and never claimed as a clean dependency install.
"""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from common import digest, model_dir, write_json
from protocol import verify
from acquire_corpus import acquire


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--python',type=Path,default=Path(sys.executable))
    p.add_argument('--workdir',type=Path,default=ROOT/'tmp/reproduction_rebuild')
    p.add_argument('--resume',action='store_true',help='Retry the existing isolated copy, archiving prior evidence first')
    a=p.parse_args()
    target=a.workdir.resolve()
    if target==ROOT or ROOT in target.parents and 'tmp' not in target.relative_to(ROOT).parts:
        raise ValueError('Use a new isolated directory under tmp or outside the project.')
    if target.exists() and not a.resume: raise ValueError('Destination already exists; use a new path or explicit --resume.')
    if a.resume and (not (target/'src/common.py').exists() or digest(target/'src/common.py')!=digest(ROOT/'src/common.py')):
        raise ValueError('Resume requires the same frozen source in the isolated destination.')
    verify()
    target.mkdir(parents=True,exist_ok=a.resume)
    out=ROOT/'results/reproduction'
    out.mkdir(parents=True,exist_ok=True)
    if a.resume:
        history=out/'attempts'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        history.mkdir(parents=True,exist_ok=False)
        for path in out.iterdir():
            if path.is_file() and path.name!='clean_environment.json': shutil.copy2(path,history/path.name)
    report=dict(started_utc=datetime.now(timezone.utc).isoformat(),workdir=str(target),
        interpreter=str(a.python.resolve()),clean_dependency_install=False,
        local_pretrained_weights_reused=True,steps=[],status='running')
    def save(): write_json(out/'run.json',report)
    save()
    def command(label,args):
        log=out/(label+'.log')
        started=time.monotonic()
        with log.open('w',encoding='utf-8') as f:
            process=subprocess.run([str(a.python.resolve()),'-X','utf8',*args],cwd=target,
                stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'HF_HUB_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1'},
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        entry=dict(name=label,exit_code=process.returncode,seconds=time.monotonic()-started,log=log.relative_to(ROOT).as_posix())
        report['steps'].append(entry);save()
        if process.returncode: raise RuntimeError(f'{label} failed; see {log}')
        print('PASS '+label,flush=True)
    try:
        for directory in ('src','app','tests','scripts','annotation_tools'):
            shutil.copytree(ROOT/directory,target/directory,dirs_exist_ok=a.resume,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        for name in ('requirements.txt','run.py'): shutil.copy2(ROOT/name,target/name)
        for directory in ('data/evaluation','protocol'):
            shutil.copytree(ROOT/directory,target/directory,dirs_exist_ok=a.resume)
        for kind in ('dense','colbert','cross_encoder'):
            source=model_dir(kind)
            # Private files, copied rather than linked, to protect the frozen source.
            destination=target/source.relative_to(ROOT)
            if not destination.exists(): shutil.copytree(source,destination)
        # The frozen index builder expects this directory on a fresh checkout.
        (target/'indexes/dense').mkdir(parents=True,exist_ok=True)
        (target/'indexes/bm25').mkdir(parents=True,exist_ok=True)
        records=acquire(ROOT/'data/corpus_manifest.json',target/'data/raw',ROOT/'data/raw')
        report['local_acquisition']=dict(documents=len(records),hashes_verified=True,network_download=False)
        save()
        # Rebuild extraction, reference alignment and both indexes; no frozen index is copied.
        command('rebuild_corpus_indexes',['run.py','--to-step','build_indexes'])
        comparisons={}
        for name in ('data/processed/chunks.jsonl','data/processed/paragraphs.jsonl','indexes/bm25/tokens.jsonl','indexes/dense/chunk_ids.json'):
            comparisons[name]=digest(ROOT/name)==digest(target/name)
        import numpy as np
        actual=np.load(target/'indexes/dense/vectors.npy',allow_pickle=False)
        frozen=np.load(ROOT/'indexes/dense/vectors.npy',allow_pickle=False)
        comparisons['dense_vectors_numerically_equal']=bool(np.allclose(actual,frozen,rtol=0,atol=1e-6))
        report['rebuilt_comparisons']=comparisons;save()
        if not all(comparisons.values()): raise RuntimeError('Rebuilt artifacts differ from frozen artifacts')
        # Fixed rankings are reused only for metric reproduction, never called a fresh model benchmark.
        for directory in ('results/retrieval','results/reranking'):
            shutil.copytree(ROOT/directory,target/directory,dirs_exist_ok=a.resume)
        command('recompute_evaluation',['src/evaluate.py'])
        for budget in (5,6):
            name=f'results/context_top{budget}/comparison.csv'
            if digest(ROOT/name)!=digest(target/name): raise RuntimeError(f'Summary differs: {name}')
        command('unit_tests',['-m','unittest','discover','-s','tests','-q'])
        command('streamlit_real_checks',['scripts/verify_delivery.py'])
        for path in (target/'results/delivery_verification').iterdir():
            if path.is_file(): shutil.copy2(path,out/('isolated_'+path.name))
        report['status']='passed_with_reused_dependencies'
        report['fresh_retrieval_reranking_benchmark']=False
        report['streamlit_evidence']='results/reproduction/isolated_streamlit_functional.json'
    except Exception as exc:
        report['status']='failed';report['error']=f'{type(exc).__name__}: {exc}'
        raise
    finally:
        report['finished_utc']=datetime.now(timezone.utc).isoformat();save()
        verify()


if __name__=='__main__': main()
