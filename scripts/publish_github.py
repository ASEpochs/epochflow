"""Publish this isolated repository using Git Credential Manager (never print tokens)."""
import json
import os
import subprocess
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
REPO = 'ASEpochs/epochflow'


def git(*args, **kwargs):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, text=True, **kwargs)


def main():
    os.environ['GIT_TERMINAL_PROMPT'] = '0'
    os.environ['GCM_INTERACTIVE'] = 'Never'
    result = git('credential', 'fill', input='protocol=https\nhost=github.com\n\n', capture_output=True)
    credential = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    with httpx.Client(headers={'Authorization': 'Bearer ' + credential['password'],
                               'Accept': 'application/vnd.github+json', 'User-Agent': 'EpochFlow-publisher'}, timeout=30) as client:
        user = client.get('https://api.github.com/user').json()
        if user.get('login') != 'ASEpochs':
            raise SystemExit('GitHub account does not match ASEpochs')
        result = client.get('https://api.github.com/repos/' + REPO)
        if result.status_code == 404:
            result = client.post('https://api.github.com/user/repos', json={
                'name': 'epochflow', 'private': True,
                'description': 'EpochFlow · 纪流 — a Chinese Agent learning studio with observable execution, knowledge retrieval and evaluation.',
                'auto_init': False})
            result.raise_for_status()
            print('Created private repository:', result.json()['html_url'])
        else:
            result.raise_for_status()
            if result.json().get('size', 0) != 0 and not (ROOT / '.runtime/github-published.json').exists():
                raise SystemExit('Existing nonempty repository; refusing to overwrite')
        git('config', 'user.name', 'ASEpochs')
        git('config', 'user.email', str(user['id']) + '+ASEpochs@users.noreply.github.com')
        remotes = git('remote', capture_output=True).stdout.splitlines()
        url = 'https://github.com/' + REPO + '.git'
        if 'origin' not in remotes:
            git('remote', 'add', 'origin', url)
        elif git('remote', 'get-url', 'origin', capture_output=True).stdout.strip() != url:
            raise SystemExit('Unexpected origin; refusing to change it')
        git('branch', '-M', 'main')
        git('push', '-u', 'origin', 'main')
        (ROOT / '.runtime').mkdir(exist_ok=True)
        (ROOT / '.runtime/github-published.json').write_text(json.dumps({'repo': REPO}), encoding='utf-8')
        print('Published:', 'https://github.com/' + REPO)


if __name__ == '__main__':
    main()
