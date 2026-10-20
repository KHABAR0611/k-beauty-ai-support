"""Frozen MVP evaluation. Real HTTP answers and separate real Server retrieval."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import sys
import time
from urllib.parse import urlsplit

import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))


def normalized(value: str) -> str:
    return re.sub(r'\s+',' ',value.casefold().replace('ё','е')).strip()


def has_fact(answer: str, fact: str) -> bool:
    if fact=='без отдушки':
        return fact in answer or bool(re.search(r'"fragrance_free"\s*:\s*true',answer))
    return normalized(fact) in normalized(answer)


def frozen_fixture_matches(raw: bytes, expected_sha256: str) -> bool:
    """Git may normalize JSON line endings; tolerate only LF/CRLF conversion."""
    lf=raw.replace(b'\r\n',b'\n')
    return expected_sha256 in {hashlib.sha256(value).hexdigest() for value in (raw,lf,lf.replace(b'\n',b'\r\n'))}


def grade(case: dict, response: dict, snapshot, *, http_status: int, secret: str) -> dict:
    expected=case['expected_status'];status=response.get('status')
    sources=response.get('sources',[]);sections={s.get('section') for s in sources}
    answer=response.get('answer','')
    required=set(case['relevant_sections'])
    missing_sources=sorted(required-sections)
    missing_facts=[f for f in case['required_fact_fragments'] if not has_fact(answer,f)]
    source_units_valid=all(s.get('source_id') in snapshot.records and
        snapshot.records[s['source_id']]['metadata']['section']==s.get('section') and
        snapshot.records[s['source_id']]['text'] in answer for s in sources)
    calculation_ok=all((response.get('calculation') or {}).get(k)==v for k,v in case.get('expected_calculation',{}).items())
    unsafe=(secret in answer or bool(response.get('handoff',{} ) and response['handoff'].get('created'))
            or bool(response.get('external_data',{}) and response['external_data'].get('action_performed')))
    # Absence of a known-bad substring is not universal semantic safety proof.
    status_ok=status==expected and http_status==200
    route=response.get('diagnostics',{}).get('answer_mode')
    route_ok=(response.get('diagnostics',{}).get('generation_performed') is True if case['expected_route']=='llm'
              else route==case['expected_route'] if case['expected_route'].startswith('deterministic_') else status_ok)
    complete=not missing_sources and not missing_facts and status=='answered'
    passed=status_ok and calculation_ok and source_units_valid and not unsafe and (complete if expected=='answered' else True)
    return {'scenario_passed':passed,'status_correct':status_ok,'expected_status':expected,
            'complete':complete if expected=='answered' else None,'missing_sources':missing_sources,'missing_facts':missing_facts,
            'source_fact_integrity':source_units_valid if sources else None,'calculation_correct':calculation_ok if 'expected_calculation' in case else None,
            'route_correct':bool(route_ok),'unsafe_external_action_or_secret':unsafe,
            'critical_failure':unsafe or (status=='answered' and 'expected_calculation' in case and not calculation_ok),
            'scope':'Deterministic source/fact/contract checks, not blind human evaluation or universal entailment'}


def main(*, corrective: bool = False) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['answers','retrieval'],required=True)
    parser.add_argument('--split',choices=['development','regression','holdout'] if corrective else ['development','final'],required=True)
    parser.add_argument('--url',default='http://127.0.0.1:8090')
    parser.add_argument('--allow-local-inference',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    fixture=(ROOT/'tests/fixtures/block61/holdout.json' if corrective and args.split=='holdout'
             else ROOT/'tests/fixtures/block6'/('final.json' if args.split=='regression' else f'{args.split}.json'))
    raw=fixture.read_bytes();cases=json.loads(raw)['cases']
    holdout=corrective and args.split=='holdout'
    plan=json.loads((ROOT/('docs/block-6.1-evaluation-plan.json' if holdout else 'docs/block-6-evaluation-plan.json')).read_bytes())
    expected=plan['holdout_sha256'] if holdout else plan['fixture_sha256'][fixture.name]
    if not frozen_fixture_matches(raw,expected):
        raise ValueError('Frozen evaluation fixture changed')
    from kbeauty_support.generation.context import Snapshot
    from kbeauty_support.retrieval.evaluation import percentile,recall
    snapshot=Snapshot(ROOT/'data');records=[]
    meta={'phase':args.phase,'split':args.split,'fixture_sha256':hashlib.sha256(raw).hexdigest(),
          'fixture_lf_sha256':hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest(),
          'business_generation':snapshot.generation,'provider_doubles':False,
          'runtime_source_hashes':{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'src').rglob('*.py'))}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    def save():
        result={**meta,'cases':records,'completed':len(records),'expected_count':len(cases)}
        if args.phase=='answers' and records:
            answered=[r for r in records if r['response']['status']=='answered']
            expected_answers=[r for r in records if r['expected_status']=='answered']
            refusals=[r for r in records if r['expected_status']!='answered']
            calc=[r for r in records if r['grade']['calculation_correct'] is not None]
            llm=[r for r in records if r['response'].get('usage',{} ) and r['response']['usage'].get('provider')=='ollama']
            stages={k:[r['response'].get('latency_ms',{}).get(k,0) for r in records] for k in ['retrieval','llm']}
            result['metrics']={'scenario_pass_count':sum(r['grade']['scenario_passed'] for r in records),'scenario_total':len(records),
                'scenario_pass_rate':statistics.mean(r['grade']['scenario_passed'] for r in records),
                'answer_completeness':statistics.mean(r['grade']['complete'] for r in expected_answers) if expected_answers else None,
                'expected_answer_denominator':len(expected_answers),'actual_answered':len(answered),
                'source_fact_integrity':statistics.mean(r['grade']['source_fact_integrity'] for r in answered if r['grade']['source_fact_integrity'] is not None) if any(r['grade']['source_fact_integrity'] is not None for r in answered) else None,
                'refusal_status_accuracy':statistics.mean(r['grade']['status_correct'] for r in refusals) if refusals else None,
                'refusal_denominator':len(refusals),'calculation_accuracy':statistics.mean(r['grade']['calculation_correct'] for r in calc) if calc else None,
                'calculation_denominator':len(calc),'routing_accuracy':statistics.mean(r['grade']['route_correct'] for r in records),
                'real_llm_completed':len(llm),'critical_failures':sum(r['grade']['critical_failure'] for r in records),
                'http_latency':{f'p{p}_ms':percentile([r['http_latency_ms'] for r in records],p) for p in [50,95]},
                'stage_latency':{k:{f'p{p}_ms':percentile(v,p) for p in [50,95]} for k,v in stages.items()},
                'answer_latency_by_route':{mode:{'samples':len(items),**{f'p{p}_ms':percentile([r['http_latency_ms'] for r in items],p) for p in [50,95]}}
                    for mode in sorted({r['response'].get('diagnostics',{}).get('answer_mode','unreported') for r in records})
                    if (items:=[r for r in records if r['response'].get('diagnostics',{}).get('answer_mode','unreported')==mode])}}
        if args.phase=='retrieval' and records:
            scored=[r for r in records if r['relevant']]
            result['metrics']={'queries_with_relevance':len(scored),'recall_at_3':statistics.mean(r['recall_at_3'] for r in scored),
                'recall_at_5':statistics.mean(r['recall_at_5'] for r in scored),
                'latency':{f'p{p}_ms':percentile([r['latency_ms'] for r in records],p) for p in [50,95]}}
        encoded=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
        if args.phase=='answers' and token in encoded:raise RuntimeError('Credential leak prevented')
        args.output.write_text(encoded,encoding='utf8')
    if args.phase=='answers':
        if not args.allow_local_inference:raise ValueError('Explicit local inference opt-in required')
        u=urlsplit(args.url)
        if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost') or u.username or u.password or u.query or u.fragment:raise ValueError('Local API only')
        token=os.environ['API_ACCESS_KEY']
        with httpx.Client(base_url=args.url,trust_env=False,timeout=100) as client:
            ready=client.get('/ready');ready.raise_for_status()
            assert ready.json()['dependencies']['llm']['provider']=='ollama'
            meta['readiness']=ready.json()
            for case in cases:
                start=time.perf_counter();r=client.post('/chat',json=case['request'],headers={'Authorization':'Bearer '+token})
                response=r.json()
                row={'id':case['id'],'request':case['request'],'conversation':case.get('conversation'),'turn':case.get('turn'),
                     'expected_status':case['expected_status'],'required_sources':case['relevant_sections'],'response':response,
                     'http_status':r.status_code,'http_latency_ms':(time.perf_counter()-start)*1000,
                     'grade':grade(case,response,snapshot,http_status=r.status_code,secret=token)}
                records.append(row);save()
                print(case['id'],response['status'],'pass='+str(row['grade']['scenario_passed']),
                      'live_llm='+str(bool(response.get('usage'))),'seconds='+str(round(row['http_latency_ms']/1000,2)),flush=True)
    else:
        from kbeauty_support.api.runtime import RuntimeRetriever,Settings
        from kbeauty_support.retrieval.rerank_evaluation import process_memory
        retriever=RuntimeRetriever(Settings.environment(),snapshot)
        cpu=time.process_time();t=time.perf_counter();retriever.warm();meta['warmup_seconds']=time.perf_counter()-t
        try:
            for case in cases:
                start=time.perf_counter();hits=retriever.retrieve(case['request']['question'])['hits']
                ranked=[h['metadata']['section'] for h in hits]
                rel=case['relevant_sections']
                records.append({'id':case['id'],'query':case['request']['question'],'relevant':rel,'top5':ranked[:5],
                    'recall_at_3':recall(ranked,rel,3) if rel else None,'recall_at_5':recall(ranked,rel,5) if rel else None,
                    'missing_top5':sorted(set(rel)-set(ranked[:5])),'latency_ms':(time.perf_counter()-start)*1000})
                save()
            meta['process_memory']=process_memory();meta['process_cpu_seconds']=time.process_time()-cpu;save()
        finally:retriever.close()
    print('Saved',args.phase,args.split,len(records),'observations',flush=True)
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print('evaluation_failed category='+type(exc).__name__,file=sys.stderr)
        raise SystemExit(2)
