from app.data_exchange.category_scenario import CATEGORY_SCENARIO_CODE
from app.data_exchange.order_scenario import ORDER_SCENARIO_CODE, ORDER_SCHEMA_VERSION
from app.data_exchange.vacation_scenario import VACATION_SCENARIO_CODE
from app.data_exchange.registry import catalog, get_scenario, scenarios


def test_only_explicitly_registered_scenario_is_uploadable() -> None:
    scenario = get_scenario(ORDER_SCENARIO_CODE)
    assert scenario is not None
    assert scenario.schema_version == ORDER_SCHEMA_VERSION
    assert get_scenario("employees; DROP TABLE employees") is None
    assert set(scenarios()) == {ORDER_SCENARIO_CODE, CATEGORY_SCENARIO_CODE, VACATION_SCENARIO_CODE}


def test_catalog_registers_categories_through_an_explicit_adapter() -> None:
    categories = next(item for item in catalog() if item["code"] == CATEGORY_SCENARIO_CODE)
    assert categories["available"] is True
    assert get_scenario(CATEGORY_SCENARIO_CODE) is not None
