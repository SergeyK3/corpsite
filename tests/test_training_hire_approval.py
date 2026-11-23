"""The manager lesson uses real HIRE, visa and task state in corpsite_test."""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.api.training_router import _attempt, _check_hire_attempt, read_evidence
from app.db.engine import engine
from app import training_hire_approval as hire_training
from tests.db_guard import assert_connected_test_database, validate_test_database_url
from dotenv import dotenv_values


def _target():
    values = dotenv_values(".env")
    return validate_test_database_url(test_database_url=values.get("TEST_DATABASE_URL"),
                                      app_database_url=values.get("DATABASE_URL"))


def _new_attempt(conn):
    user = conn.execute(text("""
        SELECT u.user_id,u.role_id,a.assignment_id FROM public.users u
        JOIN public.training_assignments a ON a.participant_user_id=u.user_id
        WHERE u.login='training_head_20261121_test' ORDER BY a.assignment_id DESC LIMIT 1
    """)).mappings().one()
    number = int(conn.execute(text("""
        SELECT COALESCE(MAX(attempt_number),0)+1000 FROM public.training_attempts
        WHERE assignment_id=:id
    """), {"id": user["assignment_id"]}).scalar_one())
    attempt_id = int(conn.execute(text("""
        INSERT INTO public.training_attempts(assignment_id,attempt_number,idempotency_key)
        VALUES (:assignment,:number,:key) RETURNING attempt_id
    """), {"assignment": user["assignment_id"], "number": number,
           "key": f"pytest-{uuid4().hex}"}).scalar_one())
    return user, attempt_id


def test_old_and_new_requirements_remain_separate():
    target = _target()
    with engine.connect() as conn:
        assert_connected_test_database(conn, target)
        rows = conn.execute(text("""
            SELECT c.version, l.rules->'required_user_steps' AS required
            FROM public.training_lesson_versions l
            JOIN public.training_course_versions c USING (course_version_id)
            WHERE c.course_code='application_administration'
              AND l.lesson_code='skill_2' AND c.version IN (2,3)
            ORDER BY c.version
        """)).mappings().all()
        assert [(r["version"], r["required"]) for r in rows] == [
            (2, ["resolution", "final_status"]), (3, ["result"])
        ]


def test_preparation_consent_and_tampering_are_bound_to_attempt(monkeypatch):
    target = _target()
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            assert_connected_test_database(conn, target)
            user, attempt_id = _new_attempt(conn)
            issued = hire_training.prepare(conn, attempt_id=attempt_id,
                                           participant_user_id=user["user_id"],
                                           participant_role_id=user["role_id"])
            assert hire_training.prepare(conn, attempt_id=attempt_id,
                                         participant_user_id=user["user_id"],
                                         participant_role_id=user["role_id"]) == issued
            assert conn.execute(text("""
                SELECT count(*) FROM public.training_attempt_objects WHERE attempt_id=:id
            """), {"id": attempt_id}).scalar_one() == 1
            assert hire_training.business_check(conn, attempt_id=attempt_id,
                                                participant_user_id=user["user_id"],
                                                issued=issued)[0] is False  # no consent
            with pytest.raises(ValueError):
                hire_training.consent(conn, attempt_id=attempt_id,
                                      participant_user_id=4566,
                                      participant_role_id=user["role_id"])
            hire_training.consent(conn, attempt_id=attempt_id,
                                  participant_user_id=user["user_id"],
                                  participant_role_id=user["role_id"])
            first_visa_id = hire_training.record(conn, attempt_id)["visa"]["decided_at"]
            first_events = conn.execute(text("""
                SELECT event_type,count(*) FROM public.training_attempt_events
                WHERE attempt_id=:id AND event_type IN ('consent_saved','task_completed')
                GROUP BY event_type
            """), {"id": attempt_id}).all()
            hire_training.consent(conn, attempt_id=attempt_id,
                                  participant_user_id=user["user_id"],
                                  participant_role_id=user["role_id"])
            assert hire_training.record(conn, attempt_id)["visa"]["decided_at"] == first_visa_id
            assert conn.execute(text("""
                SELECT event_type,count(*) FROM public.training_attempt_events
                WHERE attempt_id=:id AND event_type IN ('consent_saved','task_completed')
                GROUP BY event_type
            """), {"id": attempt_id}).all() == first_events
            hire_training.verify_partner(conn, attempt_id)
            assert hire_training.business_check(conn, attempt_id=attempt_id,
                                                participant_user_id=user["user_id"],
                                                issued=issued)[0] is True
            assert hire_training.business_check(conn, attempt_id=attempt_id,
                                                participant_user_id=user["user_id"],
                                                issued={**issued, "application_number": 1})[0] is False
            conn.execute(text("""
                UPDATE public.personnel_applications SET intended_employment_rate=0.75
                WHERE application_id=:id
            """), {"id": issued["application_number"]})
            result = hire_training.business_check(conn, attempt_id=attempt_id,
                                                  participant_user_id=user["user_id"],
                                                  issued=issued)
            assert result[0] is False and "Условия" in result[1]
        finally:
            tx.rollback()


