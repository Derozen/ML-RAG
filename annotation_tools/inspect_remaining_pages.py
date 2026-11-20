import json,csv,re,sys
from pathlib import Path
from collections import defaultdict
root=Path(__file__).resolve().parents[1]
base=root/'data/holdout_candidate'
rows=list(csv.DictReader((base/'assistant_review/round_2/coverage.csv').open(encoding='utf-8-sig')))
patterns={
'20260617':r'employment cost|hourly earnings|labor cost|wage',
'20240131':r'unemployment rate|third.quarter average',
'20220615':r'George|75.basis|75 basis|longer.run inflation expectations|unanchored',
'20251029':r'shutdown|government production|GDP growth',
'20250319':r'Waller|reserves.*trillion|ample.reserves|reserve.*abundant|tools.*available',
'20220504':r'(2023|2024).*inflation|inflation.*(2023|2024)|PCE.*forecast',
'20220727':r'PCE.*inflation|inflation.*PCE|inflation.*(2023|2024)',
'20230322':r'recession|banking system|GDP.*pace|credit conditions',
'20230920':r'GDP.*pace|activity.*solid|postmeeting statement',
'20260128':r'cuts|market.*policy|policy.*market|survey.*rate|federal funds.*target',
'20250917':r'Miran|Bowman|Waller|abstain|ratify|half.*point',
'20240731':r'Treasury bills|25 billion|35 billion|reinvest|coupon principal'}
ps=defaultdict(list)
for line in (root/'data/processed/paragraphs.jsonl').read_text(encoding='utf-8').splitlines():
 p=json.loads(line);ps[f"{p['filename']}#p{p['page']}"].append(p)
for date in sys.argv[1:]:
 pages=sorted({r['page_id'] for r in rows if r['status']=='unjudged' and date in r['page_id']},key=lambda x:int(x.rsplit('#p',1)[1]))
 for pid in pages:
  qs=[r['question_id'][-3:] for r in rows if r['status']=='unjudged' and r['page_id']==pid]
  print('\nPAGE',pid,'QUESTIONS',','.join(qs))
  for p in ps[pid]:
   t=p['text'];sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z“])',t)
   lead=sentences[0][:100]
   selected=[s for s in sentences if re.search(patterns[date],s,re.I)]
   if len(t)<200 and not selected:continue
   print(p['paragraph_id'],lead+(' ...' if len(sentences[0])>100 else ''))
   for s in selected:
    if s!=sentences[0] or len(s)>100:print('  MATCH',s)
