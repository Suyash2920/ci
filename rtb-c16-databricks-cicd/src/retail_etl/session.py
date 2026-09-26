"""Spark session helpers.

On Databricks the session already exists; locally (unit tests) a lightweight
session is created on demand.
"""

from __future__ import annotations

from pyspark.sql import SparkSession


def get_spark(app_name: str = "retail-etl") -> SparkSession:
    """Return the active Spark session, creating a local one if needed."""
    active = SparkSession.getActiveSession()
    if active is not None:
        return active
    return (
        SparkSession.builder.appName(app_name)
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
