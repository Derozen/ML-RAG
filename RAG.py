import psycopg2 
import os 
import pickle 
from dotenv import load_dotenv
import json
import requests
import numpy as np
from openai import OpenAI
from scripts.rerank import tokenize
from sentence_transformers import CrossEncoder, SentenceTransformer
load_dotenv()

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def rerank_cohere(query,rows,TOP_K=5):
    if rows==[]:
        return []
    if TOP_K>len(rows):
        TOP_K = len(rows)
    response = requests.post(
        url="https://openrouter.ai/api/v1/rerank",
        headers={
          "Authorization": f"Bearer {os.getenv('COHERE_KEY')}",
          "Content-Type": "application/json"
        },
        data=json.dumps({
          "model": "cohere/rerank-4-fast",
          "query": query,
          "documents": [r[0] for r in rows],
          "top_n": TOP_K
        })
      )
    results = response.json()
    indexs = [result['index'] for result in results["results"]]
    scores = [result['relevance_score'] for result in results["results"]]
    rows = [rows[idx] for idx in indexs]
    return [r[0] for r in rows]
    
def rerank(query,rows,TOP_K=4):
    tokenized_query = tokenize(query)
    pairs = [[query, text[0]] for text in rows]
    scores = model.predict(pairs)
    top_indices = np.argsort(scores)[::-1][:TOP_K]
    return [rows[i][0] for i in top_indices]

def retrieve(question,embedding,threshold=0.47):
    conn = psycopg2.connect(
                dbname=os.getenv('DB_NAME'),
                user=os.getenv('DB_USER'),
                host=os.getenv('DB_HOST'),
                password=os.getenv('DB_PASSWORD'),
                sslmode='require',
                port=os.getenv('DB_PORT')
            )
    cur = conn.cursor()
    cur.execute(f"""
        SELECT
            content,
            ROW_NUMBER() OVER (
                        ORDER BY embedding <=> %s::vector
                    ) AS rank,
            embedding <=> %s::vector AS distance
        FROM {os.getenv('TABNAME')}
        ORDER BY rank ASC LIMIT 10;
        """,(embedding,embedding,))
    rows = cur.fetchall()
    rows = [r for r in rows if r[2]<=threshold]
    #return rerank(question,rows,4)
    return [r[0] for r in rows[:4]]



def answer(question,context):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
                {
                    "role": "system",
                    "content": "Answer the question using only the provided context. "
                            "If the answer is not in the context, say you don't know."
                },
                {
                    "role": "user",
                    "content": f"Context:\n{context}\n\nQuestion:\n{question}"
                }
            ],
        temperature=0.7
    )

    return response.choices[0].message.content

