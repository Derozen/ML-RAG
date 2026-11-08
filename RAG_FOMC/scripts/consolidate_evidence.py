"""Versioned, source-grounded relevance revision; never edits the v1 gold file."""
from collections import defaultdict
from copy import deepcopy
import argparse
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rag_fomc.common import read_jsonl, write_jsonl, write_json, sha256

MONTHS='January February March April May June July August September October November December'.split()
# Current observed national rate/month, checked against each original factual answer.
OBSERVATIONS=[('6.7','December'),('6.2','February'),('6','March'),('5.8','May'),
 ('5.9','June'),('5.2','August'),('4.8','September'),('4.2','November'),
 ('3.9','December'),('3.8','February'),('3.6','March'),('3.6','May'),
 ('3.6','June'),('3.7','August'),('3.5','September'),('3.7','November'),
 ('3.5','December'),('3.6','February'),('3.5','March'),('3.7','May'),
 ('3.6','June'),('3.8','August'),('3.8','September'),('3.7','November'),
 ('3.7','December'),('3.9','February'),('3.8','March'),('4.0','May'),
 ('4.1','June'),('4.2','August'),('4.1','October'),('4.2','November'),
 ('4.1','December'),('4.1','February'),('4.2','April'),('4.2','May'),
 ('4.1','June'),('4.3','August'),(None,None),('4.4','September')]

def canonical_with_offsets(text):
    chars=[]; offsets=[]; skip=set()
    for m in re.finditer(r'(?<=\w)[-\u00ad]\s+(?=\w)',text): skip.update(range(m.start(),m.end()))
    for i,ch in enumerate(text):
        if i in skip: continue
        ch=ch.lower().replace('\u2019',"'").replace('\u2011','-')
        if ch.isspace():
            if chars and chars[-1]!=' ': chars.append(' '); offsets.append(i)
        else: chars.append(ch); offsets.append(i)
    return ''.join(chars),offsets

def canonical(text): return canonical_with_offsets(text)[0].strip()

def literal_match(haystack,needle):
    clean,offsets=canonical_with_offsets(haystack)
    start=clean.find(canonical(needle))
    if start<0: return None
    return haystack[offsets[start]:offsets[start+len(canonical(needle))-1]+1]

def sentences(text):
    for m in re.finditer(r'.+?(?:[.!?](?=\s+[A-Z]|$)|$)',text,re.S):
        if m.group().strip(): yield m.group().strip()

