"""Application migration must preserve rows without inventing personal destinations."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory


def test_personal_oauth_migration_upgrade_roundtrip_and_downgrade():
    migration_dir = Path(__file__).resolve().parents[4] / "migrations"
    path = migration_dir / "versions/20260909_0002_personal_oauth_settings.py"
    spec = importlib.util.spec_from_file_location("personal_settings_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as db:
        db.execute(sa.text("CREATE TABLE user_oauth_tokens(id INTEGER PRIMARY KEY)"))
        db.execute(sa.text("INSERT INTO user_oauth_tokens(id) VALUES(1)"))
        with Operations.context(MigrationContext.configure(db)):
            module.upgrade()
            table = sa.Table("user_oauth_tokens", sa.MetaData(), autoload_with=db)
            assert db.execute(sa.select(table.c.provider_config)).scalar() is None
            settings = {"instance_url": "https://personal.example.invalid"}
            db.execute(table.update().where(table.c.id == 1).values(provider_config=settings))
            assert db.execute(sa.select(table.c.provider_config)).scalar() == settings
            module.downgrade()
        assert [c["name"] for c in sa.inspect(db).get_columns("user_oauth_tokens")] == ["id"]
        assert db.execute(sa.text("SELECT id FROM user_oauth_tokens")).scalar() == 1
    assert len(ScriptDirectory(str(migration_dir)).get_heads()) == 1
    assert "20260909_0002" in {r.revision for r in ScriptDirectory(str(migration_dir)).walk_revisions()}
