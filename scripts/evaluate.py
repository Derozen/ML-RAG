import json
import os
import re
import sys
import math

def normalize(text):
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text.lower())).strip()


def is_hit(answer, chunk, threshold=0.8):
    """
    A chunk 'contains' the answer if:
      - the normalized answer is a substring of the chunk, OR
      - at least `threshold` of the answer's tokens appear in the chunk
        (handles slight rewording / truncation).
    """
    a, c = normalize(answer), normalize(chunk)
    if a in c:
        return True
    a_tokens = set(a.split())
    return bool(a_tokens) and len(a_tokens & set(c.split())) / len(a_tokens) >= threshold


def recall_at_k(samples, k=None, threshold=0.8):
    hits = 0
    for s in samples:
        retrieved = s["retrieved"][:k] if k else s["retrieved"]
        if any(is_hit(s["answer"], chunk, threshold) for chunk in retrieved):
            hits += 1
    return hits / len(samples)

def ndcg_at_k(rankings, gold, k):
    scores = []
    for qid, ranked in rankings.items():
        top = ranked[:k]
        if gold[qid] in top:
            rank = top.index(gold[qid]) + 1      # rang à partir de 1
            scores.append(1 / math.log2(rank + 1))
        else:
            scores.append(0.0)
    return sum(scores) / len(scores)

if __name__ == "__main__":
    dataset_json_path = 'data/test'
    with open(dataset_json_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    questions = []
    answers = []
    for article in dataset['data']:
            print(f"Processing article: {article['title']}")
            title = article['title']
            chunks = []
            for paragraph in article['paragraphs']:
                for qas in paragraph['qas']:
                    questions.append({'question':qas['question'],
                                    'qid':qas['id']})
                    answers.append(qas['answers'][0])
    reranking_models = ['norerank','cohere','bge']
    tabs = ['FOMC1','FOMC2']
    methods = ['vectorielle','hybride','bm25']
    columns = ['TABLE','RETRIEVAL','RERANKING','RECALL@5','RECALL@10']
    scores = {c:[] for c in columns}
    for tab in tabs:
        for rrk_model in reranking_models:
            for method in methods:
                with open(f'data/{tab}/{rrk_model}-{method}.json', 'r', encoding='utf-8') as f:
                    samples = json.load(f)
            samples = [{'qid':s['qid'],'question':s['question'],'retrieved':[e['content'] for e in s['extractions']],'answer':s['solution']['text']} for s in samples]
            score_5 = recall_at_k(samples,5)
            scores['TABLE'].append(tab)
            scores['RETRIEVAL'].append(method)
            scores['RERANKING'].append(rrk_model)
            scores['RECALL@5'].append(score_5)
    k=5
    print(f"Recall@{k}: {recall_at_k(samples, k):.3f}")