#!/usr/bin/env python3
"""Reject Cargo Git dependencies in CodeDesk manifests and lockfiles."""

from __future__ import annotations

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
LOCKFILES = (
    ROOT / "Cargo.lock",
    ROOT / "server" / "Cargo.lock",
    ROOT / "server" / "ui" / "Cargo.lock",
    ROOT / "libs" / "portable" / "Cargo.lock",
    ROOT / "libs" / "virtual_display" / "Cargo.lock",
)


def main() -> int:
    errors: list[str] = []
    for manifest in ROOT.rglob("Cargo.toml"):
        if "target" in manifest.parts:
            continue
        for line_number, line in enumerate(
            manifest.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if re.search(r"\bgit\s*=", line):
                errors.append(f"{manifest.relative_to(ROOT)}:{line_number}: {line.strip()}")

    for lockfile in LOCKFILES:
        if not lockfile.exists():
            continue
        for line_number, line in enumerate(
            lockfile.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line.startswith('source = "git+'):
                errors.append(f"{lockfile.relative_to(ROOT)}:{line_number}: {line}")

    if errors:
        print("Cargo Git dependencies are not allowed:", file=sys.stderr)
        print("\n".join(errors), file=sys.stderr)
        return 1

    print("All Cargo dependencies resolve from repository paths or crates.io.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
