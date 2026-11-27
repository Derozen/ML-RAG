import json 
import numpy as np 
import os
import pickle 
import sys
import psycopg2
from sentence_transformers import CrossEncoder, SentenceTransformer
#from transformers import AutoModel
from transformers import AutoModelForSequenceClassification
from rank_bm25 import BM25Okapi
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
from dotenv import load_dotenv
from rerank import rank, rrf, tokenize, model_lists_1, model_lists_2
load_dotenv()

TEST_SIZE = 0.8
TOP_K = 15
CHUNK_SIZE = 300     # caractères
CHUNK_MIN = 256
CHUNK_MAX = 512
CHUNK_OVERLAP = 50
def mparam(e,q,i):
     if i==0:
        return (e,e,)



def testpipeline(questions,answers,embeddings,
        rrk_model,name,tabname,
        method,sqlq1,sqlq2,model,TOP_K):
    os.makedirs(f'data/test/{tabname}',exist_ok=True)
    queries = [q['question'] for q in questions]
    qids = [q['qid'] for q in questions]
    #extractions = {tabname: {RETRIEVAL:{qid:[] for qid in qids[:N]}  for RETRIEVAL in RETRIEVALS[:N]} for tabname in tabs}
    if method=="bm25" or method=='hybride':
        with open(f"models/{tabname}_bm25.pkl", "rb") as f:
            bm25 = pickle.load(f)
    results = []
    print(f"method {method}")
    conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            host=os.getenv('DB_HOST'),
            password=os.getenv('DB_PASSWORD'),
            sslmode='require',
            port=os.getenv('DB_PORT')
        )
    
    cur = conn.cursor()
    N = len(queries)
    for i,query,qid in zip(list(range(N)),queries,qids):
        print(f"query {i+1}/{N}")
        embed = embeddings[i]
        if method == 'vectorielle' or method == 'hybride':
            cur.execute(sqlq1, (embed,embed,))

            rows = cur.fetchall()
            rows = {r[0]:(r[1],r[2],r[4]) for r in rows}
            if method == 'hybride':
                vectorielle = rows
        if method == 'bm25' or method == 'hybride':
            cur.execute(sqlq2)
            rows = cur.fetchall()
            tokenized_corpus = [tokenize(r[2]) for r in rows]
            tokenized_query = tokenize(query)
            bmscores = bm25.get_scores(tokenized_query)
            keeps = np.argsort(bmscores)[::-1][:TOP_K]
            rows = {rows[i][0]:(rows[i][1],rows[i][2],bmscores[rows[i][0]-1]) for i in keeps}
            if method == 'hybride':
                bmlist = rows
        if method == 'hybride':
            vect_id = [r for r in vectorielle.keys()]
            bm_id = [r for r in bmlist.keys()]
            rankings = [vect_id,bm_id]
            rankings = rrf(rankings,top_n=TOP_K)
            rows = {}
            for doc,score in rankings:
                if doc in vect_id:
                    rows[doc] = (vectorielle[doc][0],vectorielle[doc][1],score)
                else:
                    rows[doc] = (bmlist[doc][0],bmlist[doc][1],score)
        if rrk_model == 'norerank':
            indices = list(range(TOP_K))
            scores = [1/(60+sco+1) for sco in range(len(indices))]
        else:
            indices, scores= rank(query,[r[1] for rid,r in rows.items()],TOP_K,model,rrk_model)
        solutions = []
        row_idxs = list(rows.keys())
        for idx, score in zip(indices,scores):
            row_id = row_idxs[idx]
            row = rows[row_id]
            sol = {"title":row[0],
                "id":row_id,
                "content":row[1],
                "score_retrieve":float(row[2]),
                "score_reranking":float(score)}
            solutions.append(sol)
        results.append({
            'qid':qid,
            'question':query,
            'extractions':solutions,
            'solution':answers[i]})

    with open(f'data/test/{tabname}/{name}-{method}.json','w',encoding='utf-8') as jsol:
        jsol.write(json.dumps(results, indent=4, ensure_ascii=False))

if __name__ == "__main__":
    MODEL_NAMES = {"norerank":"norerank","Alibaba-NLP/gte-reranker-modernbert-base":"gte",
                 "mixedbread-ai/mxbai-rerank-xsmall-v1":"mxbai",
                 "cross-encoder/ms-marco-MiniLM-L-6-v2":"marco"}
                 #"jinaai/jina-reranker-v2-base-multilingual":"jina"}#"cohere":"cohere","BAAI/bge-reranker-v2-m3":"bge"
                    # }#"jinaai/jina-reranker-v3":"jina"}
    dataset_json_path = 'data/articles_with_qasv2.json'
    methods = ['hybride','bm25','vectorielle']
    #rrk_model = 'norerank'
    tabname = 'WIKIDOCS'
    # if len(sys.argv)>1:
    #     dataset_json_path = sys.argv[1]
    # if len(sys.argv)>2:
    #     method = sys.argv[2]
    # if len(sys.argv)>3:
    #     rrk_model = sys.argv[3]
    # try:
    #     name = MODEL_NAMES[rrk_model]
    # except:
    #     raise ValueError("Modèle de Reranking doit être dans MODEL_NAMES")
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
    rng = np.random.default_rng(seed=42)
    idxs = list(range(len(questions)))
    rng.shuffle(idxs)
    i = 20
    print(questions[i])
    query = questions[i]
    questions = [questions[i] for i in idxs]
    answers = [answers[i] for i in idxs]

    N = int(len(questions) * TEST_SIZE)
    N = 120
    encode_kwargs = {'normalize_embeddings': True}
    embed_model = HuggingFaceEmbeddings(
                    model_name="BAAI/bge-base-en-v1.5",
                    encode_kwargs=encode_kwargs
                )
    #embeddings = encoder.encode([q['question'] for q in questions[:N]], normalize_embeddings=True).tolist()
    embeddings = embed_model.embed_documents([q['question'] for q in questions[:N]])
    for rrk_model,name in MODEL_NAMES.items():
      if rrk_model in model_lists_1:
          model = CrossEncoder(rrk_model)
      elif rrk_model in model_lists_2:
          model = AutoModelForSequenceClassification.from_pretrained(rrk_model,trust_remote_code=True)
          model.eval()
      else:
          model = None
      sql1 = f"""
          SELECT
              id,
              title,
              content,
              ROW_NUMBER() OVER (
                          ORDER BY embedding <=> %s::vector
                      ) AS rank,
              embedding <=> %s::vector AS distance
          FROM {tabname}
          ORDER BY rank ASC LIMIT {TOP_K};
          """
      sql2 = f"""
          SELECT
              id,
              title,
              content
          FROM {tabname};
          """
      for method in methods:
        testpipeline(questions[:N],answers[:N],
                  embeddings,rrk_model,name,
                  tabname,method,sql1,sql2,model,
                  TOP_K)