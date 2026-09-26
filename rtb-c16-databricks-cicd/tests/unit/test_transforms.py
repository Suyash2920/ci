from __future__ import annotations

from datetime import date, datetime

import pytest
from pyspark.sql import functions as F

from retail_etl.transforms import (
    BRONZE_AUDIT_COLUMNS,
    add_bronze_audit_columns,
    build_daily_country_sales,
    clean_orders,
    deduplicate_latest,
)


def test_bronze_audit_columns_are_added(raw_orders):
    result = add_bronze_audit_columns(raw_orders, batch_id="B-001")
    assert set(BRONZE_AUDIT_COLUMNS).issubset(set(result.columns))
    assert result.select("_batch_id").distinct().collect()[0][0] == "B-001"
    assert result.count() == raw_orders.count()


def test_clean_orders_rejects_invalid_rows(raw_orders):
    result = clean_orders(raw_orders)
    assert sorted(r.order_id for r in result.collect()) == ["ORD-1", "ORD-2"]


def test_clean_orders_keeps_latest_duplicate(raw_orders):
    row = clean_orders(raw_orders).filter(F.col("order_id") == "ORD-1").collect()[0]
    assert row.product_id == "SKU-9"
    assert row.quantity == 5


def test_clean_orders_normalises_country(raw_orders):
    countries = {r.country for r in clean_orders(raw_orders).collect()}
    assert countries == {"IN", "US"}


def test_clean_orders_computes_gross_amount_and_date(raw_orders):
    row = clean_orders(raw_orders).filter(F.col("order_id") == "ORD-2").collect()[0]
    assert row.gross_amount == pytest.approx(25.5)
    assert row.order_date == date(2026, 1, 1)


def test_clean_orders_is_idempotent(raw_orders):
    once = clean_orders(raw_orders)
    twice = clean_orders(raw_orders)
    assert once.exceptAll(twice).count() == 0
    assert once.count() == twice.count()


def test_clean_orders_on_empty_input(spark, raw_orders):
    empty = raw_orders.limit(0)
    assert clean_orders(empty).count() == 0


def test_deduplicate_latest_requires_keys(raw_orders):
    with pytest.raises(ValueError, match="deduplication key"):
        deduplicate_latest(raw_orders, keys=[], order_by="order_ts")


def test_build_daily_country_sales(spark):
    rows = [
        ("ORD-1", "CUST-1", "IN", date(2026, 1, 1), 100.0),
        ("ORD-2", "CUST-2", "IN", date(2026, 1, 1), 50.0),
        ("ORD-3", "CUST-1", "US", date(2026, 1, 1), 20.0),
        ("ORD-4", "CUST-3", "IN", date(2026, 1, 2), 10.0),
    ]
    df = spark.createDataFrame(
        rows, "order_id string, customer_id string, country string, order_date date, gross_amount double"
    )

    result = {(r.order_date, r.country): r for r in build_daily_country_sales(df).collect()}

    india_d1 = result[(date(2026, 1, 1), "IN")]
    assert india_d1.order_count == 2
    assert india_d1.customer_count == 2
    assert india_d1.gross_revenue == pytest.approx(150.0)
    assert india_d1.avg_order_value == pytest.approx(75.0)
    assert len(result) == 3


def test_pipeline_end_to_end_shape(raw_orders):
    gold = build_daily_country_sales(clean_orders(raw_orders))
    assert gold.columns == [
        "order_date",
        "country",
        "order_count",
        "customer_count",
        "gross_revenue",
        "avg_order_value",
    ]
    assert gold.count() == 2


def test_timestamps_are_preserved(raw_orders):
    row = clean_orders(raw_orders).filter(F.col("order_id") == "ORD-1").collect()[0]
    assert row.order_ts == datetime(2026, 1, 2, 10, 0)
