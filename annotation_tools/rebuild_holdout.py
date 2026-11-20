"""Prepare annotation artifacts only. Never invokes the frozen retrieval/reranking models."""
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from itertools import combinations
from pathlib import Path
import csv
import hashlib
import json
import re
import sys
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from common import read_json,read_jsonl,write_json,write_jsonl,write_csv,digest
from protocol import verify,LOCK


def canonical(text):
    return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',text).casefold())


def tokens(text):
    return set(re.findall(r'[a-z0-9]+',text.lower()))


def main():
    verify()
    output=ROOT/'data/holdout_candidate'
    output.mkdir(exist_ok=True)
    for filename,fields in [('human_review.csv',('human_grade','reviewer')),('semantic_pairs_145.csv',('human_semantic_verdict','reviewer'))]:
        path=output/filename
        if path.exists():
            with path.open(encoding='utf-8-sig',newline='') as stream:
                if any(any(row.get(field,'').strip() for field in fields) for row in csv.DictReader(stream)):
                    raise ValueError('Human review already entered; archive a version before regeneration')
    plan=read_json(Path(__file__).with_name('holdout_v2_plan.json'))
    editorial=read_json(Path(__file__).with_name('editorial_page_review.json'))
    old=read_jsonl(ROOT/'data/evaluation/queries_145.jsonl')
    old_by_id={q['question_id']:q for q in old}
    manifest=read_json(ROOT/'data/processed/manifest.json')
    documents={d['filename']:d for d in manifest}
    for doc in manifest:
        if digest(ROOT/doc['path'])!=doc['sha256']:raise ValueError('Source PDF changed since extraction')
    paragraphs=read_jsonl(ROOT/'data/processed/paragraphs.jsonl')
    page_rows=defaultdict(list)
    for p in paragraphs:
        page_rows[f"{p['filename']}#p{p['page']}"].append(p)
    pages={pid:dict(filename=ps[0]['filename'],page=ps[0]['page'],
                   text='\n\n'.join(p['text'] for p in ps),paragraphs=ps)
           for pid,ps in page_rows.items()}
    normalized={pid:canonical(page['text']) for pid,page in pages.items()}
    old_qrels=defaultdict(set)
    for line in (ROOT/'data/evaluation/silver_qrels_PAGES.trec').read_text().splitlines():
        qid,_,pid,_=line.split();old_qrels[qid].add(pid)
    queries=[];evidence=[];judgments={};screening=[];semantic=[];pairs=[];human=[];missing=[]
    facets_covered=0;scope_total=0
    for item in plan:
        qid=item['id'];scope=set(item['documents'])
        if not scope<=set(documents):raise ValueError('Unknown scope document')
        support=defaultdict(list);grades={};facet_pages={};scope_total+=sum(p['filename'] in scope for p in pages.values())
        for facet in item['facets']:
            targets=set(facet.get('files',scope))
            hits=[]
            for pid,page in pages.items():
                if page['filename'] not in targets:continue
                if not all(canonical(needle) in normalized[pid] for needle in facet['needles']):continue
                snippets=[]
                for p in page['paragraphs']:
                    found=[needle for needle in facet['needles'] if canonical(needle) in canonical(p['text'])]
                    if found:snippets.append(dict(paragraph_id=p['paragraph_id'],quote=p['text'],matched_fragments=found,
                                                   source_sha256=p['source_sha256']))
                support[pid].append(dict(facet=facet['name'],snippets=snippets))
                grades[pid]=2
                hits.append(pid)
            facet_pages[facet['name']]=hits
            if not hits:missing.append(dict(question_id=qid,facet=facet))
            else:facets_covered+=1
        if item.get('absence_check'):
            absence=item['absence_check']
            if any(canonical(absence['term']) in normalized[pid] for pid,p in pages.items() if p['filename'] in absence['documents']):
                raise ValueError('Explicit absence check failed')
        for decision in editorial:
            if decision['question_id']!=qid:continue
            pid=decision['page_id']
            if pid in grades or pid not in pages or pages[pid]['filename'] not in scope:
                raise ValueError('Invalid or contradictory editorial decision')
            wanted=set(decision['paragraph_ids'])
            ps=[p for p in pages[pid]['paragraphs'] if p['paragraph_id'] in wanted]
            if {p['paragraph_id'] for p in ps}!=wanted:raise ValueError('Wrong paragraph provenance in editorial decision')
            grades[pid]=decision['grade']
            support[pid].append(dict(facet='editorial_corroboration_or_distractor',reason=decision['reason'],
                snippets=[dict(paragraph_id=p['paragraph_id'],quote=p['text'],matched_fragments=[],source_sha256=p['source_sha256']) for p in ps]))
        for pid in pages:
            in_scope=pages[pid]['filename'] in scope
            full_hits=[facet['name'] for facet in item['facets'] if all(canonical(n) in normalized[pid] for n in facet['needles'])]
            partial_hits=[facet['name'] for facet in item['facets'] if any(canonical(n) in normalized[pid] for n in facet['needles'])]
            status='editorial_nonrelevant' if grades.get(pid)==0 else 'supported_page_proposed' if pid in grades else 'in_scope_unjudged' if in_scope else 'outside_declared_source_scope'
            screening.append(dict(question_id=qid,page_id=pid,in_scope=in_scope,status=status,
                complete_fragment_hits=full_hits,partial_fragment_hits=partial_hits,
                judgment=grades.get(pid),
                note='No score from frozen systems. Fragment absence is not a nonrelevance judgment.'))
            if in_scope:
                human.append(dict(question_id=qid,question=item['question'],page_id=pid,
                    proposed_grade=grades.get(pid,''),covered_facets='; '.join(x['facet'] for x in support.get(pid,[])),
                    annotation_status=status,human_grade='',reviewer='',notes=''))
        for pid,items in support.items():
            judgments[qid,pid]=grades[pid]
            evidence.append(dict(question_id=qid,page_id=pid,relevance=grades[pid],covered_facets=items,
                annotation_status='proposed_strong_support_for_at_least_one_atomic_facet; independent_human_review_pending',
                source_quote_verified=True))
        nearest=[]
        for q in old:
            a=tokens(item['question']);b=tokens(q['question']);jaccard=len(a&b)/len(a|b)
            ratio=SequenceMatcher(None,item['question'].lower(),q['question'].lower()).ratio()
            nearest.append((max(jaccard,ratio),q['question_id']))
            pairs.append(dict(new_question_id=qid,old_question_id=q['question_id'],
                old_question=q['question'],string_similarity=ratio,token_jaccard=jaccard,
                semantic_equivalence='related_not_equivalent_editorial_proposal' if q['question_id'] in item['related_old'] else 'not_established_by_lexical_screen',
                human_semantic_verdict='',reviewer=''))
        neighbors=[dict(question_id=oid,question=old_by_id[oid]['question'],screening_similarity=score)
                   for score,oid in sorted(nearest,reverse=True)[:5]]
        review=dict(question_id=qid,question=item['question'],expected_answer=item['answer'],
            related_old_questions=[dict(question_id=oid,question=old_by_id[oid]['question'],
                                        shared_reference_pages=sorted(old_qrels[oid]&set(support))) for oid in item['related_old']],
            lexical_neighbors=neighbors,editorial_review=item['novelty_review'],
            status='editorial_review_proposed; independent_human_semantic_validation_pending',
            high_priority=item['id'].endswith(('019','020','014')))
        semantic.append(review)
        queries.append(dict(question_id=qid,question=item['question'],question_type=item['task_group'],
            source_scope=item['source_scope'],topic=item['topic'],split='future_test_candidate',
            group_ids=sorted({documents[name]['meeting_end'] for name in scope}),
            source_documents=item['documents'],status='pending_independent_human_annotation_validation',
            facet_page_ids=facet_pages,expected_answer=item['answer'],derivation=item.get('derivation')))
    if missing:
        write_json(output/'missing_facets.json',missing)
        raise ValueError(f'{len(missing)} evidence facets missing; no dataset published')
    if len(queries)!=20 or len({q['question_id'] for q in queries})!=20:raise ValueError('20 unique questions required')
    if any(canonical(q['question'])==canonical(p['question']) for q in queries for p in old):raise ValueError('Exact old question duplicate')
    write_jsonl(output/'queries_20.jsonl',[{k:v for k,v in q.items() if k not in ('expected_answer','derivation','facet_page_ids')} for q in queries])
    write_jsonl(output/'question_gold.jsonl',[{k:q[k] for k in ('question_id','expected_answer','derivation','facet_page_ids')} for q in queries])
    write_jsonl(output/'evidence_20.jsonl',evidence)
    (output/'qrels_PAGES_candidate.trec').write_text(''.join(f'{qid} 0 {pid} {g}\n' for (qid,pid),g in sorted(judgments.items())),encoding='utf-8')
    write_jsonl(output/'full_corpus_screening.jsonl',screening)
    write_jsonl(output/'semantic_review.jsonl',semantic)
    write_csv(output/'semantic_pairs_145.csv',pairs)
    write_csv(output/'human_review.csv',human)
    write_jsonl(output/'within_holdout_pairs.jsonl',[
        dict(question_a=a['question_id'],question_b=b['question_id'],shared_documents=sorted(set(a['source_documents'])&set(b['source_documents'])),
             token_jaccard=len(tokens(a['question'])&tokens(b['question']))/len(tokens(a['question'])|tokens(b['question'])),
             note='Related source groups must remain in the same future test partition; human semantic review pending.')
        for a,b in combinations(queries,2)])
    lines=['# Lot candidat V2 — couverture diversifiée et annotation traçable','',
        'STATUT : non scoré, annotations proposées contrôlées dans les sources, validation humaine indépendante encore requise. Aucun résultat de Recall/MRR/nDCG n’a été calculé pour ce lot.', '',
        f"Composition : {dict(Counter(q['question_type'] for q in queries))}. Sources demandées : {dict(Counter(q['source_scope'] for q in queries))}.", '',
        'Le périmètre des documents fait partie de chaque question : une question demandant un Statement précis évalue la lecture de ce document, pas toute mention générique du même sujet. Les PDF de Statements incluent leurs notes de mise en œuvre. Les questions croisées exigent l’attribution correcte des informations. Plusieurs preuves ne signifient pas toujours plusieurs documents : le cas d’application 019 réutilise des règles dupliquées entre Minutes et Statement.', '',
        f"{len(pages)} pages du corpus ont été examinées par un écran documentaire pour chaque question, soit {len(screening)} couples. Cela n’équivaut pas à {len(screening)} jugements humains. Les pages sans preuve approuvée restent NON JUGÉES. Le fichier human_review.csv expose toutes les pages du périmètre demandé, y compris celles à revoir.", '',
        f"{sum(g>0 for g in judgments.values())} qrels positifs proposés couvrent {facets_covered} facettes ; {sum(g==0 for g in judgments.values())} jugements non pertinents explicitement motivés sont également conservés. Grade 2 : preuve explicite forte d’au moins une facette nécessaire ; grade 1 : soutien partiel ou corroboration contextuelle ; grade 0 : page examinée éditorialement mais ne répondant pas à la question ciblée. Une page n’a pas à répondre seule à toute une comparaison pour être fortement pertinente. Aucun grade zéro n’a été déduit de la seule absence de mots-clés.", '',
        'Les extraits et les réponses attendues ont été relus éditorialement. La recherche de variantes repose ici sur les fragments de preuve et le périmètre documentaire ; elle peut manquer des paraphrases pertinentes. L’exhaustivité des qrels n’est donc pas revendiquée. Les métriques finales devront porter sur une version approuvée, avec cette limite documentée.', '',
        '## Contrôle sémantique','',
        'Les 145 questions ont été examinées par rapport à l’information demandée. semantic_review.jsonl expose les cas liés, les voisins lexicaux et les différences de réponse ; semantic_pairs_145.csv contient les 2 900 couples à disposition du relecteur. Une similarité de chaînes n’est pas un test d’équivalence sémantique. Les questions 014, 019 et 020 demandent une vigilance particulière sur le recouvrement d’informations avec les anciens exemples. Une première proposition 017 sur achats/réinvestissements a été retirée par prudence et remplacée par une question d’attribution de votes distincts ; annotation_tools/rejected_questions.json en conserve la trace. L’indépendance statistique des sujets issus du même corpus n’est pas établie.', '',
        'Les réponses attendues et les pages de référence sont séparées des questions dans question_gold.jsonl. Les futurs systèmes ne doivent recevoir que le champ question ; les qrels, extraits et réponses servent uniquement à l’évaluation et à la revue.', '',
        '## Validation à effectuer','',
        'Lire les preuves ci-dessous, puis les autres pages du périmètre dans human_review.csv ; ajouter les pages pertinentes manquantes, indiquer les grades 0/1/2 après lecture et signer les jugements. Pour chaque question, approuver ou rejeter son équivalence avec les questions liées et les voisins proposés. Si une question réutilise substantiellement une ancienne réponse, la remplacer avant tout score. Les cases sont laissées vides pour une vraie seconde lecture, pas préremplies comme une approbation.', '',
        'Après adjudication, versionner les questions et qrels, vérifier le gel puis évaluer une seule fois. Les variantes issues d’une même famille documentaire doivent rester dans le même lot. Ne pas ajuster le pipeline à partir de ces nouveaux résultats. Le lot de 145 questions reste inchangé et exploratoire.', '']
    by_q=defaultdict(list)
    for row in evidence:by_q[row['question_id']].append(row)
    reviews={row['question_id']:row for row in semantic}
    for q in queries:
        lines += [f"## {q['question_id']} — {q['question_type']} / {q['source_scope']}",'',q['question'],'',f"Réponse attendue : {q['expected_answer']}",'',
                  'Documents demandés : '+', '.join(q['source_documents']), '',
                  'Revue sémantique : '+reviews[q['question_id']]['editorial_review'],'',
                  'Anciennes questions liées : '+', '.join(x['question_id'] for x in reviews[q['question_id']]['related_old_questions']), '']
        for row in by_q[q['question_id']]:
            name,page=row['page_id'].rsplit('#p',1);path=documents[name]['path'].replace('\\','/')
            relative=Path(path).relative_to('data').as_posix()
            lines += [f"### [{row['page_id']}](../{relative}#page={page}) — grade proposé {row['relevance']}",'']
            seen=set()
            for facet in row['covered_facets']:
                lines += ['Facette : '+facet['facet'],'']
                if facet.get('reason'):lines += ['Motif du jugement : '+facet['reason'],'']
                for snippet in facet['snippets']:
                    if snippet['paragraph_id'] not in seen:
                        lines += ['> '+snippet['quote'],''];seen.add(snippet['paragraph_id'])
        lines += ['Seconde lecture humaine : **à compléter**.','']
    (output/'REVUE_HUMAINE.md').write_text('\n'.join(lines),encoding='utf-8')
    report=dict(version=2,status='DIVERSIFIED_ANNOTATED_CANDIDATE_UNSCORED_PENDING_SECOND_REVIEW',
        questions=len(queries),task_groups=dict(Counter(q['question_type'] for q in queries)),
        source_scopes=dict(Counter(q['source_scope'] for q in queries)),
        corpus_pages_screened=len(pages),screened_question_page_pairs=len(screening),
        in_scope_page_pairs=scope_total,positive_qrels=sum(g>0 for g in judgments.values()),
        qrels_total=len(judgments),grade_counts=dict(Counter(judgments.values())),
        editorial_page_reviews=len(editorial),in_scope_unjudged_pairs=scope_total-len(judgments),evidence_facets=facets_covered,
        evidence_documents=len({pid.split('#p')[0] for _,pid in judgments}),
        evidence_document_types=dict(Counter(documents[pid.split('#p')[0]]['type'] for (_,pid),grade in judgments.items() if grade>0)),
        qrels_exhaustive=False,human_second_review_completed=False,
        semantic_independence_established=False,lexical_pairs_screened=len(pairs),
        evaluation_performed=False,frozen_protocol_sha256=digest(LOCK),
        annotation_method='Deterministic document-scope and evidence-fragment screen; editorial answer/related-question review; independent human adjudication pending. No frozen retrieval models called.',
        files={p.name:digest(p) for p in output.iterdir() if p.is_file() and p.name not in ('validation_report.json','missing_facets.json')})
    write_json(output/'validation_report.json',report)
    verify()
    print(json.dumps({key:report[key] for key in ('questions','task_groups','source_scopes','positive_qrels','evidence_facets','in_scope_page_pairs','status')},ensure_ascii=False))


if __name__=='__main__':main()
