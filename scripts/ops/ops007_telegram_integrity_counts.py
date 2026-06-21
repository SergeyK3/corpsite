"""OPS-007 read-only Telegram integrity counts. No mutations."""
from __future__ import annotations

from sqlalchemy import text

from app.db.engine import engine

CHECKS: list[tuple[str, str]] = [
    ("users_total", "SELECT COUNT(*) FROM public.users"),
    (
        "users_with_telegram",
        "SELECT COUNT(*) FROM public.users WHERE telegram_id IS NOT NULL AND trim(telegram_id::text) <> ''",
    ),
    ("tg_bindings_legacy_rows", "SELECT COUNT(*) FROM public.tg_bindings"),
    (
        "contacts_with_telegram",
        """
        SELECT COUNT(*) FROM public.contacts
        WHERE telegram_numeric_id IS NOT NULL
           OR (telegram_username IS NOT NULL AND trim(telegram_username) <> '')
        """,
    ),
    (
        "task_event_deliveries_telegram",
        "SELECT COUNT(*) FROM public.task_event_deliveries WHERE channel = 'telegram'",
    ),
    (
        "C2_telegram_without_employee",
        """
        SELECT COUNT(*) FROM public.users u
        WHERE u.is_active
          AND u.telegram_id IS NOT NULL
          AND trim(u.telegram_id::text) <> ''
          AND u.employee_id IS NULL
        """,
    ),
    (
        "C3_employee_user_no_telegram",
        """
        SELECT COUNT(*) FROM public.employees e
        JOIN public.users u ON u.employee_id = e.employee_id AND u.is_active
        WHERE e.operational_status IN ('draft', 'active', 'suspended')
          AND (u.telegram_id IS NULL OR trim(u.telegram_id::text) = '')
        """,
    ),
    (
        "C5_duplicate_telegram_id",
        """
        SELECT COUNT(*) FROM (
            SELECT trim(telegram_id::text) AS tg
            FROM public.users
            WHERE telegram_id IS NOT NULL AND trim(telegram_id::text) <> ''
            GROUP BY trim(telegram_id::text)
            HAVING COUNT(*) > 1
        ) d
        """,
    ),
    (
        "C6_service_account_with_telegram",
        """
        SELECT COUNT(*) FROM public.users u
        WHERE u.telegram_id IS NOT NULL
          AND trim(u.telegram_id::text) <> ''
          AND (
            lower(COALESCE(u.login, '')) ~ '(^svc_|^service_|^bot_|^system_|^cron_)'
            OR lower(COALESCE(u.full_name, '')) ~ '(системн|service account|\\mbot\\b|\\mcron\\b)'
          )
        """,
    ),
    (
        "C7_inactive_user_with_telegram",
        """
        SELECT COUNT(*) FROM public.users u
        WHERE NOT COALESCE(u.is_active, TRUE)
          AND u.telegram_id IS NOT NULL
          AND trim(u.telegram_id::text) <> ''
        """,
    ),
    (
        "C8_tg_bindings_drift",
        """
        SELECT COUNT(*) FROM public.tg_bindings tb
        JOIN public.users u ON u.user_id = tb.user_id
        WHERE u.telegram_id IS NULL
           OR trim(u.telegram_id::text) = ''
           OR trim(u.telegram_id::text) <> tb.tg_user_id::text
        """,
    ),
]


def main() -> None:
    with engine.connect() as conn:
        for name, sql in CHECKS:
            try:
                value = conn.execute(text(sql)).scalar_one()
                print(f"{name}={value}")
            except Exception as exc:
                print(f"{name}=ERROR:{exc}")


if __name__ == "__main__":
    main()
