"""Store the current editable hiring document checklist."""
from alembic import op

revision = "hdc001checklist"
down_revision = "ua004telegrambindcodes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.hiring_document_checklists (
            code TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        INSERT INTO public.hiring_document_checklists (code, title, content)
        VALUES (
            'HIRING_DOCUMENT_CHECKLIST',
            'Краткий перечень документов при приёме на работу',
            $json${
              "items": [
                "Документ, удостоверяющий личность.",
                "Документ об образовании и квалификации — диплом, сертификат, лицензия или иной документ, если работа требует соответствующих знаний, квалификации или подготовки.",
                "Документ, подтверждающий трудовую деятельность — для лиц, имеющих трудовой стаж.",
                "Документ о прохождении предварительного медицинского осмотра — если его прохождение обязательно для соответствующей должности.",
                "Справка о наличии либо отсутствии судимости — в случаях, предусмотренных законодательством. Справку можно получить на портале eGov.kz."
              ],
              "note": "Точный перечень документов определяется в зависимости от должности и сообщается сотрудником отдела кадров.",
              "show_additional_notes": true,
              "additional_notes_lines": 3
            }$json$::jsonb
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE public.hiring_document_checklists")
