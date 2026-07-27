#!/usr/bin/env python3
"""Load CodeDesk build variables from .env or validate release configuration."""

from __future__ import annotations

import argparse
import ast
import base64
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


CODEDESK_BUILD_KEYS = (
    "CODEDESK_SOURCE_URL",
    "CODEDESK_ISSUES_URL",
    "CODEDESK_WEBSITE_URL",
    "CODEDESK_DOWNLOAD_URL",
    "CODEDESK_PRIVACY_URL",
    "CODEDESK_DOCS_URL",
    "CODEDESK_DOCS_MOBILE_URL",
    "CODEDESK_DOCS_LINUX_PERMISSIONS_URL",
    "CODEDESK_DOCS_X11_URL",
    "CODEDESK_DOCS_LINUX_LOGIN_URL",
    "CODEDESK_DOCS_HEADLESS_URL",
    "CODEDESK_DOCS_WHITELIST_URL",
    "CODEDESK_API_URL",
    "CODEDESK_UPDATE_API_URL",
    "CODEDESK_RENDEZVOUS_SERVERS",
    "CODEDESK_RENDEZVOUS_PUBLIC_KEY",
)

REQUIRED_RELEASE_URLS = (
    "CODEDESK_SOURCE_URL",
    "CODEDESK_ISSUES_URL",
    "CODEDESK_WEBSITE_URL",
    "CODEDESK_DOWNLOAD_URL",
    "CODEDESK_PRIVACY_URL",
    "CODEDESK_DOCS_URL",
    "CODEDESK_DOCS_MOBILE_URL",
    "CODEDESK_DOCS_LINUX_PERMISSIONS_URL",
    "CODEDESK_DOCS_X11_URL",
    "CODEDESK_DOCS_LINUX_LOGIN_URL",
    "CODEDESK_DOCS_HEADLESS_URL",
    "CODEDESK_DOCS_WHITELIST_URL",
)


def _decode_value(raw: str, line_number: int) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value[0] in ("'", '"'):
        if len(value) < 2 or value[-1] != value[0]:
            raise ValueError(f"line {line_number}: unterminated quoted value")
        try:
            decoded = ast.literal_eval(value)
        except (SyntaxError, ValueError) as error:
            raise ValueError(f"line {line_number}: invalid quoted value") from error
        if not isinstance(decoded, str):
            raise ValueError(f"line {line_number}: value must be a string")
        return decoded
    # Keep unquoted URL fragments and base64 padding intact. Comments are only
    # recognized when the complete line begins with '#'.
    return value


def load_env_file(path: Path, *, missing_ok: bool) -> dict[str, str]:
    if not path.exists():
        if missing_ok:
            return {}
        raise ValueError(f"configuration file not found: {path}")

    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"line {line_number}: expected KEY=VALUE")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ValueError(f"line {line_number}: invalid variable name {key!r}")
        values[key] = _decode_value(raw_value, line_number)
    return values


def _is_http_url(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


def _contains_rustdesk_host(value: str) -> bool:
    lowered = value.lower()
    return "rustdesk.com" in lowered or "rs-ny.rustdesk.com" in lowered


def _validate_server(server: str) -> str | None:
    if not server:
        return "server entry is empty"
    if any(character.isspace() for character in server):
        return "server entry contains whitespace"
    if "://" in server or "/" in server:
        return "server must be HOST or HOST:PORT without a URL scheme or path"
    try:
        parsed = urlsplit(f"//{server}")
        if not parsed.hostname:
            return "server host is missing"
        _ = parsed.port
    except ValueError as error:
        return str(error)
    return None


def validate_release_config(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_RELEASE_URLS:
        value = values.get(key, "").strip()
        if not value:
            errors.append(f"{key} is required for release builds")

    for key in CODEDESK_BUILD_KEYS:
        value = values.get(key, "").strip()
        if value and _contains_rustdesk_host(value):
            errors.append(f"{key} must not reference RustDesk infrastructure")

    url_keys = tuple(key for key in CODEDESK_BUILD_KEYS if key.endswith("_URL"))
    for key in url_keys:
        value = values.get(key, "").strip()
        if value and not _is_http_url(value):
            errors.append(f"{key} must be an absolute http(s) URL")

    raw_servers = values.get("CODEDESK_RENDEZVOUS_SERVERS", "")
    servers = [server.strip() for server in raw_servers.split(",") if server.strip()]
    if not servers:
        errors.append("CODEDESK_RENDEZVOUS_SERVERS must contain at least one hbbs host")
    for server in servers:
        error = _validate_server(server)
        if error:
            errors.append(f"CODEDESK_RENDEZVOUS_SERVERS: {server!r}: {error}")

    public_key = values.get("CODEDESK_RENDEZVOUS_PUBLIC_KEY", "").strip()
    if not public_key:
        errors.append("CODEDESK_RENDEZVOUS_PUBLIC_KEY is required for release builds")
    else:
        try:
            decoded_key = base64.b64decode(public_key, validate=True)
            if len(decoded_key) != 32:
                errors.append("CODEDESK_RENDEZVOUS_PUBLIC_KEY must decode to 32 bytes")
        except ValueError:
            errors.append("CODEDESK_RENDEZVOUS_PUBLIC_KEY must be valid base64")

    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="run a command with values loaded from .env")
    run_parser.add_argument("--env-file", default=".env")
    run_parser.add_argument("command_args", nargs=argparse.REMAINDER)

    check_parser = subparsers.add_parser("check", help="validate release build configuration")
    check_parser.add_argument("--env-file", default=".env")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        values = load_env_file(Path(args.env_file), missing_ok=args.command == "run")
    except (OSError, ValueError) as error:
        print(f"CodeDesk environment error: {error}", file=sys.stderr)
        return 2

    if args.command == "check":
        errors = validate_release_config(values)
        if errors:
            print("CodeDesk release configuration is invalid:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print("CodeDesk release configuration is valid.")
        return 0

    command = args.command_args
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("codedesk_env.py run requires a command after --", file=sys.stderr)
        return 2
    environment = os.environ.copy()
    environment.update(values)
    os.execvpe(command[0], command, environment)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
