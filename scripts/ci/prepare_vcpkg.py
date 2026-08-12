#!/usr/bin/env python3
"""Prepare CodeDesk's pinned native dependencies on ephemeral CI runners."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
MEDIA_PORTS = ("aom", "libvpx", "libyuv", "opus")


def run(command: list[str]) -> None:
    print("+", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def pinned_vcpkg_commit() -> str:
    manifest = json.loads((ROOT / "vcpkg.json").read_text(encoding="utf-8"))
    return manifest["vcpkg-configuration"]["default-registry"]["baseline"]


def bootstrap(vcpkg_root: Path) -> Path:
    vcpkg_root.mkdir(parents=True, exist_ok=True)
    if not (vcpkg_root / ".git").is_dir():
        run(["git", "init", str(vcpkg_root)])
        run(
            [
                "git",
                "-C",
                str(vcpkg_root),
                "remote",
                "add",
                "origin",
                "https://github.com/microsoft/vcpkg.git",
            ]
        )
    run(
        [
            "git",
            "-C",
            str(vcpkg_root),
            "fetch",
            "--depth",
            "1",
            "origin",
            pinned_vcpkg_commit(),
        ]
    )
    run(["git", "-C", str(vcpkg_root), "checkout", "--force", "--detach", "FETCH_HEAD"])
    bootstrap_script = vcpkg_root / (
        "bootstrap-vcpkg.bat" if os.name == "nt" else "bootstrap-vcpkg.sh"
    )
    if os.name == "nt":
        run(["cmd.exe", "/d", "/s", "/c", str(bootstrap_script), "-disableMetrics"])
    else:
        run([str(bootstrap_script), "-disableMetrics"])
    return vcpkg_root / ("vcpkg.exe" if os.name == "nt" else "vcpkg")


def install_media(vcpkg: Path, vcpkg_root: Path, triplets: tuple[str, ...]) -> None:
    packages = [f"{port}:{triplet}" for triplet in triplets for port in MEDIA_PORTS]
    run(
        [
            str(vcpkg),
            "--disable-metrics",
            "install",
            "--classic",
            *packages,
            f"--overlay-ports={ROOT / 'res' / 'vcpkg'}",
            f"--x-install-root={vcpkg_root / 'installed'}",
        ]
    )


def install_ios(vcpkg: Path, vcpkg_root: Path) -> None:
    run(
        [
            str(vcpkg),
            "--disable-metrics",
            "install",
            "--triplet",
            "arm64-ios",
            f"--overlay-ports={ROOT / 'res' / 'vcpkg'}",
            f"--x-install-root={vcpkg_root / 'installed'}",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "apple"), required=True)
    parser.add_argument("--with-ios", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configured_root = os.environ.get("VCPKG_ROOT", "").strip()
    if not configured_root:
        print("VCPKG_ROOT is required", file=sys.stderr)
        return 2
    vcpkg_root = Path(configured_root).expanduser().resolve()
    vcpkg = bootstrap(vcpkg_root)
    if args.platform == "windows":
        install_media(vcpkg, vcpkg_root, ("x64-windows-static",))
    else:
        install_media(vcpkg, vcpkg_root, ("arm64-osx", "x64-osx"))
        if args.with_ios:
            install_ios(vcpkg, vcpkg_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
