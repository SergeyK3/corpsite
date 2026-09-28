"""Canonical Git manifests and safe DRAFT-only synchronization.

The manifest deliberately has no database identity or audit metadata.  Its two
hashes cover the eight editable text fields only, so a server DRAFT can be
compared without exposing local implementation details.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from sqlalchemy import text

from app.db.engine import engine as default_engine
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_template_validation import TemplateValidationError, validate_template_texts

SCHEMA_VERSION = 1
TEXT_FIELDS = (
    "title_ru", "title_kk", "preamble_ru", "preamble_kk",
    "body_template_ru", "body_template_kk", "basis_template_ru", "basis_template_kk",
)
MANIFEST_FIELDS = (
    "schema_version", "item_type_code", *TEXT_FIELDS, "allowed_variables",
    "required_variables", "base_content_sha256", "content_sha256",
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_ROOT = REPOSITORY_ROOT / "app" / "resources" / "personnel_order_templates"


class ManifestError(ValueError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_sha256(item_type_code: str, values: Mapping[str, str]) -> str:
    """Hash precisely the editable snapshot, in a stable field order."""
    payload = {"item_type_code": item_type_code, **{field: values[field] for field in TEXT_FIELDS}}
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _spec_variables(item_type_code: str) -> tuple[list[str], dict[str, list[str]]]:
    spec = get_personnel_order_template_spec(item_type_code)
    return list(spec.allowed_variables), {key: list(value) for key, value in sorted(spec.required_variables.items())}


def build_manifest(item_type_code: str, values: Mapping[str, str]) -> dict[str, Any]:
    validate_template_texts(item_type_code, values)
    allowed, required = _spec_variables(item_type_code)
    base_hash = content_sha256(item_type_code, dict(get_personnel_order_template_spec(item_type_code).initial_texts))
    target_hash = content_sha256(item_type_code, values)
    return {
        "schema_version": SCHEMA_VERSION,
        "item_type_code": item_type_code,
        **{field: values[field] for field in TEXT_FIELDS},
        "allowed_variables": allowed,
        "required_variables": required,
        "base_content_sha256": base_hash,
        "content_sha256": target_hash,
    }


def manifest_path(item_type_code: str, root: Path = MANIFEST_ROOT) -> Path:
    get_personnel_order_template_spec(item_type_code)
    return root / item_type_code / "draft-v1.json"


def _manifest_bytes(manifest: Mapping[str, Any]) -> bytes:
    # Ordered construction makes the review-facing file stable even if callers
    # pass an ordinary mapping in another order.
    ordered = {field: manifest[field] for field in MANIFEST_FIELDS}
    return json.dumps(ordered, ensure_ascii=False, indent=2) .replace("\r\n", "\n").encode("utf-8") + b"\n"


def write_manifest(item_type_code: str, values: Mapping[str, str], root: Path = MANIFEST_ROOT) -> str:
    path = manifest_path(item_type_code, root)
    payload = _manifest_bytes(build_manifest(item_type_code, values))
    if path.is_file() and path.read_bytes() == payload:
        return "NO_OP"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".draft-v1-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return "EXPORT"


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Invalid manifest {path}: {exc}") from exc
    if not isinstance(manifest, dict) or tuple(manifest) != MANIFEST_FIELDS:
        raise ManifestError(f"{path}: manifest fields must be exactly {MANIFEST_FIELDS}")
    if path.read_bytes() != _manifest_bytes(manifest):
        raise ManifestError(f"{path}: manifest is not canonical UTF-8 JSON")
    item_type_code = manifest["item_type_code"]
    if not isinstance(item_type_code, str) or manifest["schema_version"] != SCHEMA_VERSION:
        raise ManifestError(f"{path}: unsupported schema or item type")
    values = {field: manifest[field] for field in TEXT_FIELDS}
    try:
        validate_template_texts(item_type_code, values)
        allowed, required = _spec_variables(item_type_code)
    except (TemplateValidationError, ValueError) as exc:
        raise ManifestError(f"{path}: {exc}") from exc
    if manifest["allowed_variables"] != allowed or manifest["required_variables"] != required:
        raise ManifestError(f"{path}: variable contract does not match PersonnelOrderTemplateSpec")
    if manifest["content_sha256"] != content_sha256(item_type_code, values):
        raise ManifestError(f"{path}: content_sha256 mismatch")
    if manifest["base_content_sha256"] != content_sha256(item_type_code, dict(get_personnel_order_template_spec(item_type_code).initial_texts)):
        raise ManifestError(f"{path}: base_content_sha256 is not the built-in server default")
    return manifest


def load_manifests(root: Path = MANIFEST_ROOT) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    manifests = [load_manifest(path) for path in sorted(root.glob("*/draft-v1.json"))]
    codes = [manifest["item_type_code"] for manifest in manifests]
    if len(codes) != len(set(codes)):
        raise ManifestError("Duplicate manifest item_type_code")
    return manifests


def export_drafts(item_types: Sequence[str], *, db_engine: Any = default_engine, root: Path = MANIFEST_ROOT) -> dict[str, str]:
    drafts: dict[str, dict[str, str]] = {}
    with db_engine.connect() as connection:
        for item_type_code in item_types:
            get_personnel_order_template_spec(item_type_code)
            row = connection.execute(text("""
                SELECT title_ru, title_kk, preamble_ru, preamble_kk, body_template_ru, body_template_kk, basis_template_ru, basis_template_kk
                FROM public.personnel_order_template_versions
                WHERE item_type_code=:type AND status='DRAFT'
                ORDER BY revision DESC, template_version_id DESC LIMIT 1
            """), {"type": item_type_code}).mappings().first()
            if row is None:
                raise ManifestError(f"No DRAFT exists for {item_type_code}")
            drafts[item_type_code] = {field: row[field] for field in TEXT_FIELDS}
    return {item_type_code: write_manifest(item_type_code, values, root) for item_type_code, values in drafts.items()}


def _status(manifest: Mapping[str, Any], row: Mapping[str, Any] | None) -> str:
    if row is None:
        return "CREATE"
    values = {field: row[field] for field in TEXT_FIELDS}
    current_hash = content_sha256(manifest["item_type_code"], values)
    if current_hash == manifest["content_sha256"]:
        return "NO_OP"
    if current_hash == manifest["base_content_sha256"]:
        return "UPDATE"
    return "CONFLICT"


def sync_manifests(*, apply: bool, db_engine: Any = default_engine, root: Path = MANIFEST_ROOT) -> dict[str, str]:
    """Report or atomically apply every manifest, touching only template versions."""
    manifests = load_manifests(root)
    results: dict[str, str] = {}
    if not apply:
        with db_engine.connect() as connection:
            for manifest in manifests:
                row = connection.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='DRAFT'"), {"type": manifest["item_type_code"]}).mappings().first()
                results[manifest["item_type_code"]] = _status(manifest, row)
        return results
    with db_engine.begin() as connection:
        planned: list[tuple[Mapping[str, Any], Mapping[str, Any] | None, str]] = []
        for manifest in manifests:
            row = connection.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND status='DRAFT' FOR UPDATE"), {"type": manifest["item_type_code"]}).mappings().first()
            status = _status(manifest, row)
            results[manifest["item_type_code"]] = status
            planned.append((manifest, row, status))
        if any(status == "CONFLICT" for _, _, status in planned):
            return results
        for manifest, row, status in planned:
            values = {field: manifest[field] for field in TEXT_FIELDS}
            if status == "CREATE":
                connection.execute(text("""
                    INSERT INTO public.personnel_order_template_versions
                    (item_type_code, version_number, status, title_ru, title_kk, preamble_ru, preamble_kk, body_template_ru, body_template_kk, basis_template_ru, basis_template_kk)
                    VALUES (:type, (SELECT COALESCE(MAX(version_number), 0) + 1 FROM public.personnel_order_template_versions WHERE item_type_code=:type), 'DRAFT', :title_ru, :title_kk, :preamble_ru, :preamble_kk, :body_template_ru, :body_template_kk, :basis_template_ru, :basis_template_kk)
                """), {**values, "type": manifest["item_type_code"]})
            elif status == "UPDATE":
                connection.execute(text("""
                    UPDATE public.personnel_order_template_versions SET
                    title_ru=:title_ru, title_kk=:title_kk, preamble_ru=:preamble_ru, preamble_kk=:preamble_kk,
                    body_template_ru=:body_template_ru, body_template_kk=:body_template_kk, basis_template_ru=:basis_template_ru, basis_template_kk=:basis_template_kk,
                    revision=revision+1, updated_at=now()
                    WHERE template_version_id=:id
                """), {**values, "id": row["template_version_id"]})
    return results
