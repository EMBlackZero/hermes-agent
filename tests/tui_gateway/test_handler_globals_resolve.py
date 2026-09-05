"""Every rebound @method handler must resolve all of its global names.

Handlers defined in the ``methods_*`` split modules are rebound onto
``tui_gateway.server``'s globals at install time (see
``method_ctx.HandlerRegistry.install``), so a plain module-level def in a
``methods_*`` module is invisible to its own handler bodies and blows up with
``NameError`` on the first call. Unit tests that import the helper from its
defining module do not catch this — they exercise a namespace that never
exists in production. This walks the real bytecode instead.
"""

import builtins
import dis

from tui_gateway import server


def _global_loads(code, seen=None):
    """Every LOAD_GLOBAL name in ``code`` and its nested code objects."""
    if seen is None:
        seen = set()
    for ins in dis.get_instructions(code):
        if ins.opname == "LOAD_GLOBAL":
            seen.add(ins.argval)
    for const in code.co_consts:
        if hasattr(const, "co_names"):
            _global_loads(const, seen)
    return seen


def test_every_registered_handler_resolves_its_globals():
    namespace = vars(server)
    unresolved = []

    for method_name, fn in sorted(server._methods.items()):
        code = getattr(fn, "__code__", None)
        if code is None:  # decorated (e.g. _profile_scoped) — unwrap
            code = getattr(getattr(fn, "__wrapped__", None), "__code__", None)
        if code is None:
            continue
        for name in _global_loads(code):
            if name not in namespace and not hasattr(builtins, name):
                unresolved.append(f"{method_name} -> {name}")

    assert not unresolved, (
        "handler bodies reference names missing from tui_gateway.server's "
        "globals; define them on server.py (like _ok/_err) or import them at "
        "call time:\n  " + "\n  ".join(unresolved)
    )


def test_process_scope_helpers_live_on_the_server_namespace():
    """Regression: these two were defined in methods_tools and unreachable."""
    assert callable(getattr(server, "_process_scope_session", None))
    assert callable(getattr(server, "_process_owned_by_session", None))
