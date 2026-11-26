import psycopg2
import json
import os 
import numpy as np
import sys
import argparse
from pathlib import Path
from sentence_transformers import SentenceTransformer
import spacy
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv
load_dotenv()


CHUNK_SIZE = 300     # caractères
CHUNK_MIN = 256
CHUNK_MAX = 512
CHUNK_OVERLAP = 50
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

def chunk_text(text: str) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE].strip())
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if c]


def store_vector(Chunks, embeddings, tabname,language='english',supabase=False):
    if not supabase:
        conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            host=os.getenv('DB_HOST'),
            password=os.getenv('DB_PASSWORD'),
            sslmode='require',
            port=os.getenv('DB_PORT')
        )
    else:
        conn = psycopg2.connect(os.getenv('SUPABASE_URL'))
    cur = conn.cursor()
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {tabname}(
        id SERIAL PRIMARY KEY,
        chunk_id TEXT,
        title TEXT,
        content TEXT,
        chunk_start INT,
        chunk_end INT,
        embedding vector(384)
    );
    """)

    conn.commit()
    data = [(c['ch_id'],c['source'], c['text'],c['chunk_start'], c['chunk_end'], e) for c,e in zip(Chunks, embeddings)]

    cur.executemany(
        f"""
        INSERT INTO {tabname} (chunk_id,title,content,chunk_start,chunk_end, embedding)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        data
    )

    conn.commit()

    cur.execute(f"""
    CREATE INDEX ON {tabname}
    USING ivfflat (embedding vector_cosine_ops);
    """)

    conn.commit()

    cur.execute(f"""
        CREATE INDEX ON {tabname}
        USING GIN (to_tsvector('{language}', content));
        """)

    cur.execute(f"ANALYZE {tabname};")
    conn.commit()
    conn.close()

    print("Data stored successfully in the database.")

if __name__ == "__main__":
    path_json_dataset = "data/squad_fomc_statements.json"
    if len(sys.argv)>1:
        path_json_dataset = sys.argv[1]
    token_type = None
    tabname = 'FOMCv2'
    use_spacy = False
    #ch_id = 1
    if len(sys.argv)>2:
        use_spacy = sys.argv[2]
    if len(sys.argv)>3:
        tabname = sys.argv[3]
    if use_spacy:
        nlp = spacy.load('en_core_web_sm') #'fr_core_news_sm'
    else:
        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE,chunk_overlap=CHUNK_OVERLAP)
    model = SentenceTransformer(EMBED_MODEL)
    with open(path_json_dataset, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    N_articles = len(dataset['data'])
    for plll in range(N_articles):
        article = dataset['data'][plll]
        print(f"Processing article: {article['title']}")
        title = article['title']
        texts = []
        paragraph = article['paragraphs'][0]
        context = paragraph['context']
        if use_spacy:
            doc = nlp(context)
            chunks = [sent.text for sent in doc.sents]
        else:
            chunks = splitter.split_text(context)
        n = len(chunks)
        for i,chk in enumerate(chunks):
            if i ==0:
                start = 0
            else:
                start = texts[-1]['chunk_end']+1 + context[texts[-1]['chunk_end']+1:].find(chk.split()[0])
            texts.append({'source':title, 'text': chk, 'chunk_size':len(chk),
                    'chunk_start':start,'chunk_end':start+len(chk)-1,
                    'ch_id':f"ch_{title.split(' - ')[-1].replace(' ','_')}_{i+1:03d}"})
        chunks = texts[-n:]
        embeddings = model.encode([c['text'] for c in texts], normalize_embeddings=True)
        store_vector(texts, embeddings.tolist(), tabname)
        print(f"Article '{title}' processed and stored in the database.")
        nqas = len(paragraph['qas'])
        for pl in range(nqas):
            qas = paragraph['qas'][pl]
            ch_sizes = [(i,c['chunk_start'],c['chunk_end']) for i,c in enumerate(chunks)]
            start = qas['answers'][0]['answer_start']
            size = len(qas['answers'][0]['text'])
            min_c = [c for c in ch_sizes if c[1]<=start][-1][0]
            max_c = [c for c in ch_sizes if c[2]>=start+size-1]
            if max_c:
                max_c = max_c[0][0]
            else:
                max_c = len(chunks)-1
            sols = [c['ch_id'] for c in chunks[min_c:max_c+1]]
            qas['answers'][0]['chunk_ids'] = sols
            paragraph['qas'][pl] = qas
        article['paragraphs'][0] = paragraph
        dataset['data'][plll] = article
    open("data/test2.json",'w',encoding='utf-8').write(json.dumps(dataset,ensure_ascii=False,indent=4))