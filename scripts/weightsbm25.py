import psycopg2
import json
import os 
import numpy as np
from dotenv import load_dotenv
import pickle
import sys
from rerank import tokenize
from rank_bm25 import BM25Okapi
load_dotenv()

def savebm25(tabname,model_folder_path):
    os.makedirs(model_folder_path,exist_ok=True)
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
        SELECT id,title,content from {tabname}
    """, )
    rows = cur.fetchall()
    documents = [r[2] for r in rows]
    tokenized_corpus = [tokenize(text) for text in documents]
    bm25 = BM25Okapi(tokenized_corpus)
    with open(os.path.join(model_folder_path,f"{tabname}bm25.pkl"), "wb") as f:
        pickle.dump(bm25, f)
if __name__ == "__main__":
    tabname = "FOMC2"
    model_folder_path = "models"
    if len(sys.argv)>1:
        tabname = sys.argv[1]
    if len(sys.argv)>2:
        model_folder_path=sys.argv[2]
    savebm25(tabname,model_folder_path)