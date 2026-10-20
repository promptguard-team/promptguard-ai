"""Operator commands, run inside the gateway container:

    python -m app.cli set-role <email> <role>

Granting the ciso role is deliberately not possible over HTTP: an endpoint
would need an administrator to authorise the first administrator.
"""

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.db import build_sessionmaker
from app.models import User, UserRole


class UserNotFoundError(LookupError):
    """No account is registered under the given email."""


async def set_role(
    sessionmaker: async_sessionmaker[AsyncSession], email: str, role: UserRole
) -> None:
    """Set the role of an existing user."""
    # Stored emails are lowercased at registration (schemas._lowercase_email).
    email = email.lower()
    async with sessionmaker() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise UserNotFoundError(email)
        user.role = role
        await session.commit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    set_role_parser = commands.add_parser("set-role", help="grant or revoke a role")
    set_role_parser.add_argument("email")
    set_role_parser.add_argument("role", choices=[r.value for r in UserRole])
    return parser


async def run(argv: list[str], sessionmaker: async_sessionmaker[AsyncSession]) -> int:
    """Parse `argv` and execute the command against `sessionmaker`."""
    args = build_parser().parse_args(argv)
    try:
        await set_role(sessionmaker, args.email, UserRole(args.role))
    except UserNotFoundError:
        print(f"no user with email {args.email}", file=sys.stderr)
        return 1
    print(f"role of {args.email} set to {args.role}")
    return 0


def main() -> int:
    engine = create_async_engine(get_settings().database_url, poolclass=NullPool)

    async def _run() -> int:
        try:
            return await run(sys.argv[1:], build_sessionmaker(engine))
        finally:
            await engine.dispose()

    return asyncio.run(_run())


if __name__ == "__main__":
    sys.exit(main())
