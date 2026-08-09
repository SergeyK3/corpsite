"""ADR-048 authority: read-only exact-IIN Person Create-or-Link resolution."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection

PersonResolutionDecision = Literal[
    "P0_CREATE",
    "P1_ADOPT",
    "AMBIGUOUS",
    "INCOMPATIBLE",
    "CONFLICT",
]


@dataclass(frozen=True)
class Adr048PersonCandidate:
    person_id: int
    iin: str
    person_status: str
    merged_into_person_id: int | None
    conflicting_employee_ids: tuple[int, ...]
    incompatibility_reasons: tuple[str, ...]

    @property
    def compatible(self) -> bool:
        return not self.incompatibility_reasons


@dataclass(frozen=True)
class Adr048PersonResolution:
    decision: PersonResolutionDecision
    candidates: tuple[Adr048PersonCandidate, ...]
    reason_codes: tuple[str, ...]


def resolve_person_create_or_link_exact_iin_tx(
    conn: Connection,
    *,
    iin: str,
    target_employee_id: int | None,
) -> Adr048PersonResolution:
    """Resolve ADR-048 P0/P1 using the caller-owned transaction; never writes."""
    if len(iin) != 12 or any(char < "0" or char > "9" for char in iin):
        raise ValueError("ADR-048 exact identity input must be 12 ASCII digits")

    person_rows = list(
        conn.execute(
            text(
                """
                SELECT person_id, iin, person_status, merged_into_person_id
                  FROM public.persons
                 WHERE iin = :iin
                 ORDER BY person_id
                """
            ),
            {"iin": iin},
        ).mappings()
    )
    target_person_id: int | None = None
    if target_employee_id is not None:
        target_person_id = conn.execute(
            text(
                "SELECT person_id FROM public.employees "
                "WHERE employee_id=:employee_id"
            ),
            {"employee_id": int(target_employee_id)},
        ).scalar_one_or_none()
        if target_person_id is not None:
            target_person_id = int(target_person_id)
    if not person_rows:
        if target_person_id is not None:
            return Adr048PersonResolution(
                decision="CONFLICT",
                candidates=(),
                reason_codes=("TARGET_EMPLOYEE_PERSON_IDENTITY_CONFLICT",),
            )
        return Adr048PersonResolution(
            decision="P0_CREATE",
            candidates=(),
            reason_codes=(),
        )

    person_ids = [int(row["person_id"]) for row in person_rows]
    linked_statement = text(
        """
        SELECT person_id, employee_id
          FROM public.employees
         WHERE person_id IN :person_ids
           AND operational_status IN ('active', 'suspended')
         ORDER BY person_id, employee_id
        """
    ).bindparams(bindparam("person_ids", expanding=True))
    linked_by_person: dict[int, list[int]] = {}
    for row in conn.execute(linked_statement, {"person_ids": person_ids}).mappings():
        employee_id = int(row["employee_id"])
        if target_employee_id is not None and employee_id == int(target_employee_id):
            continue
        linked_by_person.setdefault(int(row["person_id"]), []).append(employee_id)

    candidates: list[Adr048PersonCandidate] = []
    for row in person_rows:
        person_id = int(row["person_id"])
        reasons: list[str] = []
        if row["person_status"] == "merged" or row["merged_into_person_id"] is not None:
            reasons.append("PERSON_MERGED")
        elif row["person_status"] != "active":
            reasons.append("PERSON_INACTIVE")
        conflicting_employee_ids = tuple(linked_by_person.get(person_id, ()))
        if conflicting_employee_ids:
            reasons.append("PERSON_ACTIVE_EMPLOYEE_CONFLICT")
        candidates.append(
            Adr048PersonCandidate(
                person_id=person_id,
                iin=str(row["iin"]),
                person_status=str(row["person_status"]),
                merged_into_person_id=(
                    int(row["merged_into_person_id"])
                    if row["merged_into_person_id"] is not None
                    else None
                ),
                conflicting_employee_ids=conflicting_employee_ids,
                incompatibility_reasons=tuple(reasons),
            )
        )

    if len(candidates) > 1:
        reasons = ["PERSON_IDENTITY_AMBIGUOUS"]
        if any(not candidate.compatible for candidate in candidates):
            reasons.append("PERSON_CANDIDATE_INCOMPATIBLE")
        return Adr048PersonResolution(
            decision="AMBIGUOUS",
            candidates=tuple(candidates),
            reason_codes=tuple(reasons),
        )

    candidate = candidates[0]
    if target_person_id is not None:
        if target_person_id == candidate.person_id:
            return Adr048PersonResolution(
                decision="CONFLICT",
                candidates=(candidate,),
                reason_codes=("TARGET_EMPLOYEE_ALREADY_LINKED",),
            )
        return Adr048PersonResolution(
            decision="CONFLICT",
            candidates=(candidate,),
            reason_codes=("TARGET_EMPLOYEE_PERSON_IDENTITY_CONFLICT",),
        )
    if "PERSON_ACTIVE_EMPLOYEE_CONFLICT" in candidate.incompatibility_reasons:
        decision: PersonResolutionDecision = "CONFLICT"
    elif not candidate.compatible:
        decision = "INCOMPATIBLE"
    else:
        decision = "P1_ADOPT"
    return Adr048PersonResolution(
        decision=decision,
        candidates=(candidate,),
        reason_codes=(
            candidate.incompatibility_reasons
            if decision != "CONFLICT"
            else ("PERSON_ACTIVE_EMPLOYEE_CONFLICT",)
        ),
    )
