#!/usr/bin/env python3
"""Unified local and CI packaging entry point for CodeDesk."""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from codedesk_env import (
    CODEDESK_BUILD_KEYS,
    load_env_file,
    validate_release_config,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ROOT / "target" / "packages"
ANDROID_BUILDER_IMAGE = "codedesk-builder-android:3.24.5"
SERVER_IMAGE = "codedesk-server"
FLUTTER_VERSION = "3.24.5"
RUST_TOOLCHAIN = "1.87.0"
MACOS_TARGETS = ("aarch64-apple-darwin", "x86_64-apple-darwin")


class ReleaseError(RuntimeError):
    pass


def run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
    capture: bool = False,
    sensitive: bool = False,
) -> subprocess.CompletedProcess[str]:
    shown_command = (
        "[sensitive command omitted]"
        if sensitive
        else subprocess.list2cmdline(command)
    )
    print("+", shown_command)
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=False,
        text=True,
        capture_output=capture,
    )
    if result.returncode != 0:
        if capture:
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise ReleaseError(
            f"command failed with exit code {result.returncode}: "
            f"{shown_command}"
        )
    return result


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def load_build_environment() -> None:
    try:
        values = load_env_file(ROOT / ".env", missing_ok=True)
    except (OSError, ValueError) as error:
        raise ReleaseError(f"cannot load .env: {error}") from error
    for key, value in values.items():
        os.environ.setdefault(key, value)


def cargo_version() -> str:
    contents = (ROOT / "Cargo.toml").read_text(encoding="utf-8")
    package = re.search(r"(?ms)^\[package\]\s*(.*?)(?=^\[|\Z)", contents)
    if not package:
        raise ReleaseError("Cargo.toml has no [package] section")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', package.group(1))
    if not match:
        raise ReleaseError("Cargo.toml package version is missing")
    return match.group(1)


def flutter_version() -> tuple[str, str]:
    contents = (ROOT / "flutter" / "pubspec.yaml").read_text(encoding="utf-8")
    match = re.search(
        r"(?m)^version:\s*([0-9]+\.[0-9]+\.[0-9]+)(?:\+([0-9]+))?",
        contents,
    )
    if not match:
        raise ReleaseError("flutter/pubspec.yaml version is missing or invalid")
    return match.group(1), match.group(2) or "1"


def normalize_version(value: str | None) -> str:
    if value:
        version = value.removeprefix("v")
    else:
        version = cargo_version()
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ReleaseError(f"invalid release version: {version!r}")
    return version


def build_number() -> str:
    configured = os.environ.get("CODEDESK_BUILD_NUMBER") or os.environ.get(
        "GITHUB_RUN_NUMBER"
    )
    if configured:
        if not configured.isdigit():
            raise ReleaseError("CODEDESK_BUILD_NUMBER must be an integer")
        return configured
    result = run(
        ["git", "rev-list", "--count", "HEAD"],
        capture=True,
    )
    return result.stdout.strip()


def flutter_command() -> str:
    configured = os.environ.get("FLUTTER", "flutter")
    resolved = shutil.which(configured)
    if not resolved:
        raise ReleaseError(
            f"Flutter was not found: {configured}. CodeDesk requires Flutter {FLUTTER_VERSION}."
        )
    result = run([resolved, "--version", "--machine"], capture=True)
    if f'"frameworkVersion": "{FLUTTER_VERSION}"' not in result.stdout:
        raise ReleaseError(f"CodeDesk requires Flutter {FLUTTER_VERSION}: {resolved}")
    return resolved


def release_cargo_command() -> list[str]:
    return ["cargo", f"+{RUST_TOOLCHAIN}"]


def ensure_release_rust() -> None:
    if not command_exists("rustup") or not command_exists("cargo"):
        raise ReleaseError("rustup and cargo are required")
    toolchains = run(["rustup", "toolchain", "list"], capture=True).stdout
    if not re.search(rf"(?m)^{re.escape(RUST_TOOLCHAIN)}(?:-|$)", toolchains):
        raise ReleaseError(
            f"Rust {RUST_TOOLCHAIN} is required for release builds; run "
            f"`rustup toolchain install {RUST_TOOLCHAIN}`"
        )


