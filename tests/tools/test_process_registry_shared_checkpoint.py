import json
import time

from tools import process_registry as registry_module
from tools.process_registry import ProcessRegistry, ProcessSession

SECRET = "sk-proj-" + ("a" * 40)


def _entry(process_id="proc_shared", output="first"):
    return {
        "session_id": process_id,
        "command": "python worker.py",
        "pid": 4242,
        "pid_scope": "host",
        "host_start_time": 123,
        "cwd": "C:/work",
        "started_at": time.time(),
        "task_id": "session:telegram",
        "owner_task_id": "stored-telegram",
        "session_key": "agent:main:telegram:dm:1",
        "parent_session_id": "",
        "notify_on_complete": True,
        "watch_patterns": [],
        "output_tail": output,
    }


def test_sync_from_shared_checkpoint_imports_and_refreshes_foreign_output(tmp_path, monkeypatch):
    checkpoint = tmp_path / "processes.json"
    monkeypatch.setattr(registry_module, "CHECKPOINT_PATH", checkpoint)

    peer = ProcessRegistry()
    monkeypatch.setattr(peer, "_host_pid_is_ours", lambda _pid, _start: True)

    checkpoint.write_text(json.dumps([_entry(output="first")]), encoding="utf-8")
    assert peer.sync_from_checkpoint() == 1
    session = peer.get("proc_shared")
    assert session is not None
    assert session.detached is True
    assert session.output_buffer == "first"
    assert session.owner_task_id == "stored-telegram"

    checkpoint.write_text(json.dumps([_entry(output="second")]), encoding="utf-8")
    assert peer.sync_from_checkpoint() == 0
    assert peer.get("proc_shared").output_buffer == "second"


def test_checkpoint_persists_output_tail_for_peer_gateways(tmp_path, monkeypatch):
    checkpoint = tmp_path / "processes.json"
    monkeypatch.setattr(registry_module, "CHECKPOINT_PATH", checkpoint)

    owner = ProcessRegistry()
    session = ProcessSession(
        id="proc_shared",
        command="python worker.py",
        pid=4242,
        host_start_time=123,
        started_at=time.time(),
        output_buffer=f"visible log OPENAI_API_KEY={SECRET}",
    )
    owner._running[session.id] = session
    monkeypatch.setattr(owner, "_safe_host_start_time", lambda _pid: 123)

    owner._write_checkpoint()

    payload = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert payload[0]["output_tail"].startswith("visible log")
    assert SECRET not in payload[0]["output_tail"]
