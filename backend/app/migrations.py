from sqlalchemy import text
from sqlalchemy.engine import Engine


def apply_lightweight_migrations(engine: Engine) -> None:
    """Small dev migration bridge until the project adopts Alembic."""
    statements = [
        "ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS error_message TEXT",
        "ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS model_name VARCHAR(120)",
        "ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS search_provider VARCHAR(80)",
        "ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS plan_history JSONB DEFAULT '[]'::jsonb",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