def ensure_vcpkg_triplets(triplets: tuple[str, ...]) -> None:
    vcpkg_root = Path(
        os.environ.get(
            "VCPKG_ROOT",
            str(Path.home() / ".local" / "share" / "vcpkg"),
        )
    ).expanduser()
    missing = [
        triplet
        for triplet in triplets
        if not (vcpkg_root / "installed" / triplet).is_dir()
    ]
    if missing:
        raise ReleaseError(
            "native dependencies are missing for: " + ", ".join(missing)
        )


def dart_defines() -> list[str]:
    return [
        f"--dart-define={key}={os.environ.get(key, '')}" for key in CODEDESK_BUILD_KEYS
    ]


def ensure_output(platform_name: str) -> Path:
    output = PACKAGES / platform_name
    output.mkdir(parents=True, exist_ok=True)
    return output


def docker_platform() -> str:
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "amd64"
    if machine in ("arm64", "aarch64"):
        return "arm64"
    raise ReleaseError(f"unsupported Docker host architecture: {machine}")


def ensure_docker() -> None:
    if not command_exists("docker"):
        raise ReleaseError("Docker was not found")
    run(["docker", "buildx", "version"], capture=True)
    run(["docker", "info"], capture=True)


def package_server(version: str, *, all_architectures: bool) -> None:
    ensure_docker()
    output = ensure_output("server")
    architectures = ("amd64", "arm64") if all_architectures else (docker_platform(),)
    for architecture in architectures:
        command = [
            "docker",
            "buildx",
            "build",
            "--platform",
            f"linux/{architecture}",
            "--file",
            "server/docker/Dockerfile",
            "--tag",
            f"{SERVER_IMAGE}:{version}",
            "--tag",
            f"{SERVER_IMAGE}:{version}-{architecture}",
        ]
        if all_architectures:
            destination = (
                output
                / f"codedesk-server-{version}-linux-{architecture}.tar"
            )
            destination.unlink(missing_ok=True)
            command.extend(
                ["--output", f"type=docker,dest={destination}"]
            )
        else:
            command.extend(["--tag", f"{SERVER_IMAGE}:local", "--load"])
        command.append(".")
        run(command)


def build_android_builder() -> None:
    ensure_docker()
    command = [
        "docker",
        "build",
        "--file",
        "docker/android/Dockerfile",
        "--tag",
        ANDROID_BUILDER_IMAGE,
    ]
    ubuntu_mirror = os.environ.get("CODEDESK_UBUNTU_MIRROR", "").strip()
    if ubuntu_mirror:
        command.extend(
            ["--build-arg", f"UBUNTU_MIRROR={ubuntu_mirror.rstrip('/')}"]
        )
    mirror_build_args = {
        "CODEDESK_RUSTUP_DIST_SERVER": "RUSTUP_DIST_SERVER",
        "CODEDESK_RUSTUP_UPDATE_ROOT": "RUSTUP_UPDATE_ROOT",
        "CODEDESK_CARGO_REGISTRY_INDEX": "CODEDESK_CARGO_MIRROR_INDEX",
        "CODEDESK_FLUTTER_GIT_URL": "FLUTTER_GIT_URL",
    }
    for environment_key, build_argument in mirror_build_args.items():
        value = os.environ.get(environment_key, "").strip()
        if value:
            command.extend(["--build-arg", f"{build_argument}={value}"])
    command.append("docker/android")
    run(command)


