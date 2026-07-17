# tests/test_wp_cl_005_person_matching.py
"""Unit tests for WP-CL-005 person matching layer."""
from __future__ import annotations

from datetime import date

import pytest

from app.control_list_import.domain.person_candidate import (
    NormalizedBirthDate,
    NormalizedFullName,
    NormalizedIin,
    NormalizedPhone,
    NormalizedPlainText,
    NormalizedSex,
    PersonCandidate,
)
from app.control_list_import.domain.person_match_models import MatchReason, MatchStatus
from app.control_list_import.domain.person_match_repository import PersonLookupRecord
from app.control_list_import.matching.service import PersonMatchingService
from app.ppr.domain.identity_models import PERSON_STATUS_ACTIVE, PERSON_STATUS_MERGED


def _candidate(
    *,
    full_name: str = "Иванов Иван Иванович",
    normalized_key: str | None = "иванов иван иванович",
    iin_digits: str | None = "900101300123",
    iin_issues: tuple[str, ...] = (),
    birth_date: date | None = date(1990, 1, 1),
    source_row_id: int = 100,
) -> PersonCandidate:
    return PersonCandidate(
        import_run_id=42,
        profile_id=10,
        profile_code="control_list_default",
        profile_version=1,
        source_row_id=source_row_id,
        source_sheet_name="врачи",
        source_excel_row_number=5,
        personnel_category="doctor",
        employment_mode="primary",
        full_name=NormalizedFullName(
            raw=full_name,
            display=full_name,
            normalized_key=normalized_key,
        ),
        iin=NormalizedIin(raw=iin_digits, digits=iin_digits, issues=iin_issues),
        birth_date=NormalizedBirthDate(raw="01.01.1990", value=birth_date),
        phone=NormalizedPhone(raw=None),
        sex=NormalizedSex(raw=None),
        department_name=NormalizedPlainText(raw=None),
        position_title=NormalizedPlainText(raw=None),
    )


class FakePersonMatchReadPort:
    def __init__(
        self,
        *,
        persons: dict[int, PersonLookupRecord],
        merge_map: dict[int, int] | None = None,
    ) -> None:
        self.persons = persons
        self.merge_map = merge_map or {}

    def find_by_iin(self, iin: str) -> tuple[PersonLookupRecord, ...]:
        return tuple(
            record
            for record in self.persons.values()
            if record.iin == iin and record.person_status in {"active", "inactive"}
        )

    def find_by_fio_and_birth_date(
        self,
        *,
        normalized_fio_key: str,
        birth_date: date,
    ) -> tuple[PersonLookupRecord, ...]:
        from app.control_list_import.matching.keys import person_fio_comparison_key

        return tuple(
            record
            for record in self.persons.values()
            if record.birth_date == birth_date
            and person_fio_comparison_key(record.full_name) == normalized_fio_key
            and record.person_status in {"active", "inactive"}
        )

    def find_by_normalized_fio(self, normalized_fio_key: str) -> tuple[PersonLookupRecord, ...]:
        from app.control_list_import.matching.keys import person_fio_comparison_key

        return tuple(
            record
            for record in self.persons.values()
            if person_fio_comparison_key(record.full_name) == normalized_fio_key
            and record.person_status in {"active", "inactive"}
        )

    def resolve_survivor(self, person_id: int) -> int:
        current = person_id
        seen = {current}
        while current in self.merge_map:
            target = self.merge_map[current]
            if target in seen:
                break
            seen.add(target)
            current = target
        return current

    def load_person(self, person_id: int) -> PersonLookupRecord | None:
        return self.persons.get(person_id)


def _person(
    person_id: int,
    *,
    full_name: str,
    iin: str | None = None,
    birth_date: date | None = None,
    person_status: str = PERSON_STATUS_ACTIVE,
    merged_into: int | None = None,
) -> PersonLookupRecord:
    return PersonLookupRecord(
        person_id=person_id,
        person_status=person_status,
        merged_into_person_id=merged_into,
        iin=iin,
        full_name=full_name,
        birth_date=birth_date,
        match_key=f"iin:{iin}" if iin else f"name:{full_name}|dob:{birth_date}",
    )


def test_exact_iin_match():
    port = FakePersonMatchReadPort(
        persons={
            1: _person(1, full_name="Иванов Иван Иванович", iin="900101300123", birth_date=date(1990, 1, 1)),
        }
    )
    result = PersonMatchingService(port).match_candidate(_candidate())

    assert result.status == MatchStatus.EXACT
    assert result.primary_reason == MatchReason.EXACT_IIN
    assert result.recommended_person_id == 1
    assert result.confidence == 1.0
    assert len(result.match_candidates) == 1
    assert result.match_candidates[0].resolved_person_id == 1