def make_catalog():
    qs=read_jsonl(ROOT/'evaluation/questions.jsonl')
    paragraphs=read_jsonl(ROOT/'data/processed/paragraphs.jsonl')
    chunks=read_jsonl(ROOT/'data/processed/chunks.jsonl')
    bydoc=defaultdict(list)
    for p in paragraphs: bydoc[p['doc_id']].append(p)
    rows=[]; seen=set()
    for index,q in enumerate([q for q in qs if q['type']=='factual']):
        e=q['evidence'][0]; doc=e['doc_id']; policy=q['topic']=='policy_rate'
        if policy:
            bounds=re.search(r'(?:at|to) ([\d¼½¾ ]+) to ([\d¼½¾ ]+) percent',canonical(e['quote']))
            assert bounds, q['qid']
            target=tuple(v.strip() for v in bounds.groups())
        else: value,month=OBSERVATIONS[index//2]
        for p in bydoc[doc]:
            for sentence in sentences(p['text']):
                clean,mapping=canonical_with_offsets(sentence)
                quote=None
                if policy:
                    pattern=r'(?:target range for the federal funds rate|federal funds rate in a target range).{0,110}?([\d¼½¾]+(?: [¼½¾])?) to ([\d¼½¾]+(?: [¼½¾])?) percent'
                    for m in re.finditer(pattern,clean):
                        if tuple(v.strip() for v in m.groups())==target:
                            quote=sentence[:mapping[m.end()-1]+1].strip(); break
                elif value:
                    m=re.search(r'\bthe unemployment rate\b',clean)
                    if m and month.lower() in clean and any(abs(float(v)-float(value))<1e-8 for v in re.findall(r'(\d+(?:\.\d+)?) percent',clean[m.end():])):
                        quote=sentence
                if quote and len(quote)<1600 and (q['qid'],quote) not in seen:
                    matches=[c['chunk_id'] for c in chunks if c['doc_id']==doc and literal_match(c['text'],quote)]
                    if not matches: continue
                    seen.add((q['qid'],quote))
                    rows.append(dict(candidate_id=f'A{len(rows)+1:03}',base_qid=q['qid'],doc_id=doc,
                        topic=q['topic'],paragraph_id=p['paragraph_id'],page=p['page'],
                        quote=quote,context=p['text'],chunk_ids=matches,
                        decision='pending',reason='Candidate only; matching numbers do not establish relevance.'))
    out=ROOT/'evaluation/revision_v2'
    write_jsonl(out/'candidate_catalog.jsonl',rows)
    print(f'{len(rows)} source candidates written to {out}')

def build_revision():
    out=ROOT/'evaluation/revision_v2'
    original=read_jsonl(ROOT/'evaluation/questions.jsonl')
    catalog=read_jsonl(out/'candidate_catalog.jsonl')
    chunks=read_jsonl(ROOT/'data/processed/chunks.jsonl')
    paragraphs={p['paragraph_id']:p for p in read_jsonl(ROOT/'data/processed/paragraphs.jsonl')}
    bydoc=defaultdict(list)
    for c in chunks: bydoc[c['doc_id']].append(c)
    # Explicit decisions after reading all 186 candidate excerpts. Not human validation.
    pending={'A143':'Page-break fragment starts with "lower"; actor/context needs independent review.'}
    contextual=set('A033 A037 A073 A082 A087 A092 A097 A102 A107 A112 A117 A122 A127 A132 A138 A149 A153 A159 A164 A169'.split())
    assert sha256(out/'candidate_catalog.jsonl')=='4020574cd49198e803a65eecce2465876ae6bee149906024cd0f25202c310495', 'Candidate texts changed: redo semantic decisions.'
    assert len(catalog)==186 and catalog[-1]['candidate_id']=='A186', 'Review decisions must be redone if catalog changes.'
    additions=defaultdict(list)
    for r in catalog:
        if r['candidate_id'] in pending:
            r.update(decision='pending_context',reason=pending[r['candidate_id']])
        elif r['candidate_id'] in contextual:
            r.update(decision='context_only_not_added',reviewer='assistant',
                     reason='Participants support or judge an action appropriate; not a standalone statement of the adopted Committee decision. Existing v1 proofs are retained separately.')
        else:
            r.update(decision='accepted_by_assistant',reviewer='assistant',
                     reason=('Same meeting, explicit adopted target or implementation instruction with identical bounds; no future projection.'
                             if r['topic']=='policy_rate' else 'Same national unemployment observation and month as reference; alternative wording.'))
            if r['candidate_id']=='A142':
                r['quote']=r['quote'].split(';')[0]+';'
                r['reason']+=' Incomplete unrelated continuation after semicolon omitted.'
            additions[r['base_qid']].append(r)
    write_jsonl(out/'candidate_decisions.jsonl',catalog)
    base={q['qid']:q for q in original}
    registry={}
    provenance=[]
    pdf_cache={}
    import pymupdf
    def norm_pdf(s):
        import unicodedata
        return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',s).lower())
    def source_variant(doc,c,quote):
        actual=literal_match(c['text'],quote)
        if actual is None: return None
        matching=[paragraphs[pid] for pid in c['paragraph_ids'] if literal_match(paragraphs[pid]['text'],actual)]
        if not matching: return None
        p=matching[0]; key=(doc,p['page'])
        if key not in pdf_cache:
            with pymupdf.open(ROOT/'data/raw/minutes'/f"fomcminutes{doc[5:].replace('-','')}.pdf") as pdf:
                pdf_cache[key]=norm_pdf(pdf[p['page']-1].get_text())
        if norm_pdf(actual) not in pdf_cache[key]: return None
        return dict(chunk_id=c['chunk_id'],quote=actual,paragraph_id=p['paragraph_id'],page=p['page'],source_url=p['source_url'])

    # Register the original proof once; all derived comparisons and paraphrases reuse it.
    for q in original:
        if q['type'] not in ('factual','explanatory'): continue
        e=q['evidence'][0]; key=(e['doc_id'],e['quote'])
        revised=deepcopy(e); revised['quotes_by_chunk']={cid:e.get('quotes_by_chunk',{}).get(cid,e['quote']) for cid in e['chunk_ids']}
        revised['sources_by_chunk']={}
        candidates=[dict(candidate_id='original',quote=e['quote'],reason='Existing user-validated proof retained.')]+additions[q['qid']]
        # Exact causal clauses are re-searched over the WHOLE source document, not just retrieved candidates.
        if q['type']=='explanatory' and ';' in e['quote']:
            candidates.append(dict(candidate_id='causal_clause',quote=e['quote'].split(';')[0],
                                   reason='Complete original causal clause; unrelated post-semicolon consequence omitted.'))
        for candidate in candidates:
            for c in bydoc[e['doc_id']]:
                v=source_variant(e['doc_id'],c,candidate['quote'])
                if not v: continue
                cid=c['chunk_id']
                if cid not in revised['chunk_ids']: revised['chunk_ids'].append(cid)
                if cid not in revised['sources_by_chunk']:
                    revised['quotes_by_chunk'][cid]=v['quote']; revised['sources_by_chunk'][cid]=v
                    provenance.append(dict(base_qid=q['qid'],candidate_id=candidate['candidate_id'],
                        **v,reason=candidate['reason'],reviewer='assistant',
                        previous_accepted=cid in e['chunk_ids']))
        revised['chunk_ids']=sorted(revised['chunk_ids'])
        assert all(cid in revised['sources_by_chunk'] for cid in revised['chunk_ids']),q['qid']
        registry[key]=revised
    revised_questions=deepcopy(original); changes=[]
    for q in revised_questions:
        q['original_validation']={k:q.get(k) for k in ('validated','annotation_status','validation_date','validation_source')}
        q.update(validated=False,annotation_status='assistant_consolidated_pending_independent_review')
        q.pop('validation_date',None); q.pop('validation_source',None)
        for e in q['evidence']:
            r=registry[(e['doc_id'],e['quote'])]
            old=set(e['chunk_ids']); eid=e['evidence_id']
            e.update(deepcopy(r)); e['evidence_id']=eid
            changes.append(dict(qid=q['qid'],evidence_id=eid,old_chunk_count=len(old),
                                new_chunk_count=len(e['chunk_ids']),added_chunk_ids=sorted(set(e['chunk_ids'])-old)))
    for q in revised_questions:
        if q['type']=='paraphrase': assert q['evidence']==next(p for p in revised_questions if p['qid']==q['paraphrase_of'])['evidence']
    write_jsonl(out/'questions_consolidated.jsonl',revised_questions)
    write_jsonl(out/'source_provenance.jsonl',provenance)
    write_jsonl(out/'changes.jsonl',changes)
    # Blind pool: one row for every unique question/chunk in the union, method/rank kept separately.
    pools={}; origins=defaultdict(list)
    for split in ('dev','test'):
        for r in read_jsonl(ROOT/f'results/comparison_200_v1/{split}/rankings.jsonl'):
            key=(r['qid'],r['chunk_id']); pools[key]=r
            origins[key].append(dict(method=r['method'],rank=r['rank']))
    review=[]; method_key=[]
    for i,(key,r) in enumerate(sorted(pools.items()),1):
        q=next(q for q in revised_questions if q['qid']==r['qid'])
        accepted=any(r['chunk_id'] in e['chunk_ids'] for e in q['evidence'])
        docs={e['doc_id'] for e in q['evidence']}
        state=('accepted_by_assistant' if accepted else 'pending_same_document' if r['doc_id'] in docs
               else 'pending_absence_review' if not q['answerable'] else 'unjudged_other_document')
        row=dict(review_id=f'R{i:05}',qid=q['qid'],family_id=q['family_id'],split=q['split'],question=q['question'],
                 reference_answer=q.get('reference_answer'),chunk_id=r['chunk_id'],doc_id=r['doc_id'],
                 page_start=r['page_start'],page_end=r['page_end'],text=r['text'],decision=state)
        review.append(row); method_key.append(dict(review_id=row['review_id'],origins=origins[key]))
    write_jsonl(out/'pool_blind.jsonl',review); write_jsonl(out/'pool_method_key.jsonl',method_key)
    counts=dict(__import__('collections').Counter(r['decision'] for r in review))
    write_json(out/'annotations.json',dict(schema_version=2,status='assistant_reviewed_not_human_validated',
        questions_sha256=sha256(out/'questions_consolidated.jsonl'),chunks_sha256=sha256(ROOT/'data/processed/chunks.jsonl'),
        original_questions_sha256=sha256(ROOT/'evaluation/questions.jsonl'),
        original_annotations_sha256=sha256(ROOT/'evaluation/annotations.json'),
        candidate_decisions_sha256=sha256(out/'candidate_decisions.jsonl'),
        source_variants=len(provenance),physical_pdf_pages_checked=len(pdf_cache),
        questions_with_added_chunks=sum(any(c['added_chunk_ids'] for c in changes if c['qid']==q['qid']) for q in original),
        added_question_group_chunk_links=sum(len(c['added_chunk_ids']) for c in changes),
        pool_unique_pairs=len(review),pool_decisions=counts,
        pending_candidate_ids=list(pending),
        contextual_candidates_not_added=sorted(contextual),
        methodology='Whole-source-document literal/norm-equivalent search plus assistant-reviewed factual alternatives; method-blind pool exported.',
        limitations=['No claim of exhaustive relevance judgments.','Independent review of additions and pending pool still required.',
                     'Negative questions kept unchanged; no abstention model trained.','Rescoring historical rankings is a revised analysis, not an independent test.']))
    lines=['# Relecture des preuves consolidées (version 2)',
           '**Statut : revue par l’assistant, validation humaine des ajouts en attente.** Les fichiers v1 ne sont pas remplacés.',
           'Les citations sont recherchées dans tous les passages du document source, pas uniquement dans les classements. Les variantes factuelles ont été lues avant ajout ; chaque citation est contrôlée dans le chunk, le paragraphe et la page PDF.',
           'Les candidats du pool sans décision restent à examiner. Un passage non accepté n’est pas automatiquement non pertinent. Les questions sans réponse conservent leurs motifs initiaux, sans nouvelle certification d’absence.']
    for q in revised_questions:
        lines += [f"\n## {q['qid']} | {q['type']} | {q['split']} | famille {q['family_id']}",q['question'],
                  '\nRéponse initiale conservée : '+(q.get('reference_answer') or 'Sans réponse dans le corpus.'),
                  '\n- [ ] Ajouts et groupes vérifiés\n- [ ] Autres preuves suffisantes recherchées']
        if not q['answerable']: lines.append(q['absence_reason'])
        for e in q['evidence']:
            lines += [f"\n### Groupe {e['evidence_id']} : {e['doc_id']}"]
            old=set(next(p for p in original if p['qid']==q['qid'])['evidence'][q['evidence'].index(e)]['chunk_ids'])
            for cid in e['chunk_ids']:
                s=e['sources_by_chunk'][cid]; date=e['doc_id'][5:].replace('-','')
                lines += [f"\n**{cid}** ({'ajout' if cid not in old else 'initial'}) · [PDF p. {s['page']}](../../data/raw/minutes/fomcminutes{date}.pdf#page={s['page']})",
                          '> '+e['quotes_by_chunk'][cid]]
    (out/'RELECTURE.md').write_text('\n\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(json.loads((out/'annotations.json').read_text(encoding='utf-8')),ensure_ascii=False,indent=2))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(); parser.add_argument('stage',choices=['catalog','build'])
    args=parser.parse_args()
    make_catalog() if args.stage=='catalog' else build_revision()
