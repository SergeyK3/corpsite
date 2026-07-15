"""Deterministic PMF → PPR command_id composition (R5)."""
from __future__ import annotations

import hashlib


PMF_COMMAND_ID_VERSION = "pmf-bridge-v1"


def build_pmf_commit_command_id(
    *,
    migration_run_id: int,
    migration_item_id: int,
) -> str:
    raw = f"{PMF_COMMAND_ID_VERSION}:commit:{migration_run_id}:{migration_item_id}"
    return _stable_id(raw)


def build_pmf_void_command_id(
    *,
    migration_run_id: int,
    migration_item_id: int,
) -> str:
    raw = f"{PMF_COMMAND_ID_VERSION}:void:{migration_run_id}:{migration_item_id}"
    return _stable_id(raw)


def build_pmf_supersede_command_id(
    *,
    domain_code: str,
    record_table_name: str,
    old_record_id: int,
    replacement_identity: str,
) -> str:
    raw = (
        f"{PMF_COMMAND_ID_VERSION}:supersede:"
        f"{domain_code}:{record_table_name}:{old_record_id}:{replacement_identity}"
    )
    return _stable_id(raw)


def _stable_id(raw: str) -> str:
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"ppr-cmd-{digest[:32]}"
