from __future__ import annotations

from pathlib import Path

import pytest

from retail_etl.config import ConfigError, EtlConfig, load_config

CONF_DIR = Path(__file__).resolve().parents[2] / "src" / "retail_etl" / "conf"


@pytest.mark.parametrize(
    ("env", "expected_catalog", "fail_on_violation"),
    [("qa", "qa", False), ("prod", "prod", True)],
)
def test_load_config_per_environment(env, expected_catalog, fail_on_violation):
    cfg = load_config(env, conf_dir=CONF_DIR)
    assert cfg.catalog == expected_catalog
    assert cfg.quality["fail_on_violation"] is fail_on_violation


def test_prod_is_stricter_than_qa():
    qa = load_config("qa", conf_dir=CONF_DIR)
    prod = load_config("prod", conf_dir=CONF_DIR)
    assert prod.quality["max_rejection_rate"] < qa.quality["max_rejection_rate"]


def test_env_is_case_insensitive_and_trimmed():
    assert load_config("  PROD ", conf_dir=CONF_DIR).catalog == "prod"


@pytest.mark.parametrize("env", ["dev", "", None, "qa; drop table"])
def test_unknown_environment_is_rejected(env):
    with pytest.raises(ConfigError):
        load_config(env, conf_dir=CONF_DIR)


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config("qa", conf_dir=tmp_path)


def test_incomplete_config_file_raises(tmp_path):
    (tmp_path / "qa.yml").write_text("catalog: qa\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Missing required keys"):
        load_config("qa", conf_dir=tmp_path)


def test_table_returns_three_level_namespace():
    cfg = load_config("prod", conf_dir=CONF_DIR)
    assert cfg.table("silver", "orders_clean") == "prod.silver.orders_clean"


def test_table_rejects_unknown_layer_and_empty_name():
    cfg = load_config("qa", conf_dir=CONF_DIR)
    with pytest.raises(ConfigError):
        cfg.table("platinum", "x")
    with pytest.raises(ConfigError):
        cfg.table("gold", "")


def test_config_is_immutable():
    cfg = load_config("qa", conf_dir=CONF_DIR)
    assert isinstance(cfg, EtlConfig)
    with pytest.raises(AttributeError):
        cfg.catalog = "prod"  # type: ignore[misc]
