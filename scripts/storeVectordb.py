import psycopg2
import json
import os 
import numpy as np
import sys
import argparse
from pathlib import Path
#from sentence_transformers import SentenceTransformer
from langchain_experimental.text_splitter import SemanticChunker
from langchain_huggingface import HuggingFaceEmbeddings
import spacy
#from langchain_text_splitters import RecursiveCharacterTextSplitter
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
        paragraph_id INT,
        title TEXT,
        content TEXT,
        chunk_start INT,
        chunk_end INT,
        embedding vector(768)
    );
    """)

    conn.commit()
    data = [(c['paragraph_id'],c['source'], c['text'],c['chunk_start'], c['chunk_end'], e) for c,e in zip(Chunks, embeddings)]

    cur.executemany(
        f"""
        INSERT INTO {tabname} (paragraph_id,title,content,chunk_start,chunk_end, embedding)
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
    path_json_dataset = "data/articles_with_qas.json"
    token_type = None
    tabname = 'WIKIDOCS'
    use_spacy = False
    ch_id = 0

    if use_spacy:
        nlp = spacy.load('en_core_web_sm') #'fr_core_news_sm'
    else:
        encode_kwargs = {'normalize_embeddings': True}
        embed_model = HuggingFaceEmbeddings(
                model_name="BAAI/bge-base-en-v1.5",
                encode_kwargs=encode_kwargs
            )
        #splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE,chunk_overlap=CHUNK_OVERLAP)
        semantic_chunker = SemanticChunker(embed_model, breakpoint_threshold_type="percentile",
                                           add_start_index=True)
    #model = SentenceTransformer(EMBED_MODEL)
    with open(path_json_dataset, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    N_articles = len(dataset['data'])
    for plll in [1]:#range(N_articles):
        article = dataset['data'][plll]
        print(f"Processing article: {article['title']}")
        title = article['title']
        metadatas = [{"paragraph_id":i} for i in range(len(article['paragraphs']))]
        semantic_chunks = semantic_chunker.create_documents([p['context'] for p in article['paragraphs']],metadatas=metadatas)
        texts = [{'source':title, 'text': chk.page_content, 'chunk_size':len(chk.page_content),
                    'chunk_start':chk.metadata['start_index'],'paragraph_id':chk.metadata['paragraph_id'],
                    'chunk_end':chk.metadata['start_index']+len(chk.page_content),
                    'ch_id':ichk+1+ch_id} for ichk,chk in enumerate(semantic_chunks)]
        ch_id = texts[-1]['ch_id']
        chunks = [c.page_content for c in semantic_chunks]
        embeddings = embed_model.embed_documents(chunks)
        #store_vector(texts, embeddings, tabname)
        print(f"Article '{title}' processed and stored in the database.")
        #print(f"Article '{title}' processed and stored in the database.")
        nparags = len(article['paragraphs'])
        for npa in [1]:#range(nparags):
            ch_sizes = [(i,c['chunk_start'],c['chunk_end']) for i,c in enumerate(texts) if c['paragraph_id']==npa]
            paragraph = article['paragraphs'][npa]
            nqas = len(paragraph['qas'])
            for pl in range(nqas):
                qas = paragraph['qas'][pl]
                start = qas['answers'][0]['answer_start']
                size = len(qas['answers'][0]['text'])
                min_c = [c for c in ch_sizes if c[1]<=start][-1][0]
                max_c = [c for c in ch_sizes if c[2]>=start+size-1]
                if max_c:
                    max_c = max_c[0][0]
                else:
                    max_c = len(chunks)-1
                sols = [c['ch_id'] for c in texts[min_c:max_c+1]]
                qas['answers'][0]['ch_ids'] = sols
                paragraph['qas'][pl] = qas
            article['paragraphs'][npa] = paragraph
        dataset['data'][plll] = article
    #with open(path_json_dataset.split('.')[0]+'v2.json', 'w', encoding='utf-8') as f:
    #    json.dump(dataset, f, ensure_ascii=False, indent=4)
        
