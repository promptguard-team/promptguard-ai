from sqlalchemy import text

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

        # The engine and sessionmaker are not just set but actually wired up.
        async with app_instance.state.sessionmaker() as session:
            await session.execute(text("SELECT 1"))

    # Shutdown ran to completion without raising (a failing dispose would
    # have propagated out of the `async with` above), and the HTTP client is
    # verifiably closed rather than merely assumed to be.
    assert app_instance.state.llm_client._client.is_closed is True
