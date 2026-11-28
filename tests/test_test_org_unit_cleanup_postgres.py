"""Guarded unit cleanup against an isolated disposable PostgreSQL database."""
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.db.engine import engine
from app.services import test_org_unit_cleanup_service as cleanup


@pytest.fixture
def isolated_unit():
    name = f"Isolated unit cleanup {uuid4().hex[:10]}"
    with engine.begin() as conn:
        actor = conn.scalar(text("""INSERT INTO users(full_name,login,role_id,is_active)
            VALUES ('Isolated cleanup administrator',:login,2,true) RETURNING user_id"""),
            {'login': f'unit_cleanup_admin_{uuid4().hex[:10]}'})
        unit_id = conn.scalar(text("""INSERT INTO org_units(name,code,group_id,is_active)
            VALUES (:name,:code,(SELECT group_id FROM deps_group ORDER BY group_id LIMIT 1),true)
            RETURNING unit_id"""), {'name': name, 'code': f'UC_{uuid4().hex[:10]}'})
    return {'id': int(unit_id), 'name': name, 'actor': int(actor)}


def test_mark_preview_delete_and_audit(isolated_unit):
    uid = isolated_unit['id']
    preview = cleanup.preview_test_org_unit_cleanup(uid)
    assert not preview['is_test_marked'] and not preview['can_delete']
    with pytest.raises(ValueError, match='точное название'):
        cleanup.mark_test_org_unit(unit_id=uid, actor_user_id=isolated_unit['actor'],
                                   confirmed_name='Wrong', evidence='Independent disposable database fixture')
    cleanup.mark_test_org_unit(unit_id=uid, actor_user_id=isolated_unit['actor'],
                               confirmed_name=isolated_unit['name'], evidence='Independent disposable database fixture')
    preview = cleanup.preview_test_org_unit_cleanup(uid)
    assert preview['is_test_marked'] and preview['can_delete'], preview['blockers']
    with pytest.raises(ValueError, match='изменились'):
        cleanup.delete_test_org_unit(unit_id=uid, actor_user_id=isolated_unit['actor'], snapshot_hash='0' * 64)
    result = cleanup.delete_test_org_unit(unit_id=uid, actor_user_id=isolated_unit['actor'],
                                          snapshot_hash=preview['snapshot_hash'])
    assert result['audit_id'] and result['deleted_counts'] == {'org_units': 1}
    with engine.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM org_units WHERE unit_id=:id'), {'id': uid}) == 0
        assert conn.scalar(text('SELECT count(*) FROM test_org_unit_marks WHERE unit_id=:id'), {'id': uid}) == 1
        assert conn.scalar(text('SELECT count(*) FROM security_audit_log WHERE audit_id=:id'),
                           {'id': result['audit_id']}) == 1


def test_fk_dependency_blocks_cascade(isolated_unit):
    uid = isolated_unit['id']
    with engine.begin() as conn:
        child = conn.scalar(text('INSERT INTO org_units(name,code,parent_unit_id,group_id) VALUES (:name,:code,:parent,(SELECT group_id FROM deps_group ORDER BY group_id LIMIT 1)) RETURNING unit_id'),
                            {'name': f'Child {uuid4().hex[:8]}', 'code': f'UC_{uuid4().hex[:10]}', 'parent': uid})
    cleanup.mark_test_org_unit(unit_id=uid, actor_user_id=isolated_unit['actor'],
                               confirmed_name=isolated_unit['name'], evidence='Independent disposable database fixture')
    preview = cleanup.preview_test_org_unit_cleanup(uid)
    assert not preview['can_delete']
    assert preview['counts']['child_org_units'] == 1
    assert preview['counts']['fk:org_units.parent_unit_id'] == 1
    with pytest.raises(ValueError, match='заблокировано'):
        cleanup.delete_test_org_unit(unit_id=uid, actor_user_id=isolated_unit['actor'],
                                     snapshot_hash=preview['snapshot_hash'])
    with engine.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM org_units WHERE unit_id IN (:parent,:child)'),
                           {'parent': uid, 'child': child}) == 2


def test_audit_failure_rolls_back_delete(isolated_unit, monkeypatch):
    uid = isolated_unit['id']
    cleanup.mark_test_org_unit(unit_id=uid, actor_user_id=isolated_unit['actor'],
                               confirmed_name=isolated_unit['name'], evidence='Independent disposable database fixture')
    preview = cleanup.preview_test_org_unit_cleanup(uid)
    def fail_audit(**_kwargs):
        raise RuntimeError('audit failure')
    monkeypatch.setattr(cleanup, 'write_security_event', fail_audit)
    with pytest.raises(RuntimeError, match='audit failure'):
        cleanup.delete_test_org_unit(unit_id=uid, actor_user_id=isolated_unit['actor'],
                                     snapshot_hash=preview['snapshot_hash'])
    with engine.connect() as conn:
        assert conn.scalar(text('SELECT count(*) FROM org_units WHERE unit_id=:id'), {'id': uid}) == 1
