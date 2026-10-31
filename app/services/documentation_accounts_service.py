"""Create an independent documentation account, atomically with security audit."""
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.auth import hash_password
from app.db.engine import engine
from app.services.admin_users_service import _fetch_user, _serialize_user
from app.services.security_audit_service import write_security_event


def create_documentation_account(*, full_name: str, login: str, temporary_password: str,
                                 actor_user_id: int, profile_code: str = "DOCUMENTATION_VIEWER") -> dict:
    from app.security.sysadmin_assistant import PERMISSIONS
    if profile_code not in {"DOCUMENTATION_VIEWER", "SYSADMIN_ASSISTANT"}:
        raise ValueError("Unsupported standalone profile.")
    permissions = ["DOCUMENTATION_READ"] + (sorted(PERMISSIONS) if profile_code == "SYSADMIN_ASSISTANT" else [])
    name = " ".join(full_name.split())
    login = login.strip().lower()
    if not name or not login or any(c.isspace() for c in login):
        raise ValueError("Name and a login without whitespace are required.")
    if not 8 <= len(temporary_password) <= 200 or not temporary_password.strip():
        raise ValueError("Temporary password must contain 8 to 200 characters.")
    password_hash = hash_password(temporary_password)
    try:
        with engine.begin() as conn:
            # Acquire before row locks to avoid a lock upgrade deadlock with
            # concurrent login-policy updates or another account provisioner.
            conn.execute(text("LOCK TABLE public.users IN SHARE ROW EXCLUSIVE MODE"))
            # Recheck the actor in the transaction; no grant or env allowlist
            # substitutes for the system-administrator primary role.
            actor = conn.execute(text("""SELECT role_id FROM public.users
                WHERE user_id=:id AND is_active=TRUE AND locked_at IS NULL FOR SHARE"""),
                {"id": actor_user_id}).scalar_one_or_none()
            if actor != 2:
                raise PermissionError("System administrator required.")
            role_id = conn.execute(text("""SELECT role_id FROM public.roles
                WHERE code=:profile AND is_active=TRUE"""), {"profile": profile_code}).scalar_one_or_none()
            if role_id is None:
                raise ValueError(f"{profile_code} migration is required.")
            permission_ids = []
            for code in permissions:
                permission_id = conn.execute(text("""SELECT access_role_id FROM public.access_roles
                    WHERE code=:code AND is_active=TRUE AND access_level=:level AND level_rank=:rank"""),
                    {"code": code, "level": "OBSERVER" if code == "DOCUMENTATION_READ" else "MANAGER",
                     "rank": 10 if code == "DOCUMENTATION_READ" else 20}).scalar_one_or_none()
                if permission_id is None:
                    raise ValueError(f"Permission migration required: {code}")
                permission_ids.append(permission_id)
            if conn.execute(text("""SELECT 1 FROM public.access_grants g
                JOIN public.access_roles a ON a.access_role_id=g.access_role_id
                WHERE g.target_type='ROLE' AND g.target_id=:role AND g.active_flag=TRUE
                  AND g.revoked_at IS NULL AND NOT (a.code=ANY(:allowed)) LIMIT 1"""),
                {"role": role_id, "allowed": permissions}).first():
                raise ValueError("Standalone profile must not inherit other permissions.")
            if conn.execute(text("""SELECT 1 FROM public.users
                WHERE lower(login)=:login OR lower(google_login)=:login"""), {"login": login}).first():
                raise ValueError("Login already exists.")
            uid = conn.execute(text("""INSERT INTO public.users
                (full_name, login, google_login, password_hash, role_id, unit_id,
                 employee_id, is_active, must_change_password, token_version)
                VALUES (:name,:login,NULL,:hash,:role,NULL,NULL,TRUE,TRUE,1)
                RETURNING user_id"""),
                {"name": name, "login": login, "hash": password_hash, "role": role_id}).scalar_one()
            for permission_id in permission_ids:
                conn.execute(text("""INSERT INTO public.access_grants
                    (access_role_id,target_type,target_id,resource_key,scope_type,
                     include_subtree,starts_at,active_flag,granted_by_user_id,reason)
                    VALUES (:permission,'USER',:uid,'*','GLOBAL',FALSE,now(),TRUE,:actor,
                        'documentation_account_created')"""),
                    {"permission": permission_id, "uid": uid, "actor": actor_user_id})
            write_security_event(event_type="ACCESS_CHANGED", actor_user_id=actor_user_id,
                target_user_id=int(uid), metadata={"action": "documentation_account_created",
                "role_code": profile_code, "access_role_codes": permissions,
                "login": login}, conn=conn)
            return _serialize_user(_fetch_user(conn, int(uid)))
    except IntegrityError as exc:
        raise ValueError("Login conflicts with an existing account.") from exc
