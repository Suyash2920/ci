"""Deterministic + AI validation of the GitHub Actions workflow YAML.

The deterministic checks are the gate (they can fail the build); the AI
commentary is advisory and appended to the job summary.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

import yaml

from ai_client import complete

SYSTEM_PROMPT = """You are a GitHub Actions security and reliability reviewer.
Given workflow YAML, list concrete improvements for: least-privilege `permissions`,
action pinning, secret handling, concurrency control, caching, job modularity and
fail-fast behaviour. Reply as a short Markdown bullet list, max 150 words. No preamble."""

HARD_CODED_SECRET = re.compile(
    r"(?i)(password|token|api[_-]?key|client[_-]?secret)\s*:\s*(?!\s*\$\{\{)[\"']?[A-Za-z0-9/+_\-]{8,}"
)
UNPINNED_ACTION = re.compile(r"uses:\s*([^\s@]+)@(main|master)\s*$")


def check_workflow(path: pathlib.Path) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")

    try:
        doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return [f"{path.name}: invalid YAML -> {exc}"]

    if not isinstance(doc, dict):
        return [f"{path.name}: workflow must be a YAML mapping"]

    for lineno, line in enumerate(text.splitlines(), start=1):
        if HARD_CODED_SECRET.search(line):
            problems.append(f"{path.name}:{lineno}: possible hard-coded secret — use ${{{{ secrets.* }}}}")
        if UNPINNED_ACTION.search(line):
            problems.append(f"{path.name}:{lineno}: action pinned to a moving ref — pin to a version tag")

    # `on:` is parsed by PyYAML 1.1 semantics as the boolean True.
    if "on" not in doc and True not in doc:
        problems.append(f"{path.name}: missing trigger (`on:`)")
    if "permissions" not in doc:
        problems.append(f"{path.name}: no top-level `permissions:` block (least privilege)")
    if not doc.get("jobs"):
        problems.append(f"{path.name}: no jobs defined")

    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate GitHub Actions workflows")
    parser.add_argument("--workflow-dir", default=".github/workflows", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("ai-output/workflow-review.md"))
    parser.add_argument("--ai", action="store_true", help="Append advisory AI commentary")
    args = parser.parse_args(argv)

    files = sorted(args.workflow_dir.glob("*.yml")) + sorted(args.workflow_dir.glob("*.yaml"))
    if not files:
        print(f"No workflow files found in {args.workflow_dir}", file=sys.stderr)
        return 1

    problems = [p for f in files for p in check_workflow(f)]

    lines = ["## Workflow validation\n", f"Checked {len(files)} workflow file(s).\n"]
    if problems:
        lines.append("### ❌ Findings\n")
        lines.extend(f"- {p}" for p in problems)
    else:
        lines.append("### ✅ No structural or secret-handling issues found\n")

    if args.ai:
        combined = "\n\n".join(f"--- {f.name} ---\n{f.read_text(encoding='utf-8')}" for f in files)
        advice = complete(SYSTEM_PROMPT, combined, max_tokens=500)
        lines.append("\n### 🤖 AI suggestions (advisory)\n")
        lines.append(advice or "_AI suggestions unavailable._")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))

    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
