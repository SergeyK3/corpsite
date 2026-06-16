"""AI-assisted extraction for HR import review staging (Phase 2F.2).

AI never creates employees, documents, or apply actions — review-only drafts.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services.hr_import_analytics_service import BatchNotFoundError, load_row_payload

AI_FIELDS = (
    "education_raw",
    "diploma_specialty_raw",
    "qualification_raw",
    "education_training_raw",
    "training_raw",
    "certification_raw",
    "degree_raw",
    "awards_raw",
    "note_raw",
)

EMPTY_EXTRACTION: dict[str, list] = {
    "education": [],
    "training": [],
    "certificates": [],
    "categories": [],
    "awards": [],
    "degrees": [],
    "warnings": [],
}

SYSTEM_PROMPT = """You extract structured HR education data from Russian/Kazakh medical roster text.
Rules:
- Do NOT invent data. Use only what is explicitly present in the source text.
- If information is missing, use empty string or empty array.
- Every extracted fact MUST include source_field and source_text copied from input.
- Assign confidence 0.0-1.0 based on clarity of the source text.
- Return ONLY valid JSON matching the schema, no markdown."""

USER_PROMPT_TEMPLATE = """Extract education portfolio facts from these import fields:

{fields_json}

Return JSON:
{{
  "education": [{{"education_type":"basic|internship|residency|masters|phd","institution":"","specialty":"","completed_at":"","source_field":"","source_text":"","confidence":0.0}}],
  "training": [{{"title":"","organization":"","hours":null,"completed_at":"","source_field":"","source_text":"","confidence":0.0}}],
  "certificates": [{{"specialty":"","issued_at":"","valid_until":"","source_field":"","source_text":"","confidence":0.0}}],
  "categories": [{{"category":"","specialty":"","issued_at":"","source_field":"","source_text":"","confidence":0.0}}],
  "awards": [{{"title":"","date":"","source_field":"","source_text":"","confidence":0.0}}],
  "degrees": [{{"degree_type":"","label":"","source_field":"","source_text":"","confidence":0.0}}],
  "warnings": []
}}"""


class AiExtractionNotConfiguredError(LookupError):
    pass


def _table_exists(conn: Connection) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'hr_import_ai_extraction_drafts'
            LIMIT 1
            """
        )
    ).first()
    return row is not None


def _build_llm_input(payload: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in AI_FIELDS:
        value = str(payload.get(field, "") or "").strip()
        if value:
            result[field] = value
    return result


def _parse_llm_json(content: str) -> dict[str, Any]:
    text_val = content.strip()
    if text_val.startswith("```"):
        text_val = re.sub(r"^```(?:json)?\s*", "", text_val)
        text_val = re.sub(r"\s*```$", "", text_val)
    parsed = json.loads(text_val)
    if not isinstance(parsed, dict):
        raise ValueError("LLM response is not a JSON object")
    merged = dict(EMPTY_EXTRACTION)
    for key in merged:
        value = parsed.get(key, [])
        merged[key] = value if isinstance(value, list) else []
    return merged


def _call_openai_compatible(fields: dict[str, str]) -> dict[str, Any]:
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise AiExtractionNotConfiguredError("OPENAI_API_KEY is not configured")
    base_url = (os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1").rstrip("/")
    model = (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
    user_prompt = USER_PROMPT_TEMPLATE.format(fields_json=json.dumps(fields, ensure_ascii=False, indent=2))
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
    content = body["choices"][0]["message"]["content"]
    return _parse_llm_json(content)


def load_ai_extraction_draft(conn: Connection, batch_id: int, row_id: int) -> Optional[dict[str, Any]]:
    if not _table_exists(conn):
        return None
    row = conn.execute(
        text(
            """
            SELECT draft_id, batch_id, row_id, parse_method, status, extraction, created_at, updated_at
            FROM public.hr_import_ai_extraction_drafts
            WHERE batch_id = :batch_id AND row_id = :row_id
            LIMIT 1
            """
        ),
        {"batch_id": batch_id, "row_id": row_id},
    ).mappings().first()
    if not row:
        return None
    extraction = row["extraction"]
    if isinstance(extraction, str):
        extraction = json.loads(extraction)
    return {
        "draft_id": int(row["draft_id"]),
        "batch_id": int(row["batch_id"]),
        "row_id": int(row["row_id"]),
        "parse_method": row["parse_method"],
        "status": row["status"],
        "requires_review": True,
        "review_label": "AI-предложение. Требуется проверка.",
        "extraction": extraction or dict(EMPTY_EXTRACTION),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def run_ai_extraction(conn: Connection, batch_id: int, row_id: int) -> dict[str, Any]:
    if not _table_exists(conn):
        return {
            "skipped": True,
            "reason": "migration_not_applied",
            "requires_review": True,
            "review_label": "AI-предложение. Требуется проверка.",
            "extraction": dict(EMPTY_EXTRACTION),
        }
    row = load_row_payload(conn, batch_id, row_id)
    fields = _build_llm_input(row["payload"])
    if not fields:
        extraction = dict(EMPTY_EXTRACTION)
        extraction["warnings"] = ["Нет текстовых полей для AI-извлечения."]
        parse_method = "llm_assisted"
    else:
        try:
            extraction = _call_openai_compatible(fields)
            parse_method = "llm_assisted"
        except AiExtractionNotConfiguredError:
            extraction = dict(EMPTY_EXTRACTION)
            extraction["warnings"] = ["LLM не настроен (OPENAI_API_KEY)."]
            parse_method = "llm_unavailable"
        except Exception as exc:
            extraction = dict(EMPTY_EXTRACTION)
            extraction["warnings"] = [f"Ошибка LLM: {exc}"]
            parse_method = "llm_error"

    now = datetime.now(timezone.utc)
    conn.execute(
        text(
            """
            INSERT INTO public.hr_import_ai_extraction_drafts (
                batch_id, row_id, parse_method, status, extraction, created_at, updated_at
            )
            VALUES (
                :batch_id, :row_id, :parse_method, 'draft', CAST(:extraction AS JSONB), :now, :now
            )
            ON CONFLICT (row_id) DO UPDATE SET
                parse_method = EXCLUDED.parse_method,
                status = 'draft',
                extraction = EXCLUDED.extraction,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "batch_id": batch_id,
            "row_id": row_id,
            "parse_method": parse_method,
            "extraction": json.dumps(extraction, ensure_ascii=False),
            "now": now,
        },
    )
    draft = load_ai_extraction_draft(conn, batch_id, row_id)
    if draft is None:
        raise BatchNotFoundError(f"Failed to persist AI draft for row_id={row_id}")
    return draft
