"""Explicitly marked, dependency-free org-unit deletion for SYSADMIN."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db.engine import engine
from app.services.org_units_admin_service import check_org_unit_dependencies, _delete_org_unit_in_conn
from app.services.security_audit_service import write_security_event


def _unit(conn: Connection, unit_id: int, *, lock: bool = False) -> dict[str, Any]:
    row = conn.execute(text("""SELECT unit_id,name,code,group_id,parent_unit_id,is_active
        FROM public.org_units WHERE unit_id=:id""" + (" FOR UPDATE" if lock else "")),
        {"id": unit_id}).mappings().one_or_none()
    if row is None:
        raise LookupError("Подразделение не найдено")
    return dict(row)


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _foreign_key_dependencies(conn: Connection, unit_id: int) -> dict[str, int]:
    """Count every direct FK, including CASCADE and SET NULL references."""
    references = conn.execute(text("""SELECT n.nspname AS schema_name,c.relname AS table_name,
        a.attname AS column_name FROM pg_constraint fk
        JOIN pg_class p ON p.oid=fk.confrelid JOIN pg_class c ON c.oid=fk.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=fk.conkey[1]
        WHERE fk.contype='f' AND p.oid='public.org_units'::regclass
          AND cardinality(fk.conkey)=1 AND n.nspname='public'
        ORDER BY c.relname,a.attname""")).mappings()
    counts: dict[str, int] = {}
    for ref in references:
        table_name = str(ref['table_name']).replace('"', '""')
        column_name = str(ref['column_name']).replace('"', '""')
        count = conn.scalar(text(f'SELECT count(*) FROM public."{table_name}" WHERE "{column_name}"=:id'),
                            {'id': unit_id})
        if count:
            counts[f"{ref['table_name']}.{ref['column_name']}"] = int(count)
    return counts


def _marker(conn: Connection, unit_id: int) -> dict[str, Any] | None:
    row = conn.execute(text("""SELECT marker_id,unit_id,unit_name,unit_snapshot_hash,evidence,
        marked_by_user_id,marked_at FROM public.test_org_unit_marks WHERE unit_id=:id"""),
        {'id': unit_id}).mappings().one_or_none()
    return dict(row) if row else None


def _preview(conn: Connection, unit_id: int, *, lock: bool = False) -> dict[str, Any]:
    unit = _unit(conn, unit_id, lock=lock)
    marker = _marker(conn, unit_id)
    unit_digest = _digest(unit)
    # The existing administrator inventory catches logical references stored
    # without FKs; the catalogue scan catches every physical FK on this schema.
    logical = check_org_unit_dependencies(unit_id).dependencies
    references = _foreign_key_dependencies(conn, unit_id)
    counts = {key: int(value) for key, value in logical.items() if value}
    counts.update({f"fk:{key}": value for key, value in references.items()})
    blockers = []
    if marker is None:
        blockers.append("Тестовое происхождение подразделения не подтверждено")
    elif marker['unit_snapshot_hash'] != unit_digest or marker['unit_name'] != unit['name']:
        blockers.append("Подразделение изменилось после подтверждения тестового происхождения")
    blockers.extend(f"{key}: {value}" for key, value in counts.items() if value)
    snapshot_hash = _digest({'unit': unit, 'marker_id': marker['marker_id'] if marker else None,
                             'counts': counts})
    return {'unit_id': unit_id, 'name': unit['name'], 'unit': unit,
            'is_test_marked': marker is not None, 'marker_id': marker['marker_id'] if marker else None,
            'counts': counts, 'blockers': blockers, 'can_delete': not blockers,
            'snapshot_hash': snapshot_hash}


def preview_test_org_unit_cleanup(unit_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        return _preview(conn, unit_id)


def mark_test_org_unit(*, unit_id: int, actor_user_id: int,
                       confirmed_name: str, evidence: str) -> dict[str, Any]:
    if len(evidence.strip()) < 20:
        raise ValueError("Укажите независимое основание тестового происхождения (не менее 20 символов)")
    with engine.begin() as conn:
        unit = _unit(conn, unit_id, lock=True)
        if confirmed_name != unit['name']:
            raise ValueError("Введите точное название подразделения")
        if _marker(conn, unit_id):
            raise ValueError("Тестовое происхождение уже подтверждено")
        marker_id = conn.scalar(text("""INSERT INTO public.test_org_unit_marks
            (unit_id,unit_name,unit_snapshot_hash,evidence,marked_by_user_id)
            VALUES (:id,:name,:digest,:evidence,:actor) RETURNING marker_id"""),
            {'id': unit_id, 'name': unit['name'], 'digest': _digest(unit),
             'evidence': evidence.strip(), 'actor': actor_user_id})
        audit_id = write_security_event(event_type='ACCESS_CHANGED', actor_user_id=actor_user_id,
                             metadata={'action': 'test_org_unit_marked', 'org_unit_id': unit_id,
                                       'marker_id': marker_id, 'unit_name': unit['name']}, conn=conn)
        if audit_id is None:
            raise RuntimeError('Журнал аудита недоступен')
    return {'unit_id': unit_id, 'marker_id': marker_id}


def delete_test_org_unit(*, unit_id: int, actor_user_id: int,
                         snapshot_hash: str) -> dict[str, Any]:
    with engine.begin() as conn:
        preview = _preview(conn, unit_id, lock=True)
        if preview['snapshot_hash'] != snapshot_hash:
            raise ValueError("Зависимости изменились. Обновите предварительный просмотр")
        if not preview['can_delete']:
            raise ValueError("Удаление заблокировано: " + "; ".join(preview['blockers']))
        _delete_org_unit_in_conn(conn, unit_id=unit_id)
        audit_id = write_security_event(event_type='ORG_UNIT_DELETED', actor_user_id=actor_user_id,
            metadata={'action': 'test_org_unit_deleted', 'org_unit_id': unit_id,
                      'marker_id': preview['marker_id'], 'before': preview['unit'],
                      'deleted_counts': {'org_units': 1}}, conn=conn)
        if audit_id is None:
            raise RuntimeError('Журнал аудита недоступен')
    return {'ok': True, 'unit_id': unit_id, 'deleted_counts': {'org_units': 1}, 'audit_id': audit_id}
