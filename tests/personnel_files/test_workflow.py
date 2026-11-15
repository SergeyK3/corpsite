from datetime import date
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.personnel_files import service, storage
from app.personnel_files.access import access
from tests.personnel_files.test_policy_and_validation import image


def submit(actors, kind='certificate', **kwargs):
    if kind=='certificate':
        kwargs.setdefault('certificate', {'entry_id':1,'specialty_name_at_issue':'Вымышленная А как выдано','issued_at':date(2024,1,1),'valid_until':date(2031,1,1)})
    return service.submit(actors[1],1,kind=kind,title='Вымышленный документ',content=image('PNG') if kind!='photo' else image(),
        mime='image/png' if kind!='photo' else 'image/jpeg', filename='fictional.png',**kwargs)


def decide(actors, row, action='approve', reason=''):
    comparison = service.review_context(actors[3],str(row['version_id'])) if row['kind']=='certificate' and action=='approve' and row['state']=='pending' else None
    return service.decide(actors[3],str(row['version_id']),expected_revision=row['revision'],action=action,reason=reason,expected_certificate_context=comparison['context_token'] if comparison else None)


def test_pending_is_private_approval_publishes_and_exports_by_policy(seeded):
    actors=seeded; row=submit(actors)
    assert row['state']=='pending'
    assert service.listing(actors[4],1)['items']==[]
    for actor in (4,5,8):
        with pytest.raises(HTTPException) as exc: service.content(actors[actor],row['version_id'],operation='view')
        assert exc.value.status_code==403
    for actor in (1,3,6,7):
        assert service.content(actors[actor],row['version_id'],operation='view')[1]=='image/png'
    with pytest.raises(HTTPException): service.content(actors[1],row['version_id'],operation='download')
    row=decide(actors,row)
    for actor in range(1,9):
        if actor==2: continue
        assert service.content(actors[actor],row['version_id'],operation='view')[0].startswith(b'\x89PNG')
    for actor in (1,3):
        assert service.content(actors[actor],row['version_id'],operation='download')[0]
        assert service.content(actors[actor],row['version_id'],operation='print')[0]
    for actor in (2,4,5,6,7,8):
        with pytest.raises(HTTPException): service.content(actors[actor],row['version_id'],operation='download')
    assert all('storage_key' not in r for r in service.listing(actors[1],1)['items'])


def test_replacement_keeps_approved_until_decision_and_return_requires_reason(seeded):
    actors=seeded; old=decide(actors,submit(actors))
    new=submit(actors,set_id=old['set_id'],expected_revision=old['revision'],expected_version_id=old['version_id'])
    assert [r['version_id'] for r in service.listing(actors[4],1)['items']]==[old['version_id']]
    with pytest.raises(HTTPException): decide(actors,new,'return',' ')
    returned=decide(actors,new,'return','Не виден номер документа')
    assert returned['reason']=='Не виден номер документа'
    fresh=submit(actors,set_id=returned['set_id'],expected_revision=returned['revision'],expected_version_id=returned['version_id'])
    approved=decide(actors,fresh)
    assert [r['version_id'] for r in service.listing(actors[4],1)['items']]==[approved['version_id']]
    assert any(r['state']=='superseded' for r in service.listing(actors[1],1)['items'])
    with pytest.raises(HTTPException): decide(actors,fresh)


def test_direct_supervision_and_scoped_grants_are_revoked_on_next_request(seeded,database):
    actors=seeded; row=decide(actors,submit(actors))
    with database.begin() as conn:
        conn.execute(text('UPDATE user_supervisors SET is_active=false'))
        conn.execute(text('UPDATE access_grants SET active_flag=false WHERE target_id=5'))
    for actor in (4,5):
        with pytest.raises(HTTPException): service.content(actors[actor],row['version_id'],operation='view')
    with database.begin() as conn:
        assert not access(conn,actors[3],2).reviewer
    with pytest.raises(HTTPException): service.listing(actors[2],1)


