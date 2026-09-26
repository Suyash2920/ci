"""AI-assisted deployment report.

Combines deterministic facts (bundle target, job run status, ETL_METRICS lines)
with an AI narrative, and writes the result to the GitHub Actions job summary.

Deterministic content is always produced; the AI paragraph is additive.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from ai_client import complete, redact

SYSTEM_PROMPT = """You are a DevOps release assistant. Given the deployment facts and raw
Databricks job logs below, write a concise deployment report in Markdown with:

### What happened      - 2-4 bullets in plain English
### Data outcome       - row counts, rejection rate, data-quality verdict (from ETL_METRICS lines)
### Anomalies          - anything suspicious, or "None"
### Next step          - one recommended action for the on-call engineer

Under 200 words. State only what the facts support; never guess numbers."""


def extract_metrics(log_text: str) -> list[dict]:
    """Pull the structured ETL_METRICS lines the pipeline emits."""
    metrics = []
    for line in log_text.splitlines():
        marker = "ETL_METRICS "
        if marker in line:
            try:
                metrics.append(json.loads(line.split(marker, 1)[1].strip()))
            except json.JSONDecodeError:
                continue
    return metrics


def render_facts_table(facts: dict[str, str]) -> str:
    rows = "\n".join(f"| {k} | {v} |" for k, v in facts.items())
    return f"| Field | Value |\n| --- | --- |\n{rows}\n"


def render_metrics_table(metrics: list[dict]) -> str:
    if not metrics:
        return "_No ETL_METRICS emitted by this run._\n"
    keys = sorted({k for m in metrics for k in m})
    header = "| " + " | ".join(keys) + " |\n| " + " | ".join("---" for _ in keys) + " |\n"
    body = "\n".join("| " + " | ".join(str(m.get(k, "")) for k in keys) + " |" for m in metrics)
    return header + body + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build an AI deployment report")
    parser.add_argument("--environment", required=True)
    parser.add_argument("--status", required=True, help="success | failure")
    parser.add_argument("--commit", default="")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--log-file", type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)

    log_text = ""
    if args.log_file and args.log_file.is_file():
        log_text = redact(args.log_file.read_text(encoding="utf-8", errors="replace"))

    metrics = extract_metrics(log_text)
    facts = {
        "Environment": args.environment,
        "Unity Catalog": args.environment,
        "Status": args.status,
        "Commit": args.commit or "n/a",
        "Workflow run": args.run_url or "n/a",
    }

    sections = [
        f"# Deployment Report — `{args.environment}`\n",
        render_facts_table(facts),
        "\n## Pipeline metrics\n",
        render_metrics_table(metrics),
    ]

    narrative = complete(
        SYSTEM_PROMPT,
        f"Facts:\n{json.dumps(facts, indent=2)}\n\n"
        f"ETL metrics:\n{json.dumps(metrics, indent=2)}\n\n"
        f"Last 8000 chars of logs:\n{log_text[-8000:]}",
        max_tokens=700,
    )
    sections.append("\n## 🤖 AI summary\n\n" + (narrative or "_AI summary unavailable._") + "\n")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(sections), encoding="utf-8")
    print(f"Deployment report written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
