from pathlib import Path

import pytest

from alembic.config import Config
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.engine import Inspector

from app.models import Base

ROOT = Path(__file__).resolve().parents[1]


def test_alembic_is_configured():
    config = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())
    assert revisions, "no migrations found"


def test_there_is_exactly_one_head():
    config = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    assert len(script.get_heads()) == 1


def test_nothing_in_app_creates_tables():
    # Alembic owns the schema. create_all anywhere under app/ would silently
    # fail to add columns to an existing table while appearing to work.
    # Checking only main.py would miss create_all reintroduced through a
    # different module main.py imports (e.g. app/db.py), so scan the whole
    # package.
    offenders = [
        str(path.relative_to(ROOT))
        for path in (ROOT / "app").rglob("*.py")
        if "create_all" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, f"create_all found in: {offenders}"


def test_env_does_not_put_the_database_url_through_configparser():
    # `Config.set_main_option` stores the value in a ConfigParser, which treats
    # `%` as interpolation syntax and raises on `set` -- before any migration
    # runs. A password containing a percent sign, including the URL-encoded
    # `p%40ss` that is the correct way to carry an `@`, would therefore stop
    # the production container from starting, with an error naming neither the
    # password nor the setting. env.py builds the engine from Settings instead.
    # Comments are stripped first: env.py explains this hazard by name, and an
    # explanation of why we avoid a call must not look like the call.
    code = "\n".join(
        line
        for line in (ROOT / "alembic" / "env.py")
        .read_text(encoding="utf-8")
        .splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "set_main_option" not in code

    # Demonstrate the hazard is real rather than theoretical, so a future
    # reader can see why the structural check above exists.
    config = Config(str(ROOT / "alembic.ini"))
    with pytest.raises(ValueError, match="interpolation"):
        config.set_main_option(
            "sqlalchemy.url", "postgresql+asyncpg://u:p%40ss@db:5432/x"
        )


def _revisions_in_upgrade_order(script: ScriptDirectory) -> list:
    """All revisions from base to head, oldest first.

    ``walk_revisions`` follows ``down_revision`` pointers starting at head,
    so it yields newest-first; reverse it to get the order ``upgrade()``
    must be applied in.
    """
    revisions = list(script.walk_revisions(base="base", head="head"))
    revisions.reverse()
    return revisions


def _migrate_to_head(connection) -> None:
    """Apply every revision's upgrade(), oldest first, on `connection`."""
    script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    ctx = MigrationContext.configure(connection)
    for revision in _revisions_in_upgrade_order(script):
        with ctx.begin_transaction():
            with Operations.context(ctx):
                revision.module.upgrade()


def _describe_schema(inspector: Inspector) -> dict:
    """A dialect-independent-enough snapshot of a live schema: per table,
    the columns (name -> (type string, nullable)), indexes, primary key,
    and foreign keys.

    Column types are captured as the string rendering of the *reflected*
    type, not compared against SQLAlchemy model type objects directly —
    both schemas being compared here go through this same reflection path,
    so the comparison is reflected-vs-reflected rather than
    model-object-vs-reflected-object, which sidesteps dialect-specific
    reflection quirks (e.g. Enum coming back as VARCHAR) that would
    otherwise have nothing to do with actual schema drift.
    """
    schema = {}
    for table_name in sorted(inspector.get_table_names()):
        columns = {
            col["name"]: (str(col["type"]), bool(col["nullable"]))
            for col in inspector.get_columns(table_name)
        }
        indexes = {
            (idx["name"], tuple(idx["column_names"]), bool(idx["unique"]))
            for idx in inspector.get_indexes(table_name)
        }
        pk = tuple(
            sorted(inspector.get_pk_constraint(table_name)["constrained_columns"])
        )
        fks = {
            (
                tuple(fk["constrained_columns"]),
                fk["referred_table"],
                tuple(fk["referred_columns"]),
            )
            for fk in inspector.get_foreign_keys(table_name)
        }
        schema[table_name] = {
            "columns": columns,
            "indexes": indexes,
            "pk": pk,
            "fks": fks,
        }
    return schema


def test_migrations_at_head_reproduce_models():
    """The durable drift guard: migrations run in order to head must produce
    exactly the schema `Base.metadata` describes. Unlike checking revision
    0001 alone, this keeps holding as later revisions are added (e.g. by
    Task 9), which is exactly when baseline drift would otherwise appear
    silently — a migration set that disagrees with the models looks correct
    and fails only later, in a real database.

    What this comparison does NOT cover, because `_describe_schema` doesn't
    capture it and/or SQLite reflection can't see it:
    - `server_default` values (e.g. a column's default is compared only for
      presence via nullable/type, not for the actual default expression).
    - Foreign-key cascade options (`ondelete`/`onupdate`) — `fks` only
      records the constrained/referred columns and table, not cascade rules.
    - Enum value membership on SQLite — SQLAlchemy's `Enum` reflects there
      as a plain `VARCHAR(n)` sized to the longest label, with no CHECK
      constraint, so adding, removing, or renaming an enum member can leave
      this test green even though PostgreSQL's real enum type would differ.
    """
    migrated_engine = create_engine("sqlite:///:memory:")
    with migrated_engine.connect() as connection:
        _migrate_to_head(connection)
        migrated_schema = _describe_schema(sa_inspect(connection))

    model_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(model_engine)
    model_schema = _describe_schema(sa_inspect(model_engine))

    assert migrated_schema == model_schema


def test_head_indexes_audit_created_at():
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        _migrate_to_head(connection)
        indexes = sa_inspect(connection).get_indexes("audit_events")
    assert {(idx["name"], tuple(idx["column_names"])) for idx in indexes} >= {
        ("ix_audit_events_created_at", ("created_at",))
    }
