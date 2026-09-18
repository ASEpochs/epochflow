"""Start EpochFlow only. Press Ctrl+C to stop both child processes."""
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_port(port):
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except OSError:
            raise SystemExit(f'端口 {port} 已被占用；未结束其他进程。请先关闭对应服务。')


def main():
    python = ROOT / 'backend/.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    node = os.getenv('NODE_BINARY') or shutil.which('node')
    if not python.exists() or not node:
        raise SystemExit('请先根据 README 安装后端 .venv 与 Node 22+；也可设置 NODE_BINARY。')
    major = int(subprocess.check_output([node, '--version'], text=True).strip().lstrip('v').split('.')[0])
    if major < 22:
        raise SystemExit('请使用 Node 22+。当前 PATH 中的 Node 版本较旧，可设置 NODE_BINARY 为新版 node.exe 路径。')
    check_port(8003)
    check_port(5174)
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    environment = {**os.environ, 'VITE_PYTHON_API_URL': 'http://127.0.0.1:8003'}
    children = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        with (runtime / 'backend.log').open('a', encoding='utf-8') as backend_log, (runtime / 'frontend.log').open('a', encoding='utf-8') as frontend_log:
            children.append(subprocess.Popen([str(python), '-m', 'uvicorn', 'api.main:app', '--host', '127.0.0.1', '--port', '8003'], cwd=ROOT / 'backend', env=environment, stdout=backend_log, stderr=subprocess.STDOUT, creationflags=flags))
            children.append(subprocess.Popen([node, str(ROOT / 'frontend/node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '5174', '--strictPort'], cwd=ROOT / 'frontend', env=environment, stdout=frontend_log, stderr=subprocess.STDOUT, creationflags=flags))
            print('EpochFlow: http://127.0.0.1:5174  |  API: http://127.0.0.1:8003')
            print('保留此终端；按 Ctrl+C 关闭本次启动的前后端。日志：.runtime/')
            while all(child.poll() is None for child in children):
                time.sleep(1)
            raise SystemExit('有服务退出，请检查 .runtime 中的日志。')
    except KeyboardInterrupt:
        print('\n正在停止 EpochFlow…')
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()


if __name__ == '__main__':
    main()