def test_partner_failure_does_not_create_a_grade(monkeypatch):
    target = _target()
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            assert_connected_test_database(conn, target)
            user, attempt_id = _new_attempt(conn)
            issued = hire_training.prepare(conn, attempt_id=attempt_id,
                                           participant_user_id=user["user_id"],
                                           participant_role_id=user["role_id"])
            hire_training.consent(conn, attempt_id=attempt_id,
                                  participant_user_id=user["user_id"],
                                  participant_role_id=user["role_id"])
            monkeypatch.setattr(hire_training, "require_current_approval",
                                lambda *_: (_ for _ in ()).throw(RuntimeError("partner unavailable")))
            valid, reason, technical = hire_training.business_check(
                conn, attempt_id=attempt_id, participant_user_id=user["user_id"], issued=issued)
            assert valid is False and technical is True and "partner unavailable" in reason
            assert conn.execute(text("SELECT score FROM public.training_attempts WHERE attempt_id=:id"),
                                {"id": attempt_id}).scalar_one_or_none() is None
        finally:
            tx.rollback()


def test_foreign_attempt_and_sanitary_approval_denied():
    target = _target()
    with engine.connect() as conn:
        assert_connected_test_database(conn, target)
        manager_attempt = conn.execute(text("""
            SELECT t.attempt_id FROM public.training_attempts t
            JOIN public.training_assignments a USING(assignment_id)
            JOIN public.users u ON u.user_id=a.participant_user_id
            WHERE u.login='training_head_20261121_test'
            ORDER BY t.attempt_id DESC LIMIT 1
        """)).scalar_one()
        sanitary = conn.execute(text("""
            SELECT user_id,role_id FROM public.users
            WHERE login='sanitarka_test_20261121_test'
        """)).mappings().one()
        with pytest.raises(HTTPException) as denied:
            _attempt(conn, int(manager_attempt), dict(sanitary))
        assert denied.value.status_code == 404
        evidence_id = conn.execute(text("""
            SELECT evidence_id FROM public.training_evidence
            WHERE attempt_id=:id AND superseded_at IS NULL LIMIT 1
        """), {"id": manager_attempt}).scalar_one()
        with pytest.raises(HTTPException) as denied_image:
            read_evidence(int(evidence_id), user=dict(sanitary))
        assert denied_image.value.status_code == 404
        assert conn.execute(text("""
            SELECT count(*) FROM public.org_unit_managers WHERE user_id=:id AND is_active=TRUE
        """), {"id": sanitary["user_id"]}).scalar_one() == 0


def test_old_attempt_and_grade_are_preserved():
    target = _target()
    with engine.connect() as conn:
        assert_connected_test_database(conn, target)
        old = conn.execute(text("""
            SELECT t.status,t.score,l.rules FROM public.training_attempts t
            JOIN public.training_assignments a USING (assignment_id)
            JOIN public.training_lesson_versions l USING (lesson_version_id)
            WHERE t.attempt_id=23
        """)).mappings().one()
        assert old["status"] == "under_review" and old["score"] is None
        assert old["rules"]["required_user_steps"] == ["resolution", "final_status"]
        assert conn.execute(text("""
            SELECT count(*) FROM public.training_evidence
            WHERE attempt_id=23 AND superseded_at IS NULL
        """)).scalar_one() == 2
        assert conn.execute(text("SELECT score FROM public.training_attempts WHERE attempt_id=16")).scalar_one() == 5


def test_rechecking_unchanged_single_result_does_not_duplicate_review():
    target = _target()
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            assert_connected_test_database(conn, target)
            user = conn.execute(text("""
                SELECT user_id,role_id FROM public.users WHERE login='training_head_20261121_test'
            """)).mappings().one()
            attempt = _attempt(conn, 27, dict(user))
            before = conn.execute(text("SELECT count(*) FROM public.training_reviews WHERE attempt_id=27")).scalar_one()
            result = _check_hire_attempt(conn, attempt, dict(user))
            after = conn.execute(text("SELECT count(*) FROM public.training_reviews WHERE attempt_id=27")).scalar_one()
            assert result["status"] == "under_review" and before == after == 1
        finally:
            tx.rollback()


def test_single_result_without_consent_cannot_pass():
    target = _target()
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            assert_connected_test_database(conn, target)
            user, attempt_id = _new_attempt(conn)
            issued = hire_training.prepare(conn, attempt_id=attempt_id,
                                           participant_user_id=user["user_id"],
                                           participant_role_id=user["role_id"])
            conn.execute(text("""
                UPDATE public.training_attempts SET fixture=CAST(:fixture AS jsonb)
                WHERE attempt_id=:id
            """), {"id": attempt_id, "fixture": json.dumps(issued, ensure_ascii=False)})
            for step in ("result",):
                conn.execute(text("""
                    INSERT INTO public.training_evidence
                      (attempt_id,step_key,uploaded_by_user_id,mime_type,width,height,
                       sha256,perceptual_hash,image_bytes)
                    VALUES (:attempt,:step,:user,'image/png',100,100,:hash,'0000000000000000',:bytes)
                """), {"attempt": attempt_id, "step": step,
                       "user": user["user_id"], "hash": uuid4().hex, "bytes": b"test-image"})
            attempt = _attempt(conn, attempt_id, dict(user))
            result = _check_hire_attempt(conn, attempt, dict(user))
            assert result["status"] == "completed" and result["outcome"] == "failed"
            assert result["score"] == 2 and "Согласие" in result["message"]
        finally:
            tx.rollback()
