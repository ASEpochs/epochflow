import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['STORAGE_MODE'] = 'memory'
os.environ['APP_ENV'] = 'development'
os.environ['ANTHROPIC_API_KEY'] = ''
os.environ['APP_ACCESS_TOKEN'] = ''

from fastapi.testclient import TestClient
from api.main import app
from mcp.free_knowledge import KnowledgeBase
from memory.free_memory import MemoryManager
from memory.models import MsgRole


def test_deployment_defines_only_free_compute_and_static_site():
    import yaml
    root = Path(__file__).resolve().parents[2]
    blueprint = yaml.safe_load((root / 'render.yaml').read_text(encoding='utf-8'))
    assert not blueprint.get('databases')
    services = blueprint['services']
    assert len(services) == 2
    for service in services:
        assert 'disk' not in service
        if service['runtime'] != 'static':
            assert service['plan'] == 'free'
            assert service['rootDir'] == 'backend'
            assert 'requirements-free.txt' in service['buildCommand']
    requirements = (root / 'backend/requirements-free.txt').read_text(encoding='utf-8')
    assert 'chromadb==' not in requirements
    assert 'redis==' not in requirements


def test_ephemeral_memory_is_isolated_bounded_and_lost_on_restart():
    async def exercise():
        memory = MemoryManager()
        for i in range(30):
            await memory.add_message('alice', 'same', MsgRole.USER, str(i))
        context = await memory.get_context('alice', 'same')
        assert len(context.recent_messages) == 20
        assert context.recent_messages[0].content == '10'
        assert not (await memory.get_context('bob', 'same')).recent_messages
        assert not (await MemoryManager().get_context('alice', 'same')).recent_messages
        memory.MAX_SESSIONS = 2
        await memory.get_context('c', 'c')
        assert len(memory._sessions) == 2
        memory.TTL_SECONDS = 0
        assert not (await memory.get_context('alice', 'same')).recent_messages
        await memory.close()
        assert not memory._sessions
    asyncio.run(exercise())


def test_knowledge_retrieval_and_restart_restore_only_seed_documents():
    kb = KnowledgeBase()
    doc = {'title': '独立学习资料', 'content': '火星探测器轨道实验说明'}
    assert kb.add_documents([doc]) == 1
    assert kb.add_documents([doc]) == 0
    assert kb.search('火星探测器')[0]['title'] == '独立学习资料'
    assert kb.search('火星探测器')[0]['retrieval'] == 'character_ngram'
    assert not KnowledgeBase().search('火星探测器')
    assert kb.search('退款')[0]['content']


def test_boot_without_key_or_database_and_production_access_guard(monkeypatch):
    from anthropic.resources.messages import AsyncMessages
    async def fail_if_model_called(*args, **kwargs):
        raise AssertionError('Free unconfigured profile must not call a model')
    monkeypatch.setattr(AsyncMessages, 'create', fail_if_model_called)
    with TestClient(app) as client:
        import api.main as api
        assert isinstance(api._memory, MemoryManager)
        assert 'chromadb' not in sys.modules
        assert 'redis' not in sys.modules
        health = client.get('/health').json()
        assert health['storage_mode'] == 'memory'
        assert health['model_configured'] is False
        assert health['persistent'] is False
        assert client.post('/chat', json={'message': '你好'}).status_code == 503
        assert client.post('/eval/run').status_code == 503
        assert client.get('/knowledge/stats').json()['total_chunks'] > 0
        result = client.post('/search', params={'query': '退款'}).json()
        assert result['results']
        assert result['retrieval'] == 'character_ngram'
        assert result['reranked'] is False
        monkeypatch.setenv('APP_ENV', 'production')
        assert client.get('/knowledge/stats').status_code == 503
        monkeypatch.setenv('APP_ACCESS_TOKEN', 'test-only-token')
        assert client.get('/knowledge/stats').status_code == 401
        denied = client.get('/knowledge/stats', headers={'Origin': 'http://127.0.0.1:5173'})
        assert denied.headers['access-control-allow-origin'] == 'http://127.0.0.1:5173'
        assert client.options('/knowledge/stats', headers={
            'Origin': 'http://127.0.0.1:5173', 'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'X-Access-Token'}).status_code == 200
        headers = {'X-Access-Token': 'test-only-token'}
        assert client.get('/knowledge/stats', headers=headers).status_code == 200
        assert client.get('/health').status_code == 200
        monkeypatch.setenv('PUBLIC_DEMO', 'true')
        assert client.get('/knowledge/stats').status_code == 200
        public_health = client.get('/health').json()
        assert public_health['public_demo'] is True
        monkeypatch.setenv('PUBLIC_DEMO', 'false')
        created = client.post('/knowledge/add', headers=headers, json={'documents': [
            {'title': '工作台回归测试资料', 'content': '木星轨道测试专用内容'}]})
        assert created.status_code == 200
        listed = client.get('/knowledge/documents', headers=headers).json()['items']
        added = next(doc for doc in listed if doc['title'] == '工作台回归测试资料')
        assert added['seed'] is False
        assert added['content'].strip() == '木星轨道测试专用内容'
        assert client.delete('/knowledge/documents/' + added['id'], headers=headers).json()['removed_chunks'] == 1
        assert client.delete('/knowledge/documents/' + added['id'], headers=headers).status_code == 404
        assert client.post('/knowledge/upload', headers=headers,
                           files={'file': ('test.exe', b'content', 'application/octet-stream')}).status_code == 400
        assert client.post('/knowledge/add', headers=headers,
                           content=b'x' * (1200 * 1024 + 1)).status_code == 413
        assert client.post('/knowledge/upload', headers=headers,
                           files={'file': ('bad.json', '[123]', 'application/json')}).status_code == 400
        assert client.post('/knowledge/upload', headers=headers,
                           files={'file': ('big.txt', b'x' * (1024 * 1024 + 1), 'text/plain')}).status_code == 413
