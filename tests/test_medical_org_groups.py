"""Unit tests for canonical medical org group registry."""
from __future__ import annotations

from app.medical_org_groups import (
    SLUG_ADMIN_HOUSEHOLD,
    SLUG_CLINICAL,
    SLUG_PARACLINICAL,
    BY_GROUP_ID,
    BY_SLUG,
    department_group_api_row,
    effective_log_group_for,
    effective_log_group_name_for,
    enrich_effective_log_group_fields,
    list_filter_group_options,
    resolve_group_id_from_filter,
    slug_from_legacy_department_group,
)


def test_registry_has_three_groups_with_russian_names():
    assert len(BY_GROUP_ID) == 3
    assert BY_SLUG[SLUG_CLINICAL].display_name_ru == "Клинические"
    assert BY_SLUG[SLUG_PARACLINICAL].display_name_ru == "Параклинические"
    assert BY_SLUG[SLUG_ADMIN_HOUSEHOLD].display_name_ru == "Административно-хозяйственные"


def test_slug_from_legacy_department_group():
    assert slug_from_legacy_department_group("CLINICAL") == SLUG_CLINICAL
    assert slug_from_legacy_department_group("clinical") == SLUG_CLINICAL
    assert slug_from_legacy_department_group("ADMINISTRATIVE") == SLUG_ADMIN_HOUSEHOLD


def test_effective_log_group_for_org_group_id():
    assert effective_log_group_for(org_group_id=2) == SLUG_PARACLINICAL
    assert effective_log_group_name_for(slug=SLUG_PARACLINICAL) == "Параклинические"


def test_enrich_effective_log_group_fields():
    item = {"org_group_id": 1, "department_group": "CLINICAL"}
    enrich_effective_log_group_fields(item)
    assert item["effective_log_group"] == SLUG_CLINICAL
    assert item["effective_log_group_name"] == "Клинические"


def test_list_filter_group_options_shape():
    options = list_filter_group_options()
    assert len(options) == 3
    slugs = {o["value"] for o in options}
    assert slugs == {SLUG_CLINICAL, SLUG_PARACLINICAL, SLUG_ADMIN_HOUSEHOLD}
    for opt in options:
        assert opt["label"] == opt["effective_log_group_name"]
        assert opt["value"] == opt["effective_log_group"]
        assert opt["label"] not in slugs


def test_department_group_api_row():
    row = department_group_api_row(3, db_group_name="admin_household")
    assert row["effective_log_group"] == SLUG_ADMIN_HOUSEHOLD
    assert row["effective_log_group_name"] == "Административно-хозяйственные"
    assert row["group_name"] == "Административно-хозяйственные"


def test_resolve_group_id_from_filter_accepts_slug():
    assert resolve_group_id_from_filter(effective_log_group=SLUG_CLINICAL) == 1
    assert resolve_group_id_from_filter(department_group="2") == 2
    assert resolve_group_id_from_filter(org_group_id=3) == 3
