"""Comparer BM25, E5 et RRF sur les seules requêtes, sans consulter les références."""
import time
from collections import defaultdict
import numpy as np
from common import ROOT,CONFIG,METHODS,questions,lexical_tokens,stable_order,write_jsonl,write_json,digest,log,environment
from build_indexes import load_indexes,load_dense_encoder

def rrf(rankings,constant=60):
    scores=defaultdict(float)
    for ranking in rankings:
        if len(ranking)!=len(set(ranking)): raise ValueError('Doublon de candidat')
        for rank,cid in enumerate(ranking,1): scores[cid]+=1/(constant+rank)
    return sorted(scores,key=lambda cid:(-scores[cid],cid)),scores

def main():
    queries=questions(); chunks,bm25,vectors=load_indexes(); ids=[c['chunk_id'] for c in chunks]
    log('Chargement E5 pour les requêtes')
    model=load_dense_encoder(); records=[]; timings=[]; k=CONFIG['top_k']
    model.encode(['query: '+queries[0]['question']],normalize_embeddings=True,show_progress_bar=False)
    bm25.get_scores(lexical_tokens(queries[0]['question']))
    for number,q in enumerate(queries,1):
        schedule=list(METHODS)
        np.random.default_rng(CONFIG['seed']+number).shuffle(schedule)
        for method in schedule:
            start=time.perf_counter()
            if method in ('bm25','hybrid_rrf'):
                lexical=np.asarray(bm25.get_scores(lexical_tokens(q['question'])))
                lex_order=stable_order(lexical,ids)[:k]
            if method in ('dense','hybrid_rrf'):
                if len(model.tokenizer.encode('query: '+q['question'],truncation=False))>512: raise ValueError('Question trop longue')
                v=model.encode(['query: '+q['question']],normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)[0]
                semantic=vectors@v; dense_order=stable_order(semantic,ids)[:k]
            if method=='bm25': order=lex_order; scores=lexical
            elif method=='dense': order=dense_order; scores=semantic
            else:
                ordered,fused=rrf([[ids[i] for i in lex_order],[ids[i] for i in dense_order]],CONFIG['rrf_constant'])
                lookup={cid:i for i,cid in enumerate(ids)}; order=[lookup[cid] for cid in ordered[:k]]
                scores=np.array([fused.get(cid,0) for cid in ids])
            elapsed=time.perf_counter()-start
            timings.append(dict(question_id=q['id'],method=method,seconds=elapsed))
            records.extend(dict(question_id=q['id'],method=method,rank=rank,chunk_id=ids[i],score=float(scores[i]),
                                filename=chunks[i]['filename'],page_start=chunks[i]['page_start'],page_end=chunks[i]['page_end'])
                           for rank,i in enumerate(order,1))
        if number%10==0 or number==len(queries): log(f'Récupération {number}/{len(queries)}')
    records.sort(key=lambda r:(r['question_id'],r['method'],r['rank']))
    write_jsonl(ROOT/'results/retrieval/rankings.jsonl',records)
    write_jsonl(ROOT/'results/retrieval/timings.jsonl',timings)
    write_json(ROOT/'results/retrieval/run.json',dict(config=CONFIG,questions_sha256=digest(ROOT/'data/evaluation/queries_145.jsonl'),
        chunks_sha256=digest(ROOT/'data/processed/chunks.jsonl'),rankings_sha256=digest(ROOT/'results/retrieval/rankings.jsonl'),
        questions=len(queries),rankings=len(records),split='all',environment=environment(),
        timing='CPU, sequential methods, one timed pass after warm-up; model/index loading excluded; query encoding included. Exploratory latency, not a high-precision speed benchmark.'))
    log(f'Trois classements exportés : {len(records)} lignes')

if __name__=='__main__': main()
