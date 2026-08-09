"""ADR-065 class-3a lock and generation protocol for personnel-order evidence."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection


class PersonnelOrderEvidenceScopeError(RuntimeError):
    code = "ORDER_EVIDENCE_SCOPE_INVALID"


@dataclass(frozen=True, slots=True)
class PersonnelOrderEvidenceScopeToken:
    order_id: int
    generation: int


def create_personnel_order_evidence_scope_tx(
    conn: Connection, *, order_id: int
) -> PersonnelOrderEvidenceScopeToken:
    row = conn.execute(
        text(
            """
            INSERT INTO public.personnel_order_evidence_scopes(order_id)
            VALUES (:order_id)
            RETURNING order_id, generation
            """
        ),
        {"order_id": int(order_id)},
    ).mappings().one()
    return PersonnelOrderEvidenceScopeToken(int(row["order_id"]), int(row["generation"]))


def lock_personnel_order_evidence_scopes_tx(
    conn: Connection, *, order_ids: Iterable[int]
) -> tuple[PersonnelOrderEvidenceScopeToken, ...]:
    ids = sorted({int(value) for value in order_ids})
    if not ids:
        return ()
    statement = text(
        """
        SELECT order_id, generation
        FROM public.personnel_order_evidence_scopes
        WHERE order_id = ANY(:sorted_order_ids)
        ORDER BY order_id
        FOR UPDATE
        """
    )
    rows = list(conn.execute(statement, {"sorted_order_ids": ids}).mappings())
    if len(rows) != len(ids) or [int(row["order_id"]) for row in rows] != ids:
        raise PersonnelOrderEvidenceScopeError(
            "Personnel-order evidence scope is missing or duplicated."
        )
    return tuple(
        PersonnelOrderEvidenceScopeToken(int(row["order_id"]), int(row["generation"]))
        for row in rows
    )


def advance_personnel_order_evidence_scopes_tx(
    conn: Connection, *, tokens: Iterable[PersonnelOrderEvidenceScopeToken]
) -> tuple[PersonnelOrderEvidenceScopeToken, ...]:
    advanced: list[PersonnelOrderEvidenceScopeToken] = []
    for token in sorted(tokens, key=lambda value: value.order_id):
        row = conn.execute(
            text(
                """
                UPDATE public.personnel_order_evidence_scopes
                SET generation=generation+1,
                    updated_at=transaction_timestamp()
                WHERE order_id=:order_id AND generation=:generation
                RETURNING order_id, generation
                """
            ),
            {"order_id": token.order_id, "generation": token.generation},
        ).mappings().first()
        if row is None:
            raise PersonnelOrderEvidenceScopeError(
                "Personnel-order evidence scope generation changed concurrently."
            )
        advanced.append(
            PersonnelOrderEvidenceScopeToken(int(row["order_id"]), int(row["generation"]))
        )
    return tuple(advanced)
