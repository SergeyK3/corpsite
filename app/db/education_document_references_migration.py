"""Two independent references. Never rewrite cards, documents or program kinds."""
from sqlalchemy import text

LEVELS = (
    ('NO_EDUCATION','Без образования','Білімі жоқ',None,None,10),
    ('BASIC_SECONDARY','Основное среднее образование','Негізгі орта білім',
     '5–9 классы основной школы. Уровень уточняется по документу об образовании.',
     'Негізгі мектептің 5–9-сыныптары. Білім деңгейі білім туралы құжат бойынша нақтыланады.',20),
    ('GENERAL_SECONDARY','Общее среднее образование','Жалпы орта білім',
     '10–11 (12) классы старшей школы. Уровень уточняется по документу об образовании.',
     'Жоғары сыныптар: 10–11 (12)-сыныптар. Білім деңгейі білім туралы құжат бойынша нақтыланады.',30),
    ('TECHNICAL_VOCATIONAL','Техническое и профессиональное образование','Техникалық және кәсіптік білім',None,None,40),
    ('POST_SECONDARY','Послесреднее образование','Орта білімнен кейінгі білім',None,None,50),
    ('HIGHER','Высшее образование','Жоғары білім',None,None,60),
    ('POSTGRADUATE','Послевузовское образование','Жоғары оқу орнынан кейінгі білім',None,None,70),
)
# Legacy code ATTESTATION keeps the existing Russian name and meaning.
DOCUMENT_KK = {'DIPLOMA':'Диплом','CERTIFICATE':'Сертификат','ATTESTATION':'Куәлік',
               'COMPLETION_CERT':'Куәлік','REFERENCE':'Анықтама','OTHER':'Өзге құжат'}
SCHOOL_ATTESTATE = 'SCHOOL_ATTESTATE'


def upgrade(conn):
    conn.execute(text("SET LOCAL lock_timeout='5s'"))
    conn.execute(text('LOCK TABLE document_kinds IN SHARE ROW EXCLUSIVE MODE'))
    conn.execute(text('''CREATE TABLE IF NOT EXISTS education_levels (
        code text PRIMARY KEY, name_ru text NOT NULL CHECK(btrim(name_ru)<>''),
        name_kk text NOT NULL CHECK(btrim(name_kk)<>''), description_ru text, description_kk text,
        sort_order integer NOT NULL DEFAULT 0, is_active boolean NOT NULL DEFAULT true,
        revision integer NOT NULL DEFAULT 1 CHECK(revision>=1),
        created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
        updated_by_user_id bigint REFERENCES users(user_id) ON DELETE SET NULL
    )'''))
    for code,ru,kk,description_ru,description_kk,sort in LEVELS:
        conn.execute(text('''INSERT INTO education_levels(code,name_ru,name_kk,description_ru,description_kk,sort_order)
            VALUES(:code,:ru,:kk,:description_ru,:description_kk,:sort) ON CONFLICT(code) DO NOTHING'''),
            dict(code=code,ru=ru,kk=kk,description_ru=description_ru,description_kk=description_kk,sort=sort))
    # `name` remains the canonical RU field for every legacy consumer. The new
    # management API exposes name_ru as an alias, so the two cannot diverge.
    conn.execute(text('ALTER TABLE document_kinds ADD COLUMN IF NOT EXISTS name_kk text'))
    conn.execute(text('ALTER TABLE document_kinds ADD COLUMN IF NOT EXISTS revision integer NOT NULL DEFAULT 1'))
    conn.execute(text('ALTER TABLE document_kinds ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now()'))
    conn.execute(text('ALTER TABLE document_kinds ADD COLUMN IF NOT EXISTS updated_by_user_id bigint REFERENCES users(user_id) ON DELETE SET NULL'))
    for code,kk in DOCUMENT_KK.items():
        conn.execute(text('UPDATE document_kinds SET name_kk=:kk WHERE code=:code AND name_kk IS NULL'),dict(code=code,kk=kk))
    conn.execute(text('''INSERT INTO document_kinds(code,name,name_kk,is_active,sort_order)
        VALUES(:code,'Аттестат','Аттестат',true,70) ON CONFLICT(code) DO NOTHING'''),{'code':SCHOOL_ATTESTATE})
    for table,parent in (('education_level_audit','education_levels'),('document_kind_audit','document_kinds')):
        conn.execute(text(f'''CREATE TABLE IF NOT EXISTS {table} (
            audit_id bigserial PRIMARY KEY, code text NOT NULL REFERENCES {parent}(code) ON UPDATE RESTRICT ON DELETE RESTRICT,
            action text NOT NULL,before_value jsonb,after_value jsonb NOT NULL,
            actor_user_id bigint REFERENCES users(user_id) ON DELETE SET NULL,
            changed_at timestamptz NOT NULL DEFAULT now()
        )'''))


def downgrade(conn):
    raise RuntimeError('Removing used reference values or their RU/KK history requires a separate data audit')
