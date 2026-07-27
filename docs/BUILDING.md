# Building CodeDesk

## Source layout and tools

Clone this repository normally; no submodules are required. The client/root workspace requires Rust 1.87 or newer; the independent server workspace declares Rust 1.85. Install Git, CMake, a C/C++ toolchain, and the native dependencies required by the target platform. Flutter UI builds additionally require the Flutter SDK and the platform SDK (Android, Xcode, Windows, or Linux desktop).

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
  --overlay-ports="$PWD/res/vcpkg" \
  --x-install-root="$VCPKG_ROOT/installed"

make build-client
```

If the vcpkg repository already exists, update or reuse it instead of cloning it again. The root Makefile exports the same `VCPKG_ROOT` and `$VCPKG_ROOT/installed` defaults for client builds. The shared installed directory is required because some inherited native crates do not support a separate `VCPKG_INSTALLED_ROOT`.

For the current Flutter UI, follow the target setup under `flutter/` and use the repository's `build.py`/CI flow. The Rust library keeps the internal name `librustdesk` for FFI compatibility; user-facing application artifacts are named CodeDesk.

## Desktop application packages

Build the current Flutter macOS application and wrap it in a DMG on macOS:

```bash
make package-macos
```

The packaging script installs the project-pinned Flutter Rust Bridge generator
when necessary and regenerates the ignored Rust, Dart, and C bridge artifacts.
Flutter 3.24.5 must be installed and available in `PATH`; use
`make package-macos FLUTTER=/path/to/flutter/bin/flutter` for a nonstandard SDK
location. The version is pinned because later Flutter releases have breaking
selection and theme API changes that are incompatible with the current UI dependencies.
On macOS and Linux, the Makefile also automatically detects an SDK installed at
`$HOME/.local/share/flutter/bin/flutter`.

The output is `target/packages/codedesk-<version>-macos-<arch>.dmg`. The
local application receives an ad-hoc signature so its bundled frameworks can
launch, but it is not Developer ID signed or notarized. Distributors must replace
the ad-hoc signature with their own Apple signing and notarization workflow.

Build the current Flutter Windows application and portable installer EXE on Windows:

```bash
make package-windows
```

The output is `target/packages/codedesk-<version>-windows-<arch>-install.exe`.
The EXE is unsigned unless the distributor adds its own Windows code-signing
workflow. If Python uses a nonstandard executable name, override it with
`PYTHON=<command>`. Both package targets must run natively on their target
operating system; they are not cross-compilation commands.

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

## Containers

Container build context must be the repository root so `libs/hbb_common` is available:

```bash
docker build -f server/docker/Dockerfile -t codedesk-server .
docker build -f server/docker-classic/Dockerfile -t codedesk-server-classic .
```

Do not run these builds with `server/` as the Docker context.

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

The root Makefile loads `.env` for client checks, tests, builds, and desktop
packaging. `build.py` forwards the same values to Flutter as `--dart-define`
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
