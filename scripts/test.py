import json 
import os 
import psycopg2
from dotenv import load_dotenv
load_dotenv()


with open('data/squad_fomc_statements.json', 'r', encoding='utf-8') as f:
        dataset = json.load(f)
for article in dataset['data']:
    #print(f"Processing article: {article['title']}")
    title = article['title']
    texts = []
    if len(article['paragraphs']) > 1:
        print(title)
        for qas in article['paragraphs'][0]['qas']:
            if len(qas['answers']) > 1:
                print("Here")

conn = psycopg2.connect(
            dbname=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            host=os.getenv('DB_HOST'),
            password=os.getenv('DB_PASSWORD'),
            sslmode='require',
            port=os.getenv('DB_PORT')
        )
cur = conn.cursor()


folders = ['data/test/FOMC1', 'data/test/FOMC2']
tabs = ['FOMCv1','FOMCv2']
dscr = ['data/test.json','data/test2.json']
for folder,tabname,dpath in zip(folders,tabs,dscr):

    with open(dpath, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
    answers = {}
    for article in dataset['data']:
        for qas in article['paragraphs'][0]['qas']:
            answers[qas['id']] = qas['answers'][0]['chunk_ids']
    cur.execute(f"""
        SELECT id,chunk_id,content FROM {tabname};
    """)
    rows = cur.fetchall()
    files = [os.path.join(folder,f) for f in os.listdir(folder) if f.endswith('.json')]




    for file in files:
        with open(file,'r',encoding='utf-8') as fjs:
            fres = json.load(fjs)
        N = len(fres)
        for i in range(N):
            M = 15
            for j in range(M):
                fres[i]['extractions'][j]['chunk_id'] = rows[fres[i]['extractions'][j]['id']-1][1]
                fres[i]['solution']['chunks'] = answers[fres[i]['qid']]
                if rows[fres[i]['extractions'][j]['id']-1][2] != fres[i]['extractions'][j]['content'] :
                    print(f"Divergence for {rows[fres[i]['extractions'][j]['id']-1][0]}")
        with open(file,'w',encoding='utf-8') as fjs:
            fjs.write(json.dumps(fres,indent=4,ensure_ascii=False))
    
          