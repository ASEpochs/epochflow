"""Sync one verified local commit when Git's HTTPS transport is unavailable.

Uses Git Credential Manager without printing credentials. Requires the remote
main branch to match the local commit's parent; never overwrites remote changes.
"""
import base64
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def git(*args, data=None):
    return subprocess.run(['git', *args], cwd=ROOT, input=data, check=True, capture_output=True).stdout


def main():
    os.environ['GIT_TERMINAL_PROMPT'] = '0'
    os.environ['GCM_INTERACTIVE'] = 'Never'
    if git('status', '--porcelain').strip():
        raise SystemExit('Commit local changes first; working tree must be clean')
    secrets = []
    for path in ('backend/.env.local', '.env.deploy.local'):
        for key, value in dotenv_values(ROOT / path).items():
            if ('KEY' in key or 'TOKEN' in key) and value and len(value) > 12:
                secrets.append(value.encode())
    records = []
    for record in git('ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if not record:
            continue
        metadata, filename = record.split(b'\t', 1)
        mode, kind, sha = metadata.decode().split()
        content = git('cat-file', 'blob', sha)
        if any(secret in content for secret in secrets):
            raise SystemExit('Credential detected in committed file: ' + filename.decode())
        records.append((filename.decode(), mode, kind, sha, content))
    credential = dict(line.split('=', 1) for line in git('credential', 'fill', data=b'protocol=https\nhost=github.com\n\n').decode().splitlines() if '=' in line)
    with httpx.Client(base_url='https://api.github.com/repos/ASEpochs/epochflow', headers={
        'Authorization': 'Bearer ' + credential['password'], 'Accept': 'application/vnd.github+json'}, timeout=90) as client:
        def request(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        remote = request('GET', '/git/ref/heads/main')['object']['sha']
        current = git('rev-parse', 'HEAD').decode().strip()
        if remote == current:
            print('Already synchronized')
            return
        parent = git('rev-parse', 'HEAD^').decode().strip()
        if parent != remote:
            raise SystemExit('Remote differs from local parent; resolve history before uploading')
        known = {entry['sha'] for entry in request('GET', '/git/trees/' + remote, params={'recursive': 1})['tree']}
        entries = []
        for path, mode, kind, sha, content in records:
            entry = {'path': path, 'mode': mode, 'type': kind}
            if sha in known:
                entry['sha'] = sha
            else:
                try:
                    entry['content'] = content.decode('utf-8')
                except UnicodeDecodeError:
                    entry['sha'] = request('POST', '/git/blobs', json={
                        'encoding': 'base64', 'content': base64.b64encode(content).decode()})['sha']
            entries.append(entry)
        tree = request('POST', '/git/trees', json={'tree': entries})['sha']
        if tree != git('rev-parse', 'HEAD^{tree}').decode().strip():
            raise SystemExit('Source tree identity mismatch; remote branch not changed')
        timestamp = git('show', '-s', '--format=%at', 'HEAD').decode().strip()
        author = {'name': 'ASEpochs', 'email': '121391438+ASEpochs@users.noreply.github.com',
                  'date': datetime.fromtimestamp(int(timestamp), timezone.utc).isoformat()}
        message = git('show', '-s', '--format=%B', 'HEAD').decode().rstrip() + '\n'
        commit = request('POST', '/git/commits', json={'message': message, 'tree': tree,
                         'parents': [parent], 'author': author, 'committer': author})['sha']
        raw = f"tree {tree}\nparent {parent}\nauthor {author['name']} <{author['email']}> {timestamp} +0000\ncommitter {author['name']} <{author['email']}> {timestamp} +0000\n\n{message}".encode()
        if git('hash-object', '-t', 'commit', '-w', '--stdin', data=raw).decode().strip() != commit:
            raise SystemExit('Commit identity mismatch; remote branch not changed')
        request('PATCH', '/git/refs/heads/main', json={'sha': commit, 'force': False})
        git('update-ref', 'refs/heads/main', commit, current)
        git('update-ref', 'refs/remotes/origin/main', commit)
        print('Synchronized verified source tree:', commit)


if __name__ == '__main__':
    main()
