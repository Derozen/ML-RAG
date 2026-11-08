"""Rebuild the review draft from actual corpus passages; never promote it to gold."""
from pathlib import Path
import collections
import csv
import hashlib
import json
import re
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]

# Curated causal passages: paragraph suffix, sentence cue, focused question.
EXPLANATIONS = [
('0144','reserves were projected','Why were reserve balances projected to rise through the summer?'),
('0047','Rates implied','What reportedly explained the rise in rates implied by interest rate futures?'),
('0106','Many participants also remarked','Which factors did participants cite as likely reasons for hiring difficulties?'),
('0106','The staff expected','Why did the staff expect twelve-month PCE inflation to move down?'),
('0101','The staff expected','Why did the staff expect twelve-month PCE inflation to moderate in the second half of 2021?'),
('0084','near-term outlook','Why did the staff revise its near-term inflation outlook upward?'),
('0088','near-term outlook','Why did the staff revise its near-term inflation outlook upward?'),
('0099','The near-term outlook','Why was the near-term consumer price inflation outlook revised upward?'),
('0207','The near-term projection','Why was the staff near-term economic activity projection weaker than in December?'),
('0044','Global financial conditions tightened','What developments accounted for tighter global financial conditions?'),
('0039','Treasury yields increased','What primarily accounted for the rise in Treasury yields across the curve?'),
('0079','With regard to PCE','Why did the staff raise its PCE inflation projection for the second half of 2022?'),
('0045','Treasury yields fell','What expectations accounted for the fall in Treasury yields?'),
('0072','financial conditions tightened','What largely accounted for tighter US financial conditions?'),
('0069','nominal Treasury yields ended','What two factors accounted for higher nominal Treasury yields?'),
('0113','The staff slightly lowered','Why did the staff slightly lower its potential output outlook?'),
('0155','In part reflecting','What policy effect partly explained the staff expectation of slower GDP growth and a softer labor market?'),
('0104','Reflecting the','Why was core inflation forecast to slow sharply the following year?'),
('0080','Use of the ON RRP','Why did ON RRP facility use decline at times during the intermeeting period?'),
('0072','Policy-sensitive rates increased','What developments explained the increase in policy-sensitive rates?'),
('0066','market-implied peak','Why did the market-implied peak federal funds rate rise and then partly retrace?'),
('0099','The economic forecast','Why was the staff economic forecast stronger than in July?'),
('0074','The rise since July','What mostly accounted for the rise since July in longer-dated nominal Treasury yields?'),
('0066','conditions eased','What three developments drove the easing in financial conditions?'),
('0115','Staff models suggested','What did staff models identify as the main explanation for lower short-term yields?'),
('0081','at longer maturities','What accounted for higher Treasury yields at longer maturities?'),
('0077','Despite the ongoing','Why was ON RRP take-up largely steady despite balance sheet runoff?'),
('0072','Financial conditions eased','What mainly accounted for the modest easing in financial conditions?'),
('0011','effective federal funds rate','Why had repo rates edged higher during the intermeeting period?'),
('0006','Nominal Treasury yields declined','What drove the notable decline in nominal Treasury yields?'),
('0006','Broad equity prices also rose','What likely contributed to the rise in broad equity prices?'),
('0018','In the near term','Why did the manager expect ON RRP volumes to rise in the near term?'),
('0098','baseline projection for inflation','Why were risks to the staff baseline inflation projection seen as tilted upward?'),
('0048','Inflation in 2025','Why did staff forecast inflation in 2025 above the previous year rate?'),
('0055','The staff projection','Why was the staff GDP growth projection for 2025 and 2026 weaker than in March?'),
('0050','The staff projection','Why was the staff GDP growth projection higher than in May?'),
('0018','Valuations of the','What mainly drove S&P 500 valuations further above long-run averages?'),
('0012','Near-term expectations','Why had near-term policy rate expectations moved lower?'),
('0018','The manager also noted','Why might further reductions in the SOMA portfolio prove short lived?'),
('0019','In light of','What conditions and objective supported starting reserve management purchases that month?'),
]

