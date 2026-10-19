"""Real dense/BM25/RRF, index generation safety and persistence on an isolated Server."""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import subprocess
import time
import urllib.request
from uuid import uuid4

import pytest

from kbeauty_support.retrieval.dense import BgeM3Encoder, REVISION, digest, encoded
from kbeauty_support.retrieval.hybrid import HybridIndex
from kbeauty_support.retrieval.sparse import RussianBm25, build_hybrid, validate_hybrid

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def server():
    if not os.environ.get("KBEAUTY_HYBRID_SERVER_TESTS"):
        pytest.skip("Explicit real hybrid Server opt-in required")
    from qdrant_client import QdrantClient
    client=QdrantClient(url=os.environ["QDRANT_URL"],api_key=os.environ["QDRANT_API_KEY"],timeout=30,trust_env=False)
    artifact=json.loads(Path(os.environ["KBEAUTY_HYBRID_ARTIFACT"]).read_bytes())
    dense=json.loads(Path(os.environ["KBEAUTY_EMBEDDING_ARTIFACT"]).read_bytes())
    validate_hybrid(artifact)
    encoder=BgeM3Encoder(Path(os.environ["KBEAUTY_MODEL_DIR"]))
    index=HybridIndex(client,alias="kbeauty_hybrid_it_"+uuid4().hex)
    try:
        yield client,index,artifact,dense,encoder
    finally:
        client.close()


def health(path):
    request=urllib.request.Request(os.environ["QDRANT_URL"]+path,headers={"api-key":os.environ["QDRANT_API_KEY"]})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=5) as response:
        return response.status


def changed(dense,encoder):
    value=copy.deepcopy(dense)
    value["records"]=value["records"][:-1]
    value["descriptor"]["preparation_generation"]=digest(uuid4().bytes)
    value["generation"]=digest(encoded(value["descriptor"]))
    value["records"][0]["payload"]["text"]+="\nПроверка новой редакции текста при интеграционном обновлении."
    text=value["records"][0]["payload"]["text"]
    value["records"][0]["vector"]=encoder.encode([text])[0]
    value["records"][0]["payload"]["metadata"]["chunk_sha256"]=digest(text.encode())
    for record in value["records"]:
        record["payload"]["index"]={**value["descriptor"],"generation":value["generation"]}
        record["payload"]["metadata"]["preparation_generation"]=value["descriptor"]["preparation_generation"]
    value["content_sha256"]=digest(encoded({k:v for k,v in value.items() if k!='content_sha256'}))
    return build_hybrid(value)


def test_version_health_and_20_consistent_points(server,tmp_path):
    client,index,artifact,_,_=server
    assert client.info().version=='1.15.1'
    assert health('/readyz')==health('/healthz')==200
    assert index.publish(artifact,tmp_path)['points']==20
    assert index.publish(artifact,tmp_path)['status']=='noop'
    index._verify(index.resolve(),artifact)
    points,_=client.scroll(index.resolve(),limit=64,with_vectors=True)
    assert all(set(p.vector)=={'dense','bm25'} for p in points)
    products=[p.payload for p in points if p.payload.get('product')]
    assert len(products)==9
    assert next(p for p in products if p['metadata']['product_id']=='KB-004')['price_kopecks']==189000


def test_all_three_modes_and_sparse_independence(server,tmp_path):
    _,index,artifact,_,encoder=server
    index.publish(artifact,tmp_path)
    results={mode:index.search('KB-005',None if mode=='bm25' else encoder,mode=mode) for mode in ('dense','bm25','hybrid')}
    assert len({r['generation'] for r in results.values()})==1
    assert all(r['hits'][0]['metadata']['section']=='KB-005' for r in results.values())


def test_real_rrf_matches_independent_rank_formula(server,tmp_path):
    from qdrant_client import models as m
    client,index,artifact,_,encoder=server
    index.publish(artifact,tmp_path)
    name=index.resolve()
    query='бонусами WELCOME10 доставка'
    dense=encoder.encode([query])[0]
    spec=artifact['descriptor']['sparse_model']
    sparse=m.SparseVector(**RussianBm25(avg_len=spec['avg_len']).query(query))
    a=client.query_points(name,query=dense,using='dense',limit=20).points
    b=client.query_points(name,query=sparse,using='bm25',limit=20).points
    expected={}
    for branch in (a,b):
        for rank,point in enumerate(branch):
            expected[point.id]=expected.get(point.id,0)+1/(rank+2)
    fused=client.query_points(name,query=m.FusionQuery(fusion=m.Fusion.RRF),prefetch=[
        m.Prefetch(query=dense,using='dense',limit=20),m.Prefetch(query=sparse,using='bm25',limit=20)],limit=20).points
    assert set(expected)=={p.id for p in fused}
    assert all(math.isclose(p.score,expected[p.id],rel_tol=1e-5) for p in fused)


