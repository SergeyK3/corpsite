"""Official draft snapshot builder (UDE-010)."""
from __future__ import annotations

from app.document_engine.editorial.editorial_models import (
    EditorialBlock,
    OfficialDraftLocaleBlock,
    OfficialDraftSnapshot,
)
from app.document_engine.read_services.facade import DocumentEngineReadSnapshot


class OfficialDraftBuilder:
    """Assembles OfficialDraftSnapshot from read models — no DocumentId."""

    @staticmethod
    def _draft_block_from_editorial(block: EditorialBlock) -> OfficialDraftLocaleBlock:
        return OfficialDraftLocaleBlock(
            locale=block.locale,
            block_type=block.block_type,
            scope=block.scope,
            order_item_id=block.order_item_id,
            generated_text=block.generated_text,
            override_text=block.override.override_text,
            effective_text=block.effective_text,
            review_state=block.review_state,
            staleness_state=block.staleness_state,
            fingerprint=block.fingerprint,
            text_source_type=block.text_source_type,
        )

    @staticmethod
    def from_snapshot(snapshot: DocumentEngineReadSnapshot) -> OfficialDraftSnapshot:
        from app.document_engine.editorial.editorial_service import EditorialService

        editorial = EditorialService.from_snapshot(snapshot)
        locale_blocks: list[OfficialDraftLocaleBlock] = []
        for section in editorial.sections:
            for block in section.blocks:
                locale_blocks.append(OfficialDraftBuilder._draft_block_from_editorial(block))

        metadata = snapshot.document.metadata
        return OfficialDraftSnapshot(
            document_kind=snapshot.document.document_kind,
            specialization=snapshot.document.specialization,
            workspace_reference=snapshot.document.document_id.value,
            order_type_code=metadata.order_type_code,
            lifecycle_state=snapshot.document.lifecycle_state,
            locale_blocks=tuple(locale_blocks),
            item_count=len(snapshot.items),
            draft_metadata={
                "order_number": metadata.order_number,
                "order_date": metadata.order_date,
                "source_mode": metadata.source_mode,
                "legal_basis_article": metadata.legal_basis_article,
                "basis_summary": metadata.basis_summary,
                "updated_at": metadata.updated_at,
            },
        )
