"""Construire les index BM25/E5 et télécharger les checkpoints publics épinglés."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import urllib.request

from common import ROOT,CONFIG,digest,log,model_dir,write_json,write_jsonl,read_json,read_jsonl,lexical_tokens,prepare_torch,environment,E5Tokenizer

def download_models():
    for kind in ('dense','colbert','cross_encoder'):
        name=CONFIG[kind+'_model']; revision=CONFIG[kind+'_revision']; target=model_dir(kind)
        target.mkdir(parents=True,exist_ok=True)
        url=f'https://huggingface.co/api/models/{name}/revision/{revision}?blobs=true'
        with urllib.request.urlopen(url,timeout=90) as response: meta=json.load(response)
        wanted={'config.json','tokenizer.json','tokenizer_config.json','special_tokens_map.json','vocab.txt','onnx_config.json','model.safetensors'}
        if kind=='dense':
            wanted.update({'modules.json','sentence_bert_config.json','1_Pooling/config.json'})
        manifest=[]
        for row in meta['siblings']:
            filename=row['rfilename']
            if filename not in wanted: continue
            dest=target/filename
            dest.parent.mkdir(parents=True,exist_ok=True)
            if filename!='model.safetensors':
                if not dest.exists():
                    with urllib.request.urlopen(f'https://huggingface.co/{name}/resolve/{revision}/{filename}',timeout=90) as response:
                        dest.write_bytes(response.read())
                manifest.append({'file':filename,'sha256':digest(dest),'bytes':dest.stat().st_size}); continue
            expected=row['lfs']['sha256']; size=row['lfs']['size']
            if dest.exists() and dest.stat().st_size==size and digest(dest)==expected:
                manifest.append({'file':filename,'sha256':expected,'bytes':size}); continue
            block_size=2*1024*1024; count=(size+block_size-1)//block_size
            parts=target/'download_parts'; parts.mkdir(exist_ok=True)
            def fetch(index):
                start=index*block_size; end=min(size,(index+1)*block_size)-1; part=parts/f'{index:04}.part'
                if part.exists() and part.stat().st_size==end-start+1: return
                for retry in range(4):
                    try:
                        request=urllib.request.Request(f'https://huggingface.co/{name}/resolve/{revision}/model.safetensors?segment={start}',headers={'Range':f'bytes={start}-{end}'})
                        with urllib.request.urlopen(request,timeout=120) as response:
                            if response.status!=206: raise ValueError('HTTP Range non respecté')
                            data=response.read(end-start+2)
                        if len(data)!=end-start+1: raise ValueError('Bloc incomplet')
                        part.write_bytes(data); return
                    except Exception:
                        if retry==3: raise
                        time.sleep(2*(retry+1))
            log(f'Téléchargement {name} ({size/1e6:.1f} Mo, {count} blocs)')
            with ThreadPoolExecutor(max_workers=4) as pool:
                for i,_ in enumerate(pool.map(fetch,range(count)),1):
                    if i%10==0 or i==count: log(f'{kind}: {i}/{count} blocs')
            temp=target/'weights.tmp'
            with temp.open('wb') as stream:
                for i in range(count): stream.write((parts/f'{i:04}.part').read_bytes())
            if digest(temp)!=expected: raise ValueError(f'Empreinte invalide : {name}')
            temp.replace(dest); manifest.append({'file':filename,'sha256':expected,'bytes':size})
        write_json(target/'verified_files.json',{'model':name,'revision':revision,'files':manifest})
        log(f'Checkpoint vérifié : {name}')

def load_dense_encoder():
    prepare_torch()
    from sentence_transformers import SentenceTransformer
    model=SentenceTransformer(str(model_dir('dense')),device='cpu',local_files_only=True)
    light=E5Tokenizer()
    for text in ['passage: did not change 4¾ percent.','query: Why did inflation rise?']:
        if model.tokenizer.encode(text)!=light.encode(text): raise ValueError('Tokenizers E5 non équivalents')
    return model

def build():
    import numpy as np
    chunks=sorted(read_jsonl(ROOT/'data/processed/chunks.jsonl'),key=lambda c:c['chunk_id'])
    chunk_hash=digest(ROOT/'data/processed/chunks.jsonl')
    if len({c['chunk_id'] for c in chunks})!=len(chunks): raise ValueError('IDs de chunks dupliqués')
    tokens=[{'chunk_id':c['chunk_id'],'tokens':lexical_tokens(c['search_text'])} for c in chunks]
    write_jsonl(ROOT/'indexes/bm25/tokens.jsonl',tokens)
    write_json(ROOT/'indexes/bm25/metadata.json',dict(config=CONFIG,chunks_sha256=chunk_hash,
        tokens_sha256=digest(ROOT/'indexes/bm25/tokens.jsonl'),corpus_size=len(chunks)))
    log('Chargement du modèle E5 pour l’index dense')
    model=load_dense_encoder(); texts=['passage: '+c['search_text'] for c in chunks]
    if any(len(model.tokenizer.encode(s,truncation=False))>512 for s in texts): raise ValueError('Passage trop long')
    started=time.perf_counter()
    vectors=np.asarray(model.encode(texts,batch_size=CONFIG['batch_size'],normalize_embeddings=True,
                      convert_to_numpy=True,show_progress_bar=True),dtype=np.float32)
    if vectors.shape!=(len(chunks),384) or not np.isfinite(vectors).all(): raise ValueError('Vecteurs invalides')
    if not np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-4): raise ValueError('Vecteurs non normalisés')
    np.save(ROOT/'indexes/dense/vectors.npy',vectors,allow_pickle=False)
    write_json(ROOT/'indexes/dense/chunk_ids.json',[c['chunk_id'] for c in chunks])
    write_json(ROOT/'indexes/dense/metadata.json',dict(config=CONFIG,chunks_sha256=chunk_hash,
        shape=list(vectors.shape),vectors_sha256=digest(ROOT/'indexes/dense/vectors.npy'),
        ids_sha256=digest(ROOT/'indexes/dense/chunk_ids.json'),encoding_seconds=time.perf_counter()-started,
        environment=environment()))
    log(f'Index construits : {len(chunks)} passages, vecteurs {vectors.shape}')

def load_indexes():
    import numpy as np
    from rank_bm25 import BM25Okapi
    chunks=sorted(read_jsonl(ROOT/'data/processed/chunks.jsonl'),key=lambda c:c['chunk_id'])
    ids=[c['chunk_id'] for c in chunks]; meta=read_json(ROOT/'indexes/dense/metadata.json')
    lexical_meta=read_json(ROOT/'indexes/bm25/metadata.json')
    actual=digest(ROOT/'data/processed/chunks.jsonl')
    if meta['chunks_sha256']!=actual or lexical_meta['chunks_sha256']!=actual: raise ValueError('Index périmé')
    # Query-set size does not affect document embeddings or BM25 corpus statistics.
    without_queries=lambda config:{k:v for k,v in config.items() if k!='questions'}
    if without_queries(meta['config'])!=without_queries(CONFIG) or without_queries(lexical_meta['config'])!=without_queries(CONFIG):
        raise ValueError('Configuration de l’index modifiée')
    for path,key in [(ROOT/'indexes/dense/vectors.npy','vectors_sha256'),(ROOT/'indexes/dense/chunk_ids.json','ids_sha256')]:
        if digest(path)!=meta[key]: raise ValueError('Index dense corrompu')
    if digest(ROOT/'indexes/bm25/tokens.jsonl')!=lexical_meta['tokens_sha256']: raise ValueError('Index BM25 corrompu')
    tokens=read_jsonl(ROOT/'indexes/bm25/tokens.jsonl')
    if ids!=read_json(ROOT/'indexes/dense/chunk_ids.json') or ids!=[t['chunk_id'] for t in tokens]: raise ValueError('Alignement IDs/index invalide')
    vectors=np.load(ROOT/'indexes/dense/vectors.npy',allow_pickle=False)
    if vectors.shape!=(len(ids),384) or not np.allclose(np.linalg.norm(vectors,axis=1),1,atol=1e-4): raise ValueError('Matrice dense invalide')
    bm25=BM25Okapi([t['tokens'] for t in tokens],k1=CONFIG['bm25_k1'],b=CONFIG['bm25_b'])
    return chunks,bm25,vectors

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download-models',action='store_true'); args=parser.parse_args()
    if args.download_models: download_models()
    else: build()
