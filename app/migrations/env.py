"""Alembic environment: the app passes an open connection in config.attributes["connection"]."""

from alembic import context

from app import models  # noqa: F401  (register tables)
from app.db import Base

config = context.config
target_metadata = Base.metadata


def run() -> None:
    connection = config.attributes["connection"]
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=connection.dialect.name == "sqlite",  # SQLite needs batch mode for ALTER TABLE
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


run()
