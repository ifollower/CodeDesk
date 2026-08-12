#!/usr/bin/env python3
"""Safely extract a GitHub source archive and materialize symbolic links."""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile


def stripped_path(name: str, strip_components: int) -> PurePosixPath | None:
    parts = PurePosixPath(name).parts
    if len(parts) <= strip_components:
        return None
    relative = PurePosixPath(*parts[strip_components:])
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe archive path: {name}")
    return relative


def destination_path(root: Path, relative: PurePosixPath) -> Path:
    candidate = root.joinpath(*relative.parts).resolve()
    root_resolved = root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"archive entry escapes destination: {relative}")
    return candidate


def resolve_link(member: tarfile.TarInfo, relative: PurePosixPath) -> PurePosixPath:
    target = PurePosixPath(member.linkname)
    if member.issym():
        target = relative.parent / target
    normalized: list[str] = []
    for part in target.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not normalized:
                raise ValueError(f"unsafe link target: {member.name} -> {member.linkname}")
            normalized.pop()
        else:
            normalized.append(part)
    return PurePosixPath(*normalized)


def extract(archive: Path, destination: Path, strip_components: int) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    links: list[tuple[tarfile.TarInfo, PurePosixPath]] = []

    with tarfile.open(archive, "r:gz") as source:
        for member in source.getmembers():
            relative = stripped_path(member.name, strip_components)
            if relative is None:
                continue
            output = destination_path(destination, relative)
            if member.isdir():
                output.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                output.parent.mkdir(parents=True, exist_ok=True)
                extracted = source.extractfile(member)
                if extracted is None:
                    raise ValueError(f"could not read archive member: {member.name}")
                with extracted, output.open("wb") as target:
                    shutil.copyfileobj(extracted, target)
                os.chmod(output, member.mode)
            elif member.issym() or member.islnk():
                links.append((member, relative))

    unresolved = links
    while unresolved:
        remaining: list[tuple[tarfile.TarInfo, PurePosixPath]] = []
        progressed = False
        for member, relative in unresolved:
            target_relative = resolve_link(member, relative)
            target = destination_path(destination, target_relative)
            output = destination_path(destination, relative)
            if not target.exists():
                remaining.append((member, relative))
                continue
            output.parent.mkdir(parents=True, exist_ok=True)
            if target.is_dir():
                shutil.copytree(target, output, dirs_exist_ok=True)
            else:
                shutil.copy2(target, output)
            progressed = True
        if not progressed and remaining:
            descriptions = ", ".join(
                f"{member.name} -> {member.linkname}" for member, _ in remaining
            )
            raise ValueError(f"could not materialize archive links: {descriptions}")
        unresolved = remaining


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--strip-components", type=int, default=1)
    args = parser.parse_args()
    extract(args.archive, args.destination, args.strip_components)


if __name__ == "__main__":
    main()
