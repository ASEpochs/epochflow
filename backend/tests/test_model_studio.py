import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.models import Experiment, payload_for, router
from api.security import RequestBoundary
from core import siliconflow
from core.model_catalog import CATALOG, AGENT_MODELS
from core.model_scope import agent_model_scope, selected_model, model_errors, openai_payload
from core.llm_utils import create_async_client


def test_catalog_exact_count_and_distinct_modalities():
    assert len(CATALOG) == len({m['id'] for m in CATALOG}) == 50
    assert len({m['category'] for m in CATALOG}) == 9
    assert not any(m['agent'] for m in CATALOG if m['category'] != 'text')


@pytest.mark.parametrize('model,fields,endpoint,expected', [
    ('Qwen/Qwen-Image', {}, 'images/generations', {'image_size': '1328x1328'}),
    ('Qwen/Qwen-Image-Edit-2509', {'media_url': 'https://example.com/image.png'}, 'images/generations', {'image': 'https://example.com/image.png'}),
    ('Wan-AI/Wan2.2-I2V-A14B', {'media_url': 'https://example.com/image.png'}, 'video/submit', {'image_size': '1280x720'}),
    ('FunAudioLLM/CosyVoice2-0.5B', {'voice': 'anna'}, 'audio/speech', {'voice': 'FunAudioLLM/CosyVoice2-0.5B:anna', 'response_format': 'mp3'}),
    ('Qwen/Qwen3-Embedding-8B', {'documents': ['hello', 'world']}, 'embeddings', {'input': ['hello', 'world']}),
    ('Pro/BAAI/bge-reranker-v2-m3', {'documents': ['hello']}, 'rerank', {'documents': ['hello'], 'query': 'test'}),
])
def test_modality_payloads(model, fields, endpoint, expected):
    item, payload = asyncio.run(payload_for(Experiment(model=model, prompt='test', **fields)))
    assert item['endpoint'] == endpoint
    assert all(payload[k] == v for k, v in expected.items())
    if 'Image-Edit' in model:
        assert 'image_size' not in payload


@pytest.mark.parametrize('model,fields', [
    ('Qwen/Qwen-Image-Edit', {}), ('Wan-AI/Wan2.2-I2V-A14B', {}),
    ('deepseek-ai/DeepSeek-V3.2', {'media_url': 'https://example.com/a.png'}),
    ('Qwen/Qwen3-VL-8B-Instruct', {'media_url': 'https://example.com/a.mp3', 'media_type': 'audio'}),
    ('Qwen/Qwen3-VL-8B-Instruct', {'media_url': 'http://127.0.0.1/a'}),
    ('LoRA/Qwen/Qwen2.5-7B-Instruct', {}), ('not-in-catalog', {}),
])
def test_invalid_inputs_never_reach_provider(model, fields):
    with pytest.raises(HTTPException):
        asyncio.run(payload_for(Experiment(model=model, prompt='test', **fields)))


def test_omni_video_input_and_lora_actual_id():
    item, payload = asyncio.run(payload_for(Experiment(model='Qwen/Qwen3-Omni-30B-A3B-Instruct',
        prompt='Summarize', media_url='https://example.com/movie.mp4', media_type='video')))
    assert payload['messages'][0]['content'][1] == {'type': 'video_url', 'video_url': {
        'url': 'https://example.com/movie.mp4', 'fps': 1, 'max_frames': 16}}
    _, payload = asyncio.run(payload_for(Experiment(model='LoRA/Qwen/Qwen2.5-7B-Instruct',
        prompt='test', adapter_id='ft:my-trained-model:123')))
    assert payload['model'] == 'ft:my-trained-model:123'


def test_agent_model_context_isolated_during_concurrent_tool_roundtrips(monkeypatch):
    seen = []
    async def fake(endpoint, payload, **kwargs):
        await asyncio.sleep(.01)
        seen.append(payload)
        if payload['messages'][-1]['role'] == 'tool':
            return {'choices': [{'message': {'content': payload['model']}}]}
        return {'choices': [{'message': {'tool_calls': [{'id': 'call1', 'function': {
            'name': 'search', 'arguments': '{"query":"退款"}'}}]}}]}
    monkeypatch.setattr(siliconflow, 'request', fake)

    async def run():
        async with create_async_client('test-key', 'https://api.siliconflow.cn') as client:
            async def one(model):
                async with agent_model_scope(SimpleNamespace(model=model)):
                    kwargs = dict(model='global-default', max_tokens=100, messages=[{'role': 'user', 'content': 'check'}],
                                  tools=[{'name': 'search', 'input_schema': {'type': 'object'}}])
                    resp = await client.messages.create(**kwargs)
                    assert resp.content[0]['input'] == {'query': '退款'}
                    kwargs['messages'] += [{'role': 'assistant', 'content': resp.content},
                        {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 'call1', 'content': 'OK'}]}]
                    final = await client.messages.create(**kwargs)
                    assert final.content[0]['text'] == model
                    assert not model_errors.get()
            await asyncio.gather(*(one(model) for model in list(AGENT_MODELS)[:2]))
            assert selected_model.get() is None
            assert model_errors.get() is None
    asyncio.run(run())
    assert len(seen) == 4
    assert all(row['messages'][-1]['tool_call_id'] == 'call1' for row in seen if row['messages'][-1]['role'] == 'tool')


