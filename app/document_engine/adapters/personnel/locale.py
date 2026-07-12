"""Personnel locale read adapter (UDE-008)."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from app.document_engine.adapters.personnel._mapping import (
    optional_str,
    parse_locale_code,
    parse_staleness_state,
    parse_text_source_type,
)
from app.document_engine.adapters.personnel.views import (
    PersonnelLocaleBlockReadView,
    PersonnelLocaleSnapshotReadView,
)


class PersonnelLocaleAdapter:
    """Maps PO editorial blocks and legacy localized texts → shared locale views."""

    @staticmethod
    def from_editorial_block(block: Mapping[str, Any]) -> PersonnelLocaleBlockReadView:
        override = optional_str(block.get("override_text"))
        generated = optional_str(block.get("generated_text"))
        effective = optional_str(block.get("effective_text")) or ""
        return PersonnelLocaleBlockReadView(
            block_id=int(block["block_id"]),
            scope=str(block.get("scope") or "order"),
            order_item_id=(
                int(block["order_item_id"])
                if block.get("order_item_id") is not None
                else None
            ),
            locale=parse_locale_code(block.get("locale")),
            block_type=str(block.get("block_type") or ""),
            generated_text=generated,
            override_text=override,
            effective_text=effective,
            text_source_type=parse_text_source_type(
                override_text=override,
                generated_text=generated,
            ),
            staleness_state=parse_staleness_state(block.get("review_status")),
            source_fingerprint=optional_str(block.get("source_fingerprint")),
            generator_key=optional_str(block.get("generator_key")),
            generator_version=optional_str(block.get("generator_version")),
            review_status=str(block.get("review_status") or "CURRENT"),
        )

    @staticmethod
    def from_editorial_state(editorial: Mapping[str, Any]) -> tuple[PersonnelLocaleBlockReadView, ...]:
        blocks: list[PersonnelLocaleBlockReadView] = []
        for block in editorial.get("order_blocks") or []:
            blocks.append(PersonnelLocaleAdapter.from_editorial_block(block))
        for group in editorial.get("items") or []:
            for block in group.get("blocks") or []:
                blocks.append(PersonnelLocaleAdapter.from_editorial_block(block))
        return tuple(blocks)

    @staticmethod
    def from_localized_text(row: Mapping[str, Any]) -> PersonnelLocaleSnapshotReadView:
        title = optional_str(row.get("title"))
        preamble = optional_str(row.get("preamble"))
        body = optional_str(row.get("body_text"))
        return PersonnelLocaleSnapshotReadView(
            localized_text_id=int(row["localized_text_id"]),
            locale=parse_locale_code(row.get("locale")),
            title=title,
            preamble=preamble,
            body_text=body,
            text_source_type=parse_text_source_type(
                override_text=None,
                generated_text=title or preamble or body,
                is_authoritative_legacy=bool(row.get("is_authoritative")),
            ),
            is_authoritative=bool(row.get("is_authoritative")),
            render_version=int(row.get("render_version") or 1),
        )

    @staticmethod
    def from_localized_texts(
        rows: Iterable[Mapping[str, Any]],
    ) -> tuple[PersonnelLocaleSnapshotReadView, ...]:
        return tuple(PersonnelLocaleAdapter.from_localized_text(row) for row in rows)
