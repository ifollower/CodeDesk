# Building CodeDesk

## Source layout and tools

Clone this repository normally; no submodules are required. Release builders use
Rust 1.87.x and Flutter 3.24.5. Install Git, Make, Python 3, and the native
dependencies required by the target platform. The unified release script
requires Python 3.9 or newer.

Install the pinned release toolchain without changing the toolchain used for
ordinary development:

```bash
rustup toolchain install 1.87.0
```

The root and `server/` are separate Cargo workspaces with separate lockfiles. Run commands from the repository root so paths and packaging contexts are consistent.

## Shared library

```bash
cargo test -p hbb_common --locked
```

## Client

The Rust client depends on native media, capture, input, and UI libraries. Once target prerequisites are installed:

```bash
cargo build --locked
```

### Apple Silicon macOS

The capture library requires static `aom`, `libvpx`, and `libyuv` packages. Homebrew no longer provides `libyuv`, so install these packages with vcpkg instead of creating a fake Homebrew Cellar entry:

```bash
brew install nasm vcpkg
mkdir -p "$HOME/.local/share"
test -d "$HOME/.local/share/vcpkg/.git" || \
  git clone https://github.com/microsoft/vcpkg.git "$HOME/.local/share/vcpkg"

export VCPKG_ROOT="$HOME/.local/share/vcpkg"
vcpkg install --classic \
  aom:arm64-osx libvpx:arm64-osx libyuv:arm64-osx opus:arm64-osx \
  aom:x64-osx libvpx:x64-osx libyuv:x64-osx opus:x64-osx \
  --overlay-ports="$PWD/res/vcpkg" \
  --x-install-root="$VCPKG_ROOT/installed"

# Required when the iOS hwcodec feature is enabled.
vcpkg install --triplet arm64-ios \
  --overlay-ports="$PWD/res/vcpkg" \
  --x-install-root="$VCPKG_ROOT/installed"

make build-client
```

If the vcpkg repository already exists, update or reuse it instead of cloning it again. The root Makefile exports the same `VCPKG_ROOT` and `$VCPKG_ROOT/installed` defaults for client builds. The shared installed directory is required because some inherited native crates do not support a separate `VCPKG_INSTALLED_ROOT`.

For the current Flutter UI, follow the target setup under `flutter/` and use the repository's `build.py`/CI flow. The Rust library keeps the internal name `librustdesk` for FFI compatibility; user-facing application artifacts are named CodeDesk.

## Unified package commands

The root Makefile delegates packaging to `scripts/release.py`. Start by checking
the current machine:

```bash
make doctor
```

Package the targets supported by the host:

```bash
make package-local PROFILE=dev
```

All outputs are written below `target/packages/<platform>/`. Only the server and
Android are built in Linux containers. Apple packages require macOS and Xcode;
Windows packages require Windows and Visual Studio.

### Server image

Build and load the image for the current Docker architecture:

```bash
make package-server
make server-up
make server-logs
make server-down
```

Export both supported architectures without publishing to a registry:

```bash
make package-server-all
```

This creates:

```text
target/packages/server/codedesk-server-<version>-linux-amd64.tar
target/packages/server/codedesk-server-<version>-linux-arm64.tar
```

Load an exported image with `docker load -i <file>`. The server exposes TCP
21115–21119 plus UDP 21116 and stores keys/database state in `/data`.
Set `RELAY=<public-host>:21117` when starting the container if clients must use
the relay service; no example or public relay hostname is embedded by default.

### Android

The Android toolchain image pins Flutter 3.24.5, Rust 1.87.0, Android Platform
34, Build Tools 34.0.0, and NDK 26.3.11579264. The host only needs Docker:

```bash
make docker-android-builder
make package-android PROFILE=dev FORMAT=apk
make install-android
```

Release signing uses a keystore outside the repository:

```bash
export ANDROID_KEYSTORE_FILE="$HOME/.codedesk/release.keystore"
export ANDROID_KEY_ALIAS="codedesk"
export ANDROID_KEY_PASSWORD="..."
export ANDROID_STORE_PASSWORD="..."
make package-android PROFILE=release FORMAT=all
```

The first build compiles the pinned vcpkg media dependencies and can take a
long time. Cargo, Gradle, pub, and vcpkg caches are retained below
`target/docker-cache/android`. Set `CODEDESK_ANDROID_CACHE_HOST` to an absolute
host directory to keep the cache outside a CI checkout.

### macOS and iOS

macOS packaging runs natively on an Apple Silicon Mac and builds both Rust
targets before combining them into a Universal 2 bundle. The required Xcode
version is recorded in `.xcode-version`:

