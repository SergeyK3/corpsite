"""Fixed personnel position types and conservative, ID-bound initial assignments."""
from __future__ import annotations

from pathlib import Path
import json

from sqlalchemy import text


TYPES = ((1, "Врачи"), (2, "Медсёстры и фельдшеры"), (3, "Санитарки"), (4, "Прочий персонал"))
MANIFEST = Path(__file__).resolve().parents[2] / "reference-data" / "position-types" / "backfill-v1.json"


def upgrade(connection) -> dict[int, int]:
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.position_types (
            code SMALLINT PRIMARY KEY CHECK (code BETWEEN 1 AND 4),
            name TEXT NOT NULL UNIQUE CHECK (btrim(name) <> '')
        )
    """))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS public.position_type_backfill_marks (
            position_id BIGINT PRIMARY KEY REFERENCES public.positions(position_id) ON DELETE CASCADE,
            initial_type_code SMALLINT NOT NULL REFERENCES public.position_types(code)
        )
    """))
    for code, name in TYPES:
        connection.execute(text("""
            INSERT INTO public.position_types (code, name) VALUES (:code, :name)
            ON CONFLICT (code) DO NOTHING
        """), {"code": code, "name": name})
    actual = connection.execute(text("SELECT code, name FROM public.position_types ORDER BY code")).all()
    if actual != list(TYPES):
        raise RuntimeError("The fixed position type catalog differs from the expected four values")
    connection.execute(text("""
        ALTER TABLE public.positions ADD COLUMN IF NOT EXISTS type_code SMALLINT
    """))
    connection.execute(text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_positions_type_code') THEN
                ALTER TABLE public.positions ADD CONSTRAINT fk_positions_type_code
                    FOREIGN KEY (type_code) REFERENCES public.position_types(code);
            END IF;
        END $$
    """))
    # CREATE OR REPLACE VIEW must retain the existing column order. Append the
    # new FK after the original columns so existing view consumers keep working.
    connection.execute(text("""
        CREATE OR REPLACE VIEW public.position_directory AS
        SELECT p.position_id, p.name, p.category, p.name_kk,
               p.document_nominative_ru, p.document_possessive_kk,
               p.translation_status, p.document_form_status, p.record_kind, p.revision,
               m.job_code, j.job_nameru AS family_name_ru,
               j.job_namekk AS family_name_kk, j.job_namekk_doc AS family_document_kk,
               p.name AS job_nameru,
               CASE WHEN p.translation_status='confirmed' THEN p.name_kk END AS job_namekk,
               CASE WHEN p.document_form_status='confirmed' THEN p.document_possessive_kk END AS job_namekk_doc,
               p.type_code
        FROM public.positions p
        LEFT JOIN public.position_job_catalog m USING (position_id)
        LEFT JOIN public.job_positions_catalog j USING (job_code)
    """))
    return backfill(connection)


def backfill(connection) -> dict[int, int]:
    """Process a matching ID/name once, even if someone later clears its type."""
    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))["assignments"]
    counts = {code: 0 for code, _ in TYPES}
    for item in rows:
        result = connection.execute(text("""
            WITH first_seen AS (
                INSERT INTO public.position_type_backfill_marks(position_id, initial_type_code)
                SELECT position_id, :code FROM public.positions
                WHERE position_id = :id AND name = :name
                ON CONFLICT (position_id) DO NOTHING RETURNING position_id
            )
            UPDATE public.positions SET type_code = :code
            WHERE position_id IN (SELECT position_id FROM first_seen) AND type_code IS NULL
        """), {"id": item["id"], "name": item["name"], "code": item["type_code"]})
        counts[item["type_code"]] += result.rowcount
    return counts
