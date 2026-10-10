"""Opt-in local recovery only. No autogeneration and no offline execution."""
from pathlib import Path

from alembic import context
from dotenv import dotenv_values
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[2]
if context.is_offline_mode():
    raise RuntimeError('Recovery requires online snapshot checks; offline upgrades are forbidden')
if context.get_x_argument(as_dictionary=True).get('approved_local_recovery') != '1':
    raise RuntimeError('Preparation only. An explicitly authorized recovery/rehearsal must opt in.')
explicit = context.config.get_main_option('sqlalchemy.url')
url = make_url(explicit or dotenv_values(root / '.env')['DATABASE_URL'])
if url.host not in {'localhost', '127.0.0.1', '::1'} or url.database not in {'corpsite', 'corpsite_stage3_rehearsal'}:
    raise RuntimeError('STOP: only the working local database or its named rehearsal copy is allowed')
with create_engine(url, isolation_level='REPEATABLE READ').connect() as connection:
    context.configure(connection=connection, target_metadata=None, transactional_ddl=True)
    with context.begin_transaction():
        context.run_migrations()
