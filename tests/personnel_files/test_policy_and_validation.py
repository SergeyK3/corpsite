import io
from unittest.mock import patch

import pytest
from PIL import Image
import pymupdf
from fastapi import HTTPException
from app.personnel_files.policy import Access, transition
from app.personnel_files import storage


def image(kind='JPEG', size=(600,800)):
    out=io.BytesIO(); Image.new('RGB',size,(20,90,130)).save(out,format=kind); return out.getvalue()


def pdf(pages=2):
    with pymupdf.open() as doc:
        for _ in range(pages):
            doc.new_page().insert_text((30,30),'FICTIONAL TEST DOCUMENT')
        return doc.tobytes()


@pytest.mark.parametrize('actor', [Access(leader=True),Access(technical=True)])
def test_view_only_roles_cannot_export(actor):
    assert actor.visible('approved')
    assert not actor.export('certificate','approved')
    assert actor.visible('pending') == actor.technical


def test_owner_export_restricted_to_approved_certificates_and_diplomas():
    actor=Access(owner=True)
    assert actor.export('certificate','approved')
    assert actor.export('diploma','approved')
    assert not actor.export('certificate','pending')
    for kind in ('identity','photo','name_change'):
        assert not actor.export(kind,'approved')


def test_transition_requires_reason_and_rejects_reapproving_archived():
    assert transition('pending','approve','')=='approved'
    with pytest.raises(ValueError): transition('pending','return',' ')
    with pytest.raises(ValueError): transition('archived','approve','')


def test_real_decoding_rejects_spoofed_images_and_wrong_photo_dimensions():
    with pytest.raises(Exception): storage.render(b'not an image','image/png','certificate')
    with pytest.raises(Exception): storage.render(image(size=(60,80)),'image/jpeg','photo')
    with pytest.raises(ValueError): storage.render(image('PNG'),'image/jpeg','certificate')
    assert len(storage.render(image(),'image/jpeg','photo'))==1


def test_pdf_page_limit_and_encryption():
    assert len(storage.render(pdf(2),'application/pdf','certificate'))==2
    with pytest.raises(ValueError): storage.render(pdf(21),'application/pdf','certificate')
    with pymupdf.open(stream=pdf(),filetype='pdf') as doc:
        protected=doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256,user_pw='test')
    with pytest.raises(ValueError): storage.render(protected,'application/pdf','certificate')


def test_pdf_javascript_is_rejected_even_in_compressed_objects():
    with pymupdf.open(stream=pdf(),filetype='pdf') as doc:
        doc.xref_set_key(doc.pdf_catalog(),'OpenAction','<</S/JavaScript/JS(app.alert(1))>>')
        dangerous=doc.tobytes(deflate=True)
    with pytest.raises(ValueError): storage.render(dangerous,'application/pdf','certificate')


def test_missing_scanner_fails_closed(tmp_path):
    with patch('shutil.which',return_value=None), pytest.raises(HTTPException) as exc:
        storage.scan(tmp_path/'fictional.pdf')
    assert exc.value.status_code==503


def test_path_traversal_is_rejected(monkeypatch,tmp_path):
    monkeypatch.setenv('PERSONNEL_FILE_STORAGE_ROOT',str(tmp_path))
    with pytest.raises(ValueError): storage.path('../../outside','original')


def test_upload_limit_counts_chunked_body_without_content_length():
    import asyncio
    from app.personnel_files.upload_limit import PersonnelFileUploadLimit
    entered=[]; responses=[]
    async def app(*_): entered.append(True)
    chunks=iter([{'type':'http.request','body':b'x'*(6*1024*1024),'more_body':True},
                 {'type':'http.request','body':b'x'*(6*1024*1024),'more_body':False}])
    async def receive(): return next(chunks)
    async def send(message): responses.append(message)
    asyncio.run(PersonnelFileUploadLimit(app)({'type':'http','method':'POST','path':'/api/personnel-files/me'},receive,send))
    assert not entered
    assert responses[0]['status']==413
