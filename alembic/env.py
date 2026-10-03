import os
from logging.config import fileConfig
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
explicit_database_url = config.get_main_option("sqlalchemy.url")
if not explicit_database_url or not explicit_database_url.strip():
    if os.getenv("ALEMBIC_USE_TEST_DATABASE") == "1":
        # This opt-in path is deliberately independent of DATABASE_URL so an
        # operator cannot accidentally upgrade a development/production DB.
        database_url = os.getenv("TEST_DATABASE_URL") or ""
        parsed = urlparse(database_url)
        database_name = (parsed.path or "").rstrip("/").split("/")[-1]
        if parsed.hostname not in {"localhost", "127.0.0.1"} or database_name != "corpsite_test":
            raise RuntimeError("ALEMBIC_USE_TEST_DATABASE requires loopback TEST_DATABASE_URL for corpsite_test")
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    else:
        # Normal application/CLI startup keeps the established .env fallback.  A URL
        # supplied explicitly through Alembic Config is authoritative and is never
        # replaced by process environment or .env state.
        load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL is not set and sqlalchemy.url was not supplied")
        # ConfigParser treats '%' as interpolation; escape for passwords containing it.
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
