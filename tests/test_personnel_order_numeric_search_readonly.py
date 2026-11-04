"""Exercise real PostgreSQL filter predicates using VALUES, without writing rows."""
import json
import unittest
from sqlalchemy import text
from app.db.engine import engine
from app.services.personnel_orders_query_service import _build_list_filters


class NumericOrderSearchTests(unittest.TestCase):
    def filters(self,**overrides):
        values=dict(status=None,order_type_code=None,date_from=None,date_to=None,employee_id=None,org_unit_id=None,
            q='61',record_quality='WORKING',reconstruction_quality=None,include_closed=False)
        values.update(overrides)
        return _build_list_filters(**values)

    def test_numeric_predicate_matches_only_the_number_mask_and_filters_before_pagination(self):
        numbers=['61','61-ж','61 тест','61/2','561','1361','526-д','1152/2','[60/1 немесе 61]-ж','610',None]
        rows=[dict(order_id=61000+index,order_number=number,order_date='1961-01-01',source_title='SYNTHETIC TEXT 61',
            order_type_code='HIRE',status='DRAFT',storage_json={}) for index,number in enumerate(numbers)]
        source=""" FROM jsonb_to_recordset(CAST(:fixtures AS jsonb)) AS po(order_id integer,order_number text,order_date date,
            source_title text,order_type_code text,status text,storage_json jsonb,archived_at timestamptz,deleted_at timestamptz) WHERE """
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            for query in ('61',' 61 '):
                clauses,params=self.filters(q=query)
                params['fixtures']=json.dumps(rows)
                where=' AND '.join(clauses)
                self.assertNotIn('q_pattern',params)
                self.assertEqual(conn.execute(text('SELECT count(*)'+source+where),params).scalar_one(),8)
                selected=conn.execute(text('SELECT order_number'+source+where+' ORDER BY order_id LIMIT 2 OFFSET 2'),params).scalars().all()
                self.assertEqual(selected,['61 тест','61/2'])
            clauses,params=self.filters(status='SIGNED')
            self.assertEqual(conn.execute(text('SELECT count(*)'+source+' AND '.join(clauses)),{**params,'fixtures':json.dumps(rows)}).scalar_one(),0)
            clauses,params=self.filters(date_from='2020-01-01')
            self.assertEqual(conn.execute(text('SELECT count(*)'+source+' AND '.join(clauses)),{**params,'fixtures':json.dumps(rows)}).scalar_one(),0)

    def test_text_queries_keep_the_existing_fields(self):
        clauses,params=self.filters(q='2 тест')
        sql=' AND '.join(clauses)
        self.assertEqual(params['q_pattern'],'%2 тест%')
        self.assertIn('po.source_title',sql)
        self.assertIn('CAST(po.order_id AS text)',sql)
        self.assertIn('search_employee',sql)
        self.assertNotIn('q_order_number',params)
