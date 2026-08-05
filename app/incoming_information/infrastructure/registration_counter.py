"""Registration number counter with row lock (ADR-062)."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection


def allocate_registration_number(conn: Connection, *, registration_year: int) -> tuple[int, str]:
    conn.execute(
        text(
            """
            INSERT INTO public.incoming_document_registration_counters (
                registration_year, last_seq
            )
            VALUES (:year, 0)
            ON CONFLICT (registration_year) DO NOTHING
            """
        ),
        {"year": int(registration_year)},
    )
    row = conn.execute(
        text(
            """
            SELECT last_seq
            FROM public.incoming_document_registration_counters
            WHERE registration_year = :year
            FOR UPDATE
            """
        ),
        {"year": int(registration_year)},
    ).one()
    new_seq = int(row[0]) + 1
    conn.execute(
        text(
            """
            UPDATE public.incoming_document_registration_counters
            SET last_seq = :seq, updated_at = now()
            WHERE registration_year = :year
            """
        ),
        {"year": int(registration_year), "seq": new_seq},
    )
    registration_number = f"ВХ-{registration_year}-{new_seq:04d}"
    return new_seq, registration_number
