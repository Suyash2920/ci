"""AI-generated release notes from the git commit range being promoted to PROD."""

from __future__ import annotations

import argparse
import pathlib
import subprocess  # noqa: S404 - fixed, non-shell git invocation
import sys

from ai_client import complete

SYSTEM_PROMPT = """You are a release manager for a Databricks data platform.
Turn the raw commit log into release notes in Markdown with these sections:

### Highlights
### Data Pipeline Changes
### CI/CD & Infrastructure
### Fixes
### Upgrade / Operational Notes   - migrations, backfills, config or secret changes needed

Group related commits, use plain business English, drop noise such as
"merge branch" or "fix typo". Omit a section if it has no content."""


def git(*args: str) -> str:
    result = subprocess.run(  # noqa: S603 - argument list is fixed, shell=False
        ["git", *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        print(f"[git] {' '.join(args)} failed: {result.stderr.strip()}", file=sys.stderr)
        return ""
    return result.stdout.strip()


def commit_log(previous_tag: str | None, head: str) -> str:
    rng = f"{previous_tag}..{head}" if previous_tag else head
    return git("log", rng, "--no-merges", "--pretty=format:- %s (%an)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate release notes for a PROD promotion")
    parser.add_argument("--version", required=True)
    parser.add_argument("--previous-tag", default=None)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args(argv)

    previous = args.previous_tag or git("describe", "--tags", "--abbrev=0", "HEAD^") or None
    log = commit_log(previous, args.head)

    header = f"# Release {args.version}\n\nRange: `{previous or 'initial'}..{args.head}`\n"
    if not log:
        body = "\n_No user-facing commits in this range._\n"
    else:
        generated = complete(SYSTEM_PROMPT, f"Commit log:\n\n{log}", max_tokens=900)
        body = f"\n{generated}\n" if generated else f"\n## Commits\n\n{log}\n"

    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw_section = f"\n<details><summary>Raw commit log</summary>\n\n{log or '_empty_'}\n\n</details>\n"
    args.output.write_text(header + body + raw_section, encoding="utf-8")
    print(f"Release notes written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
