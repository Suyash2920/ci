"""Environment-aware configuration.

The same code is deployed to both environments; only the Unity Catalog name
changes (``qa`` vs ``prod``). Nothing environment-specific is hard-coded in the
transformation logic.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VALID_ENVIRONMENTS = ("qa", "prod")


class ConfigError(ValueError):
    """Raised when the supplied configuration is invalid."""


@dataclass(frozen=True)
class EtlConfig:
    """Resolved configuration for a single pipeline run."""

    env: str
    catalog: str
    bronze_schema: str
    silver_schema: str
    gold_schema: str
    source_path: str
    quality: dict[str, Any] = field(default_factory=dict)

    def table(self, layer: str, name: str) -> str:
        """Return the fully qualified Unity Catalog table name."""
        schemas = {
            "bronze": self.bronze_schema,
            "silver": self.silver_schema,
            "gold": self.gold_schema,
        }
        if layer not in schemas:
            raise ConfigError(f"Unknown layer '{layer}'. Expected one of {sorted(schemas)}.")
        if not name:
            raise ConfigError("Table name must not be empty.")
        return f"{self.catalog}.{schemas[layer]}.{name}"


def _config_dir() -> Path:
    # Config ships inside the wheel so the job does not depend on workspace files.
    override = os.environ.get("ETL_CONF_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "conf"


def load_config(env: str, conf_dir: str | Path | None = None) -> EtlConfig:
    """Load and validate the configuration for ``env``.

    Args:
        env: ``qa`` or ``prod``.
        conf_dir: Optional override for the directory holding ``<env>.yml``.
    """
    normalized = (env or "").strip().lower()
    if normalized not in VALID_ENVIRONMENTS:
        raise ConfigError(f"Unsupported environment '{env}'. Expected one of {list(VALID_ENVIRONMENTS)}.")

    base = Path(conf_dir) if conf_dir else _config_dir()
    path = base / f"{normalized}.yml"
    if not path.is_file():
        raise ConfigError(f"Configuration file not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    missing = [k for k in ("catalog", "schemas", "source_path") if k not in raw]
    if missing:
        raise ConfigError(f"Missing required keys {missing} in {path}")

    schemas = raw["schemas"]
    return EtlConfig(
        env=normalized,
        catalog=str(raw["catalog"]),
        bronze_schema=str(schemas["bronze"]),
        silver_schema=str(schemas["silver"]),
        gold_schema=str(schemas["gold"]),
        source_path=str(raw["source_path"]),
        quality=dict(raw.get("quality") or {}),
    )
