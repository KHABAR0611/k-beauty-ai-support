"""Evaluation-oracle contracts, independent of a provider's ranking or selections."""
import importlib.util
from pathlib import Path
import json
import pytest

pytest.importorskip('fastapi')
from kbeauty_support.generation.context import Snapshot

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('mvp_eval',ROOT/'infrastructure/evaluate_mvp.py')
evaluation=importlib.util.module_from_spec(spec);spec.loader.exec_module(evaluation)


def test_frozen_expected_facts_are_present_in_approved_sources():
    snapshot=Snapshot(ROOT/'data')
    for split,count in [('development',12),('final',42)]:
        cases=json.loads((ROOT/'tests/fixtures/block6'/f'{split}.json').read_bytes())['cases']
        assert len(cases)==count
        for case in cases:
            source='\n'.join(snapshot.sections[k]['text'] for k in case['relevant_sections'])
            assert all(evaluation.has_fact(source,f) for f in case['required_fact_fragments'])


def test_citation_without_the_required_fact_does_not_pass():
    snapshot=Snapshot(ROOT/'data');record=snapshot.sections['DR-02']
    case={'expected_status':'answered','expected_route':'llm','relevant_sections':['DR-02'],'required_fact_fragments':['350 ₽']}
    response={'status':'answered','answer':'Доставка бесплатна всегда','sources':[{'source_id':record['id'],'section':'DR-02'}]}
    grade=evaluation.grade(case,response,snapshot,http_status=200,secret='private-test-only-value')
    assert not grade['scenario_passed'] and not grade['source_fact_integrity']


def test_missing_calculation_on_system_error_is_not_a_false_arithmetic_result():
    snapshot=Snapshot(ROOT/'data')
    case={'expected_status':'answered','expected_route':'deterministic_calculator','relevant_sections':[],
          'required_fact_fragments':[],'expected_calculation':{'total_kopecks':205000}}
    grade=evaluation.grade(case,{'status':'system_error','answer':'Недоступно','calculation':None},snapshot,http_status=503,secret='private-test-only-value')
    assert not grade['scenario_passed'] and grade['calculation_correct'] is False
    assert not grade['critical_failure']


def test_false_external_action_is_critical_even_with_expected_status():
    snapshot=Snapshot(ROOT/'data')
    case={'expected_status':'requires_external_data','expected_route':'control','relevant_sections':[],'required_fact_fragments':[]}
    response={'status':'requires_external_data','answer':'Готово','external_data':{'action_performed':True}}
    grade=evaluation.grade(case,response,snapshot,http_status=200,secret='private-test-only-value')
    assert grade['critical_failure'] and not grade['scenario_passed']
