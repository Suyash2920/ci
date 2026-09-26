"""Job entry points for the bronze, silver and gold tasks.

Each entry point is exposed as a console script so the Databricks job can run it
as a ``python_wheel_task`` — the same command also runs locally for debugging.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from retail_etl import quality, storage, transforms
from retail_etl.config import EtlConfig, load_config
from retail_etl.session import get_spark

BRONZE_TABLE = "orders_raw"
SILVER_TABLE = "orders_clean"
GOLD_TABLE = "daily_country_sales"


def _parse_args(argv: list[str] | None, description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--env", required=True, choices=["qa", "prod"], help="Target environment")
    parser.add_argument("--batch-id", default=None, help="Batch identifier (defaults to UTC timestamp)")
    parser.add_argument("--source-path", default=None, help="Override the configured source path")
    args = parser.parse_args(argv)
    if not args.batch_id:
        args.batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return args


def _log(stage: str, payload: dict) -> None:
    """Structured one-line log so the GenAI log summariser can parse job output."""
    print(f"ETL_METRICS {json.dumps({'stage': stage, **payload}, default=str)}")


def run_bronze(cfg: EtlConfig, batch_id: str, source_path: str | None = None) -> str:
    spark = get_spark("retail-etl-bronze")
    storage.ensure_schemas(spark, cfg)
    raw = storage.read_raw_csv(spark, source_path or cfg.source_path)
    bronze = transforms.add_bronze_audit_columns(raw, batch_id)
    fqn = storage.write_table(bronze, cfg, "bronze", BRONZE_TABLE, mode="overwrite")
    _log("bronze", {"table": fqn, "rows": bronze.count(), "batch_id": batch_id})
    return fqn


def run_silver(cfg: EtlConfig, batch_id: str) -> str:
    spark = get_spark("retail-etl-silver")
    bronze = storage.read_table(spark, cfg, "bronze", BRONZE_TABLE)
    silver = transforms.clean_orders(bronze).cache()

    report = quality.profile(bronze, silver)
    quality.enforce(
        report,
        max_rejection_rate=float(cfg.quality.get("max_rejection_rate", 0.05)),
        fail_on_violation=bool(cfg.quality.get("fail_on_violation", True)),
    )

    fqn = storage.write_table(silver, cfg, "silver", SILVER_TABLE, partition_by=["order_date"])
    _log("silver", {"table": fqn, "batch_id": batch_id, **report.as_dict()})
    return fqn


def run_gold(cfg: EtlConfig, batch_id: str) -> str:
    spark = get_spark("retail-etl-gold")
    silver = storage.read_table(spark, cfg, "silver", SILVER_TABLE)
    gold = transforms.build_daily_country_sales(silver)
    fqn = storage.write_table(gold, cfg, "gold", GOLD_TABLE, mode="overwrite")
    _log("gold", {"table": fqn, "rows": gold.count(), "batch_id": batch_id})
    return fqn


def bronze_main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv, "Ingest the raw retail feed into the bronze layer")
    run_bronze(load_config(args.env), args.batch_id, args.source_path)
    return 0


def silver_main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv, "Cleanse bronze orders into the silver layer")
    run_silver(load_config(args.env), args.batch_id)
    return 0


def gold_main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv, "Aggregate silver orders into the gold layer")
    run_gold(load_config(args.env), args.batch_id)
    return 0


if __name__ == "__main__":  # pragma: no cover - manual local execution
    sys.exit(bronze_main())
