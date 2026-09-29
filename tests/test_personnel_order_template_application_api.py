from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.directory import personnel_orders_routes as routes
from app.auth import get_current_user
from app.directory.rbac import require_personnel_admin_or_403
from app.services.personnel_order_template_application_service import TemplateApplicationError

PATH='/directory/personnel-orders/17/template-application'
PREVIEW=PATH+'/preview'
def _user(): return {'user_id':42}


def _editorial_block(*, block_id: int, scope: str, order_item_id: int | None, block_type: str):
    """A complete real EditorialStateResponse block, not a response shortcut."""
    return {
        'block_id': block_id,
        'scope': scope,
        'order_item_id': order_item_id,
        'locale': 'ru',
        'block_type': block_type,
        'generated_text': 'generated',
        'override_text': None,
        'effective_text': 'generated',
        'generator_key': 'template',
        'generator_version': '1',
        'source_fingerprint': 'fp',
        'review_status': 'CURRENT',
        'basis_required': None,
        'editable': True,
        'revision': 2,
        'generated_at': None,
        'edited_at': None,
        'edited_by_user_id': None,
    }


def _editorial_state_response():
    order_block = _editorial_block(
        block_id=101, scope='ORDER', order_item_id=None, block_type='TITLE'
    )
    item_block = _editorial_block(
        block_id=201, scope='ITEM', order_item_id=33, block_type='BODY'
    )
    return {
        'order_id': 17,
        'order_status': 'DRAFT',
        'editable': True,
        'order_blocks': [order_block],
        'items': [{
            'order_item_id': 33,
            'item_number': 1,
            'item_type_code': 'TERMINATION',
            'basis_required': True,
            'blocks': [item_block],
        }],
    }


def test_preview_and_apply_http_contract(monkeypatch):
    app.dependency_overrides[get_current_user]=_user
    monkeypatch.setattr(routes,'require_personnel_admin_or_403',lambda u:None)
    monkeypatch.setattr(routes,'preview_template_application',lambda **_: {'available':True,'template':{'template_version_id':1,'version_number':2,'item_type_code':'TERMINATION'},'has_overrides':False,'override_blocks':[],'has_prior_application':False,'last_application':None,'current':{},'proposed':{},'order_revision':1})
    monkeypatch.setattr(routes,'apply_template_application',lambda *a,**k: _editorial_state_response())
    try:
        c=TestClient(app); assert c.get(PREVIEW).status_code==200; assert c.post(PATH,json={'expected_document_revision':1}).status_code==200
    finally: app.dependency_overrides.clear()
def test_application_conflict_and_validation_are_not_500(monkeypatch):
    app.dependency_overrides[get_current_user]=_user; monkeypatch.setattr(routes,'require_personnel_admin_or_403',lambda u:None)
    monkeypatch.setattr(routes,'apply_template_application',lambda *a,**k: (_ for _ in ()).throw(TemplateApplicationError('conflict',True)))
    try: assert TestClient(app).post(PATH,json={'expected_document_revision':1}).status_code==409
    finally: app.dependency_overrides.clear()
def test_application_rbac_does_not_call_service(monkeypatch):
    called=[]; app.dependency_overrides[get_current_user]=_user; monkeypatch.setattr(routes,'require_personnel_admin_or_403',lambda u: (_ for _ in ()).throw(HTTPException(403,'forbidden'))); monkeypatch.setattr(routes,'preview_template_application',lambda *_:called.append(1))
    try: assert TestClient(app).get(PREVIEW).status_code==403 and not called
    finally: app.dependency_overrides.clear()
