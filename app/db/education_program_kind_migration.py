"""Replace only the education_kind enumeration with a stable-code reference."""
from sqlalchemy import text

# Existing codes are immutable compatibility keys, not the runtime allowlist.
SEED = (
    ('basic', 'Основное образование', 'Негізгі білім', 10),
    ('internship', 'Интернатура', 'Интернатура', 20),
    ('residency', 'Резидентура', 'Резидентура', 30),
    ('masters', 'Магистратура', 'Магистратура', 40),
    ('phd', 'Докторантура (PhD)', 'Докторантура (PhD)', 50),
    ('other', 'Другое', 'Басқа', 60),
    # Project has no prior label. Kazakh term: adilet.zan.kz/kaz/docs/V040003005_
    ('aspirantura', 'Аспирантура', 'Аспирантура', 70),
)


def upgrade(conn):
    conn.execute(text("SET LOCAL lock_timeout='5s'"))
    conn.execute(text('LOCK TABLE public.person_education IN SHARE ROW EXCLUSIVE MODE'))
    exists = conn.execute(text("SELECT to_regclass('public.education_program_kinds') IS NOT NULL")).scalar_one()
    if not exists:
        unknown = conn.execute(text("SELECT count(*) FROM person_education WHERE education_kind <> ALL(:codes)"), {'codes': [r[0] for r in SEED]}).scalar_one()
        if unknown:
            raise RuntimeError(f'Education reference migration stopped: {unknown} rows have unrecognized codes; review without recoding records')
    conn.execute(text('''CREATE TABLE IF NOT EXISTS public.education_program_kinds (
        code text PRIMARY KEY, name_ru text NOT NULL CHECK (btrim(name_ru)<>''),
        name_kk text NOT NULL CHECK (btrim(name_kk)<>''), is_active boolean NOT NULL DEFAULT true,
        sort_order integer NOT NULL DEFAULT 0, revision integer NOT NULL DEFAULT 1 CHECK(revision>=1),
        created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
        updated_by_user_id bigint REFERENCES users(user_id) ON DELETE SET NULL
    )'''))
    for code, ru, kk, order in SEED:
        conn.execute(text('INSERT INTO education_program_kinds(code,name_ru,name_kk,sort_order) VALUES(:code,:ru,:kk,:sort) ON CONFLICT(code) DO NOTHING'), dict(code=code,ru=ru,kk=kk,sort=order))
    conn.execute(text('''CREATE TABLE IF NOT EXISTS public.education_program_kind_audit (
        audit_id bigserial PRIMARY KEY, code text NOT NULL REFERENCES education_program_kinds(code) ON DELETE RESTRICT ON UPDATE RESTRICT,
        action text NOT NULL, before_value jsonb, after_value jsonb NOT NULL,
        actor_user_id bigint REFERENCES users(user_id) ON DELETE SET NULL,
        changed_at timestamptz NOT NULL DEFAULT now()
    )'''))
    conn.execute(text('ALTER TABLE person_education DROP CONSTRAINT IF EXISTS chk_person_education_kind'))
    if not conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='person_education'::regclass AND conname='fk_person_education_program_kind')")).scalar_one():
        conn.execute(text('ALTER TABLE person_education ADD CONSTRAINT fk_person_education_program_kind FOREIGN KEY(education_kind) REFERENCES education_program_kinds(code) ON UPDATE RESTRICT ON DELETE RESTRICT'))


def downgrade(conn):
    raise RuntimeError('An editable reference cannot be reduced to the legacy six-code CHECK without a separate data audit')
