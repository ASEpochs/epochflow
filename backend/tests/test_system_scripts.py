import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "开启系统.py"
SPEC = importlib.util.spec_from_file_location("system_start_test", SCRIPT)
system = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(system)


def process(pid, parent, name, command, created="creation-1"):
    return {"ProcessId": pid, "ParentProcessId": parent, "Name": name,
            "CommandLine": command, "Created": created}


def test_match_exact_project_and_descendants_not_other_python():
    snapshot = [
        process(100, 50, "python.exe", f'"{system.BACKEND / ".venv/Scripts/python.exe"}" -m uvicorn api.main:app'),
        process(101, 100, "python.exe", "shared-base-python -m uvicorn api.main:app"),
        process(102, 101, "python.exe", "multiprocessing worker"),
        process(200, 50, "python.exe", "C:/another-project/python.exe -m uvicorn api.main:app"),
        process(201, 200, "python.exe", "multiprocessing worker"),
        process(300, 50, "node.exe", f'node "{system.FRONTEND / "node_modules/vite/bin/vite.js"}"'),
        process(301, 300, "esbuild.exe", "esbuild"),
        process(400, 50, "python.exe", f'"{system.BACKEND / ".venv/Scripts/python.exe"}" -m pytest'),
    ]
    assert system.project_process_ids(snapshot) == {100, 101, 102, 300, 301}


def test_include_relative_launcher_but_not_interactive_shell():
    launcher = process(100, 50, "powershell.exe", "powershell -File .\\start-local.ps1 -Direct -Port 8002")
    child = process(101, 100, "python.exe", f'"{system.BACKEND / ".venv/Scripts/python.exe"}" api\\main.py')
    shell = process(50, 1, "powershell.exe", "powershell.exe")
    assert system.project_process_ids([launcher, child, shell]) == {100, 101}


def test_refuse_reused_pid_when_stopping(monkeypatch):
    original = process(100, 50, "python.exe", f'"{system.BACKEND / ".venv/Scripts/python.exe"}" api\\main.py')
    replacement = process(100, 50, "python.exe", "unrelated program", created="creation-2")
    monkeypatch.setattr(system, "processes", lambda: [replacement])
    run = Mock()
    monkeypatch.setattr(system.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="身份发生变化"):
        system.stop_project_processes([original])
    run.assert_not_called()


def test_closed_port_needs_no_process_lookup(monkeypatch):
    monkeypatch.setattr(system, "port_open", lambda port: False)
    lookup = Mock()
    monkeypatch.setattr(system, "processes", lookup)
    assert system.require_owned_port(8002) is False
    lookup.assert_not_called()


def test_reject_foreign_port_owner(monkeypatch):
    monkeypatch.setattr(system, "port_open", lambda port: True)
    monkeypatch.setattr(system, "powershell_json", lambda script: [{"OwningProcess": 900, "LocalAddress": "127.0.0.1"}])
    monkeypatch.setattr(system, "processes", lambda: [])
    with pytest.raises(RuntimeError, match="被其他"):
        system.require_owned_port(8002)


def test_reuse_confirmed_project_port(monkeypatch):
    owner = process(100, 50, "python.exe", f'"{system.BACKEND / ".venv/Scripts/python.exe"}" -m uvicorn api.main:app')
    monkeypatch.setattr(system, "port_open", lambda port: True)
    monkeypatch.setattr(system, "powershell_json", lambda script: [{"OwningProcess": 100, "LocalAddress": "127.0.0.1"}])
    monkeypatch.setattr(system, "processes", lambda: [owner])
    assert system.require_owned_port(8002) is True


def test_reuse_healthy_databases(monkeypatch):
    monkeypatch.setattr(system, "docker_executable", lambda: "docker.exe")
    run = Mock(return_value=Mock(returncode=0, stdout="true healthy\n"))
    monkeypatch.setattr(system.subprocess, "run", run)
    assert system.databases_ready() is True
    assert run.call_count == 2


def test_stopped_database_requires_startup(monkeypatch):
    monkeypatch.setattr(system, "docker_executable", lambda: "docker.exe")
    monkeypatch.setattr(system.subprocess, "run", Mock(return_value=Mock(returncode=0, stdout="false healthy\n")))
    assert system.databases_ready() is False
