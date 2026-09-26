"""Unity Catalog read/write helpers.

All persistence goes through this module so the transformation code stays pure
and the table naming convention is enforced in exactly one place.
"""

from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession

from retail_etl.config import EtlConfig
from retail_etl.schemas import RAW_ORDERS_SCHEMA


def ensure_schemas(spark: SparkSession, cfg: EtlConfig) -> None:
    """Create the bronze/silver/gold schemas in the target catalog if absent."""
    for schema in (cfg.bronze_schema, cfg.silver_schema, cfg.gold_schema):
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{cfg.catalog}`.`{schema}`")


def read_raw_csv(spark: SparkSession, path: str) -> DataFrame:
    """Read the raw order feed using the explicit bronze contract schema."""
    return (
        spark.read.option("header", "true")
        .option("mode", "PERMISSIVE")
        .schema(RAW_ORDERS_SCHEMA)
        .csv(path)
    )


def read_table(spark: SparkSession, cfg: EtlConfig, layer: str, name: str) -> DataFrame:
    return spark.read.table(cfg.table(layer, name))


def write_table(
    df: DataFrame,
    cfg: EtlConfig,
    layer: str,
    name: str,
    mode: str = "overwrite",
    partition_by: list[str] | None = None,
) -> str:
    """Write ``df`` as a managed Delta table and return its fully qualified name."""
    fqn = cfg.table(layer, name)
    writer = df.write.format("delta").mode(mode).option("overwriteSchema", "true")
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.saveAsTable(fqn)
    return fqn