def ensure_android_builder() -> None:
    result = subprocess.run(
        ["docker", "image", "inspect", ANDROID_BUILDER_IMAGE],
        cwd=ROOT,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        build_android_builder()


def _android_signing_directory() -> tempfile.TemporaryDirectory[str]:
    keystore = os.environ.get("ANDROID_KEYSTORE_FILE", "")
    required = {
        "ANDROID_KEY_ALIAS": os.environ.get("ANDROID_KEY_ALIAS", ""),
        "ANDROID_KEY_PASSWORD": os.environ.get("ANDROID_KEY_PASSWORD", ""),
        "ANDROID_STORE_PASSWORD": os.environ.get("ANDROID_STORE_PASSWORD", ""),
    }
    if not keystore or not Path(keystore).expanduser().is_file():
        raise ReleaseError("ANDROID_KEYSTORE_FILE must point to a release keystore")
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise ReleaseError(f"missing Android signing values: {', '.join(missing)}")

    temporary = tempfile.TemporaryDirectory(prefix="codedesk-android-signing-")
    secret_dir = Path(temporary.name)
    shutil.copy2(Path(keystore).expanduser(), secret_dir / "android-keystore")
    properties = (
        f"keyAlias={required['ANDROID_KEY_ALIAS']}\n"
        f"keyPassword={required['ANDROID_KEY_PASSWORD']}\n"
        "storeFile=/run/secrets/android-keystore\n"
        f"storePassword={required['ANDROID_STORE_PASSWORD']}\n"
    )
    signing_file = secret_dir / "android-signing.properties"
    signing_file.write_text(properties, encoding="utf-8")
    signing_file.chmod(0o600)
    return temporary


def validate_android_signing() -> None:
    keystore = os.environ.get("ANDROID_KEYSTORE_FILE", "")
    if not keystore or not Path(keystore).expanduser().is_file():
        raise ReleaseError("ANDROID_KEYSTORE_FILE must point to a release keystore")
    missing = [
        key
        for key in (
            "ANDROID_KEY_ALIAS",
            "ANDROID_KEY_PASSWORD",
            "ANDROID_STORE_PASSWORD",
        )
        if not os.environ.get(key)
    ]
    if missing:
        raise ReleaseError(f"missing Android signing values: {', '.join(missing)}")


def package_android(
    version: str,
    *,
    profile: str,
    package_format: str,
) -> None:
    if profile == "dev" and package_format in ("aab", "all"):
        raise ReleaseError("Android AAB packaging requires PROFILE=release")
    if profile == "release":
        validate_android_signing()
    ensure_docker()
    ensure_android_builder()
    ensure_output("android")
    cache = Path(
        os.environ.get(
            "CODEDESK_ANDROID_CACHE_HOST",
            str(ROOT / "target" / "docker-cache" / "android"),
        )
    ).expanduser().resolve()
    cache.mkdir(parents=True, exist_ok=True)
    vcpkg_installed = cache / "vcpkg-installed"
    vcpkg_installed.mkdir(parents=True, exist_ok=True)

    command = [
        "docker",
        "run",
        "--rm",
        "--mount",
        f"type=bind,source={ROOT},target=/workspace",
        "--mount",
        f"type=bind,source={cache},target=/cache/codedesk-android",
        "--mount",
        f"type=bind,source={vcpkg_installed},target=/opt/vcpkg/installed",
        "--env",
        "CODEDESK_ANDROID_CACHE=/cache/codedesk-android",
    ]
    if hasattr(os, "getuid"):
        command.extend(["--user", f"{os.getuid()}:{os.getgid()}"])
    for key in CODEDESK_BUILD_KEYS:
        command.extend(["--env", f"{key}={os.environ.get(key, '')}"])

    signing: tempfile.TemporaryDirectory[str] | None = None
    try:
        if profile == "release":
            signing = _android_signing_directory()
            secret_dir = Path(signing.name)
            command.extend(
                [
                    "--mount",
                    "type=bind,"
                    f"source={secret_dir / 'android-keystore'},"
                    "target=/run/secrets/android-keystore,readonly",
                    "--mount",
                    "type=bind,"
                    f"source={secret_dir / 'android-signing.properties'},"
                    "target=/run/secrets/android-signing.properties,readonly",
                ]
            )
        command.extend(
            [
                ANDROID_BUILDER_IMAGE,
                "--profile",
                profile,
                "--format",
                package_format,
                "--version",
                version,
                "--build-number",
                build_number(),
            ]
        )
        run(command)
    finally:
        if signing is not None:
            signing.cleanup()


def generate_flutter_bridge() -> None:
    flutter = flutter_command()
    configured_codegen = os.environ.get("FLUTTER_RUST_BRIDGE_CODEGEN")
    codegen = configured_codegen or str(
        Path.home() / ".cargo" / "bin" / "flutter_rust_bridge_codegen"
    )
    installed_version = ""
    if Path(codegen).is_file():
        result = subprocess.run(
            [codegen, "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        installed_version = f"{result.stdout} {result.stderr}"
    if "1.80.1" not in installed_version:
        if configured_codegen:
            raise ReleaseError(
                f"{configured_codegen} is not flutter_rust_bridge_codegen 1.80.1"
            )
        ensure_release_rust()
        run(
            [
                *release_cargo_command(),
                "install",
                "flutter_rust_bridge_codegen",
                "--version",
                "1.80.1",
                "--features",
                "uuid",
                "--locked",
                "--force",
            ]
        )
    run([flutter, "pub", "get"], cwd=ROOT / "flutter")
    run(
        [
            codegen,
            "--rust-input",
            "./src/flutter_ffi.rs",
            "--dart-output",
            "./flutter/lib/generated_bridge.dart",
            "--c-output",
            "./flutter/macos/Runner/bridge_generated.h",
            "--class-name",
            "Rustdesk",
        ]
    )


def require_platform(expected: str) -> None:
    if platform.system() != expected:
        raise ReleaseError(f"this package must be built on {expected}")


def _macos_cargo_environment(target: str) -> dict[str, str]:
    environment = os.environ.copy()
    environment["MACOSX_DEPLOYMENT_TARGET"] = "10.14"
    triplet = "arm64-osx" if target.startswith("aarch64") else "x64-osx"
    environment["VCPKG_DEFAULT_TRIPLET"] = triplet
    environment["VCPKG_TARGET_TRIPLET"] = triplet
    return environment


def _verify_universal_macho(app: Path) -> None:
    failures: list[str] = []
    for candidate in app.rglob("*"):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        result = subprocess.run(
            ["file", "-b", str(candidate)],
            check=False,
            text=True,
            capture_output=True,
        )
        if "Mach-O" not in result.stdout:
            continue
        archs = run(["lipo", "-archs", str(candidate)], capture=True).stdout.split()
        if not {"arm64", "x86_64"}.issubset(set(archs)):
            failures.append(f"{candidate.relative_to(app)} ({' '.join(archs)})")
    if failures:
        raise ReleaseError(
            "macOS bundle contains non-universal Mach-O files:\n- "
            + "\n- ".join(failures)
        )


def _zip_paths(destination: Path, paths: list[Path], base: Path) -> None:
    destination.unlink(missing_ok=True)
    existing = [path for path in paths if path.exists()]
    if not existing:
        return
    if len(existing) == 1:
        run(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                str(existing[0]),
                str(destination),
            ]
        )
        return
    with tempfile.TemporaryDirectory(prefix="codedesk-symbols-") as temporary:
        stage = Path(temporary)
        for path in existing:
            target = stage / path.name
            if path.is_dir():
                shutil.copytree(path, target, symlinks=True)
            else:
                shutil.copy2(path, target)
        run(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                str(stage),
                str(destination),
            ]
        )


def package_macos(version: str, *, profile: str) -> None:
    require_platform("Darwin")
    for command in ("cargo", "rustup", "lipo", "codesign", "hdiutil", "xcrun"):
        if not command_exists(command):
            raise ReleaseError(f"required macOS command was not found: {command}")
    ensure_release_rust()
    ensure_vcpkg_triplets(("arm64-osx", "x64-osx"))
    identity = ""
    private_key = ""
    key_id = ""
    issuer = ""
    if profile == "release":
        identity = os.environ.get("APPLE_DEVELOPER_IDENTITY", "")
        private_key = os.environ.get("APPLE_NOTARY_PRIVATE_KEY", "")
        key_id = os.environ.get("APPLE_NOTARY_KEY_ID", "")
        issuer = os.environ.get("APPLE_NOTARY_ISSUER_ID", "")
        if not identity:
            raise ReleaseError("APPLE_DEVELOPER_IDENTITY is required for release")
        if not private_key or not Path(private_key).expanduser().is_file():
            raise ReleaseError("APPLE_NOTARY_PRIVATE_KEY must point to an App Store API key")
        if not key_id or not issuer:
            raise ReleaseError("APPLE_NOTARY_KEY_ID and APPLE_NOTARY_ISSUER_ID are required")
    flutter = flutter_command()
    generate_flutter_bridge()
    run(
        [
            "rustup",
            "target",
            "add",
            "--toolchain",
            RUST_TOOLCHAIN,
            *MACOS_TARGETS,
        ]
    )

    features = os.environ.get("CODEDESK_MACOS_FEATURES", "flutter")
    for target in MACOS_TARGETS:
        run(
            [
                *release_cargo_command(),
                "build",
                "--locked",
                "--release",
                "--target",
                target,
                "--features",
                features,
                "--lib",
                "--bin",
                "service",
            ],
            env=_macos_cargo_environment(target),
        )

    release_dir = ROOT / "target" / "release"
    release_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            "lipo",
            "-create",
            *[
                str(ROOT / "target" / target / "release" / "liblibrustdesk.dylib")
                for target in MACOS_TARGETS
            ],
            "-output",
            str(release_dir / "librustdesk.dylib"),
        ]
    )
    run(
        [
            "lipo",
            "-create",
            *[
                str(ROOT / "target" / target / "release" / "service")
                for target in MACOS_TARGETS
            ],
            "-output",
            str(release_dir / "service"),
        ]
    )

    run([flutter, "clean"], cwd=ROOT / "flutter")
    flutter_env = os.environ.copy()
    flutter_env["FLUTTER_XCODE_ARCHS"] = "arm64 x86_64"
    flutter_env["FLUTTER_XCODE_ONLY_ACTIVE_ARCH"] = "NO"
    flutter_env["CODEDESK_APPLE_TEAM_ID"] = os.environ.get("APPLE_TEAM_ID", "")
    run(
        [flutter, "build", "macos", "--release", *dart_defines()],
        cwd=ROOT / "flutter",
        env=flutter_env,
    )
    app = (
        ROOT
        / "flutter"
        / "build"
        / "macos"
        / "Build"
        / "Products"
        / "Release"
        / "CodeDesk.app"
    )
    shutil.copy2(release_dir / "service", app / "Contents" / "MacOS" / "service")
    _verify_universal_macho(app)

    entitlements = ROOT / "flutter" / "macos" / "Runner" / "Release.entitlements"
    if profile == "release":
        run(
            [
                "codesign",
                "--force",
                "--deep",
                "--options",
                "runtime",
                "--timestamp",
                "--sign",
                identity,
                "--entitlements",
                str(entitlements),
                str(app),
            ]
        )
    else:
        run(
            [
                "codesign",
                "--force",
                "--deep",
                "--sign",
                "-",
                "--entitlements",
                str(entitlements),
                str(app),
            ]
        )
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)])

    output = ensure_output("macos")
    stage = ROOT / "target" / "release-stage" / "macos"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    shutil.copytree(app, stage / "CodeDesk.app", symlinks=True)
    (stage / "Applications").symlink_to("/Applications")
    dmg = output / f"codedesk-{version}-macos-universal.dmg"
    dmg.unlink(missing_ok=True)
    run(
        [
            "hdiutil",
            "create",
            "-volname",
            "CodeDesk",
            "-srcfolder",
            str(stage),
            "-ov",
            "-format",
            "UDZO",
            str(dmg),
        ]
    )

    if profile == "release":
        run(
            [
                "codesign",
                "--force",
                "--timestamp",
                "--sign",
                identity,
                str(dmg),
            ]
        )
        run(
            [
                "xcrun",
                "notarytool",
                "submit",
                str(dmg),
                "--key",
                str(Path(private_key).expanduser()),
                "--key-id",
                key_id,
                "--issuer",
                issuer,
                "--wait",
            ]
        )
        run(["xcrun", "stapler", "staple", str(dmg)])

    app_binary = app / "Contents" / "MacOS" / "CodeDesk"
    rust_dsym = output / "librustdesk.dylib.dSYM"
    service_dsym = output / "service.dSYM"
    app_dsym = output / "CodeDesk.app.dSYM"
    for binary, dsym in (
        (release_dir / "librustdesk.dylib", rust_dsym),
        (release_dir / "service", service_dsym),
        (app_binary, app_dsym),
    ):
        shutil.rmtree(dsym, ignore_errors=True)
        run(["dsymutil", str(binary), "-o", str(dsym)])
    symbols = output / f"codedesk-{version}-macos-symbols.zip"
    _zip_paths(symbols, [rust_dsym, service_dsym, app_dsym], output)
    for dsym in (rust_dsym, service_dsym, app_dsym):
        shutil.rmtree(dsym, ignore_errors=True)
    print(f"macOS package: {dmg}")