```bash
# Ad-hoc signed development DMG
make package-macos PROFILE=dev

# Developer ID signed and notarized DMG
export APPLE_DEVELOPER_IDENTITY="Developer ID Application: ..."
export APPLE_NOTARY_PRIVATE_KEY="$HOME/.codedesk/AuthKey_ABC123.p8"
export APPLE_NOTARY_KEY_ID="ABC123"
export APPLE_NOTARY_ISSUER_ID="..."
make package-macos PROFILE=release
```

Both `arm64-osx` and `x64-osx` native dependencies must be installed in the
configured vcpkg root. The release script rejects a bundle containing a
single-architecture Mach-O file.

iOS requires an installed development or App Store certificate and provisioning
profile:

```bash
export APPLE_TEAM_ID="YOUR_TEAM_ID"
export APPLE_PROVISIONING_PROFILE_NAME="codedesk-ios-app-store"
make package-ios PROFILE=release DISTRIBUTION=app-store
```

The IPA is produced for TestFlight/App Store validation but is not uploaded
automatically.

### Windows

Run on Windows x64 with Flutter 3.24.5, Rust 1.87.x, Visual Studio 2022 C++
Build Tools, the Windows SDK, CMake, Python and GNU Make:

```powershell
# Unsigned development installer
make package-windows PROFILE=dev

# Sign bundle files and the final installer
$env:WINDOWS_SIGNING_PFX = "C:\secrets\codedesk.pfx"
$env:WINDOWS_SIGNING_PASSWORD = "..."
$env:WINDOWS_TIMESTAMP_URL = "http://timestamp.digicert.com"
make package-windows PROFILE=release
```

The Rust FFI library keeps its inherited internal `librustdesk` filename;
published installers and applications are named CodeDesk.

## Server

Build every server binary against the root shared library:

```bash
DATABASE_URL=sqlite://./db_v2.sqlite3 \
  cargo build --manifest-path server/Cargo.toml --locked --release --bins
```

Expected binaries are `hbbs`, `hbbr`, and `codedesk-utils`.

Windows release builds do not bundle the inherited RustDesk virtual-display or
printer drivers. The corresponding UI installation entry remains unavailable
unless independently built and signed CodeDesk driver packages are placed at
`CodeDeskIddDriver/CodeDeskIddDriver.inf` and
`drivers/CodeDeskPrinterDriver/CodeDeskPrinterDriver.inf` in the application
directory.

## Self-hosted release runners

The tag workflow expects one runner with each custom label:

```text
self-hosted, codedesk-linux
self-hosted, codedesk-macos
self-hosted, codedesk-windows
```

Configure the public `CODEDESK_*` values as GitHub repository variables.
Configure certificate passwords, base64-encoded keystores/certificates,
provisioning profiles, and notary credentials as GitHub Actions secrets; see
`.github/workflows/release.yml` for their exact names.

The workflow imports credentials into temporary files/keychains, deletes them
in `always()` cleanup steps, builds all five target groups, and creates a draft
GitHub Release. It does not push a container image.

To publish version `X.Y.Z`, first update the Cargo and Flutter versions, then:

```bash
make release-check VERSION=X.Y.Z
git tag vX.Y.Z
git push origin vX.Y.Z
```

## Debian packages

Debian builds must also start from a full clone. The helper stages both workspaces and invokes Cargo with the server manifest:

```bash
server/debian/build.sh
```

Never copy only `server/` into the package builder.

## CodeDesk build configuration

Copy the tracked example before building a configured client:

```bash
cp .env.example .env
```

Fill in the public source, issue, website, download, privacy, documentation,
API, update, rendezvous, and rendezvous-public-key values in `.env`. The file
is ignored by Git and is used only while building; it is not copied into an
application package or the server Docker image. Do not store private server
keys, signing certificates, or API credentials in this file.

The root Makefile loads `.env` for client checks, tests, builds, and client
packaging. The release scripts forward the same values to Flutter as `--dart-define`
arguments, while `hbb_common` embeds them in the Rust core. Direct `cargo` or
`flutter build` commands do not load `.env` automatically.

Empty development configuration is supported: CodeDesk will not contact a
RustDesk public service and will prompt the user to configure an ID Server.
An empty API or update URL disables the corresponding client integration.
Before publishing a configured build, run:

```bash
make release-config-check
```

## Release gates

Before publishing a CodeDesk binary:

1. Test the shared library, client, all server binaries, and relevant Flutter/native targets.
2. Run connection integration tests for registration, direct connection, forced relay, reconnect, remote desktop/input, file transfer, and terminal.
3. Verify protobuf compatibility and compare behavior with the imported baseline.
4. Build Docker, Debian, and release artifacts from a fresh ordinary clone.
5. Verify CodeDesk and RustDesk coexist without sharing application IDs, services, storage, or deep links.
6. Run `make release-config-check` and verify the embedded CodeDesk service and documentation endpoints.
7. Keep the optional Windows remote-printer component disabled until an independently signed driver and coexistence-safe install/uninstall behavior have been validated.