def test_interrupted_update_reencodes_text_and_removes_stale_points(server,tmp_path,monkeypatch):
    client,index,artifact,dense,encoder=server
    index.publish(artifact,tmp_path)
    before=index.resolve()
    update=changed(dense,encoder)
    assert update['records'][0]['vector']!=artifact['records'][0]['vector']
    assert update['records'][0]['bm25']!=artifact['records'][0]['bm25']
    real=client.upsert
    calls=0
    def fail(*args,**kwargs):
        nonlocal calls
        calls+=1
        if calls==2: raise ConnectionError('Injected partial hybrid upsert')
        return real(*args,**kwargs)
    monkeypatch.setattr(client,'upsert',fail)
    with pytest.raises(ConnectionError): index.publish(update,tmp_path)
    assert index.resolve()==before
    assert client.count('kbeauty_hybrid_'+update['generation'],exact=True).count==4
    index._verify(before,artifact)
    monkeypatch.setattr(client,'upsert',real)
    assert index.publish(update,tmp_path)['points']==19
    assert index.publish(update,tmp_path)['status']=='noop'
    points,_=client.scroll(index.resolve(),limit=64,with_vectors=True)
    assert artifact['records'][-1]['id'] not in {str(p.id) for p in points}
    index._verify(index.resolve(),update)
    index.publish(artifact,tmp_path)


def test_alias_change_during_query_keeps_one_generation(server,tmp_path,monkeypatch):
    client,index,artifact,dense,encoder=server
    index.publish(artifact,tmp_path)
    before=index.resolve()
    update=changed(dense,encoder)
    real_encode=encoder.encode
    def switching(texts):
        index.publish(update,tmp_path)
        return real_encode(texts)
    monkeypatch.setattr(encoder,'encode',switching)
    result=index.search('возврат крема',encoder,mode='hybrid')
    assert index.resolve()!=before
    assert result['collection']==before and result['generation']==artifact['generation']
    monkeypatch.setattr(encoder,'encode',real_encode)
    index.publish(artifact,tmp_path)


def test_readback_failure_never_switches_alias(server,tmp_path,monkeypatch):
    _,index,artifact,dense,encoder=server
    index.publish(artifact,tmp_path)
    previous=index.resolve()
    update=changed(dense,encoder)
    monkeypatch.setattr(index,'_verify',lambda *args: (_ for _ in ()).throw(RuntimeError('Injected sparse readback failure')))
    with pytest.raises(RuntimeError): index.publish(update,tmp_path)
    assert index.resolve()==previous


def test_restart_preserves_both_vectors_alias_and_rankings(server,tmp_path):
    if os.environ.get('KBEAUTY_ALLOW_SMOKE_RESTART')!='1': pytest.skip('Explicit restart opt-in required')
    assert os.environ['QDRANT_URL']=='http://127.0.0.1:6394'
    client,index,artifact,_,encoder=server
    index.publish(artifact,tmp_path)
    before={mode:index.search('KB-004',encoder if mode!='bm25' else None,mode=mode) for mode in ('dense','bm25','hybrid')}
    subprocess.run(['docker','compose','-p','kbeauty-review-check','restart','qdrant'],cwd=ROOT,
        env=dict(os.environ,QDRANT_HTTP_PORT='6394'),check=True,capture_output=True,timeout=60)
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        try:
            if health('/readyz')==200: break
        except OSError: pass
        time.sleep(1)
    assert health('/readyz')==health('/healthz')==200
    assert index.publish(artifact,tmp_path)['status']=='noop'
    for mode,old in before.items():
        after=index.search('KB-004',encoder if mode!='bm25' else None,mode=mode)
        assert [h['id'] for h in after['hits']]==[h['id'] for h in old['hits']]
