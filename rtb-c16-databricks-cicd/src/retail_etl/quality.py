"""Data quality gates.

The gate is intentionally strict in ``prod`` and advisory in ``qa`` — the
threshold comes from ``conf/<env>.yml`` so the same code enforces different
contracts per environment.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


class DataQualityError(RuntimeError):
    """Raised when a pipeline run violates its data quality contract."""


@dataclass(frozen=True)
class QualityReport:
    input_rows: int
    output_rows: int
    null_key_rows: int
    duplicate_key_rows: int

    @property
    def rejected_rows(self) -> int:
        return max(self.input_rows - self.output_rows, 0)

    @property
    def rejection_rate(self) -> float:
        if self.input_rows == 0:
            return 0.0
        return self.rejected_rows / self.input_rows

    def as_dict(self) -> dict[str, float | int]:
        return {
            "input_rows": self.input_rows,
            "output_rows": self.output_rows,
            "null_key_rows": self.null_key_rows,
            "duplicate_key_rows": self.duplicate_key_rows,
            "rejected_rows": self.rejected_rows,
            "rejection_rate": round(self.rejection_rate, 4),
        }


def profile(source: DataFrame, result: DataFrame, key: str = "order_id") -> QualityReport:
    """Compare a source and its cleaned result to produce a quality report."""
    input_rows = source.count()
    output_rows = result.count()
    null_keys = source.filter(F.col(key).isNull()).count()
    distinct_keys = result.select(key).distinct().count()
    return QualityReport(
        input_rows=input_rows,
        output_rows=output_rows,
        null_key_rows=null_keys,
        duplicate_key_rows=output_rows - distinct_keys,
    )


def enforce(report: QualityReport, max_rejection_rate: float, fail_on_violation: bool) -> None:
    """Apply the quality contract, raising in fail-fast environments."""
    violations: list[str] = []
    if report.output_rows == 0 and report.input_rows > 0:
        violations.append("all source rows were rejected")
    if report.duplicate_key_rows > 0:
        violations.append(f"{report.duplicate_key_rows} duplicate business keys survived cleansing")
    if report.rejection_rate > max_rejection_rate:
        violations.append(
            f"rejection rate {report.rejection_rate:.2%} exceeds threshold {max_rejection_rate:.2%}"
        )

    if not violations:
        return

    message = "Data quality violations: " + "; ".join(violations)
    if fail_on_violation:
        raise DataQualityError(message)
    print(f"[WARN] {message}")
