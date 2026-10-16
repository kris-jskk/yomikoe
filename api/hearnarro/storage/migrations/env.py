"""Alembic environment for the HearNarro SQLite database (D7).

The URL comes from the Alembic config (set by ``hearnarro.storage.db.run_migrations``) or,
for the ``alembic`` CLI, from ``HEARNARRO_DATA_DIR``. Migrations are raw DDL, so there is
no ``target_metadata`` and autogenerate is not used.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from hearnarro.storage.db import db_path, resolve_data_dir, sync_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

url = config.get_main_option("sqlalchemy.url") or sync_url(db_path(resolve_data_dir(None)))


def run_migrations_offline() -> None:
    context.configure(url=url, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