def read(path):
    return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]

def sentences(text):
    return re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)

def build():
    paragraphs = read(ROOT/'data/processed/paragraphs.jsonl')
    chunks = read(ROOT/'data/processed/chunks.jsonl')
    by_doc = collections.defaultdict(list)
    for p in paragraphs:
        by_doc[p['doc_id']].append(p)
    docs = sorted(by_doc)
    assert len(docs) == 40
    questions, facts = [], {}

    def proof(p, quote, eid='support'):
        matches = [c['chunk_id'] for c in chunks if c['doc_id']==p['doc_id'] and quote in c['text']
                   and p['paragraph_id'] in c['paragraph_ids']]
        if not matches:
            raise ValueError(f"No chunk contains {p['paragraph_id']}: {quote}")
        return dict(evidence_id=eid, doc_id=p['doc_id'], paragraph_id=p['paragraph_id'],
                    page=p['page'], quote=quote, chunk_ids=matches, source_url=p['source_url'])

    def choose(doc, predicate):
        for p in by_doc[doc]:
            for s in re.split(r'(?<=;)\s+', '\n'.join(sentences(p['text']))):
                for s in s.split('\n'):
                    if not (predicate(p,s) and s.endswith(('.', ';'))):
                        continue
                    try:
                        return proof(p,s)
                    except ValueError:
                        continue
        raise ValueError(f'No suitable fact: {doc}')

    def add(question, kind, split, evidence, family=None, answer=None, **extra):
        qid=f'Q{len(questions)+1:03d}'
        q=dict(qid=qid, family_id=family or qid, question=question, type=kind, split=split,
               answerable=bool(evidence), reference_answer=answer or ' '.join(e['quote'] for e in evidence),
               evidence=evidence, validated=False, annotation_status='draft_pending_independent_review', **extra)
        questions.append(q)
        return q

    for i,doc in enumerate(docs):
        date=doc.removeprefix('FOMC_'); split='dev' if i%8 in (1,5) else 'test'
        rate=choose(doc, lambda p,s: 'target range for the federal funds rate' in s.replace('- ','')
                    and ('decided' in s.replace('- ','') or 'agreed' in s.replace('- ','')) and 'percent' in s
                    and ('Committee Policy' in p['section'] or 'Committee' in s))
        special=doc=='FOMC_2025-10-29'
        econ=choose(doc, lambda p,s: ('lack of the Employment Situation report' in s if special else
                    re.search(r'\bthe unemployment rate\b.{0,110}?\d',s.replace('- ',''),re.I) is not None
                    and any(month in s.replace('- ','') for month in ['January','February','March','April','May','June','July','August','September','October','November','December'])
                    and 'percent' in s.replace('- ','')))
        facts[doc]=(rate,econ)
        a=add(f'At the meeting ending {date}, what federal funds target range did the Committee decide on?',
              'factual',split,[rate],topic='policy_rate')
        b=add(('At the meeting ending 2025-10-29, which monthly Employment Situation report was unavailable, and what sources did participants use instead?' if special else
               f'In the minutes of the meeting ending {date}, what national unemployment rate was reported, and for which month?'),
              'factual',split,[econ],topic='unemployment')
        parent=a if i%2==0 else b
        wording=(f'Which lower and upper bounds did the FOMC choose for its policy rate at the meeting ending {date}?'
                 if i%2==0 else f'Which month and US unemployment percentage are given in the minutes of the meeting ending {date}?')
        add(wording,'paraphrase',split,parent['evidence'],family=parent['family_id'],
            answer=parent['reference_answer'],paraphrase_of=parent['qid'],topic=parent['topic'])
        suffix,cue,wording=EXPLANATIONS[i]
        p=next(p for p in by_doc[doc] if p['paragraph_id']==f'{doc}_P{suffix}')
        quote=next(s for s in sentences(p['text']) if cue.lower() in s.lower())
        add(f'According to the minutes of the meeting ending {date}: {wording}',
            'explanatory',split,[proof(p,quote)],topic='causal_explanation')

    for year in range(5):
        group=docs[year*8:year*8+8]
        test=[d for j,d in enumerate(group) if j not in (1,5)]
        pairs=[('dev',group[1],group[5])]+[('test',a,b) for a,b in zip(test,test[1:])]
        for k,(split,a,b) in enumerate(pairs):
            metric=0 if 'FOMC_2025-10-29' in (a,b) else (year+k)%2
            evidence=[dict(facts[d][metric],evidence_id=f'meeting_{n}') for n,d in enumerate((a,b),1)]
            dates=[d.removeprefix('FOMC_') for d in (a,b)]
            wording=(f'Compare the federal funds target ranges chosen at the meetings ending {dates[0]} and {dates[1]}. Give both ranges.'
                     if metric==0 else f'Compare the national unemployment rates reported in the minutes for the meetings ending {dates[0]} and {dates[1]}. Give each rate and its observation month.')
            answer='\n'.join(f"{d}: {e['quote']}" for d,e in zip(dates,evidence))
            add(wording,'comparative',split,evidence,answer=answer,topic='policy_rate' if metric==0 else 'unemployment')
        add(f'According to the supplied minutes from {2021+year}, what target range did the FOMC choose at its first meeting in {2030+year}?',
            'unanswerable','dev',[],absence_reason='The supplied corpus covers meetings in 2021–2025; it does not contain this future meeting.',
            absence_scope='outside_corpus_dates')
        missing=[
            'Give the complete list of transaction identifiers for every individual Treasury purchase made by the New York Fed Desk.',
            'Give the full names and individual allotments of every private counterparty to each overnight reverse repo operation.',
            'Give the exact numerical recession probability privately assigned by each named FOMC participant.',
            'Give every individual household-level observation used to calculate the unemployment rates discussed.',
            'Give the complete order-by-order trade blotter underlying the reported Treasury market movements.'
        ][year]
        add(f'Using only the supplied minutes from {2021+year}: {missing}',
            'unanswerable','test',[],absence_reason='The minutes contain aggregate discussion, not the requested exhaustive microdata or private individual records.',
            absence_scope='granularity_not_in_minutes')

    out=ROOT/'evaluation'; out.mkdir(exist_ok=True)
    for name,rows in [('questions_200_draft',questions),('dev_50_draft',[q for q in questions if q['split']=='dev']),
                      ('test_150_draft',[q for q in questions if q['split']=='test'])]:
        (out/f'{name}.jsonl').write_text(''.join(json.dumps(q,ensure_ascii=False)+'\n' for q in rows),encoding='utf-8')
    with (out/'questions_200_index.csv').open('w',encoding='utf-8-sig',newline='') as f:
        fields=['qid','family_id','split','type','question','answerable','reference_answer']
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); writer.writeheader(); writer.writerows(questions)
    lines=['# 200 propositions de questions — revue des preuves',
           '50 développement / 150 test. Questions en anglais comme les rapports et le modèle E5 utilisé.',
           '**Statut : propositions, pas encore validées humainement.** Les réponses proposées reprennent les citations pour éviter des ajouts non justifiés.',
           'Pour chaque question : vérifier la clarté, la réponse, les pages et les passages pertinents supplémentaires. Les mois des statistiques peuvent différer des dates des réunions.',
           'Les questions sans réponse le sont relativement au corpus fourni. Leur absence doit aussi être confirmée en revue humaine.']
    for q in questions:
        lines += [f"\n## {q['qid']} · {q['split']} · {q['type']} · famille {q['family_id']}",q['question'],
                  '\n**Réponse proposée :** '+(q['reference_answer'] or 'Absente du corpus.'),
                  '\n- [ ] Clarté et portée vérifiées\n- [ ] Réponse et preuves vérifiées\n- [ ] Autres passages pertinents recherchés']
        for e in q['evidence']:
            pdf=f"../data/raw/minutes/fomcminutes{e['doc_id'][5:].replace('-','')}.pdf#page={e['page']}"
            lines += [f"\n**Preuve {e['evidence_id']}** : [{e['doc_id']}, page PDF {e['page']}]({pdf}) · [source officielle]({e['source_url']}#page={e['page']})",
                      '> '+e['quote'], '\nPassages : '+', '.join(e['chunk_ids'])]
        if not q['answerable']: lines += ['\n**Motif :** '+q['absence_reason']]
    (out/'questions_200_review.md').write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    report=audit(questions,paragraphs,chunks)
    (out/'questions_200_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return report

def audit(questions, paragraphs, chunks):
    counts=collections.Counter(q['type'] for q in questions)
    assert counts==dict(factual=80,paraphrase=40,explanatory=40,comparative=30,unanswerable=10)
    assert collections.Counter(q['split'] for q in questions)==dict(dev=50,test=150)
    assert len({q['qid'] for q in questions})==200
    assert len({q['question'] for q in questions})==200
    families=collections.defaultdict(set); documents=collections.defaultdict(set)
    pmap={p['paragraph_id']:p for p in paragraphs}; cmap={c['chunk_id']:c for c in chunks}
    proofs=0
    pdf_pages={}
    import pymupdf
    def normalized_pdf(text):
        return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD',text).lower())
    for q in questions:
        assert q['validated'] is False
        families[q['family_id']].add(q['split'])
        if q['type']=='comparative': assert len({e['doc_id'] for e in q['evidence']})==2
        for e in q['evidence']:
            p=pmap[e['paragraph_id']]
            assert e['quote'] in p['text'] and e['page']==p['page']
            assert e['chunk_ids']
            key=(e['doc_id'],e['page'])
            if key not in pdf_pages:
                path=ROOT/'data/raw/minutes'/f"fomcminutes{e['doc_id'][5:].replace('-','')}.pdf"
                with pymupdf.open(path) as pdf:
                    pdf_pages[key]=normalized_pdf(pdf[e['page']-1].get_text())
            assert normalized_pdf(e['quote']) in pdf_pages[key], f"PDF evidence mismatch: {q['qid']}"
            for cid in e['chunk_ids']:
                assert e['quote'] in cmap[cid]['text'] and cmap[cid]['doc_id']==e['doc_id']
            documents[q['split']].add(e['doc_id']); proofs+=1
    assert all(len(s)==1 for s in families.values())
    assert not documents['dev'] & documents['test']
    assert len(documents['dev']|documents['test'])==40
    return dict(questions=200,types=dict(counts),splits=dict(collections.Counter(q['split'] for q in questions)),
                proof_groups_checked=proofs,original_pdf_pages_checked=len(pdf_pages),pdf_quote_failures=0,
                documents_covered=40,families=len(families),
                cross_split_families=0,cross_split_evidence_documents=0,
                checks='Exact quotes in paragraphs/chunks; alphanumeric-normalized quotes on original physical PDF pages; document IDs and page metadata. Normalization ignores punctuation and PDF word-break hyphens.',
                limitations=['Independent human review pending.','No claim of exhaustive relevance judgments.',
                             'Unanswerability requires independent corpus review.','Rate and unemployment comparisons are deliberately controlled; broader economic diversity can be added after review.'],
                chunks_sha256=hashlib.sha256((ROOT/'data/processed/chunks.jsonl').read_bytes()).hexdigest(),
                questions_sha256=hashlib.sha256((ROOT/'evaluation/questions_200_draft.jsonl').read_bytes()).hexdigest())

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(build(),ensure_ascii=False,indent=2))
