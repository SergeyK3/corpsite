"""Shared helpers for WP-ADR061-001D HIRE apply photo tests."""
from __future__ import annotations

import io

from PIL import Image


def make_hire_test_jpeg(*, width: int = 600, height: int = 800) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(90, 120, 160)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def ensure_application_intake_photo(client, headers, application_id: int) -> str:
    """Upload intake photo via public token while draft is still editable."""
    issue = client.post(
        f"/directory/personnel-applications/{application_id}/intake-link",
        headers=headers,
    )
    assert issue.status_code == 200, issue.text
    token = issue.json()["intake_url_path"].split("/intake/")[-1]
    open_resp = client.get(f"/intake/{token}")
    assert open_resp.status_code == 200, open_resp.text
    content = make_hire_test_jpeg()
    upload = client.put(
        f"/intake/{token}/photo",
        files={"file": ("photo.jpg", content, "image/jpeg")},
    )
    assert upload.status_code == 200, upload.text
    return str(upload.json()["photo_file_id"])
