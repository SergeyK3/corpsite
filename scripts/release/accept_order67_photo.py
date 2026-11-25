"""Attach a generated fictional JPEG to the isolated test acceptance application."""
from __future__ import annotations

import hashlib
import io
import json
import os
from uuid import uuid4

from PIL import Image, ImageDraw
from sqlalchemy import text

from app.db.engine import engine
from app.personnel_intake.domain.photo_validation import validate_intake_photo_bytes
from app.personnel_intake.infrastructure.photo_storage import save_intake_photo

APPLICATION_ID = int(os.environ.get("ACCEPT_APPLICATION_ID", "79"))
PERSON_ID = int(os.environ.get("ACCEPT_PERSON_ID", "87"))


def main() -> None:
    with engine.begin() as conn:
        db = conn.execute(text("select current_database()")).scalar_one()
        if db != "corpsite_hire_accept_20261120_test":
            raise SystemExit(f"Refusing database {db!r}")
        state = conn.execute(text("""
            select a.person_id, o.status from public.personnel_applications a
            join public.personnel_orders o on o.order_id=a.personnel_order_id
            where a.application_id=:id
        """), {"id": APPLICATION_ID}).one()
        if state != (PERSON_ID, "REGISTERED"):
            raise SystemExit(f"Unexpected acceptance state: {state!r}")
        existing = conn.execute(text("""
            select draft_id from public.personnel_intake_drafts where application_id=:id
        """), {"id": APPLICATION_ID}).scalar_one_or_none()
        if existing is not None:
            raise SystemExit("Acceptance intake draft already exists")

        image = Image.new("RGB", (600, 800), "#e1e9ef")
        draw = ImageDraw.Draw(image)
        draw.ellipse((190, 145, 410, 365), fill="#5e87a8")
        draw.rounded_rectangle((115, 380, 485, 790), radius=150, fill="#5e87a8")
        content = io.BytesIO()
        image.save(content, "JPEG", quality=82)
        photo_bytes = content.getvalue()
        validate_intake_photo_bytes(photo_bytes, content_type="image/jpeg")
        file_id = uuid4().hex
        save_intake_photo(APPLICATION_ID, file_id, photo_bytes)
        link_id = conn.execute(text("""
            insert into public.personnel_intake_links
                (application_id, token_hash, status, issued_by_user_id, expires_at, submitted_at)
            values (:id, :hash, 'submitted', 5, now() + interval '1 day', now())
            returning link_id
        """), {"id": APPLICATION_ID,
               "hash": hashlib.sha256(f"order67-fictional-{uuid4().hex}".encode()).hexdigest()}).scalar_one()
        payload = {"personal": {"last_name": "Тестовая", "first_name": "Майра",
                                "photo_file_id": file_id}}
        conn.execute(text("""
            insert into public.personnel_intake_drafts
                (application_id, link_id, status, payload, submitted_at)
            values (:id, :link_id, 'submitted', cast(:payload as jsonb), now())
        """), {"id": APPLICATION_ID, "link_id": link_id,
               "payload": json.dumps(payload, ensure_ascii=False)})
        print(json.dumps({"database": db, "application_id": APPLICATION_ID,
                          "person_id": PERSON_ID, "photo_file_id": file_id,
                          "generated_jpeg_bytes": len(photo_bytes)}))


if __name__ == "__main__":
    main()
