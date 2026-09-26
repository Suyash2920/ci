from __future__ import annotations

import json

import pytest

from retail_etl import pipeline


def test_batch_id_defaults_to_utc_timestamp():
    args = pipeline._parse_args(["--env", "qa"], "test")
    assert args.batch_id.endswith("Z")
    assert len(args.batch_id) == 16


def test_explicit_batch_id_is_respected():
    args = pipeline._parse_args(["--env", "prod", "--batch-id", "B-42"], "test")
    assert args.batch_id == "B-42"
    assert args.env == "prod"


def test_invalid_environment_is_rejected_by_cli():
    with pytest.raises(SystemExit):
        pipeline._parse_args(["--env", "dev"], "test")


def test_env_is_mandatory():
    with pytest.raises(SystemExit):
        pipeline._parse_args([], "test")


def test_metrics_log_line_is_machine_readable(capsys):
    pipeline._log("silver", {"table": "qa.silver.orders_clean", "rows": 10})
    line = capsys.readouterr().out.strip()
    assert line.startswith("ETL_METRICS ")
    payload = json.loads(line.removeprefix("ETL_METRICS "))
    assert payload == {"stage": "silver", "table": "qa.silver.orders_clean", "rows": 10}


@pytest.mark.parametrize(
    ("main", "runner"),
    [
        (pipeline.bronze_main, "run_bronze"),
        (pipeline.silver_main, "run_silver"),
        (pipeline.gold_main, "run_gold"),
    ],
)
def test_entry_points_delegate_to_runners(monkeypatch, main, runner):
    calls: list[tuple] = []
    monkeypatch.setattr(pipeline, runner, lambda *a, **kw: calls.append((a, kw)) or "table")
    monkeypatch.setattr(pipeline, "load_config", lambda env: f"cfg-{env}")

    assert main(["--env", "qa", "--batch-id", "B-1"]) == 0
    assert calls[0][0][0] == "cfg-qa"
    assert calls[0][0][1] == "B-1"
