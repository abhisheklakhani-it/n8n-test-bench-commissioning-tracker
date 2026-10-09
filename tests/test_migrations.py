"""Updates must never lose data: upgrade a database that already contains data."""

from alembic import command
from sqlalchemy import create_engine, text

from app.db import alembic_config


def _upgrade(engine, revision):
    with engine.begin() as conn:
        cfg = alembic_config()
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, revision)


def test_upgrade_keeps_existing_data(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    _upgrade(engine, "0001")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO step_templates (code, position, name_de, name_en, discipline, depends_on, instructions_de, instructions_en, "
            "checklist_de, checklist_en, measurements) VALUES ('S01', 1, 'Alt', 'Old', 'MECH', '[]', 'x', 'x', '[\"a\"]', '[\"a\"]', '[]')"))
        conn.execute(text("INSERT INTO analysis_entries (section, data, position, archived, created_at, updated_at) "
                          "VALUES ('kpi', '{\"name\": \"Durchlaufzeit\"}', 1, 0, '2026-10-09', '2026-10-09')"))
    _upgrade(engine, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version FROM step_templates WHERE code = 'S01'")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM analysis_entries")).scalar() == 1
        assert conn.execute(text("SELECT count(*) FROM step_revisions")).scalar() == 0
