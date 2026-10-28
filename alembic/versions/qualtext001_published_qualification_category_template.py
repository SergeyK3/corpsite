"""Import the reviewed, published qualification-category personnel template.

Source: local template 42 / published version 56 (read-only export).
Texts are frozen verbatim, including whitespace and certificate placeholders.
Server identities and publication time are generated here; no local actor IDs,
source IDs or category seed rows are inserted. Existing templates are untouched.
"""
from alembic import op
from sqlalchemy import text

revision = "qualtext001"
down_revision = "medqual001"
branch_labels = None
depends_on = None

EXPORT_SHA256 = '64fd8b00b688cbe2829955ee321dcdf99070e5cb347fceeb259492900bc70129'

TEMPLATE = {'item_type_code': 'QUALIFICATION_CATEGORY',
 'name_ru': 'Об изменении квалификационной категории',
 'name_kk': 'Біліктілік санаты туралы мәліметіне өзгеріс енгізу туралы',
 'is_default': False}

VERSION = {'version_number': 2,
 'revision': 2,
 'based_on_built_in': False,
 'title_ru': 'Об изменении квалификационной категории',
 'title_kk': 'Біліктілік санаты туралы мәліметіне өзгеріс енгізу туралы',
 'print_title_ru': 'Об изменении квалификационной категории',
 'print_title_kk': 'Біліктілік санаты туралы мәліметіне өзгеріс енгізу туралы',
 'preamble_ru': 'На основании справки специалиста здравоохранения, выданной Комитетом по '
                'медико-фармацевтическому контролю Министерства здравоохранения Республики '
                'Казахстан,',
 'preamble_kk': 'Қазақстан Республикасының Денсаулық сақтау министрлігі Медициналық және '
                'фармацевтикалық бақылау комитетімен берілген Денсаулық сақтау саласының маманы '
                'сертификатының негізінде',
 'body_template_ru': 'С {{effective_date.ru}} категория '
                     '{{position.document_genitive_ru}}{{medical_specialty.clause_ru}} '
                     '{{org_unit.document_genitive_ru}} {{employee.full_name_genitive_ru}} будет '
                     'считаться „{{qualification_category.level_ru}}“ до '
                     '{{qualification_category.valid_until_ru}}.',
 'body_template_kk': '{{effective_date.kk}} бастап {{org_unit.document_genitive_kk}} '
                     '{{position.document_possessive_kk}}{{medical_specialty.clause_kk}} '
                     '{{employee.full_name_genitive_kk}} санаты '
                     '„{{qualification_category.level_kk}}“ '
                     '{{qualification_category.valid_until_kk}} дейін болып есептелсін.',
 'basis_template_ru': 'Основание: Сертификат № KZ0000000000000 от ',
 'basis_template_kk': 'Негіз:  № KZ0000000000000 сертификат.'}


def upgrade() -> None:
    conn = op.get_bind()
    # Serialize name checks and insertion against other template writers.
    conn.execute(text("LOCK TABLE public.personnel_order_templates IN SHARE ROW EXCLUSIVE MODE"))
    exists = conn.execute(text("""
        SELECT template_id FROM public.personnel_order_templates
        WHERE item_type_code=:item_type_code
          AND (name_ru=:name_ru OR name_kk=:name_kk)
        LIMIT 1
    """), TEMPLATE).first()
    if exists is not None:
        raise RuntimeError(
            "QUALIFICATION_CATEGORY release template already exists; "
            "review the existing template instead of duplicating or replacing it"
        )
    template_id = conn.execute(text("""
        INSERT INTO public.personnel_order_templates
            (item_type_code, name_ru, name_kk, is_default)
        VALUES (:item_type_code, :name_ru, :name_kk, :is_default)
        RETURNING template_id
    """), TEMPLATE).scalar_one()
    conn.execute(text("""
        INSERT INTO public.personnel_order_template_versions (
            template_id, item_type_code, version_number, revision, status,
            title_ru, title_kk, print_title_ru, print_title_kk,
            preamble_ru, preamble_kk, body_template_ru, body_template_kk,
            basis_template_ru, basis_template_kk, based_on_built_in, published_at
        ) VALUES (
            :template_id, :item_type_code, :version_number, :revision, 'PUBLISHED',
            :title_ru, :title_kk, :print_title_ru, :print_title_kk,
            :preamble_ru, :preamble_kk, :body_template_ru, :body_template_kk,
            :basis_template_ru, :basis_template_kk, :based_on_built_in,
            statement_timestamp()
        )
    """), {**VERSION, "template_id": template_id, "item_type_code": TEMPLATE["item_type_code"]})


def downgrade() -> None:
    # Published text may already be referenced by orders and audit snapshots.
    # Do not guess an identity or remove a publication during a release rollback.
    raise RuntimeError(
        "qualtext001 retains its published template; "
        "use a reviewed forward migration to change or retire it"
    )
