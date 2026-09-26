"""AI-assisted pull-request review.

Reads a unified diff from a file and writes a markdown review to stdout / a file.
The review is advisory only — it is posted as a PR comment and never fails the
build, satisfying the "do not rely solely on AI suggestions" quality rule.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from ai_client import complete

SYSTEM_PROMPT = """You are a senior data engineer reviewing a pull request for a
Databricks medallion (bronze/silver/gold) ETL project deployed through GitHub Actions.

Review the diff and reply in GitHub-flavoured Markdown with exactly these sections:
### Summary            - 2-3 bullet points on what changed and why it matters
### Risks              - correctness, data-quality, idempotency, performance and
                         QA-vs-PROD configuration drift risks. Say "None identified" if clean.
### Security           - hard-coded credentials, injection, unsafe file/SQL handling, over-broad
                         permissions. Say "None identified" if clean.
### Test Coverage      - which changed behaviours lack a unit test
### Suggested Actions  - a short, concrete checklist

Be specific and reference file names. Do not invent code that is not in the diff.
Never output secret values. Keep the whole review under 400 words."""

FALLBACK = (
    "### AI Review\n\n"
    "_AI review unavailable (no provider configured or the call failed). "
    "Falling back to the automated lint, test, coverage and SonarQube gates._\n"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate an AI code review from a diff file")
    parser.add_argument("--diff-file", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--max-diff-chars", type=int, default=20_000)
    args = parser.parse_args(argv)

    if not args.diff_file.is_file():
        print(f"Diff file not found: {args.diff_file}", file=sys.stderr)
        return 1

    diff = args.diff_file.read_text(encoding="utf-8", errors="replace")
    if not diff.strip():
        args.output.write_text("### AI Review\n\n_No reviewable changes in this PR._\n", encoding="utf-8")
        return 0

    truncated = diff[: args.max_diff_chars]
    note = "\n\n_(diff truncated for review)_" if len(diff) > args.max_diff_chars else ""

    review = complete(SYSTEM_PROMPT, f"Pull request diff:\n\n```diff\n{truncated}\n```", max_tokens=1000)
    body = f"## 🤖 AI Code Review\n\n{review}{note}\n" if review else FALLBACK

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        body + "\n---\n_Generated automatically. A human approval is still required to merge._\n",
        encoding="utf-8",
    )
    print(f"Review written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
