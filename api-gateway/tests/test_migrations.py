from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

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


def test_lifespan_no_longer_creates_tables():
    # Alembic owns the schema. create_all in the lifespan would silently fail
    # to add columns to an existing table while appearing to work.
    source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert "create_all" not in source
