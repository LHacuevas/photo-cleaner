"""
Alembic environment: migrations run against the app's engine (config.DATABASE_URL),
or against the connection passed in by database.init_db().
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import Base, engine  # noqa: E402

config = context.config
target_metadata = Base.metadata

# Only configure logging when run from the alembic CLI, not when the app runs migrations
if config.config_file_name and "connection" not in config.attributes:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def run_migrations(connection):
    # render_as_batch: SQLite can only ALTER tables by recreating them
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    run_migrations(connection)
else:
    with engine.connect() as connection:
        run_migrations(connection)
        connection.commit()
