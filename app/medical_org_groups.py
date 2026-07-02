"""Canonical medical org group registry — single source of truth for group_id, slug, display name."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Internal slugs (DB/API identifiers). Display names are Russian only.
SLUG_CLINICAL = "clinical"
SLUG_PARACLINICAL = "paraclinical"
SLUG_ADMIN_HOUSEHOLD = "admin_household"


@dataclass(frozen=True)
class MedicalOrgGroup:
    group_id: int
    slug: str
    display_name_ru: str


MEDICAL_ORG_GROUPS: tuple[MedicalOrgGroup, ...] = (
    MedicalOrgGroup(1, SLUG_CLINICAL, "Клинические"),
    MedicalOrgGroup(2, SLUG_PARACLINICAL, "Параклинические"),
    MedicalOrgGroup(3, SLUG_ADMIN_HOUSEHOLD, "Административно-хозяйственные"),
)

BY_GROUP_ID: dict[int, MedicalOrgGroup] = {g.group_id: g for g in MEDICAL_ORG_GROUPS}
BY_SLUG: dict[str, MedicalOrgGroup] = {g.slug: g for g in MEDICAL_ORG_GROUPS}

# Legacy department_recoding.department_group storage (unchanged in DB).
LEGACY_DEPARTMENT_GROUP_TO_SLUG: dict[str, str] = {
    "CLINICAL": SLUG_CLINICAL,
    "PARACLINICAL": SLUG_PARACLINICAL,
    "ADMINISTRATIVE": SLUG_ADMIN_HOUSEHOLD,
}


def group_by_id(group_id: int | None) -> MedicalOrgGroup | None:
    if group_id is None:
        return None
    try:
        return BY_GROUP_ID.get(int(group_id))
    except (TypeError, ValueError):
        return None


def group_by_slug(slug: str | None) -> MedicalOrgGroup | None:
    if slug is None:
        return None
    s = str(slug).strip().lower()
    if not s:
        return None
    return BY_SLUG.get(s)


def slug_from_legacy_department_group(value: str | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    direct = group_by_slug(raw)
    if direct:
        return direct.slug
    return LEGACY_DEPARTMENT_GROUP_TO_SLUG.get(raw.upper())


def resolve_group_id(
    *,
    org_group_id: int | None = None,
    effective_log_group: str | None = None,
) -> int | None:
    if org_group_id is not None:
        try:
            gid = int(org_group_id)
            if gid > 0 and gid in BY_GROUP_ID:
                return gid
        except (TypeError, ValueError):
            pass
    spec = group_by_slug(effective_log_group)
    return spec.group_id if spec else None


def resolve_group_id_from_filter(
    *,
    org_group_id: int | None = None,
    effective_log_group: str | None = None,
    department_group: str | None = None,
) -> int | None:
    gid = resolve_group_id(org_group_id=org_group_id, effective_log_group=effective_log_group)
    if gid is not None:
        return gid
    if department_group is not None:
        slug = slug_from_legacy_department_group(department_group)
        if slug:
            return resolve_group_id(effective_log_group=slug)
        try:
            parsed = int(str(department_group).strip())
            if parsed >= 1 and parsed in BY_GROUP_ID:
                return parsed
        except ValueError:
            pass
    return None


def effective_log_group_for(
    *,
    org_group_id: int | None = None,
    department_group: str | None = None,
) -> str | None:
    spec = group_by_id(org_group_id)
    if spec:
        return spec.slug
    return slug_from_legacy_department_group(department_group)


def effective_log_group_name_for(
    *,
    org_group_id: int | None = None,
    department_group: str | None = None,
    slug: str | None = None,
) -> str | None:
    if slug:
        spec = group_by_slug(slug)
        if spec:
            return spec.display_name_ru
    eff = slug or effective_log_group_for(org_group_id=org_group_id, department_group=department_group)
    spec = group_by_slug(eff)
    return spec.display_name_ru if spec else None


def enrich_effective_log_group_fields(item: dict[str, Any]) -> dict[str, Any]:
    org_group_id_raw = item.get("org_group_id")
    org_group_id: int | None
    try:
        org_group_id = int(org_group_id_raw) if org_group_id_raw is not None else None
    except (TypeError, ValueError):
        org_group_id = None

    department_group = item.get("department_group")
    slug = effective_log_group_for(
        org_group_id=org_group_id,
        department_group=str(department_group) if department_group is not None else None,
    )
    item["effective_log_group"] = slug
    item["effective_log_group_name"] = effective_log_group_name_for(slug=slug)
    return item


def list_filter_group_options() -> list[dict[str, Any]]:
    return [
        {
            "value": g.slug,
            "label": g.display_name_ru,
            "group_id": g.group_id,
            "effective_log_group": g.slug,
            "effective_log_group_name": g.display_name_ru,
        }
        for g in MEDICAL_ORG_GROUPS
    ]


def department_group_api_row(group_id: int, *, db_group_name: Optional[str] = None) -> dict[str, Any]:
    spec = group_by_id(group_id)
    if spec:
        return {
            "group_id": spec.group_id,
            "code": spec.slug,
            "effective_log_group": spec.slug,
            "group_name": spec.display_name_ru,
            "effective_log_group_name": spec.display_name_ru,
            "description": None,
            "is_active": True,
        }
    fallback = str(db_group_name or "").strip() or f"Группа {group_id}"
    return {
        "group_id": group_id,
        "code": None,
        "effective_log_group": None,
        "group_name": fallback,
        "effective_log_group_name": None,
        "description": None,
        "is_active": True,
    }
