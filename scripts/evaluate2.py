import sys
import json 
import math
import pandas as pd

def gold_chunks(chunks, para_id, ans_start, ans_end):
    # chunks : liste de dicts {id, para_id, start, end} (positions en caractères dans le paragraphe)
    return {c["id"] for c in chunks
            if c["para_id"] == para_id
            and c["start"] < ans_end and c["end"] > ans_start}   # recouvrement

def recall_at_k(rankings, gold, k):
    scores = []
    for qid, ranked in rankings.items():
        rel = gold[qid]                     # ensemble d'identifiants de chunks
        scores.append(len(set(ranked[:k]) & rel) / len(rel))
    return sum(scores) / len(scores)

def hit_at_k(rankings, gold, k):
    return sum(bool(set(r[:k]) & gold[q]) for q, r in rankings.items()) / len(rankings)

import math

def ndcg_at_k(rankings, gold, k):
    scores = []
    for qid, ranked in rankings.items():
        rel = gold[qid]
        dcg = sum(1 / math.log2(i + 1)
                  for i, c in enumerate(ranked[:k], 1) if c in rel)
        idcg = sum(1 / math.log2(i + 1)
                   for i in range(1, min(len(rel), k) + 1))
        scores.append(dcg / idcg)
    return sum(scores) / len(scores)


if __name__ == "__main__":
    mreranks = ['norerank']
    mrets = ['vectorielle','hybride','bm25']
    columns = ['TABLE','RETRIEVAL','RERANKING','RECALL@5','RECALL@10','nDCG@5','nDCG@10']
    scores = {c:[] for c in columns}
    tab = 'WIKIDOCS'
    for mrrk in mreranks:
        for mrxt in mrets:
            with open(f'data/test/{tab}/{mrrk}-{mrxt}.json', 'r', encoding='utf-8') as f:
                samples = json.load(f)
            rankings = {s['qid']: [ext['id'] for ext in s['extractions']]  for s in samples}
            gold =  {s['qid']:set( s['solution']['ch_ids'] ) for s in samples } 
            rc_5 = recall_at_k(rankings,gold,5)
            rc_10 = recall_at_k(rankings,gold,10)
            ndc_5 = ndcg_at_k(rankings,gold,5)
            ndc_10 = ndcg_at_k(rankings,gold,10)
            scores['TABLE'].append(tab)
            scores['RETRIEVAL'].append(mrxt)
            scores['RERANKING'].append(mrrk)
            scores['RECALL@5'].append(rc_5)
            scores['RECALL@10'].append(rc_10)
            scores['nDCG@5'].append(ndc_5)
            scores['nDCG@10'].append(ndc_10)

data = pd.DataFrame(scores)
data.to_csv('data/scores2.csv')