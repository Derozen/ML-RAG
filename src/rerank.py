"""Reclasser les mêmes 20 candidats par BM25, ColBERT MaxSim et cross-encoder."""
from collections import defaultdict
import argparse
import gc
import json
import string
import time
import numpy as np
from common import ROOT,CONFIG,METHODS,RERANKERS,questions,read_jsonl,read_json,write_jsonl,write_json,digest,log,model_dir,prepare_torch,stable_order,environment
from build_indexes import load_indexes

def maxsim(query,document):
    if len(query)==0 or len(document)==0: raise ValueError('Matrice de tokens vide')
    return float(np.max(query@document.T,axis=1).sum())

class ColBERT:
    """Checkpoint ColBERT réel : encodeur BERT, projection apprise, marqueurs et MaxSim."""
    def __init__(self):
        self.torch=prepare_torch()
        from transformers import AutoConfig,AutoTokenizer,BertModel
        from safetensors.torch import load_file
        path=model_dir('colbert')
        config=AutoConfig.from_pretrained(str(path),local_files_only=True)
        state=load_file(str(path/'model.safetensors'),device='cpu')
        projection_keys=[k for k in state if k.endswith('linear.weight')]
        if len(projection_keys)!=1: raise ValueError(f'Projection ColBERT introuvable : {projection_keys}')
        key=projection_keys[0]; self.projection=state[key].float()
        backbone={k.removeprefix('bert.'):v for k,v in state.items() if k.startswith('bert.')}
        if not backbone: raise ValueError('Poids encodeur ColBERT introuvables')
        self.model=BertModel(config,add_pooling_layer=False)
        # Pooler is unused in token embeddings; every encoder and projection weight must be loaded.
        backbone={k:v for k,v in backbone.items() if not k.startswith('pooler.')}
        self.model.load_state_dict(backbone,strict=True); self.model.eval()
        self.tokenizer=AutoTokenizer.from_pretrained(str(path),local_files_only=True,use_fast=True)
        self.options=read_json(path/'onnx_config.json')
        if self.projection.shape!=(self.options['embedding_dim'],config.hidden_size): raise ValueError('Projection inattendue')
        self.skip={self.tokenizer.convert_tokens_to_ids(p) for p in self.options['skiplist_words']}
        self.truncations={'query':0,'document':0}

    def encode(self,texts,is_query):
        torch=self.torch; outputs=[]; limit=CONFIG['colbert_query_length' if is_query else 'colbert_document_length']
        marker=self.options['query_prefix_id' if is_query else 'document_prefix_id']
        for start in range(0,len(texts),CONFIG['batch_size']):
            batch=texts[start:start+CONFIG['batch_size']]
            lengths=[len(self.tokenizer.encode(s,add_special_tokens=True,truncation=False))+1 for s in batch]
            self.truncations['query' if is_query else 'document']+=sum(n>limit for n in lengths)
            tokens=self.tokenizer(batch,padding=True,truncation=True,max_length=limit-1,return_tensors='pt')
            for name,value in list(tokens.items()):
                fill=marker if name=='input_ids' else 1 if name=='attention_mask' else 0
                column=torch.full((value.shape[0],1),fill,dtype=value.dtype)
                tokens[name]=torch.cat([value[:,:1],column,value[:,1:]],dim=1)
            with torch.inference_mode():
                hidden=self.model(**tokens).last_hidden_state
                projected=torch.nn.functional.normalize(hidden@self.projection.T,p=2,dim=-1)
            for i in range(len(batch)):
                keep=tokens['attention_mask'][i].bool()
                if not is_query:
                    for token_id in self.skip: keep &= tokens['input_ids'][i]!=token_id
                outputs.append(projected[i][keep].cpu().numpy().astype(np.float32))
            if not is_query and (start//CONFIG['batch_size'])%25==0: log(f'ColBERT encode {min(start+len(batch),len(texts))}/{len(texts)} passages')
        return outputs

class CrossEncoder:
    def __init__(self):
        self.torch=prepare_torch()
        from transformers import AutoTokenizer,AutoModelForSequenceClassification
        path=str(model_dir('cross_encoder'))
        self.tokenizer=AutoTokenizer.from_pretrained(path,local_files_only=True)
        self.model=AutoModelForSequenceClassification.from_pretrained(path,local_files_only=True)
        self.model.eval(); self.truncations=0

    def score(self,query,documents):
        result=[]
        for start in range(0,len(documents),CONFIG['batch_size']):
            batch=documents[start:start+CONFIG['batch_size']]
            self.truncations+=sum(len(self.tokenizer.encode(query,s,truncation=False))>CONFIG['cross_encoder_max_length'] for s in batch)
            tokens=self.tokenizer([query]*len(batch),batch,padding=True,truncation='only_second',
                                  max_length=CONFIG['cross_encoder_max_length'],return_tensors='pt')
            with self.torch.inference_mode(): values=self.model(**tokens).logits.squeeze(-1)
            result.extend(values.cpu().numpy().astype(float).tolist())
        return result

def validate_pool(before,after):
    a=[r['chunk_id'] for r in before]; b=[r['chunk_id'] for r in after]
    if len(a)!=20 or len(b)!=20 or len(set(b))!=20 or set(a)!=set(b): raise ValueError('Le reranker a modifié les candidats')

def main(only=None):
    from common import lexical_tokens
    queries=questions()
    chunks,bm25,_=load_indexes(); by_id={c['chunk_id']:c for c in chunks}; index={c['chunk_id']:i for i,c in enumerate(chunks)}
    source=ROOT/'results/retrieval/rankings.jsonl'; initial=read_jsonl(source)
    run=read_json(ROOT/'results/retrieval/run.json')
    if run['questions_sha256']!=digest(ROOT/'data/evaluation/queries_145.jsonl') or run['chunks_sha256']!=digest(ROOT/'data/processed/chunks.jsonl'):
        raise ValueError('Classements périmés')
    pools=defaultdict(list)
    for r in initial: pools[(r['question_id'],r['method'])].append(r)
    selected=[only] if only else list(RERANKERS)
    for name in selected:
        output=ROOT/f'results/reranking/{name}.jsonl'
        if output.exists():
            metadata=read_json(ROOT/f'results/reranking/{name}_run.json')
            if metadata['input_rankings_sha256']!=digest(source) or metadata['config']!=CONFIG: raise ValueError('Cache reranking périmé')
            log(f'Reranking déjà calculé : {name}'); continue
        log(f'Reranker : {name}')
        rows=[]; timings=[]; notes={}
        if name=='colbert':
            model=ColBERT()
            candidate_ids=sorted({r['chunk_id'] for r in initial})
            started=time.perf_counter()
            embeddings=model.encode([by_id[cid]['search_text'] for cid in candidate_ids],False)
            document_embeddings=dict(zip(candidate_ids,embeddings))
            notes['document_preencoding_seconds']=time.perf_counter()-started
            notes['document_preencoding_scope']='Union of retrieved candidates, no relevance labels; excluded from online reranking times.'
            del embeddings
        elif name=='cross_encoder': model=CrossEncoder()
        # Warm-up excluded, with no qrels read.
        first=queries[0]; first_ids=[r['chunk_id'] for r in pools[(first['id'],'bm25')]]
        if name=='colbert':
            model.encode([first['question']],True)
        elif name=='cross_encoder': model.score(first['question'],[by_id[first_ids[0]]['search_text']])
        else: bm25.get_scores(lexical_tokens(first['question']))
        for n,q in enumerate(queries,1):
            for retrieval in METHODS:
                before=sorted(pools[(q['id'],retrieval)],key=lambda r:r['rank'])
                ids=[r['chunk_id'] for r in before]
                start=time.perf_counter()
                if name=='bm25':
                    scores_full=bm25.get_scores(lexical_tokens(q['question']))
                    scores=[scores_full[index[cid]] for cid in ids]
                elif name=='colbert':
                    query=model.encode([q['question']],True)[0]
                    scores=[maxsim(query,document_embeddings[cid]) for cid in ids]
                else: scores=model.score(q['question'],[by_id[cid]['search_text'] for cid in ids])
                order=stable_order(scores,ids)
                after=[dict(question_id=q['id'],retrieval=retrieval,reranker=name,rank=rank,
                            chunk_id=ids[i],score=float(scores[i])) for rank,i in enumerate(order,1)]
                seconds=time.perf_counter()-start
                validate_pool(before,after)
                if retrieval=='bm25' and name=='bm25' and ids!=[r['chunk_id'] for r in after]: raise ValueError('Contrôle BM25→BM25 incohérent')
                rows.extend(after); timings.append(dict(question_id=q['id'],retrieval=retrieval,reranker=name,seconds=seconds))
            if n%10==0 or n==len(queries): log(f'{name} : {n}/{len(queries)} questions')
        if name!='bm25': notes['truncation_counts']=model.truncations
        write_jsonl(output,rows)
        write_jsonl(ROOT/f'results/reranking/{name}_timings.jsonl',timings)
        write_json(ROOT/f'results/reranking/{name}_run.json',dict(config=CONFIG,questions=len(queries),rankings=len(rows),
            input_rankings_sha256=digest(source),output_sha256=digest(output),candidate_set_checks=len(queries)*len(METHODS),
            model_notes=notes,environment=environment(),timing='One sequential timed pass after warm-up. ColBERT document preencoding excluded and reported separately. Query encoding included; no cross-method pair-score cache.'))
        if name!='bm25':
            del model
            if name=='colbert': del document_embeddings
            gc.collect()
        log(f'Reranking {name} terminé : {len(rows)} rangs')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--only',choices=RERANKERS)
    main(parser.parse_args().only)
