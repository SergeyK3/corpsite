from copy import deepcopy
from datetime import date
import pytest
from sqlalchemy import text
from tests.test_category_template_native import fresh_database
from tests.category_template_fixture import seed_category_fixture
from app.services.personnel_order_category_contract import SAMPLE, category_values, prepare_category_payload, valid_until
from app.db.personnel_order_category_migration import upgrade


def test_migration_and_snapshot_update_only_touch_the_synthetic_order(fresh_database):
    seed_category_fixture(fresh_database)
    with fresh_database.begin() as conn:
        conn.execute(text('CREATE TABLE employees(employee_id bigint PRIMARY KEY,full_name text)'))
        conn.execute(text("INSERT INTO employees VALUES(900001,'TEST employee')"))
        conn.execute(text("CREATE TABLE personnel_orders(order_type_code text CONSTRAINT chk_personnel_orders_order_type_code CHECK(order_type_code IN ('HIRE','TRANSFER')))"))
        conn.execute(text("CREATE TABLE personnel_order_items(item_type_code text CONSTRAINT chk_personnel_order_items_item_type_code CHECK(item_type_code IN ('HIRE','TRANSFER')))"))
        conn.execute(text("INSERT INTO personnel_orders VALUES('HIRE')"))
        upgrade(conn);upgrade(conn)
        assert conn.execute(text('SELECT order_type_code FROM personnel_orders')).scalars().all()==['HIRE']
        conn.execute(text("INSERT INTO personnel_orders VALUES('QUALIFICATION_CATEGORY')"))
        conn.execute(text("INSERT INTO personnel_order_items VALUES('QUALIFICATION_CATEGORY')"))
        sample=deepcopy(SAMPLE)
        sample['medical_specialty']['name_ru']='FORGED'
        saved=prepare_category_payload(conn,sample,900001,date(2026,6,11))
        assert saved['medical_specialty']['name_ru']=='Терапия'
        assert saved['qualification_category']['valid_until']=='2031-06-10'
        conn.execute(text("UPDATE medical_specialties SET name='CHANGED',name_kk='CHANGED' WHERE medical_specialty_id=900003"))
        updated=prepare_category_payload(conn,{**saved,'qualification_category':{**saved['qualification_category'],'category':'first'}},900001,date(2026,6,11),saved)
        assert updated['medical_specialty']==saved['medical_specialty']
        assert category_values(updated)['qualification_category.level_ru']=='первой'
        assert conn.execute(text('SELECT full_name FROM employees')).scalar_one()=='TEST employee'
        with pytest.raises(ValueError,match='совпадать'):
            prepare_category_payload(conn,updated,900001,date(2026,6,12),saved)
        with pytest.raises(ValueError,match='highest'):
            prepare_category_payload(conn,{**saved,'qualification_category':{**saved['qualification_category'],'category':'none'}},900001,date(2026,6,11),saved)


@pytest.mark.parametrize('level,ru,kk',[('highest','высшей','жоғары'),('first','первой','бірінші'),('second','второй','екінші')])
def test_instrumental_russian_and_kazakh_category_level(level,ru,kk):
    sample=deepcopy(SAMPLE);sample['qualification_category']['category']=level
    values=category_values(sample)
    assert values['qualification_category.level_ru']==ru
    assert values['qualification_category.level_kk']==kk
    assert values['qualification_category.category_code_ru']=='7.2 (Р)'
    assert values['qualification_category.category_code_kk']=='7.2 (R)'


def test_exact_five_calendar_years_minus_one_day():
    assert valid_until('2026-06-11').isoformat()=='2031-06-10'
    assert valid_until('2024-02-29').isoformat()=='2029-02-27'
