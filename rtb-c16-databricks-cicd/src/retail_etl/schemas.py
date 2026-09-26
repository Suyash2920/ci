"""Explicit schemas for the raw retail feed.

Explicit schemas keep ingestion deterministic and make the contract visible to
reviewers and to the unit tests.
"""

from __future__ import annotations

from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# All fields are nullable: the CSV reader is PERMISSIVE and the silver layer —
# not the reader — is responsible for rejecting incomplete records.
RAW_ORDERS_SCHEMA = StructType(
    [
        StructField("order_id", StringType(), nullable=True),
        StructField("customer_id", StringType(), nullable=True),
        StructField("product_id", StringType(), nullable=True),
        StructField("country", StringType(), nullable=True),
        StructField("quantity", IntegerType(), nullable=True),
        StructField("unit_price", DoubleType(), nullable=True),
        StructField("order_ts", TimestampType(), nullable=True),
    ]
)
