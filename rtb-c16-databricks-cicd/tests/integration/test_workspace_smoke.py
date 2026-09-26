"""Post-deployment smoke tests.

These run against the real Databricks workspace after a bundle deployment and
are skipped automatically when no workspace credentials are present, so the
same suite stays green on a developer laptop.

Run with:  pytest -m integration tests/integration
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

REQUIRED_ENV = ("DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID")


@pytest.fixture(scope="module")
def client():
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
    if missing:
        pytest.skip(f"Skipping integration tests, missing env: {missing}")
    from databricks.sdk import WorkspaceClient

    return WorkspaceClient()


@pytest.fixture(scope="module")
def catalog() -> str:
    return os.environ.get("TARGET_CATALOG", "qa")


def _scalar(client, warehouse_id: str, statement: str):
    from databricks.sdk.service.sql import StatementState

    response = client.statement_execution.execute_statement(
        warehouse_id=warehouse_id, statement=statement, wait_timeout="50s"
    )
    assert response.status is not None
    assert response.status.state == StatementState.SUCCEEDED, response.status
    assert response.result is not None and response.result.data_array
    return response.result.data_array[0][0]


@pytest.fixture(scope="module")
def warehouse_id() -> str:
    return os.environ["DATABRICKS_WAREHOUSE_ID"]


def test_medallion_tables_exist(client, warehouse_id, catalog):
    for layer, table in (("bronze", "orders_raw"), ("silver", "orders_clean"), ("gold", "daily_country_sales")):
        count = int(_scalar(client, warehouse_id, f"SELECT COUNT(*) FROM {catalog}.{layer}.{table}"))
        assert count > 0, f"{catalog}.{layer}.{table} is empty after deployment"


def test_silver_has_no_duplicate_business_keys(client, warehouse_id, catalog):
    duplicates = int(
        _scalar(
            client,
            warehouse_id,
            f"SELECT COUNT(*) FROM (SELECT order_id FROM {catalog}.silver.orders_clean "
            "GROUP BY order_id HAVING COUNT(*) > 1)",
        )
    )
    assert duplicates == 0


def test_gold_revenue_is_non_negative(client, warehouse_id, catalog):
    minimum = float(
        _scalar(client, warehouse_id, f"SELECT MIN(gross_revenue) FROM {catalog}.gold.daily_country_sales")
    )
    assert minimum >= 0
