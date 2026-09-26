"""Tests for the GenAI helper scripts.

The LLM call itself is stubbed — what matters is that the pipeline degrades
safely without a provider and that no secret ever reaches the model.
"""

from __future__ import annotations

import textwrap

import pytest

import ai_client
import deployment_report
import review_pr
import validate_workflows


@pytest.fixture(autouse=True)
def _no_provider(monkeypatch):
    for var in ("OPENAI_API_KEY", "GITHUB_TOKEN"):
        monkeypatch.delenv(var, raising=False)


def test_resolve_provider_returns_none_without_credentials():
    assert ai_client.resolve_provider() is None


def test_openai_takes_precedence(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-value-1234567890")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_abcdefghijklmnopqrstuvwxyz")
    assert ai_client.resolve_provider().name == "openai"


def test_github_models_used_as_fallback(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_abcdefghijklmnopqrstuvwxyz")
    provider = ai_client.resolve_provider()
    assert provider.name == "github-models"
    assert provider.url.startswith("https://")


def test_complete_returns_none_without_provider():
    assert ai_client.complete("sys", "user") is None


@pytest.mark.parametrize(
    "raw",
    [
        token = "mock_databricks_token",
        "ghp_abcdefghijklmnopqrstuvwxyz012345",
        "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz",
        "password: SuperSecret123",
    ],
)
def test_redact_masks_credentials(raw):
    assert "REDACTED" in ai_client.redact(raw)


def test_redact_leaves_normal_text_alone():
    text = "Refactored clean_orders to drop non-positive quantities."
    assert ai_client.redact(text) == text


def test_extract_metrics_parses_structured_log_lines():
    log = textwrap.dedent(
        """
        starting task
        ETL_METRICS {"stage": "silver", "input_rows": 10, "output_rows": 8}
        ETL_METRICS not-json
        ETL_METRICS {"stage": "gold", "rows": 3}
        """
    )
    metrics = deployment_report.extract_metrics(log)
    assert [m["stage"] for m in metrics] == ["silver", "gold"]


def test_render_metrics_table_handles_empty_input():
    assert "No ETL_METRICS" in deployment_report.render_metrics_table([])


def test_review_pr_falls_back_when_ai_unavailable(tmp_path):
    diff = tmp_path / "pr.diff"
    diff.write_text("+++ b/src/retail_etl/transforms.py\n+print('hi')\n", encoding="utf-8")
    out = tmp_path / "review.md"

    assert review_pr.main(["--diff-file", str(diff), "--output", str(out)]) == 0
    assert "AI review unavailable" in out.read_text(encoding="utf-8")


def test_review_pr_handles_empty_diff(tmp_path):
    diff = tmp_path / "pr.diff"
    diff.write_text("   \n", encoding="utf-8")
    out = tmp_path / "review.md"
    assert review_pr.main(["--diff-file", str(diff), "--output", str(out)]) == 0
    assert "No reviewable changes" in out.read_text(encoding="utf-8")


def test_review_pr_reports_missing_diff_file(tmp_path):
    assert review_pr.main(["--diff-file", str(tmp_path / "nope"), "--output", str(tmp_path / "o.md")]) == 1


def _write_workflow(tmp_path, body: str, name: str = "ci.yml"):
    path = tmp_path / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_workflow_validator_accepts_a_good_workflow(tmp_path):
    path = _write_workflow(
        tmp_path,
        """
        name: CI
        on:
          push:
            branches: [main]
        permissions:
          contents: read
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
        """,
    )
    assert validate_workflows.check_workflow(path) == []


def test_workflow_validator_flags_hardcoded_secret(tmp_path):
    path = _write_workflow(
        tmp_path,
        """
        name: Bad
        on: push
        permissions:
          contents: read
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo ok
                env:
                  DATABRICKS_TOKEN: dapi0123456789abcdef
        """,
    )
    assert any("hard-coded secret" in p for p in validate_workflows.check_workflow(path))


def test_workflow_validator_flags_unpinned_action_and_missing_permissions(tmp_path):
    path = _write_workflow(
        tmp_path,
        """
        name: Bad
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@main
        """,
    )
    problems = validate_workflows.check_workflow(path)
    assert any("moving ref" in p for p in problems)
    assert any("permissions" in p for p in problems)


def test_workflow_validator_flags_invalid_yaml(tmp_path):
    path = _write_workflow(tmp_path, "name: [unclosed\n")
    assert any("invalid YAML" in p for p in validate_workflows.check_workflow(path))
