"""Run real Streamlit smoke checks and preserve evidence; never score holdout.

AppTest executes the real app and retrieval models, without mocks. The HTTP check
confirms the local server responds, not pixel-perfect browser rendering.
"""
import argparse
import ast
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from protocol import verify, LOCK
from common import digest


def check_http(out):
    """Start and stop only the server owned by this check."""
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with (out / 'server.log').open('w', encoding='utf-8') as log:
        proc = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'app/streamlit_app.py',
                                 '--server.headless=true', '--server.address=127.0.0.1',
                                 f'--server.port={port}', '--browser.gatherUsageStats=false'],
                                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        try:
            deadline = time.monotonic()+45
            while True:
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health', timeout=1) as response:
                        health = response.read().decode()
                        assert response.status == 200 and health == 'ok'
                    break
                except OSError:
                    if time.monotonic() > deadline or proc.poll() is not None:
                        raise RuntimeError('Streamlit local server did not become healthy')
                    time.sleep(.3)
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=3) as response:
                assert response.status == 200
            return dict(health='ok', homepage_http=200, port=port)
        finally:
            proc.terminate()
            proc.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--generation', action='store_true', help='Also run one real structured Ollama response on an old dev query')
    parser.add_argument('--http-only', action='store_true', help='Only check the local HTTP server, without model loading')
    args = parser.parse_args()
    out = ROOT / 'results/delivery_verification'
    out.mkdir(exist_ok=True)
    path = out / ('streamlit_http.json' if args.http_only else 'streamlit_with_generation.json' if args.generation else 'streamlit_functional.json')
    report = dict(started_utc=datetime.now(timezone.utc).isoformat(),
                  frozen_protocol_sha256=digest(LOCK), tests=[],
                  new_holdout_scored=False, final_independent_test_executed=False,
                  browser_visual_layout_verified=False, real_retrieval_models=not args.http_only,
                  mocked_model_calls=False)

    def save():
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')

    def add(name, **details):
        report['tests'].append(dict(name=name, passed=True, **details))
        save()
        print('PASS ' + name, flush=True)

    save()
    try:
        verify()
        if args.http_only:
            add('real_streamlit_http_server', **check_http(out))
            report['status'] = 'passed'
            return
        files = [*ROOT.glob('src/*.py'), *ROOT.glob('app/*.py'), *ROOT.glob('scripts/*.py'), *ROOT.glob('tests/*.py'), ROOT / 'run.py']
        for f in files:
            ast.parse(f.read_text(encoding='utf-8-sig'), filename=str(f))
        add('python_syntax', files=len(files))
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(ROOT / 'app/streamlit_app.py'), default_timeout=360)
        at.run(timeout=120)
        assert not at.exception, [e.value for e in at.exception]
        assert at.selectbox(key='context_k').value == 6
        assert at.selectbox(key='search_mode').value == 'classic'
        add('streamlit_startup', default_context=6, default_mode='classic')

        def submit(timeout=360):
            buttons = [b for b in at.button if b.label.startswith('Search')]
            assert len(buttons) == 1
            buttons[0].click().run(timeout=timeout)
            assert not at.exception, [e.value for e in at.exception]

        at.toggle(key='use_llm').set_value(False).run()
        at.text_input(key='question').set_value('')
        submit()
        assert any('enter a question' in e.value.lower() for e in at.error)
        add('empty_question_guard')
        qs = [json.loads(l) for l in (ROOT / 'data/evaluation/queries_145.jsonl').read_text(encoding='utf-8').splitlines()]
        query = next(q for q in qs if q['question_id'] == 'FOMC_003')
        assert query['split'] == 'dev'
        expected = next(json.loads(l) for l in (ROOT / 'results/context_top6/contexts.jsonl').read_text(encoding='utf-8').splitlines()
                        if json.loads(l)['question_id'] == query['question_id']
                        and json.loads(l)['retrieval'] == 'hybrid_rrf' and json.loads(l)['reranker'] == 'colbert')
        runs = {}
        for budget in (6, 5):
            at.selectbox(key='search_mode').select('classic')
            at.selectbox(key='retrieval_method').select('hybrid_rrf')
            at.selectbox(key='reranker_method').select('colbert')
            at.selectbox(key='context_k').select(budget)
            at.text_input(key='question').set_value(query['question'])
            submit()
            assert not at.error, [e.value for e in at.error]
            run = at.session_state['rag_result']
            passages = run['passages']
            assert len(passages) == budget and [p['rank'] for p in passages] == list(range(1, budget+1))
            assert len({p['chunk_id'] for p in passages}) == budget
            assert [p['chunk_id'] for p in passages] == expected['chunk_ids'][:budget]
            assert all(p['text'] and p['pages'] and p['source_url'].startswith('https://www.federalreserve.gov/') for p in passages)
            assert len(at.get('download_button')) >= 2
            runs[str(budget)] = run
            add(f'real_classic_rrf_colbert_top{budget}', question_id=query['question_id'],
                chunk_ids=[p['chunk_id'] for p in passages], timings=run['timings'],
                matches_existing_benchmark=True, selected_passages=budget)
        at.button(key='detailed_scores').click().run(timeout=180)
        assert not at.exception and not at.error, [e.value for e in at.error]
        assert at.session_state['rag_explanation'] is not None
        add('real_explainability_panel')
        # No date in this dev query: forced temporal mode must fall back safely.
        at.selectbox(key='search_mode').select('temporal')
        submit()
        assert not at.error
        assert at.session_state['rag_result']['mode'] == 'classic'
        # launch() warns and then st.rerun() clears transient messages. Inspect
        # the persisted actual mode rather than requiring that warning to remain.
        add('temporal_fallback_without_period', persisted_mode='classic',
            transient_warning_visible_after_rerun=any('not suitable' in w.value for w in at.warning))
        if args.generation:
            old = next(q for q in qs if q['question_id'] == 'FOMC_035')
            assert old['split'] == 'dev'
            at.selectbox(key='search_mode').select('classic')
            at.selectbox(key='context_k').select(6)
            at.toggle(key='use_llm').set_value(True)
            at.toggle(key='structured_generation').set_value(True)
            at.text_input(key='question').set_value(old['question'])
            print('RUN real Ollama generation on FOMC_035 (not holdout)', flush=True)
            submit(timeout=420)
            assert not at.error, [e.value for e in at.error]
            generated = at.session_state['rag_result']
            assert generated.get('model') == 'qwen2.5:3b'
            assert generated.get('structured_answer') and generated.get('answer')
            (out / 'real_generation_dev.json').write_text(json.dumps(generated, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
            add('real_structured_generation_dev', question_id=old['question_id'],
                generation_timing=generated.get('generation_timing'),
                semantic_correctness_certified=False,
                output_file='real_generation_dev.json')
        (out / ('app_runs_with_generation.json' if args.generation else 'app_runs.json')).write_text(json.dumps(runs, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
        add('real_streamlit_http_server', **check_http(out))
        verify()
        report['status'] = 'passed'
    except Exception as exc:
        report['status'] = 'failed'
        report['failure'] = dict(type=type(exc).__name__, message=str(exc))
        raise
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    main()