def test_technical_users_cannot_approve_or_upload(seeded):
    actors=seeded; row=submit(actors)
    for actor in (6,7):
        with pytest.raises(HTTPException): service.decide(actors[actor],row['version_id'],expected_revision=1,action='approve',reason='')
        with pytest.raises(HTTPException): service.submit(actors[actor],1,kind='certificate',title='Test',content=image(),mime='image/jpeg',filename='test.jpg')


def test_only_one_concurrent_decision_commits(seeded):
    actors=seeded; row=submit(actors)
    def attempt():
        try: return decide(actors,row)['state']
        except HTTPException as exc: return exc.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _: attempt(),range(2)))
    assert sorted(map(str,results))==['409','approved']


def test_bad_storage_and_checksum_never_leak_original(seeded,database):
    actors=seeded; row=decide(actors,submit(actors))
    with database.connect() as conn: r=service.row(conn,row['version_id'])
    storage.path(r['storage_key'],'original').write_bytes(b'altered synthetic test')
    with pytest.raises(HTTPException) as exc: service.content(actors[1],row['version_id'],operation='download')
    assert exc.value.status_code==404


def test_failed_database_transaction_discards_prepared_file(seeded,monkeypatch,tmp_path):
    actors=seeded
    def fail(*args,**kwargs): raise RuntimeError('Synthetic audit failure')
    monkeypatch.setattr(service,'event',fail)
    with pytest.raises(RuntimeError): submit(actors)
    assert not list((tmp_path/'files').glob('*/original'))


def test_name_change_is_separate_and_requires_approved_identity(seeded,database):
    actors=seeded
    proposal={'last_name':'Тестовая','first_name':'Личность','middle_name':''}
    row=decide(actors,submit(actors,kind='name_change',proposed_name=proposal))
    with database.connect() as conn: assert conn.execute(text('SELECT full_name FROM persons WHERE person_id=1')).scalar_one()=='Вымышленный Работник'
    args=dict(expected_revision=row['revision'],expected_full_name='Вымышленный Работник',effective_date=date.today(),reason='Проверено вымышленное основание')
    with pytest.raises(HTTPException): service.apply_name(actors[3],row['version_id'],**args)
    decide(actors,submit(actors,kind='identity'))
    updated=service.apply_name(actors[3],row['version_id'],**args)
    assert updated['name_applied_at'] is not None
    with database.connect() as conn:
        assert conn.execute(text('SELECT full_name FROM persons WHERE person_id=1')).scalar_one()=='Тестовая Личность'
    with pytest.raises(HTTPException): service.apply_name(actors[3],row['version_id'],**args)


def test_audit_is_append_only_and_denials_are_recorded(seeded,database):
    actors=seeded; row=submit(actors)
    with pytest.raises(HTTPException): service.content(actors[2],row['version_id'],operation='view')
    actions={e['action'] for e in service.history(actors[1],1)}
    assert {'submitted','access_denied'}<=actions
    with pytest.raises(Exception),database.begin() as conn:
        conn.execute(text('DELETE FROM personnel_file_events'))


def test_http_preview_requires_auth_and_download_cannot_bypass_policy(seeded):
    from app.auth import get_current_user
    from app.personnel_files.router import router
    actors=seeded; row=decide(actors,submit(actors))
    app=FastAPI(); app.include_router(router)
    client=TestClient(app)
    path=f'/api/personnel-files/versions/{row["version_id"]}'
    assert client.get(path+'/preview').status_code==401
    app.dependency_overrides[get_current_user]=lambda: actors[4]
    response=client.get(path+'/preview')
    assert response.status_code==200
    assert response.headers['cache-control']=='private, no-store'
    assert response.headers['content-type']=='image/png'
    assert client.get(path+'/download').status_code==403
    assert client.get(path+'/print').status_code==403
    app.dependency_overrides[get_current_user]=lambda: actors[1]
    assert client.get(path+'/download').headers['content-disposition'].startswith('attachment;')


def test_revoked_managed_photo_does_not_fall_back_to_legacy(seeded):
    actors=seeded; photo=decide(actors,submit(actors,kind='photo'))
    assert service.active_photo(actors[1],1)[0]
    decide(actors,photo,'revoke','Неверная фотография')
    assert service.active_photo(actors[1],1)==(True,None)


