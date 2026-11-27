import psycopg2
import re
import numpy as np
from rank_bm25 import BM25Okapi
#from langchain_cohere import CohereRerank
from sentence_transformers import CrossEncoder, SentenceTransformer
from transformers import AutoModel
import requests
import os
import json
from dotenv import load_dotenv
load_dotenv()

def tokenize(text):
    return re.findall(r'\w+', text.lower())

def rank_cohere(query,texts, top_k):
  response = requests.post(
    url="https://openrouter.ai/api/v1/rerank",
    headers={
      "Authorization": f"Bearer {os.getenv('COHERE_KEY')}",
      "Content-Type": "application/json"
    },
    data=json.dumps({
      "model": "cohere/rerank-4-fast",
      "query": query,
      "documents": texts,
      "top_n": top_k
    })
  )
  results = response.json()
  indexs = [result['index'] for result in results["results"]]
  scores = [result['relevance_score'] for result in results["results"]]
  return indexs, scores
model_lists_1 = ["BAAI/bge-reranker-v2-m3",
                 "Alibaba-NLP/gte-reranker-modernbert-base",
                 "mixedbread-ai/mxbai-rerank-xsmall-v1"
                 ]
model_lists_2 = ["jinaai/jina-reranker-v2-base-multilingual"]
def rrf(rankings: list[list[int]], k: int = 60, weights=None, top_n: int = 10):
    """rankings : une liste d'identifiants triés par pertinence décroissante, par méthode."""
    scores: dict[int, float] = {}
    for i, ranking in enumerate(rankings):
        w = weights[i] if weights else 1.0
        for rank, doc_id in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + w / (k + rank)
    return sorted(scores.items(), key=lambda x: -x[1])[:top_n]   # [(doc_id, score), ...]

def rank(query,texts,top_k,model,model_name):
    if model_name=='cohere':
      return rank_cohere(query,texts,top_k)
    elif model_name in model_lists_1:
      tokenized_query = tokenize(query)
      pairs = [[query, text] for text in texts]
      scores = model.predict(pairs)
      top_indices = np.argsort(scores)[::-1][:top_k]
      return top_indices, [scores[i] for i in top_indices]
    elif model_name in model_lists_2:
      scores = model.compute_score(pairs, max_length=1024)
      top_indices = np.argsort(scores)[::-1][:top_k]
      return top_indices, scores
    else:
      raise ValueError(f"Model {model_name} not supported")
    # print(f"Index: {result['index']}, Score: {result['relevance_score']}")
    # print(f"  Document: {result['document']['text']}")



