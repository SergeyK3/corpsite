"""Extend the existing specialty identity without rewriting its consumers."""
from sqlalchemy import text


def upgrade(connection):
    connection.execute(text("ALTER TABLE public.medical_specialties ADD COLUMN IF NOT EXISTS name_kk TEXT"))


def downgrade(connection):
    raise RuntimeError("Kazakh specialty names are user data; preserve them before rollback")
