# tests/test_ops026_telegram_expert_slot_guard.py
"""OPS-026 — guard against dev/personal Telegram IDs in QM_AMB expert slots."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Documented dev/personal IDs that must not be bound to production QM_AMB expert slot.
FORBIDDEN_QM_AMB_TELEGRAM_IDS = frozenset(
    {
        "885342581",  # legacy UI placeholder / key_contacts DIRECTOR dev row
    }
)

QM_AMB_EXPECTED_TELEGRAM_ID = "7685102887"

TELEGRAM_ID_PATTERN = re.compile(r"\b\d{9,12}\b")

SCAN_PATHS = (
    REPO_ROOT / "key_contacts.csv",
    REPO_ROOT / "db" / "init" / "020_seed_roles_users_employees.sql",
    REPO_ROOT / "scripts" / "pilot" / "qm_roles_users_bootstrap.sql",
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _qm_amb_row_from_key_contacts(text: str) -> str | None:
    for line in text.splitlines():
        if line.startswith("QM_AMB,"):
            return line
    return None


def test_key_contacts_qm_amb_has_no_forbidden_telegram_id():
    path = REPO_ROOT / "key_contacts.csv"
    if not path.exists():
        pytest.skip("key_contacts.csv not present")

    row = _qm_amb_row_from_key_contacts(_read_text(path))
    assert row is not None, "QM_AMB row missing in key_contacts.csv"

    ids = TELEGRAM_ID_PATTERN.findall(row)
    forbidden_hits = FORBIDDEN_QM_AMB_TELEGRAM_IDS.intersection(ids)
    assert not forbidden_hits, f"QM_AMB key_contacts row contains forbidden telegram id(s): {forbidden_hits}"


def test_seed_files_do_not_assign_forbidden_telegram_to_qm_amb():
    hits: list[str] = []
    for rel in SCAN_PATHS:
        path = REPO_ROOT / rel if not isinstance(rel, Path) else rel
        if not path.exists():
            continue
        text = _read_text(path)
        if "QM_AMB" not in text and "qm_amb" not in text:
            continue
        for forbidden in FORBIDDEN_QM_AMB_TELEGRAM_IDS:
            if forbidden in text and ("QM_AMB" in text or "qm_amb" in text):
                # Narrow: forbidden id appears on same line as QM_AMB/qm_amb
                for line in text.splitlines():
                    lower = line.lower()
                    if forbidden in line and ("qm_amb" in lower or "qm_amb," in line):
                        hits.append(f"{path.name}: {line.strip()}")

    assert not hits, "Forbidden dev telegram id on QM_AMB line in seed/fixture files:\n" + "\n".join(hits)


def test_qm_amb_expected_telegram_id_documented_in_audit_sql():
    audit_sql = REPO_ROOT / "docs" / "ops" / "OPS-026-telegram-id-audit.sql"
    assert audit_sql.exists(), "OPS-026 audit SQL must exist"
    text = _read_text(audit_sql)
    assert QM_AMB_EXPECTED_TELEGRAM_ID in text
