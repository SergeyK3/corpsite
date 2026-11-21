"""Repair the isolated electronic-hire acceptance administrator fixture.

Run only from the test release with its backend.env loaded. The database name
guard prevents this fixture operation from changing production or training.
"""

from sqlalchemy import text

from app.db.engine import engine


TEST_DATABASE = "corpsite_hire_accept_20261120_test"
LOGIN = "hire_test_admin"
ROLE_ID = 2  # Existing application RBAC contract for a system administrator.
DISPLAY_NAME = "Тестовый системный администратор"


def main() -> None:
    with engine.begin() as conn:
        database = conn.scalar(text("SELECT current_database()"))
        if database != TEST_DATABASE:
            raise RuntimeError(f"Refusing to update non-acceptance database: {database}")

        user = conn.execute(text("""
            SELECT user_id, role_id FROM public.users
            WHERE login = :login FOR UPDATE
        """), {"login": LOGIN}).mappings().one()
        if int(user["role_id"]) not in (2, 4):
            raise RuntimeError("Unexpected hire_test_admin role; inspect before repairing")

        existing_role = conn.execute(text("""
            SELECT code FROM public.roles WHERE role_id = :role_id
        """), {"role_id": ROLE_ID}).mappings().first()
        if existing_role is None:
            conn.execute(text("""
                INSERT INTO public.roles (role_id, code, name, is_active)
                VALUES (:role_id, 'SYSADMIN', :name, TRUE)
            """), {"role_id": ROLE_ID, "name": DISPLAY_NAME})
        elif existing_role["code"] != "SYSADMIN":
            raise RuntimeError("Role 2 has an unexpected code; inspect before repairing")

        conn.execute(text("""
            UPDATE public.roles SET name = :name, is_active = TRUE
            WHERE role_id = :role_id AND code = 'SYSADMIN'
        """), {"role_id": ROLE_ID, "name": DISPLAY_NAME})
        conn.execute(text("""
            UPDATE public.users SET role_id = :role_id, full_name = :name
            WHERE user_id = :user_id AND login = :login
        """), {"role_id": ROLE_ID, "name": DISPLAY_NAME,
               "user_id": user["user_id"], "login": LOGIN})
        print(f"Repaired acceptance user {LOGIN} (user_id={user['user_id']})")


if __name__ == "__main__":
    main()
