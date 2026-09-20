import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app import main
from app.db import build_engine as _real_build_engine


async def test_lifespan_sets_app_state_and_shuts_down_cleanly(tmp_path, monkeypatch):
    """Drive the real lifespan context manager end-to-end.

    tests/conftest.py builds the app and sets app.state.* by hand, so the
    real lifespan in app/main.py never runs in any other test. No
    LifespanManager (asgi-lifespan) is installed, and httpx.ASGITransport
    does not send lifespan events on its own, so the least invasive option
    is to drive `lifespan(app)` directly as the async context manager it
    already is.

    Settings.database_url is always a postgresql+asyncpg URL, and asyncpg
    isn't even installed in this dev venv, so `build_engine` is monkeypatched
    to redirect to a file-backed SQLite database instead. A file (not
    `:memory:`): build_engine's explicit pool_size/max_overflow (Fix 5)
    requires a poolclass that accepts them, and SQLite's `:memory:` default
    (StaticPool) does not.
    """
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'lifespan.db'}"
    monkeypatch.setattr(main, "build_engine", lambda _url: _real_build_engine(db_url))

    app_instance = main.create_app()
    async with main.lifespan(app_instance):
        assert app_instance.state.engine is not None
        assert app_instance.state.sessionmaker is not None
        assert app_instance.state.llm_client is not None
        assert app_instance.state.classifier_client is not None

        # The engine and sessionmaker are not just set but actually wired up.
        async with app_instance.state.sessionmaker() as session:
            await session.execute(text("SELECT 1"))

    # Shutdown ran to completion without raising (a failing dispose would
    # have propagated out of the `async with` above), and both HTTP clients
    # are verifiably closed rather than merely assumed to be.
    assert app_instance.state.llm_client._client.is_closed is True
    assert app_instance.state.classifier_client._client.is_closed is True


async def test_lifespan_shutdown_still_releases_remaining_resources_when_a_client_fails_to_close(
    tmp_path, monkeypatch
):
    """The shutdown nests try/finally three deep so that a client whose
    aclose() raises still leaves the remaining client closed and the engine
    disposed, instead of aborting the rest of shutdown. The happy-path test
    above can't exercise this: with no exception, a flattened sequence of
    awaits would look identical. This test forces llm_client.aclose() to
    raise and checks the two properties that only hold if the nesting (not a
    flat sequence) is what runs.
    """
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'lifespan_failure.db'}"
    monkeypatch.setattr(main, "build_engine", lambda _url: _real_build_engine(db_url))

    # AsyncEngine.dispose is a read-only instance attribute (proxied to the
    # sync engine), so it can't be monkeypatched per-instance. Patch the
    # class method instead and spy on the call before delegating to the
    # original, so we can tell whether dispose() actually ran.
    dispose_calls: list[bool] = []
    original_dispose = AsyncEngine.dispose

    async def _spy_dispose(self, *args, **kwargs):
        dispose_calls.append(True)
        await original_dispose(self, *args, **kwargs)

    monkeypatch.setattr(AsyncEngine, "dispose", _spy_dispose)

    async def _raise_on_close():
        raise RuntimeError("boom")

    app_instance = main.create_app()
    with pytest.raises(RuntimeError, match="boom"):
        async with main.lifespan(app_instance):
            monkeypatch.setattr(
                app_instance.state.llm_client, "aclose", _raise_on_close
            )

    # llm_client's aclose raised, but the classifier client was still closed
    # and the engine was still disposed rather than being skipped.
    assert app_instance.state.classifier_client._client.is_closed is True
    assert dispose_calls == [True]
