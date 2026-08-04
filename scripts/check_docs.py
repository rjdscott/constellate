#!/usr/bin/env python3
"""Deterministic doc-consistency checks, run by `make doc-check` (in `make check`/CI).

Proves what a script can prove; the /phase-gate skill covers judgment calls.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = (".venv", "node_modules", ".idea", ".claude", ".git")
errors: list[str] = []


def md_files() -> list[Path]:
    return [f for f in ROOT.rglob("*.md") if not any(part in SKIP_DIRS for part in f.parts)]


def check_links() -> None:
    """Every relative markdown link resolves (template placeholders exempt)."""
    for f in md_files():
        for m in re.finditer(r"\]\((?!http|#|mailto)([^)]+?)(?:#[^)]*)?\)", f.read_text()):
            target = m.group(1)
            if "NNNN" in target:  # ADR template placeholder
                continue
            if not (f.parent / target).resolve().exists():
                errors.append(f"{f.relative_to(ROOT)}: broken link -> {target}")


def check_adr_index() -> None:
    """One index row per ADR file; row status matches the file's Status line."""
    adr_dir = ROOT / "docs/adr"
    index = (adr_dir / "README.md").read_text()
    for f in sorted(adr_dir.glob("[0-9]" * 4 + "-*.md")):
        m = re.search(r"^- \*\*Status:\*\* (\w+)", f.read_text(), re.M)
        if not m:
            errors.append(f"{f.relative_to(ROOT)}: no Status line")
            continue
        row = re.search(rf"\|\s*\[\d+\]\({re.escape(f.name)}\)\s*\|[^|]+\|\s*(\w+)", index)
        if not row:
            errors.append(f"docs/adr/README.md: no index row for {f.name}")
        elif row.group(1) != m.group(1).split()[0]:
            errors.append(
                f"docs/adr/README.md: {f.name} status mismatch "
                f"(index {row.group(1)!r} vs file {m.group(1)!r})"
            )


def check_plans() -> None:
    """Status-table rows point at real phase files; 🟢 phases have no unchecked
    boxes and a non-empty progress log; every phase file has a table row."""
    for plan_readme in ROOT.glob("docs/plans/*/README.md"):
        plan_dir = plan_readme.parent
        rel = plan_readme.relative_to(ROOT)
        rows = re.findall(
            r"^\|\s*\d+\s*\|\s*\[[^\]]+\]\(([^)]+)\)\s*\|\s*(\S+)", plan_readme.read_text(), re.M
        )
        listed = set()
        for target, status in rows:
            listed.add(target)
            phase = plan_dir / target
            if not phase.exists():
                errors.append(f"{rel}: status row links missing file {target}")
                continue
            text = phase.read_text()
            if status == "🟢":
                if re.search(r"^- \[ \]", text, re.M):
                    errors.append(f"{rel}: {target} marked 🟢 but has unchecked tasks")
                log = text.split("## Progress log", 1)
                if len(log) < 2 or not re.search(r"\d{4}-\d{2}-\d{2}", log[1]):
                    errors.append(f"{rel}: {target} marked 🟢 but progress log empty")
        for phase in plan_dir.glob("phase-*.md"):
            if phase.name not in listed:
                errors.append(f"{rel}: phase file {phase.name} missing from status table")


def check_runbooks() -> None:
    """Every runbook is registered in the runbooks index."""
    rb_dir = ROOT / "docs/runbooks"
    index = (rb_dir / "README.md").read_text()
    for f in rb_dir.glob("*.md"):
        if f.name != "README.md" and f"({f.name})" not in index:
            errors.append(f"docs/runbooks/README.md: no index row for {f.name}")


def main() -> int:
    check_links()
    check_adr_index()
    check_plans()
    check_runbooks()
    if errors:
        print(f"doc-check: {len(errors)} problem(s)")
        for e in errors:
            print(f"  {e}")
        return 1
    print("doc-check: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
