"""Person matching service: Person Candidate → PersonMatchResult (WP-CL-005).

Read-only — no Person creation, mutation, apply, or fuzzy auto-selection.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from app.control_list_import.domain.person_candidate import PersonCandidate
from app.control_list_import.domain.person_match_models import (
    MatchReason,
    MatchStatus,
    PersonMatchCandidate,
    PersonMatchResult,
)
from app.control_list_import.domain.person_match_repository import (
    PersonLookupRecord,
    PersonMatchReadPort,
)
from app.control_list_import.matching.keys import person_fio_comparison_key

_SCORE_EXACT_IIN = 1.0
_SCORE_FIO_BIRTH_DATE = 0.9
_SCORE_FIO_ONLY = 0.5


class PersonMatchingService:
    """Match normalized Person Candidates against existing canonical Person rows."""

    def __init__(self, port: PersonMatchReadPort) -> None:
        self._port = port

    def match_candidate(self, candidate: PersonCandidate) -> PersonMatchResult:
        base = self._result_shell(candidate)

        if candidate.iin.is_valid:
            iin_outcome = self._match_by_iin(candidate, base)
            if iin_outcome is not None:
                return iin_outcome

        if candidate.full_name.normalized_key and candidate.birth_date.is_valid:
            fio_dob_outcome = self._match_by_fio_and_birth_date(candidate, base)
            if fio_dob_outcome is not None:
                return fio_dob_outcome

        if candidate.full_name.normalized_key:
            return self._match_by_fio_only(candidate, base)

        return self._build_result(
            base,
            status=MatchStatus.NOT_FOUND,
            primary_reason=MatchReason.CANDIDATE_INCOMPLETE,
            reasons=(MatchReason.CANDIDATE_INCOMPLETE, MatchReason.NO_MATCH),
            confidence=0.0,
            recommended_person_id=None,
            match_candidates=(),
        )

    def match_run(self, candidates: list[PersonCandidate]) -> list[PersonMatchResult]:
        return [self.match_candidate(candidate) for candidate in candidates]

    def _match_by_iin(
        self,
        candidate: PersonCandidate,
        base: tuple[Optional[int], Optional[int]],
    ) -> Optional[PersonMatchResult]:
        assert candidate.iin.digits is not None
        records = self._port.find_by_iin(candidate.iin.digits)
        hits = self._records_to_candidates(
            records,
            reason=MatchReason.EXACT_IIN,
            score=_SCORE_EXACT_IIN,
            confidence=_SCORE_EXACT_IIN,
        )
        resolved_ids = {hit.resolved_person_id for hit in hits}

        if not hits:
            return None

        if len(resolved_ids) > 1:
            return self._build_result(
                base,
                status=MatchStatus.AMBIGUOUS,
                primary_reason=MatchReason.MULTIPLE_MATCHES,
                reasons=(MatchReason.EXACT_IIN, MatchReason.MULTIPLE_MATCHES),
                confidence=_SCORE_EXACT_IIN,
                recommended_person_id=None,
                match_candidates=hits,
            )

        hit = hits[0]
        if self._attributes_conflict(hit, candidate):
            return self._build_result(
                base,
                status=MatchStatus.INVALID,
                primary_reason=MatchReason.IIN_ATTRIBUTE_CONFLICT,
                reasons=(MatchReason.EXACT_IIN, MatchReason.IIN_ATTRIBUTE_CONFLICT),
                confidence=0.0,
                recommended_person_id=None,
                match_candidates=hits,
            )

        return self._build_result(
            base,
            status=MatchStatus.EXACT,
            primary_reason=MatchReason.EXACT_IIN,
            reasons=(MatchReason.EXACT_IIN,),
            confidence=_SCORE_EXACT_IIN,
            recommended_person_id=hit.resolved_person_id,
            match_candidates=hits,
        )

    def _match_by_fio_and_birth_date(
        self,
        candidate: PersonCandidate,
        base: tuple[Optional[int], Optional[int]],
    ) -> Optional[PersonMatchResult]:
        assert candidate.full_name.normalized_key is not None
        assert candidate.birth_date.value is not None
        records = self._port.find_by_fio_and_birth_date(
            normalized_fio_key=candidate.full_name.normalized_key,
            birth_date=candidate.birth_date.value,
        )
        hits = self._records_to_candidates(
            records,
            reason=MatchReason.PROBABLE_FIO_BIRTH_DATE,
            score=_SCORE_FIO_BIRTH_DATE,
            confidence=_SCORE_FIO_BIRTH_DATE,
        )
        resolved_ids = {hit.resolved_person_id for hit in hits}

        if not hits:
            return None

        if len(resolved_ids) > 1:
            return self._build_result(
                base,
                status=MatchStatus.AMBIGUOUS,
                primary_reason=MatchReason.MULTIPLE_MATCHES,
                reasons=(MatchReason.PROBABLE_FIO_BIRTH_DATE, MatchReason.MULTIPLE_MATCHES),
                confidence=_SCORE_FIO_BIRTH_DATE,
                recommended_person_id=None,
                match_candidates=hits,
            )

        hit = hits[0]
        return self._build_result(
            base,
            status=MatchStatus.PROBABLE,
            primary_reason=MatchReason.PROBABLE_FIO_BIRTH_DATE,
            reasons=(MatchReason.PROBABLE_FIO_BIRTH_DATE,),
            confidence=_SCORE_FIO_BIRTH_DATE,
            recommended_person_id=hit.resolved_person_id,
            match_candidates=hits,
        )

    def _match_by_fio_only(
        self,
        candidate: PersonCandidate,
        base: tuple[Optional[int], Optional[int]],
    ) -> PersonMatchResult:
        assert candidate.full_name.normalized_key is not None
        records = self._port.find_by_normalized_fio(candidate.full_name.normalized_key)
        hits = self._records_to_candidates(
            records,
            reason=MatchReason.WEAK_FIO_ONLY,
            score=_SCORE_FIO_ONLY,
            confidence=_SCORE_FIO_ONLY,
        )
        resolved_ids = {hit.resolved_person_id for hit in hits}

        if not hits:
            return self._build_result(
                base,
                status=MatchStatus.NOT_FOUND,
                primary_reason=MatchReason.NO_MATCH,
                reasons=(MatchReason.NO_MATCH,),
                confidence=0.0,
                recommended_person_id=None,
                match_candidates=(),
            )

        if len(resolved_ids) > 1:
            return self._build_result(
                base,
                status=MatchStatus.AMBIGUOUS,
                primary_reason=MatchReason.MULTIPLE_MATCHES,
                reasons=(MatchReason.WEAK_FIO_ONLY, MatchReason.MULTIPLE_MATCHES),
                confidence=_SCORE_FIO_ONLY,
                recommended_person_id=None,
                match_candidates=hits,
            )

        return self._build_result(
            base,
            status=MatchStatus.PROBABLE,
            primary_reason=MatchReason.WEAK_FIO_ONLY,
            reasons=(MatchReason.WEAK_FIO_ONLY,),
            confidence=_SCORE_FIO_ONLY,
            recommended_person_id=None,
            match_candidates=hits,
        )

    def _records_to_candidates(
        self,
        records: tuple[PersonLookupRecord, ...],
        *,
        reason: MatchReason,
        score: float,
        confidence: float,
    ) -> tuple[PersonMatchCandidate, ...]:
        hits: list[PersonMatchCandidate] = []
        seen_resolved: set[int] = set()
        for record in records:
            resolved_id = self._port.resolve_survivor(record.person_id)
            if resolved_id in seen_resolved:
                continue
            seen_resolved.add(resolved_id)
            resolved_record = record
            merge_redirected = resolved_id != record.person_id
            if merge_redirected:
                loaded = self._port.load_person(resolved_id)
                if loaded is not None:
                    resolved_record = loaded
            hits.append(
                PersonMatchCandidate(
                    source_person_id=record.person_id,
                    resolved_person_id=resolved_id,
                    person_status=resolved_record.person_status,
                    full_name=resolved_record.full_name,
                    iin=resolved_record.iin,
                    birth_date=resolved_record.birth_date,
                    match_key=resolved_record.match_key,
                    merge_redirected=merge_redirected,
                    reason=reason,
                    score=score,
                    confidence=confidence,
                )
            )
        return tuple(hits)

    def _attributes_conflict(
        self,
        hit: PersonMatchCandidate,
        candidate: PersonCandidate,
    ) -> bool:
        if candidate.birth_date.is_valid and hit.birth_date is not None:
            if hit.birth_date != candidate.birth_date.value:
                return True
        if candidate.full_name.normalized_key:
            hit_key = person_fio_comparison_key(hit.full_name)
            if hit_key and hit_key != candidate.full_name.normalized_key:
                return True
        return False

    @staticmethod
    def _result_shell(candidate: PersonCandidate) -> tuple[Optional[int], Optional[int]]:
        return candidate.import_run_id, candidate.source_row_id

    @staticmethod
    def _build_result(
        base: tuple[Optional[int], Optional[int]],
        *,
        status: MatchStatus,
        primary_reason: MatchReason,
        reasons: tuple[MatchReason, ...],
        confidence: float,
        recommended_person_id: Optional[int],
        match_candidates: tuple[PersonMatchCandidate, ...],
    ) -> PersonMatchResult:
        import_run_id, source_row_id = base
        return PersonMatchResult(
            import_run_id=import_run_id,
            source_row_id=source_row_id,
            status=status,
            match_candidates=match_candidates,
            primary_reason=primary_reason,
            reasons=reasons,
            confidence=confidence,
            recommended_person_id=recommended_person_id,
        )
