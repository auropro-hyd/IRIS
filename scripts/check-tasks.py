#!/usr/bin/env python3
"""Structural check on the tasks/ tree.

Asserts that:

1. Every workstream folder under `tasks/` contains the three required files:
   `spec.md`, `plan.md`, `tasks.md`.
2. Every `tasks.md` has at least one task line matching `- [ ] **T0\\d{2,}**`.
3. Every `spec.md` carries the required frontmatter keys:
   `Workstream`, `Status`, `Architect`, `Input`.
4. Every `*.md` under `tasks/` is free of em-dash (U+2014) and en-dash (U+2013).

Exits non-zero with a per-failure summary on any violation.

This script is invoked by `.github/workflows/docs-ci.yml` on every PR. It is
also safe to run locally:

    python3 scripts/check-tasks.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_ROOT = REPO_ROOT / "tasks"

REQUIRED_FILES = ("spec.md", "plan.md", "tasks.md")
SPEC_REQUIRED_KEYS = ("Workstream", "Status", "Architect", "Input")
TASK_LINE_PATTERN = re.compile(r"^- \[[ x]\] \*\*T0\d{2,}\*\*", re.MULTILINE)
SPEC_KEY_PATTERN = "**{key}**:"

# Workstream folders look like `001-project-scaffold`. The `tasks/README.md`
# itself is not a workstream folder; the script skips files directly under
# `tasks/`.
WORKSTREAM_DIR_PATTERN = re.compile(r"^\d{3}-[a-z0-9-]+$")


def workstream_folders() -> list[Path]:
    if not TASKS_ROOT.exists():
        return []
    return sorted(
        p for p in TASKS_ROOT.iterdir() if p.is_dir() and WORKSTREAM_DIR_PATTERN.match(p.name)
    )


def check_required_files(folder: Path) -> list[str]:
    errors: list[str] = []
    for name in REQUIRED_FILES:
        target = folder / name
        if not target.exists():
            errors.append(f"{folder.name}: missing required file `{name}`.")
    return errors


def check_tasks_has_task_lines(folder: Path) -> list[str]:
    tasks_md = folder / "tasks.md"
    if not tasks_md.exists():
        return []  # already reported by check_required_files
    content = tasks_md.read_text(encoding="utf-8")
    if not TASK_LINE_PATTERN.search(content):
        return [
            f"{folder.name}/tasks.md: no task line found "
            "(expected at least one `- [ ] **T0xx** ...`)."
        ]
    return []


def check_spec_frontmatter(folder: Path) -> list[str]:
    spec_md = folder / "spec.md"
    if not spec_md.exists():
        return []  # already reported by check_required_files
    content = spec_md.read_text(encoding="utf-8")
    errors: list[str] = []
    for key in SPEC_REQUIRED_KEYS:
        marker = SPEC_KEY_PATTERN.format(key=key)
        if marker not in content:
            errors.append(
                f"{folder.name}/spec.md: missing frontmatter key `{key}` "
                f"(expected a line beginning with `{marker}`)."
            )
    return errors


def check_dashes(folder: Path) -> list[str]:
    errors: list[str] = []
    for md in folder.rglob("*.md"):
        text = md.read_text(encoding="utf-8")
        em = text.count("—")
        en = text.count("–")
        relative = md.relative_to(REPO_ROOT)
        if em:
            errors.append(
                f"{relative}: {em} em-dash(es) found (project style uses "
                "periods, commas, parentheses, or colons instead)."
            )
        if en:
            errors.append(f"{relative}: {en} en-dash(es) found.")
    return errors


def main() -> int:
    if not TASKS_ROOT.exists():
        print("FAIL: tasks/ directory not found", file=sys.stderr)
        return 1

    folders = workstream_folders()
    if not folders:
        print("FAIL: no workstream folders found under tasks/", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    for folder in folders:
        all_errors.extend(check_required_files(folder))
        all_errors.extend(check_tasks_has_task_lines(folder))
        all_errors.extend(check_spec_frontmatter(folder))
        all_errors.extend(check_dashes(folder))

    if all_errors:
        print(f"FAIL: {len(all_errors)} issue(s) found in tasks/ tree:")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print(f"OK: {len(folders)} workstream(s) checked, no issues found.")
    for folder in folders:
        print(f"  - {folder.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
