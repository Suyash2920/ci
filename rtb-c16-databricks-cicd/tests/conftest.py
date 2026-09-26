"""Shared pytest fixtures.

A single local Spark session is reused across the whole test session because
session start-up dominates the runtime of the suite in CI.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from pyspark.sql import SparkSession

from retail_etl.schemas import RAW_ORDERS_SCHEMA


@pytest.fixture(scope="session")
def spark() -> SparkSession:
    session = (
        SparkSession.builder.appName("retail-etl-tests")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


@pytest.fixture()
def raw_orders(spark: SparkSession):
    """A small feed containing valid rows plus every dirty-data case we handle."""
    rows = [
        ("ORD-1", "CUST-1", "SKU-1", "in", 2, 10.0, datetime(2026, 1, 1, 10, 0)),
        ("ORD-2", "CUST-2", "SKU-2", " US ", 1, 25.5, datetime(2026, 1, 1, 11, 0)),
        # duplicate business key — the later timestamp must win
        ("ORD-1", "CUST-1", "SKU-9", "IN", 5, 10.0, datetime(2026, 1, 2, 10, 0)),
        # rejected: blank customer id
        ("ORD-3", "   ", "SKU-3", "UK", 1, 5.0, datetime(2026, 1, 1, 12, 0)),
        # rejected: non-positive quantity
        ("ORD-4", "CUST-4", "SKU-4", "UK", 0, 5.0, datetime(2026, 1, 1, 13, 0)),
        # rejected: non-positive price
        ("ORD-5", "CUST-5", "SKU-5", "DE", 3, 0.0, datetime(2026, 1, 1, 14, 0)),
        # rejected: null order id
        (None, "CUST-6", "SKU-6", "DE", 3, 7.0, datetime(2026, 1, 1, 15, 0)),
    ]
    return spark.createDataFrame(rows, schema=RAW_ORDERS_SCHEMA)
