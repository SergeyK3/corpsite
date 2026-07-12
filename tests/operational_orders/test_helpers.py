# tests/operational_orders/test_helpers.py
"""Shared helpers for OO editorial workflow tests."""
from __future__ import annotations

BASE = "/api/operational-orders/draft-workspaces"


def workspace_payload(
    *,
    seed,
    author_ref: str,
    locales: tuple[str, ...] = ("ru",),
):
    blocks = []
    for locale in locales:
        blocks.append(
            {
                "locale": locale,
                "block_type": "TITLE",
                "submitted_text": f"{locale.upper()} submitted title",
                "source_type": "SUBMITTED",
                "sequence": 1,
            }
        )
        blocks.append(
            {
                "locale": locale,
                "block_type": "BODY",
                "submitted_text": f"{locale.upper()} submitted body",
                "source_type": "SUBMITTED",
                "sequence": 1,
            }
        )
    return {
        "initiator": {"reference_type": "PERSON", "reference": "init-helper-001", "display_name": "Initiator"},
        "content_author": {"reference_type": "PERSON", "reference": author_ref, "display_name": "Author"},
        "submitting_org_unit_id": int(seed["unit_id"]),
        "blocks": blocks,
    }


def create_ready_workspace(client, headers, seed, *, author_ref: str, locales: tuple[str, ...]):
    create_resp = client.post(BASE, json=workspace_payload(seed=seed, author_ref=author_ref, locales=locales), headers=headers)
    assert create_resp.status_code == 200, create_resp.text
    workspace_id = create_resp.json()["workspace"]["workspace_id"]
    client.post(f"{BASE}/{workspace_id}/accept", json={}, headers=headers)
    client.post(f"{BASE}/{workspace_id}/validate", json={}, headers=headers)
    ready_resp = client.post(f"{BASE}/{workspace_id}/ready-for-editorial", json={}, headers=headers)
    assert ready_resp.status_code == 200, ready_resp.text
    return workspace_id, ready_resp.json()


def confirm_block(client, headers, workspace_id, block, *, role: str, confirmer_ref: str, version: int | None = None):
    body = {
        "block_id": block["block_id"],
        "confirmation_role": role,
        "confirmer": {"reference_type": "PERSON", "reference": confirmer_ref, "display_name": role},
        "block_expected_version": block["version"],
    }
    if version is not None:
        body["expected_version"] = version
    return client.post(f"{BASE}/{workspace_id}/confirmations", json=body, headers=headers)
