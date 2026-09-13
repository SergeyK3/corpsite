from app.api.ppr_router import _include_additional_status_facts


def test_personnel_admin_can_receive_editable_note_facts_and_source_hint(monkeypatch):
    monkeypatch.setattr("app.api.ppr_router.include_sensitive_identity_fields", lambda _user: False)
    monkeypatch.setattr("app.api.ppr_router.evaluate_personnel_admin_access", lambda _user: True)
    assert _include_additional_status_facts({"user_id": 7}) is True


def test_non_admin_without_sensitive_identity_access_cannot_receive_note_hint(monkeypatch):
    monkeypatch.setattr("app.api.ppr_router.include_sensitive_identity_fields", lambda _user: False)
    monkeypatch.setattr("app.api.ppr_router.evaluate_personnel_admin_access", lambda _user: False)
    assert _include_additional_status_facts({"user_id": 7}) is False