def test_owner_receives_persistent_decision_notifications(seeded):
    actors=seeded; row=submit(actors)
    assert service.listing(actors[1],1)['notifications']==[]
    decide(actors,row,'return','Прикрепите оборотную сторону')
    result=service.listing(actors[1],1)
    assert result['notifications'][0]['action']=='return'
    assert 'оборотную' in result['notifications'][0]['detail']['reason']
    service.acknowledge(actors[1],1,result['notifications'][0]['event_id'])
    assert service.listing(actors[1],1)['notifications']==[]
    with pytest.raises(HTTPException): service.acknowledge(actors[2],1,result['notifications'][0]['event_id'])


def test_queue_filters_scope_and_denied_unrelated_grant_resources(seeded,database):
    actors=seeded; row=submit(actors)
    assert len(service.review_queue(actors[3],None)['items'])==1
    assert service.review_queue(actors[2],None)['items']==[]
    with database.begin() as conn:
        conn.execute(text("UPDATE access_grants SET resource_key='unrelated' WHERE target_id=3"))
    assert service.review_queue(actors[3],None)['items']==[]
    with pytest.raises(HTTPException): decide(actors,row)


def test_corrupt_preview_is_not_returned_and_rejected_upload_is_cleaned(seeded,database,monkeypatch,tmp_path):
    actors=seeded; row=submit(actors)
    with database.connect() as conn: r=service.row(conn,row['version_id'])
    storage.path(r['storage_key'],'page-1.png').write_bytes(b'corrupt preview')
    with pytest.raises(HTTPException): service.content(actors[1],row['version_id'],operation='view')
    existing=len(list((tmp_path/'files').glob('*/original')))
    def reject(_): raise HTTPException(422,'Synthetic scanner rejection')
    monkeypatch.setattr(storage,'scan',reject)
    with pytest.raises(HTTPException): submit(actors)
    assert len(list((tmp_path/'files').glob('*/original')))==existing
    assert 'technical_rejected' in {r['action'] for r in service.history(actors[1],1)}


def test_replacement_checks_exact_version_not_only_reused_revision_number(seeded):
    actors=seeded; old=decide(actors,submit(actors))
    pending=submit(actors,set_id=old['set_id'],expected_revision=old['revision'],expected_version_id=old['version_id'])
    new=decide(actors,pending)
    assert old['revision']==new['revision']
    with pytest.raises(HTTPException) as exc:
        submit(actors,set_id=old['set_id'],expected_revision=old['revision'],expected_version_id=old['version_id'])
    assert exc.value.status_code==409


def test_http_upload_goes_to_review_not_direct_publication(seeded):
    from app.auth import get_current_user
    from app.personnel_files.router import router
    from app.personnel_files.upload_limit import PersonnelFileUploadLimit
    actors=seeded
    app=FastAPI(); app.add_middleware(PersonnelFileUploadLimit); app.include_router(router)
    app.dependency_overrides[get_current_user]=lambda: actors[1]
    client=TestClient(app)
    response=client.post('/api/personnel-files/persons/1',data={'kind':'certificate','title':'Вымышленный сертификат'},
        files={'file':('fictional.png',image('PNG'),'image/png')})
    assert response.status_code==422
    import json
    response=client.post('/api/personnel-files/persons/1',data={'kind':'certificate','title':'Вымышленный сертификат',
        'certificate':json.dumps({'entry_id':1,'specialty_name_at_issue':'Вымышленная А','issued_at':'2024-01-01','valid_until':'2031-01-01'})},
        files={'file':('fictional.png',image('PNG'),'image/png')})
    assert response.status_code==201
    assert response.json()['state']=='pending'
    assert not response.json()['can_export']
    assert service.listing(actors[4],1)['items']==[]


def test_photo_pdf_export_is_limited_to_hr_even_for_technical_readers(seeded):
    actors=seeded
    for actor in (1,4,5,6,7,8):
        with pytest.raises(HTTPException): service.authorize_photo_export(actors[actor],1)
    service.authorize_photo_export(actors[3],1)
