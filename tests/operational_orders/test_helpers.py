# tests/operational_orders/test_helpers.py
"""Shared helpers for OO editorial workflow tests."""
from __future__ import annotations

BASE = "/api/operational-orders/draft-workspaces"
WORKSPACES_BASE = "/api/operational-orders/workspaces"
DOCUMENTS_BASE = "/api/operational-orders/documents"


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


def create_editorial_ready_workspace(client, headers, seed, *, author_ref: str, locales: tuple[str, ...] = ("ru", "kk")):
    workspace_id, detail = create_ready_workspace(
        client, headers, seed, author_ref=author_ref, locales=locales
    )
    for block in detail["blocks"]:
        confirm_block(
            client,
            headers,
            workspace_id,
            block,
            role="CONTENT_AUTHOR",
            confirmer_ref=author_ref,
        )
    fresh = client.get(f"{BASE}/{workspace_id}", headers=headers).json()
    for ru_block in [b for b in fresh["blocks"] if b["locale"] == "ru"]:
        kk_block = next(
            b
            for b in fresh["blocks"]
            if b["locale"] == "kk"
            and b["block_type"] == ru_block["block_type"]
            and b["sequence"] == ru_block["sequence"]
        )
        client.post(
            f"{BASE}/{workspace_id}/reconciliations",
            json={"ru_block_id": ru_block["block_id"], "kk_block_id": kk_block["block_id"]},
            headers=headers,
        )
    ready_detail = client.get(f"{BASE}/{workspace_id}", headers=headers).json()
    ready_resp = client.post(
        f"{BASE}/{workspace_id}/editorial-package-ready",
        json={"expected_version": ready_detail["workspace"]["version"]},
        headers=headers,
    )
    assert ready_resp.status_code == 200, ready_resp.text
    return workspace_id, ready_resp.json()


def promote_workspace(client, headers, workspace_id, *, expected_version: int | None = None):
    body = {}
    if expected_version is not None:
        body["expected_version"] = expected_version
    return client.post(f"{WORKSPACES_BASE}/{workspace_id}/promote", json=body, headers=headers)


def create_promoted_document(client, headers, seed, *, author_ref: str | None = None):
    author = author_ref or str(seed["executor_user_id"])
    workspace_id, _ = create_editorial_ready_workspace(client, headers, seed, author_ref=author)
    promoted = promote_workspace(client, headers, workspace_id)
    assert promoted.status_code == 200, promoted.text
    document_id = promoted.json()["document"]["document"]["document_id"]
    return workspace_id, document_id, promoted.json()


def assign_signing_authority(
    client,
    headers,
    document_id,
    *,
    reference: str,
    expected_version: int | None = None,
    org_unit_id: int | None = None,
):
    body = {
        "authority": {
            "reference_type": "PERSON",
            "reference": reference,
            "display_name": "Signer",
        }
    }
    if expected_version is not None:
        body["expected_version"] = expected_version
    if org_unit_id is not None:
        body["authority_org_unit_id"] = org_unit_id
    return client.post(f"{DOCUMENTS_BASE}/{document_id}/signing-authority", json=body, headers=headers)


def mark_ready_for_signature(client, headers, document_id, *, expected_version: int | None = None):
    body = {}
    if expected_version is not None:
        body["expected_version"] = expected_version
    return client.post(f"{DOCUMENTS_BASE}/{document_id}/ready-for-signature", json=body, headers=headers)


def return_to_created(client, headers, document_id, *, reason: str, expected_version: int | None = None):
    body = {"reason": reason}
    if expected_version is not None:
        body["expected_version"] = expected_version
    return client.post(f"{DOCUMENTS_BASE}/{document_id}/return-to-created", json=body, headers=headers)
