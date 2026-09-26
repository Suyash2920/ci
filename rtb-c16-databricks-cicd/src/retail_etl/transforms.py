"""Pure DataFrame transformations.

Every function here takes a DataFrame and returns a DataFrame with no I/O, no
global state and no environment awareness. That is what makes the pipeline
unit-testable on a local Spark session in CI.
"""

from __future__ import annotations

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

BRONZE_AUDIT_COLUMNS = ("_ingested_at", "_source_file", "_batch_id")


def add_bronze_audit_columns(df: DataFrame, batch_id: str) -> DataFrame:
    """Attach lineage/audit columns required by the bronze contract."""
    return (
        df.withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.input_file_name())
        .withColumn("_batch_id", F.lit(batch_id))
    )


def _is_blank(column: Column) -> Column:
    return column.isNull() | (F.trim(column) == F.lit(""))


def clean_orders(df: DataFrame) -> DataFrame:
    """Normalise raw order rows into the silver shape.

    - trims and upper-cases the country code
    - drops rows without an order id or customer id
    - drops non-positive quantities / prices (returns are handled separately)
    - deduplicates on ``order_id`` keeping the latest ``order_ts``
    """
    normalized = (
        df.withColumn("order_id", F.trim(F.col("order_id")))
        .withColumn("customer_id", F.trim(F.col("customer_id")))
        .withColumn("product_id", F.trim(F.col("product_id")))
        .withColumn("country", F.upper(F.trim(F.col("country"))))
    )

    valid = normalized.filter(
        ~_is_blank(F.col("order_id"))
        & ~_is_blank(F.col("customer_id"))
        & (F.col("quantity") > 0)
        & (F.col("unit_price") > 0)
    )

    with_amount = valid.withColumn(
        "gross_amount",
        F.round(F.col("quantity") * F.col("unit_price"), 2),
    ).withColumn("order_date", F.to_date(F.col("order_ts")))

    return deduplicate_latest(with_amount, keys=["order_id"], order_by="order_ts")


def deduplicate_latest(df: DataFrame, keys: list[str], order_by: str) -> DataFrame:
    """Keep one row per ``keys`` combination: the one with the greatest ``order_by``."""
    if not keys:
        raise ValueError("At least one deduplication key is required.")

    window = Window.partitionBy(*keys).orderBy(F.col(order_by).desc_nulls_last())
    return df.withColumn("_rn", F.row_number().over(window)).filter(F.col("_rn") == 1).drop("_rn")


def build_daily_country_sales(df: DataFrame) -> DataFrame:
    """Gold aggregate: revenue and order counts per country per day."""
    return (
        df.groupBy("order_date", "country")
        .agg(
            F.countDistinct("order_id").alias("order_count"),
            F.countDistinct("customer_id").alias("customer_count"),
            F.round(F.sum("gross_amount"), 2).alias("gross_revenue"),
            F.round(F.avg("gross_amount"), 2).alias("avg_order_value"),
        )
        .orderBy("order_date", "country")
    )