def test_agent_model_context_resets_after_failure(monkeypatch):
    async def fail(*args, **kwargs):
        raise HTTPException(502, 'provider unavailable')
    monkeypatch.setattr(siliconflow, 'request', fail)
    async def run():
        async with create_async_client('key', 'https://api.siliconflow.cn') as client:
            with pytest.raises(HTTPException):
                async with agent_model_scope(SimpleNamespace(model='deepseek-ai/DeepSeek-V3.2')):
                    await client.messages.create(messages=[], model='x')
            assert selected_model.get() is None
            assert model_errors.get() is None
    asyncio.run(run())


def test_catalog_checks_status_once_without_generation(monkeypatch):
    calls = []
    async def fake(endpoint, **kwargs):
        calls.append(endpoint)
        return {'data': [{'id': row['id']} for row in CATALOG]}
    monkeypatch.setattr(siliconflow, 'request', fake)
    monkeypatch.setattr(siliconflow, '_catalog_cache', None)
    monkeypatch.setattr(siliconflow, '_catalog_expiry', 0)
    async def run():
        first, second = await siliconflow.catalog_status(), await siliconflow.catalog_status()
        assert first == second
        assert first['listed_count'] == 50
        assert sum(m['availability'] == 'requires_adapter' for m in first['items']) == 4
    asyncio.run(run())
    assert calls == ['models']


def test_experiments_guarded_and_vectors_keep_input_order(monkeypatch):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('APP_ACCESS_TOKEN', 'test-access')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-model-key')
    calls = []
    async def fake(endpoint, payload, **kwargs):
        calls.append(endpoint)
        if endpoint == 'embeddings':
            return {'data': [{'index': 1, 'embedding': [0., 1.]}, {'index': 0, 'embedding': [1., 0.]}]}
        return {'results': [{'index': 1, 'relevance_score': .9}, {'index': 0, 'relevance_score': .2}]}
    monkeypatch.setattr(siliconflow, 'request', fake)
    app = FastAPI(); app.add_middleware(RequestBoundary); app.include_router(router)
    headers = {'X-Access-Token': 'test-access'}
    body = {'model': 'Qwen/Qwen3-Embedding-0.6B', 'documents': ['A', 'B']}
    with TestClient(app) as client:
        assert client.post('/models/run', json=body).status_code == 401
        assert calls == []
        data = client.post('/models/run', headers=headers, json=body).json()
        assert data['vectors'] == [[1., 0.], [0., 1.]]
        assert data['similarity'] == [[1., 0.], [0., 1.]]
        data = client.post('/models/run', headers=headers, json={**body, 'model': 'Qwen/Qwen3-Reranker-0.6B', 'prompt': 'test'}).json()
        assert data['results'][0]['text'] == 'B'
        assert client.post('/models/run', headers=headers, json={**body, 'documents': ['x'*4001]}).status_code == 422
        monkeypatch.setenv('ANTHROPIC_API_KEY', '')
        assert client.post('/models/run', headers=headers, json=body).status_code == 503
        assert len(calls) == 2


def test_parallel_body_reads_cannot_bypass_model_concurrency_limit(monkeypatch):
    monkeypatch.setenv('APP_ACCESS_TOKEN', '')
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    async def run():
        bodies, finish = asyncio.Event(), asyncio.Event()
        admitted, statuses = [], []
        async def downstream(scope, receive, send):
            admitted.append(True)
            await finish.wait()
            await send({'type': 'http.response.start', 'status': 200, 'headers': []})
            await send({'type': 'http.response.body', 'body': b''})
        boundary = RequestBoundary(downstream)
        async def one():
            async def receive():
                await bodies.wait()
                return {'type': 'http.request', 'body': b'{}'}
            async def send(message):
                if message['type'] == 'http.response.start': statuses.append(message['status'])
            await boundary({'type': 'http', 'method': 'POST', 'path': '/models/run', 'headers': []}, receive, send)
        tasks = [asyncio.create_task(one()) for _ in range(3)]
        await asyncio.sleep(0)
        bodies.set()
        await asyncio.sleep(0)
        assert len(admitted) == 2
        assert statuses == [429]
        finish.set()
        await asyncio.gather(*tasks)
        assert boundary.active_models == 0
    asyncio.run(run())


def test_provider_errors_do_not_echo_secrets_or_request_bodies(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_BASE_URL', 'https://api.siliconflow.cn/v1')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-secret-must-not-appear')
    client_class = httpx.AsyncClient
    def handle(req):
        assert str(req.url) == 'https://api.siliconflow.cn/v1/chat/completions'
        assert req.headers['Authorization'] == 'Bearer test-secret-must-not-appear'
        return httpx.Response(401, json={'message': 'test-secret-must-not-appear'})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: client_class(transport=httpx.MockTransport(handle), **kwargs))
    with pytest.raises(HTTPException) as caught:
        asyncio.run(siliconflow.request('chat/completions', {'model': 'test'}))
    assert 'test-secret' not in caught.value.detail
    assert '401' in caught.value.detail
