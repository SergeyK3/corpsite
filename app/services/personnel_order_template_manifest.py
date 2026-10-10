"""Canonical, append-only Git manifests for personnel-order DRAFT templates."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from sqlalchemy import text

from app.db.engine import engine as default_engine
from app.services.personnel_order_template_specs import get_personnel_order_template_spec
from app.services.personnel_order_template_validation import TemplateValidationError, validate_template_texts

SCHEMA_VERSION = 1
TEXT_FIELDS = ("title_ru", "title_kk", "preamble_ru", "preamble_kk", "body_template_ru", "body_template_kk", "basis_template_ru", "basis_template_kk")
MANIFEST_FIELDS = ("schema_version", "item_type_code", *TEXT_FIELDS, "allowed_variables", "required_variables", "base_content_sha256", "content_sha256")
_FILENAME = re.compile(r"^draft-v([1-9][0-9]*)\.json$")
_TOKEN = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_ROOT = REPOSITORY_ROOT / "app" / "resources" / "personnel_order_templates"
_HISTORICAL_TERMINATION_ALLOWED_VARIABLES = (
    "employee.full_name", "employee.full_name_instrumental_kk",
    "position.title_ru", "position.title_kk", "org_unit.title_ru",
    "org_unit.title_kk", "effective_date", "termination.reason",
    "termination.unused_leave_days", "basis",
)
_HISTORICAL_MANIFESTS = {
    # Frozen v1 predates the approved Russian title correction (2026-10-06).
    ("LEAVE.UNPAID.GRANT", 1, "52bf1df2e2d79cfc900207022525b890a47ab71b426b6fa9b0b2f51f29159cd5"):
        ("94aa0e60cc35f4634067addc48467cdaca669bfbc17d9f194e4d4c8107c03fe4", (
            "employee.full_name", "position.title_ru", "position.title_kk", "org_unit.title_ru",
            "org_unit.title_kk", "leave.start_ru", "leave.start_kk", "leave.end_ru", "leave.end_kk",
            "leave.days", "leave.period_text_ru", "leave.period_text_kk", "leave.period_clause_ru",
            "leave.period_clause_kk", "org_unit.document_genitive_kk", "position.document_possessive_kk",
            "position.document_nominative_ru", "employee.full_name_dative_ru", "employee.full_name_dative_kk",
            "employee.full_name_genitive_kk", "basis.application_date_ru", "basis.application_date_kk",
            "basis.application_number_suffix",
        )),
    ("TERMINATION", 1, "5dc8c6dda024ec1ae9ffd84a6e73afbc06af49278017f798a5caa6d3c29d2e36"):
        ("1ad82a8101f6a205bb13d7565d77c14d81f33a3824895c5b69d209b84b3a503a", _HISTORICAL_TERMINATION_ALLOWED_VARIABLES),
    ("TERMINATION", 2, "3dffc622255ca91a0301333714f0b6ee3dc48c52c34e78a1e28714622c3b4b1a"):
        ("5dc8c6dda024ec1ae9ffd84a6e73afbc06af49278017f798a5caa6d3c29d2e36", _HISTORICAL_TERMINATION_ALLOWED_VARIABLES),
}


class ManifestError(ValueError):
    pass


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_sha256(item_type_code: str, values: Mapping[str, str]) -> str:
    return hashlib.sha256(_canonical_json({"item_type_code": item_type_code, **{field: values[field] for field in TEXT_FIELDS}})).hexdigest()


def _built_in_hash(item_type_code: str) -> str:
    return content_sha256(item_type_code, dict(get_personnel_order_template_spec(item_type_code).initial_texts))


def _spec_variables(item_type_code: str) -> tuple[list[str], dict[str, list[str]]]:
    spec = get_personnel_order_template_spec(item_type_code)
    return list(spec.allowed_variables), {key: list(value) for key, value in sorted(spec.required_variables.items())}


def _validate_declared_variable_contract(
    path: Path,
    item_type_code: str,
    values: Mapping[str, str],
    allowed_variables: Any,
    required_variables: Any,
    content_hash: str,
    base_hash: str,
) -> None:
    """Validate current manifests strictly and two frozen historical snapshots."""
    if not isinstance(allowed_variables, list) or not all(isinstance(value, str) for value in allowed_variables):
        raise ManifestError(f"{item_type_code}: invalid allowed_variables")
    if len(set(allowed_variables)) != len(allowed_variables):
        raise ManifestError(f"{item_type_code}: duplicate allowed_variables")
    if not isinstance(required_variables, dict) or any(
        not isinstance(field, str)
        or not isinstance(required, list)
        or not all(isinstance(value, str) for value in required)
        for field, required in required_variables.items()
    ):
        raise ManifestError(f"{item_type_code}: invalid required_variables")
    current_allowed, current_required = _spec_variables(item_type_code)
    if allowed_variables == current_allowed and required_variables == current_required:
        return
    key = (item_type_code, _version(path), content_hash)
    historical = _HISTORICAL_MANIFESTS.get(key)
    if historical is None:
        raise ManifestError(f"{path}: variable contract does not match PersonnelOrderTemplateSpec")
    expected_base, expected_allowed = historical
    if base_hash != expected_base or tuple(allowed_variables) != expected_allowed or required_variables != {}:
        raise ManifestError(f"{path}: historical manifest contract does not match its immutable snapshot")
    declared = set(allowed_variables)
    referenced = {token for value in values.values() for token in _TOKEN.findall(value)}
    if not referenced <= declared:
        raise ManifestError(f"{path}: historical template uses undeclared variables")


def build_manifest(item_type_code: str, values: Mapping[str, str], *, base_content_sha256: str | None = None) -> dict[str, Any]:
    validate_template_texts(item_type_code, values)
    allowed, required = _spec_variables(item_type_code)
    return {"schema_version": SCHEMA_VERSION, "item_type_code": item_type_code, **{field: values[field] for field in TEXT_FIELDS}, "allowed_variables": allowed, "required_variables": required, "base_content_sha256": base_content_sha256 or _built_in_hash(item_type_code), "content_sha256": content_sha256(item_type_code, values)}


def manifest_path(item_type_code: str, root: Path = MANIFEST_ROOT, version: int = 1) -> Path:
    get_personnel_order_template_spec(item_type_code)
    if version < 1: raise ManifestError("Manifest version must be positive")
    return root / item_type_code / f"draft-v{version}.json"


def _manifest_bytes(manifest: Mapping[str, Any]) -> bytes:
    return json.dumps({field: manifest[field] for field in MANIFEST_FIELDS}, ensure_ascii=False, indent=2).replace("\r\n", "\n").encode("utf-8") + b"\n"


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(payload); output.flush(); os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def _version(path: Path) -> int:
    match = _FILENAME.match(path.name)
    if not match: raise ManifestError(f"Invalid manifest filename: {path}")
    return int(match.group(1))


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_bytes(); manifest = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"Invalid manifest {path}: {exc}") from exc
    if not isinstance(manifest, dict) or tuple(manifest) != MANIFEST_FIELDS: raise ManifestError(f"{path}: manifest fields must be exactly {MANIFEST_FIELDS}")
    if raw != _manifest_bytes(manifest): raise ManifestError(f"{path}: manifest is not canonical UTF-8 JSON")
    item_type_code = manifest["item_type_code"]
    if not isinstance(item_type_code, str) or manifest["schema_version"] != SCHEMA_VERSION: raise ManifestError(f"{path}: unsupported schema or item type")
    values = {field: manifest[field] for field in TEXT_FIELDS}
    try:
        validate_template_texts(item_type_code, values)
    except (TemplateValidationError, ValueError) as exc:
        raise ManifestError(f"{path}: {exc}") from exc
    if manifest["content_sha256"] != content_sha256(item_type_code, values): raise ManifestError(f"{path}: content_sha256 mismatch")
    if not isinstance(manifest["base_content_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", manifest["base_content_sha256"]): raise ManifestError(f"{path}: invalid base_content_sha256")
    _validate_declared_variable_contract(path, item_type_code, values, manifest["allowed_variables"], manifest["required_variables"], manifest["content_sha256"], manifest["base_content_sha256"])
    return manifest


def load_manifest_chains(root: Path = MANIFEST_ROOT) -> dict[str, list[dict[str, Any]]]:
    if not root.exists(): return {}
    grouped: dict[str, list[tuple[int, Path, dict[str, Any]]]] = {}
    for path in sorted(root.glob("*/draft-v*.json")):
        version, manifest = _version(path), load_manifest(path)
        if path.parent.name != manifest["item_type_code"]: raise ManifestError(f"{path}: directory and item_type_code differ")
        grouped.setdefault(manifest["item_type_code"], []).append((version, path, manifest))
    chains: dict[str, list[dict[str, Any]]] = {}
    for item_type_code, entries in grouped.items():
        entries.sort(key=lambda entry: entry[0]); versions = [entry[0] for entry in entries]
        if versions != list(range(1, len(entries) + 1)): raise ManifestError(f"{item_type_code}: manifest versions must be continuous from v1")
        manifests = [entry[2] for entry in entries]
        first_version, first_path, first = entries[0]
        if first["base_content_sha256"] != _built_in_hash(item_type_code):
            key = (item_type_code, first_version, first["content_sha256"])
            historical = _HISTORICAL_MANIFESTS.get(key)
            if historical is None or historical[0] != first["base_content_sha256"]:
                raise ManifestError(f"{item_type_code}: v1 base must be the built-in content hash")
        for previous, current in zip(manifests, manifests[1:]):
            if current["base_content_sha256"] != previous["content_sha256"]: raise ManifestError(f"{item_type_code}: manifest base chain is broken")
        chains[item_type_code] = manifests
    return chains


def load_manifests(root: Path = MANIFEST_ROOT) -> list[dict[str, Any]]:
    return [chain[-1] for _, chain in sorted(load_manifest_chains(root).items())]


def write_manifest(item_type_code: str, values: Mapping[str, str], root: Path = MANIFEST_ROOT) -> str:
    chain = load_manifest_chains(root).get(item_type_code, [])
    if chain and content_sha256(item_type_code, values) == chain[-1]["content_sha256"]: return "NO_OP"
    version, path = len(chain) + 1, manifest_path(item_type_code, root, len(chain) + 1)
    if path.exists(): raise ManifestError(f"{path}: refusing to overwrite an existing manifest")
    base = chain[-1]["content_sha256"] if chain else _built_in_hash(item_type_code)
    _write_atomic(path, _manifest_bytes(build_manifest(item_type_code, values, base_content_sha256=base)))
    return "EXPORT"


def export_drafts(item_types: Sequence[str], *, db_engine: Any = default_engine, root: Path = MANIFEST_ROOT) -> dict[str, str]:
    drafts: dict[str, dict[str, str]] = {}
    with db_engine.connect() as connection:
        for item_type_code in item_types:
            get_personnel_order_template_spec(item_type_code)
            row = connection.execute(text("""SELECT title_ru, title_kk, preamble_ru, preamble_kk, body_template_ru, body_template_kk, basis_template_ru, basis_template_kk FROM public.personnel_order_template_versions WHERE item_type_code=:type AND template_id IN (SELECT template_id FROM public.personnel_order_templates WHERE item_type_code=:type AND is_default) AND status='DRAFT' ORDER BY revision DESC, template_version_id DESC LIMIT 1"""), {"type": item_type_code}).mappings().first()
            if row is None: raise ManifestError(f"No DRAFT exists for {item_type_code}")
            drafts[item_type_code] = {field: row[field] for field in TEXT_FIELDS}
    return {item_type_code: write_manifest(item_type_code, values, root) for item_type_code, values in drafts.items()}


def export_published(
    item_type_code: str,
    *,
    expected_template_version_id: int,
    db_engine: Any = default_engine,
    root: Path = MANIFEST_ROOT,
) -> dict[str, str]:
    """Export one explicitly identified immutable PUBLISHED snapshot to a manifest.

    This is intentionally separate from ``export_drafts``: it never creates a
    DRAFT or mutates the source row, and refuses any id/type/status mismatch.
    """
    get_personnel_order_template_spec(item_type_code)
    if expected_template_version_id <= 0:
        raise ManifestError("expected_template_version_id must be positive")
    with db_engine.connect() as connection:
        row = connection.execute(
            text(
                """SELECT template_version_id, item_type_code, status,
                          title_ru, title_kk, preamble_ru, preamble_kk,
                          body_template_ru, body_template_kk,
                          basis_template_ru, basis_template_kk
                   FROM public.personnel_order_template_versions
                   WHERE template_version_id=:template_version_id"""
            ),
            {"template_version_id": expected_template_version_id},
        ).mappings().first()
    if row is None:
        raise ManifestError(f"Template version {expected_template_version_id} was not found")
    if int(row["template_version_id"]) != expected_template_version_id:
        raise ManifestError("Template version id mismatch")
    if str(row["item_type_code"]) != item_type_code:
        raise ManifestError("Template version item type does not match requested item type")
    if str(row["status"]) != "PUBLISHED":
        raise ManifestError("Template version must have PUBLISHED status")
    values = {field: row[field] for field in TEXT_FIELDS}
    return {item_type_code: write_manifest(item_type_code, values, root)}


def _sync_plan(chain: Sequence[Mapping[str, Any]], row: Mapping[str, Any] | None) -> tuple[str, Sequence[Mapping[str, Any]]]:
    if row is None: return "CREATE", [chain[-1]]
    item_type_code = str(chain[-1]["item_type_code"])
    current_hash = content_sha256(item_type_code, {field: row[field] for field in TEXT_FIELDS})
    if current_hash == chain[-1]["content_sha256"]:
        return "NO_OP", []
    if current_hash == chain[0]["base_content_sha256"]: return ("CREATE", [chain[-1]]) if row.get("status") == "PUBLISHED" else ("UPDATE", chain)
    for index, manifest in enumerate(chain):
        if current_hash == manifest["content_sha256"]:
            if index == len(chain) - 1: return "NO_OP", []
            return ("CREATE", [chain[-1]]) if row.get("status") == "PUBLISHED" else ("UPDATE", chain[index + 1:])
    return "CONFLICT", []


def sync_manifests(*, apply: bool, db_engine: Any = default_engine, root: Path = MANIFEST_ROOT, item_type_code: str | None = None) -> dict[str, str]:
    """Validate and apply each type's append-only chain in one transaction."""
    chains, results = load_manifest_chains(root), {}
    if item_type_code is not None:
        if item_type_code not in chains:
            raise ManifestError(f"No manifest for {item_type_code}")
        chains = {item_type_code: chains[item_type_code]}
    if not apply:
        with db_engine.connect() as connection:
            for item_type_code, chain in chains.items():
                row = connection.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND template_id IN (SELECT template_id FROM public.personnel_order_templates WHERE item_type_code=:type AND is_default) AND status='DRAFT' UNION ALL SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND template_id IN (SELECT template_id FROM public.personnel_order_templates WHERE item_type_code=:type AND is_default) AND status='PUBLISHED' LIMIT 1"), {"type": item_type_code}).mappings().first()
                results[item_type_code] = _sync_plan(chain, row)[0]
        return results
    with db_engine.begin() as connection:
        planned: list[tuple[str, Sequence[Mapping[str, Any]], Mapping[str, Any] | None, str]] = []
        for item_type_code, chain in chains.items():
            row = connection.execute(text("SELECT * FROM public.personnel_order_template_versions WHERE item_type_code=:type AND template_id IN (SELECT template_id FROM public.personnel_order_templates WHERE item_type_code=:type AND is_default) AND status IN ('DRAFT','PUBLISHED') ORDER BY CASE status WHEN 'DRAFT' THEN 0 ELSE 1 END FOR UPDATE"), {"type": item_type_code}).mappings().first()
            status, manifests = _sync_plan(chain, row); results[item_type_code] = status; planned.append((item_type_code, manifests, row, status))
        if any(status == "CONFLICT" for _, _, _, status in planned): return results
        for item_type_code, manifests, row, status in planned:
            if status == "CREATE":
                values = {field: manifests[-1][field] for field in TEXT_FIELDS}
                connection.execute(text("""INSERT INTO public.personnel_order_template_versions (item_type_code, version_number, status, title_ru, title_kk, preamble_ru, preamble_kk, body_template_ru, body_template_kk, basis_template_ru, basis_template_kk) VALUES (:type, (SELECT COALESCE(MAX(version_number), 0) + 1 FROM public.personnel_order_template_versions WHERE item_type_code=:type AND template_id IN (SELECT template_id FROM public.personnel_order_templates WHERE item_type_code=:type AND is_default)), 'DRAFT', :title_ru, :title_kk, :preamble_ru, :preamble_kk, :body_template_ru, :body_template_kk, :basis_template_ru, :basis_template_kk)"""), {**values, "type": item_type_code})
            elif status == "UPDATE":
                for manifest in manifests:
                    values = {field: manifest[field] for field in TEXT_FIELDS}
                    connection.execute(text("""UPDATE public.personnel_order_template_versions SET title_ru=:title_ru, title_kk=:title_kk, preamble_ru=:preamble_ru, preamble_kk=:preamble_kk, body_template_ru=:body_template_ru, body_template_kk=:body_template_kk, basis_template_ru=:basis_template_ru, basis_template_kk=:basis_template_kk, revision=revision+1, updated_at=now() WHERE template_version_id=:id"""), {**values, "id": row["template_version_id"]})
    return results