def _write_export_options(
    destination: Path,
    *,
    method: str,
    team_id: str,
    profile_name: str,
) -> None:
    destination.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>method</key>
  <string>{method}</string>
  <key>teamID</key>
  <string>{team_id}</string>
  <key>provisioningProfiles</key>
  <dict>
    <key>com.codedesk.remote</key>
    <string>{profile_name}</string>
  </dict>
</dict>
</plist>
""".format(method=method, team_id=team_id, profile_name=profile_name),
        encoding="utf-8",
    )


def package_ios(
    version: str,
    *,
    profile: str,
    distribution: str,
) -> None:
    require_platform("Darwin")
    ensure_release_rust()
    ensure_vcpkg_triplets(("arm64-ios",))
    team_id = os.environ.get("APPLE_TEAM_ID", "")
    profile_name = os.environ.get("APPLE_PROVISIONING_PROFILE_NAME", "")
    if not team_id or not profile_name:
        raise ReleaseError(
            "APPLE_TEAM_ID and APPLE_PROVISIONING_PROFILE_NAME are required for iOS"
        )
    if profile == "release" and distribution != "app-store":
        raise ReleaseError("the current release pipeline supports app-store iOS export")
    flutter = flutter_command()
    generate_flutter_bridge()
    run(
        [
            "rustup",
            "target",
            "add",
            "--toolchain",
            RUST_TOOLCHAIN,
            "aarch64-apple-ios",
        ]
    )
    run(
        [
            *release_cargo_command(),
            "build",
            "--locked",
            "--features",
            os.environ.get("CODEDESK_IOS_FEATURES", "flutter,hwcodec"),
            "--release",
            "--target",
            "aarch64-apple-ios",
            "--lib",
        ]
    )

    method = "development" if profile == "dev" else "app-store"
    export_options = ROOT / "target" / "release-stage" / "ExportOptions.plist"
    export_options.parent.mkdir(parents=True, exist_ok=True)
    _write_export_options(
        export_options,
        method=method,
        team_id=team_id,
        profile_name=profile_name,
    )
    environment = os.environ.copy()
    environment["CODEDESK_APPLE_TEAM_ID"] = team_id
    run(
        [
            flutter,
            "build",
            "ipa",
            "--release",
            "--build-name",
            version,
            "--build-number",
            build_number(),
            "--export-options-plist",
            str(export_options),
            *dart_defines(),
        ],
        cwd=ROOT / "flutter",
        env=environment,
    )
    ipa_files = list((ROOT / "flutter" / "build" / "ios" / "ipa").glob("*.ipa"))
    if len(ipa_files) != 1:
        raise ReleaseError(f"expected one IPA, found {len(ipa_files)}")
    output = ensure_output("ios")
    suffix = "development" if profile == "dev" else "app-store"
    destination = output / f"codedesk-{version}-ios-{suffix}.ipa"
    shutil.copy2(ipa_files[0], destination)
    dsym_root = (
        ROOT
        / "flutter"
        / "build"
        / "ios"
        / "archive"
        / "Runner.xcarchive"
        / "dSYMs"
    )
    _zip_paths(
        output / f"codedesk-{version}-ios-dsym.zip",
        [dsym_root],
        dsym_root.parent,
    )
    print(f"iOS package: {destination}")


def _find_signtool() -> str:
    configured = os.environ.get("SIGNTOOL", "signtool")
    resolved = shutil.which(configured)
    if not resolved:
        raise ReleaseError("signtool was not found")
    return resolved


def sign_windows_file(path: Path) -> None:
    pfx = os.environ.get("WINDOWS_SIGNING_PFX", "")
    password = os.environ.get("WINDOWS_SIGNING_PASSWORD", "")
    timestamp = os.environ.get(
        "WINDOWS_TIMESTAMP_URL", "http://timestamp.digicert.com"
    )
    if not pfx or not Path(pfx).expanduser().is_file() or not password:
        raise ReleaseError(
            "WINDOWS_SIGNING_PFX and WINDOWS_SIGNING_PASSWORD are required"
        )
    run(
        [
            _find_signtool(),
            "sign",
            "/fd",
            "SHA256",
            "/td",
            "SHA256",
            "/tr",
            timestamp,
            "/f",
            str(Path(pfx).expanduser()),
            "/p",
            password,
            str(path),
        ],
        sensitive=True,
    )


def package_windows(version: str, *, profile: str) -> None:
    require_platform("Windows")
    ensure_release_rust()
    environment = os.environ.copy()
    environment["RUSTUP_TOOLCHAIN"] = RUST_TOOLCHAIN
    if profile == "release":
        _find_signtool()
        pfx = os.environ.get("WINDOWS_SIGNING_PFX", "")
        if not pfx or not Path(pfx).expanduser().is_file():
            raise ReleaseError("WINDOWS_SIGNING_PFX must point to a PFX file")
        environment["CODEDESK_SIGN_WINDOWS_BUNDLE"] = "1"
    run([sys.executable, "build.py", "--flutter"], env=environment)
    old_package = (
        ROOT
        / "target"
        / "packages"
        / f"codedesk-{version}-windows-x64-install.exe"
    )
    if not old_package.is_file():
        raise ReleaseError(f"Windows installer was not generated: {old_package}")
    output = ensure_output("windows")
    destination = output / f"codedesk-{version}-windows-x64-setup.exe"
    destination.unlink(missing_ok=True)
    shutil.move(str(old_package), destination)
    if profile == "release":
        sign_windows_file(destination)

    symbols_stage = ROOT / "target" / "release-stage" / "windows-symbols"
    shutil.rmtree(symbols_stage, ignore_errors=True)
    symbols_stage.mkdir(parents=True)
    for base in (
        ROOT / "target" / "release",
        ROOT / "flutter" / "build" / "windows",
    ):
        if base.exists():
            for pdb in base.rglob("*.pdb"):
                relative = pdb.relative_to(base)
                target = symbols_stage / base.name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(pdb, target)
    archive = output / f"codedesk-{version}-windows-symbols"
    shutil.make_archive(str(archive), "zip", symbols_stage)
    print(f"Windows package: {destination}")


def install_android(version: str) -> None:
    if not command_exists("adb"):
        raise ReleaseError("adb was not found")
    package = (
        PACKAGES / "android" / f"codedesk-{version}-android-arm64.apk"
    )
    if not package.is_file():
        raise ReleaseError(f"Android APK was not found: {package}")
    run(["adb", "install", "-r", str(package)])


def release_check(version: str) -> None:
    cargo = cargo_version()
    flutter, _ = flutter_version()
    errors: list[str] = []
    if version != cargo:
        errors.append(f"Git/release version {version} != Cargo version {cargo}")
    if version != flutter:
        errors.append(f"Git/release version {version} != Flutter version {flutter}")
    values = {key: os.environ.get(key, "") for key in CODEDESK_BUILD_KEYS}
    errors.extend(validate_release_config(values))
    if errors:
        raise ReleaseError("release check failed:\n- " + "\n- ".join(errors))
    print(f"CodeDesk release configuration is valid for v{version}.")


def validate_client_package_version(version: str) -> None:
    flutter, _ = flutter_version()
    if version != cargo_version() or version != flutter:
        raise ReleaseError(
            f"client package version {version} must match Cargo and Flutter versions"
        )


def doctor(target: str | None) -> None:
    system = platform.system()
    targets = [target] if target else ["server", "android"]
    if not target:
        if system == "Darwin":
            targets.extend(["macos", "ios"])
        elif system == "Windows":
            targets.append("windows")

    failures: list[str] = []
    for current in targets:
        try:
            if current in ("server", "android"):
                ensure_docker()
            if current == "android":
                image = subprocess.run(
                    ["docker", "image", "inspect", ANDROID_BUILDER_IMAGE],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if image.returncode != 0:
                    raise ReleaseError(
                        "Android builder image is missing; run "
                        "`make docker-android-builder`"
                    )
            if current in ("macos", "ios"):
                require_platform("Darwin")
                ensure_release_rust()
                flutter_command()
                for command in ("cargo", "rustup", "xcodebuild", "codesign"):
                    if not command_exists(command):
                        raise ReleaseError(f"{command} was not found")
                expected_xcode = (ROOT / ".xcode-version").read_text(
                    encoding="utf-8"
                ).strip()
                actual_xcode = run(
                    ["xcodebuild", "-version"], capture=True
                ).stdout.splitlines()[0]
                if actual_xcode != f"Xcode {expected_xcode}":
                    raise ReleaseError(
                        f"CodeDesk requires Xcode {expected_xcode}; found {actual_xcode}"
                    )
                required_triplets = (
                    ("arm64-osx", "x64-osx")
                    if current == "macos"
                    else ("arm64-ios",)
                )
                ensure_vcpkg_triplets(required_triplets)
            if current == "windows":
                require_platform("Windows")
                ensure_release_rust()
                flutter_command()
                for command in ("cargo", "cmake"):
                    if not command_exists(command):
                        raise ReleaseError(f"{command} was not found")
            print(f"[ok] {current}")
        except ReleaseError as error:
            failures.append(f"{current}: {error}")
    if failures:
        raise ReleaseError("doctor found problems:\n- " + "\n- ".join(failures))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument(
        "--target",
        choices=("server", "android", "macos", "ios", "windows"),
    )

    builder_parser = subparsers.add_parser("build-image")
    builder_parser.add_argument("target", choices=("android",))

    package_parser = subparsers.add_parser("package")
    package_parser.add_argument(
        "target", choices=("server", "android", "macos", "ios", "windows")
    )
    package_parser.add_argument("--version")
    package_parser.add_argument("--profile", choices=("dev", "release"), default="dev")
    package_parser.add_argument(
        "--format", choices=("apk", "aab", "all"), default="apk"
    )
    package_parser.add_argument(
        "--distribution", choices=("development", "app-store"), default="app-store"
    )
    package_parser.add_argument("--all-architectures", action="store_true")

    install_parser = subparsers.add_parser("install-android")
    install_parser.add_argument("--version")

    check_parser = subparsers.add_parser("release-check")
    check_parser.add_argument("--version", required=True)
    return parser.parse_args()


def main() -> int:
    os.chdir(ROOT)
    args = parse_args()
    try:
        if args.command == "release-check" or (
            args.command == "package" and args.target != "server"
        ):
            load_build_environment()
        if args.command == "doctor":
            doctor(args.target)
        elif args.command == "build-image":
            build_android_builder()
        elif args.command == "install-android":
            install_android(normalize_version(args.version))
        elif args.command == "release-check":
            release_check(normalize_version(args.version))
        elif args.command == "package":
            version = normalize_version(args.version)
            if args.target != "server":
                validate_client_package_version(version)
            if args.target == "server":
                package_server(version, all_architectures=args.all_architectures)
            elif args.target == "android":
                package_android(
                    version,
                    profile=args.profile,
                    package_format=args.format,
                )
            elif args.target == "macos":
                package_macos(version, profile=args.profile)
            elif args.target == "ios":
                package_ios(
                    version,
                    profile=args.profile,
                    distribution=args.distribution,
                )
            elif args.target == "windows":
                package_windows(version, profile=args.profile)
        return 0
    except (OSError, ReleaseError) as error:
        print(f"CodeDesk release error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