def test_probable_fio_and_birth_date_match():
    port = FakePersonMatchReadPort(
        persons={
            2: _person(2, full_name="Петров Петр Петрович", birth_date=date(1985, 5, 20)),
        }
    )
    candidate = _candidate(
        full_name="Петров Петр Петрович",
        normalized_key="петров петр петрович",
        iin_digits=None,
        birth_date=date(1985, 5, 20),
    )
    result = PersonMatchingService(port).match_candidate(candidate)

    assert result.status == MatchStatus.PROBABLE
    assert result.primary_reason == MatchReason.PROBABLE_FIO_BIRTH_DATE
    assert result.recommended_person_id == 2


def test_ambiguous_multiple_persons():
    port = FakePersonMatchReadPort(
        persons={
            3: _person(3, full_name="Сидоров Сидор Сидорович", iin="900101300123", birth_date=date(1990, 1, 1)),
            4: _person(4, full_name="Сидорова Сидора Сидоровна", iin="900101300123", birth_date=date(1990, 1, 1)),
        }
    )
    result = PersonMatchingService(port).match_candidate(_candidate(full_name="Сидоров Сидор Сидорович"))

    assert result.status == MatchStatus.AMBIGUOUS
    assert MatchReason.MULTIPLE_MATCHES in result.reasons
    assert result.recommended_person_id is None
    assert len(result.match_candidates) == 2


def test_not_found():
    port = FakePersonMatchReadPort(persons={})
    candidate = _candidate(
        full_name="Неизвестный Человек Тестович",
        normalized_key="неизвестный человек тестович",
        iin_digits=None,
        birth_date=None,
    )
    result = PersonMatchingService(port).match_candidate(candidate)

    assert result.status == MatchStatus.NOT_FOUND
    assert result.primary_reason == MatchReason.NO_MATCH
    assert result.recommended_person_id is None


def test_invalid_iin_attribute_conflict():
    port = FakePersonMatchReadPort(
        persons={
            5: _person(
                5,
                full_name="Кузнецов Кузьма Кузьмич",
                iin="900101300123",
                birth_date=date(1970, 2, 2),
            ),
        }
    )
    result = PersonMatchingService(port).match_candidate(_candidate())

    assert result.status == MatchStatus.INVALID
    assert result.primary_reason == MatchReason.IIN_ATTRIBUTE_CONFLICT
    assert MatchReason.EXACT_IIN in result.reasons
    assert result.recommended_person_id is None


def test_merged_person_redirects_to_survivor():
    class MergedRedirectPort(FakePersonMatchReadPort):
        def find_by_iin(self, iin: str) -> tuple[PersonLookupRecord, ...]:
            return (self.persons[10],)

    port = MergedRedirectPort(
        persons={
            10: _person(
                10,
                full_name="Merged Loser",
                iin="900101300123",
                birth_date=date(1990, 1, 1),
                person_status=PERSON_STATUS_MERGED,
                merged_into=20,
            ),
            20: _person(
                20,
                full_name="Иванов Иван Иванович",
                iin="900101300123",
                birth_date=date(1990, 1, 1),
            ),
        },
        merge_map={10: 20},
    )
    result = PersonMatchingService(port).match_candidate(_candidate())

    assert result.status == MatchStatus.EXACT
    assert result.recommended_person_id == 20
    assert result.match_candidates[0].source_person_id == 10
    assert result.match_candidates[0].resolved_person_id == 20
    assert result.match_candidates[0].merge_redirected is True


def test_fio_only_does_not_auto_match():
    port = FakePersonMatchReadPort(
        persons={
            6: _person(6, full_name="Ахметов Болат Касымович", birth_date=date(1988, 3, 3)),
        }
    )
    candidate = _candidate(
        full_name="Ахметов Болат Касымович",
        normalized_key="ахметов болат касымович",
        iin_digits=None,
        birth_date=None,
    )
    result = PersonMatchingService(port).match_candidate(candidate)

    assert result.status == MatchStatus.PROBABLE
    assert result.primary_reason == MatchReason.WEAK_FIO_ONLY
    assert result.recommended_person_id is None
    assert len(result.match_candidates) == 1


def test_fio_only_ambiguous_when_multiple_namesakes():
    port = FakePersonMatchReadPort(
        persons={
            7: _person(7, full_name="Алиев Али Алиевич", birth_date=date(1980, 1, 1)),
            8: _person(8, full_name="Алиев Али Алиевич", birth_date=date(1999, 9, 9)),
        }
    )
    candidate = _candidate(
        full_name="Алиев Али Алиевич",
        normalized_key="алиев али алиевич",
        iin_digits=None,
        birth_date=None,
    )
    result = PersonMatchingService(port).match_candidate(candidate)

    assert result.status == MatchStatus.AMBIGUOUS
    assert result.recommended_person_id is None
