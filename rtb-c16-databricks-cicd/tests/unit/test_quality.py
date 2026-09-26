from __future__ import annotations

import pytest

from retail_etl.quality import DataQualityError, QualityReport, enforce, profile
from retail_etl.transforms import clean_orders


def test_profile_counts_rejections(raw_orders):
    report = profile(raw_orders, clean_orders(raw_orders))
    assert report.input_rows == 7
    assert report.output_rows == 2
    assert report.null_key_rows == 1
    assert report.duplicate_key_rows == 0
    assert report.rejected_rows == 5


def test_rejection_rate_of_empty_source_is_zero():
    assert QualityReport(0, 0, 0, 0).rejection_rate == 0.0


def test_report_serialises_for_logging():
    payload = QualityReport(10, 9, 1, 0).as_dict()
    assert payload["rejection_rate"] == 0.1
    assert set(payload) == {
        "input_rows",
        "output_rows",
        "null_key_rows",
        "duplicate_key_rows",
        "rejected_rows",
        "rejection_rate",
    }


def test_enforce_passes_within_threshold():
    enforce(QualityReport(100, 98, 2, 0), max_rejection_rate=0.05, fail_on_violation=True)


def test_enforce_raises_in_prod_when_threshold_exceeded():
    with pytest.raises(DataQualityError, match="rejection rate"):
        enforce(QualityReport(100, 50, 0, 0), max_rejection_rate=0.05, fail_on_violation=True)


def test_enforce_raises_on_surviving_duplicates():
    with pytest.raises(DataQualityError, match="duplicate business keys"):
        enforce(QualityReport(100, 100, 0, 3), max_rejection_rate=0.5, fail_on_violation=True)


def test_enforce_raises_when_everything_rejected():
    with pytest.raises(DataQualityError, match="all source rows were rejected"):
        enforce(QualityReport(100, 0, 0, 0), max_rejection_rate=1.0, fail_on_violation=True)


def test_enforce_only_warns_in_qa(capsys):
    enforce(QualityReport(100, 50, 0, 0), max_rejection_rate=0.05, fail_on_violation=False)
    assert "[WARN] Data quality violations" in capsys.readouterr().out
