"""ADR-038 Phase B.1 — sync package format (writer + validator)."""
from __future__ import annotations

from app.services.sync.package_schema import (
    PACKAGE_VERSION,
    READER_VERSION,
    SCHEMA_VERSION,
    EmployeeImportProfileOverrideSyncRecord,
    EmployeeSyncRecord,
    SyncPackageValidationResult,
    SyncPackageWriteResult,
)
from app.services.sync.export_service import SyncExportError, SyncExportResult, export_hr_sync_package
from app.services.sync.import_service import (
    EmployeeResolveResult,
    EmployeeResolveStatus,
    SyncImportError,
    SyncImportResult,
    import_hr_sync_package,
    resolve_employee_key,
)
from app.services.sync.conflict_policy import (
    CONFLICT_TYPE_SECTION_OVERLAP,
    CONFLICT_TYPE_TARGET_NEWER,
    SyncOverrideClassification,
    classify_sync_override,
    merge_profile_overrides,
)
from app.services.sync.preview_service import (
    SyncPreviewItem,
    SyncPreviewResult,
    classification_to_preview_item,
    preview_hr_sync_package,
    preview_result_to_dict,
)
from app.services.sync.package_validator import validate_sync_package
from app.services.sync.package_writer import write_sync_package

__all__ = [
    "PACKAGE_VERSION",
    "READER_VERSION",
    "SCHEMA_VERSION",
    "EmployeeImportProfileOverrideSyncRecord",
    "EmployeeResolveResult",
    "EmployeeResolveStatus",
    "EmployeeSyncRecord",
    "SyncExportError",
    "SyncExportResult",
    "SyncOverrideClassification",
    "CONFLICT_TYPE_SECTION_OVERLAP",
    "CONFLICT_TYPE_TARGET_NEWER",
    "classify_sync_override",
    "merge_profile_overrides",
    "SyncImportError",
    "SyncImportResult",
    "SyncPreviewItem",
    "SyncPreviewResult",
    "SyncPackageValidationResult",
    "SyncPackageWriteResult",
    "export_hr_sync_package",
    "import_hr_sync_package",
    "classification_to_preview_item",
    "preview_hr_sync_package",
    "preview_result_to_dict",
    "resolve_employee_key",
    "validate_sync_package",
    "write_sync_package",
]
