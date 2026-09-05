from types import SimpleNamespace

from tools.process_registry import process_registry
from tui_gateway import server


def test_session_processes_accepts_durable_owner_when_gateway_routing_key_differs(monkeypatch):
    """Telegram processes must remain visible from the desktop's stored session."""
    entry = {"session_id": "proc_telegram", "status": "running"}
    proc = SimpleNamespace(
        session_key="agent:main:telegram:dm:5944283363",
        owner_task_id="stored-telegram",
        parent_session_id="",
        output_buffer="working",
    )

    monkeypatch.setattr(process_registry, "list_sessions", lambda: [entry.copy()])
    monkeypatch.setattr(process_registry, "get", lambda _process_id: proc)

    assert server._session_processes({"session_key": "stored-telegram"}) == [
        {"session_id": "proc_telegram", "status": "running", "output_tail": "working"}
    ]


def test_session_processes_does_not_cross_durable_session_boundaries(monkeypatch):
    entry = {"session_id": "proc_other", "status": "running"}
    proc = SimpleNamespace(
        session_key="agent:main:telegram:dm:other",
        owner_task_id="stored-other",
        parent_session_id="stored-other",
        output_buffer="private",
    )

    monkeypatch.setattr(process_registry, "list_sessions", lambda: [entry.copy()])
    monkeypatch.setattr(process_registry, "get", lambda _process_id: proc)

    assert server._session_processes({"session_key": "stored-telegram"}) == []


def test_process_scope_falls_back_to_durable_session_id(monkeypatch):
    """Durable fallback only applies for 4001 (session not found), not other errors."""
    missing_runtime_error = {"error": {"code": 4001}}
    monkeypatch.setattr(server, "_sess", lambda _params, _rid: (None, missing_runtime_error), raising=False)

    session, error = server._process_scope_session(
        {"session_id": "stored-telegram"},
        "request-1",
    )

    assert error is None
    assert session == {"session_key": "stored-telegram"}


def test_process_scope_propagates_non_4001_errors(monkeypatch):
    """Non-4001 errors (auth, validation) must propagate, not trigger durable fallback."""
    auth_error = {"error": {"code": 403}}
    monkeypatch.setattr(server, "_sess", lambda _params, _rid: (None, auth_error), raising=False)

    session, error = server._process_scope_session(
        {"session_id": "stored-telegram"},
        "request-1",
    )

    assert session is None
    assert error == auth_error


def test_process_scope_keeps_missing_session_id_error(monkeypatch):
    expected_error = {"error": {"code": 404}}
    monkeypatch.setattr(server, "_sess", lambda _params, _rid: (None, expected_error), raising=False)

    session, error = server._process_scope_session({}, "request-1")

    assert session is None
    assert error is expected_error


def test_process_kill_syncs_peer_registry_and_accepts_durable_owner(monkeypatch):
    proc = SimpleNamespace(
        session_key="agent:main:telegram:dm:5944283363",
        owner_task_id="stored-telegram",
        parent_session_id="",
    )
    synced = []
    monkeypatch.setattr(server, "_sess", lambda _params, _rid: (None, {"error": {"code": 4001}}))
    monkeypatch.setattr(process_registry, "sync_from_checkpoint", lambda: synced.append(True))
    monkeypatch.setattr(process_registry, "get", lambda _process_id: proc)
    monkeypatch.setattr(process_registry, "kill_process", lambda process_id: {"status": "killed", "session_id": process_id})

    response = server._methods["process.kill"](
        "request-1",
        {"session_id": "stored-telegram", "process_id": "proc_telegram"},
    )

    assert synced == [True]
    assert response["result"] == {"status": "killed", "session_id": "proc_telegram"}
