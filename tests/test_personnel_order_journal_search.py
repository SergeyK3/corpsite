"""Global journal search applies before pagination and preserves name/ID search."""
from contextlib import nullcontext
from uuid import uuid4
from sqlalchemy import text
from app.db.engine import engine
from app.services import personnel_orders_query_service as journal


def test_search_finds_an_older_order_beyond_the_page_by_number_name_title_and_id(seed,monkeypatch):
    token='SEARCH-'+uuid4().hex;actor=int(seed['initiator_user_id'])
    with engine.connect() as conn:
        transaction=conn.begin()
        class TransactionEngine:
            def connect(self):return nullcontext(conn)
            def begin(self):return nullcontext(conn)
        monkeypatch.setattr(journal,'engine',TransactionEngine())
        insert=text("INSERT INTO personnel_orders(order_number,order_date,order_type_code,status,source_mode,created_by,source_title) VALUES(:number,:day,'HIRE','DRAFT','PAPER',:actor,:title) RETURNING order_id")
        try:
            employee=conn.execute(text('SELECT employee_id FROM employees ORDER BY employee_id LIMIT 1')).scalar_one()
            target=conn.execute(insert,{'number':token+'-NUMBER','day':'2000-01-01','actor':actor,'title':token+'-TITLE'}).scalar_one()
            conn.execute(text("INSERT INTO personnel_order_items(order_id,item_number,item_type_code,employee_id,payload) VALUES(:id,1,'HIRE',:employee,jsonb_build_object('source_employee_name',CAST(:name AS text)))"),{'id':target,'employee':employee,'name':token+'-NAME'})
            for suffix in ('A','B'):
                conn.execute(insert,{'number':token+'-'+suffix,'day':'2099-01-01','actor':actor,'title':'Newer record'})
            assert target not in {row['order_id'] for row in journal.list_personnel_orders(limit=2)['items']}
            for query in (token+'-NUMBER',token+'-TITLE',token+'-NAME',str(target)):
                result=journal.list_personnel_orders(q=query,limit=2)
                assert target in {row['order_id'] for row in result['items']},query
            result=journal.list_personnel_orders(q=token+'-NAME',employee_id=employee,limit=2)
            assert result['total']==1 and result['items'][0]['order_id']==target
        finally:transaction.rollback()
