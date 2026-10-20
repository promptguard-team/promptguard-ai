import pytest
from sqlalchemy import select

from app.cli import UserNotFoundError, run, set_role
from app.models import User, UserRole


async def _register(client, email):
    resp = await client.post(
        "/auth/register", json={"email": email, "password": "secret123"}
    )
    assert resp.status_code == 201


async def _role_of(app, email):
    async with app.state.sessionmaker() as session:
        result = await session.execute(select(User.role).where(User.email == email))
        return result.scalar_one()


async def test_set_role_promotes_and_demotes(app, client):
    await _register(client, "boss@example.com")

    await set_role(app.state.sessionmaker, "boss@example.com", UserRole.ciso)
    assert await _role_of(app, "boss@example.com") is UserRole.ciso

    await set_role(app.state.sessionmaker, "boss@example.com", UserRole.chat_user)
    assert await _role_of(app, "boss@example.com") is UserRole.chat_user


async def test_set_role_matches_email_case_insensitively(app, client):
    await _register(client, "boss@example.com")

    await set_role(app.state.sessionmaker, "Boss@Example.COM", UserRole.ciso)

    assert await _role_of(app, "boss@example.com") is UserRole.ciso


async def test_set_role_unknown_email_raises(app):
    with pytest.raises(UserNotFoundError):
        await set_role(app.state.sessionmaker, "nobody@example.com", UserRole.ciso)


async def test_run_returns_1_and_names_the_email_on_unknown_user(app, capsys):
    code = await run(["set-role", "nobody@example.com", "ciso"], app.state.sessionmaker)

    assert code == 1
    assert "nobody@example.com" in capsys.readouterr().err


async def test_run_rejects_an_unknown_role(app):
    with pytest.raises(SystemExit) as exc:
        await run(["set-role", "boss@example.com", "admin"], app.state.sessionmaker)
    assert exc.value.code == 2


async def test_ciso_headers_fixture_is_a_ciso(client, ciso_headers):
    resp = await client.get("/auth/me", headers=ciso_headers)

    assert resp.status_code == 200
    assert resp.json()["role"] == "ciso"
