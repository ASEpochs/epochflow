"""Create EpochFlow Free services only; read secrets from ignored local files."""
import json
import secrets
from pathlib import Path

import httpx
from dotenv import dotenv_values, set_key

ROOT = Path(__file__).resolve().parents[1]
REPO = 'https://github.com/ASEpochs/epochflow'
STATE = ROOT / '.runtime/render-services.json'


def main():
    local = dotenv_values(ROOT / '.env.deploy.local')
    model = dotenv_values(ROOT / 'backend/.env.local')
    token = local.get('RENDER_API_KEY')
    if not token:
        raise SystemExit('Missing RENDER_API_KEY in .env.deploy.local')
    access = local.get('APP_ACCESS_TOKEN') or secrets.token_urlsafe(32)
    set_key(str(ROOT / '.env.deploy.local'), 'APP_ACCESS_TOKEN', access)
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    def save():
        STATE.parent.mkdir(exist_ok=True)
        STATE.write_text(json.dumps(state, indent=2), encoding='utf-8')
    with httpx.Client(base_url='https://api.render.com/v1', headers={'Authorization': 'Bearer ' + token}, timeout=60) as client:
        def request(method, path, **kwargs):
            result = client.request(method, path, **kwargs)
            if not result.is_success:
                # Never print request payloads containing secrets.
                print('Render response:', result.status_code, result.text[:700])
                result.raise_for_status()
            return result.json() if result.content else {}
        owners = request('GET', '/owners', params={'limit': 100})
        if len(owners) != 1:
            raise SystemExit('Choose the workspace before deploying; multiple workspaces available')
        owner_id = owners[0]['owner']['id']
        existing = request('GET', '/services', params={'limit': 100})
        names = {item['service']['name']: item['service']['id'] for item in existing}
        for name, key in [('epochflow-api', 'backend'), ('epochflow-web', 'frontend')]:
            if name in names and state.get(key, {}).get('id') != names[name]:
                raise SystemExit('An unrelated service already uses ' + name)
        base = {'ownerId': owner_id, 'repo': REPO, 'branch': 'main', 'autoDeploy': 'yes'}
        if 'backend' not in state:
            env = {'PYTHON_VERSION': '3.12.8', 'APP_ENV': 'production', 'STORAGE_MODE': 'memory',
                   'PUBLIC_DEMO': 'true', 'PROMETHEUS_PORT': '0', 'FRONTEND_ORIGINS': 'https://epochflow-web.onrender.com',
                   **{key: model[key] for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL', 'ANTHROPIC_MODEL') if model.get(key)}}
            payload = {**base, 'type': 'web_service', 'name': 'epochflow-api', 'rootDir': 'backend',
                       'envVars': [{'key': key, 'value': value} for key, value in env.items()],
                       'serviceDetails': {'runtime': 'python', 'plan': 'free', 'region': 'singapore',
                           'numInstances': 1, 'healthCheckPath': '/health', 'envSpecificDetails': {
                               'buildCommand': 'pip install -r requirements-free.txt',
                               'startCommand': 'uvicorn api.main:app --host 0.0.0.0 --port $PORT'}}}
            assert payload['serviceDetails']['plan'] == 'free' and 'disk' not in payload['serviceDetails']
            created = request('POST', '/services', json=payload)
            service = created.get('service', created)
            state['backend'] = {'id': service['id'], 'url': service['serviceDetails']['url']}
            save()
            print('Created free backend:', state['backend']['url'])
        if 'frontend' not in state:
            payload = {**base, 'type': 'static_site', 'name': 'epochflow-web', 'rootDir': 'frontend',
                       'envVars': [{'key': 'NODE_VERSION', 'value': '22.16.0'},
                                   {'key': 'VITE_PYTHON_API_URL', 'value': state['backend']['url']}],
                       'serviceDetails': {'buildCommand': 'npm ci && npm run build', 'publishPath': 'dist',
                                          'routes': [{'type': 'rewrite', 'source': '/*', 'destination': '/index.html'}]}}
            created = request('POST', '/services', json=payload)
            service = created.get('service', created)
            state['frontend'] = {'id': service['id'], 'url': service['serviceDetails']['url']}
            save()
            print('Created static frontend:', state['frontend']['url'])
        # Set only this service's CORS origin; preserve all other secret values.
        request('PUT', f"/services/{state['backend']['id']}/env-vars/FRONTEND_ORIGINS", json={'value': state['frontend']['url']})
        print(json.dumps(state, ensure_ascii=False))


if __name__ == '__main__':
    main()
