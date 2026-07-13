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

For the current Flutter UI, follow the target setup under `flutter/` and use the repository's `build.py`/CI flow. The Rust library keeps the internal name `librustdesk` for FFI compatibility; user-facing application artifacts are named CodeDesk.

## Server

Build every server binary against the root shared library:

```bash
DATABASE_URL=sqlite://./db_v2.sqlite3 \
  cargo build --manifest-path server/Cargo.toml --locked --release --bins
```

Expected binaries are `hbbs`, `hbbr`, and `rustdesk-utils`. Their inherited binary names remain stable for deployment compatibility.

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

## Source link in application builds

The About page deliberately has no guessed repository URL. Distributors must inject the exact source location for their build:

```bash
flutter build <target> --dart-define=CODEDESK_SOURCE_URL=https://example.org/owner/codedesk
```

## Release gates

Before publishing a CodeDesk binary:

1. Test the shared library, client, all server binaries, and relevant Flutter/native targets.
2. Run connection integration tests for registration, direct connection, forced relay, reconnect, remote desktop/input, file transfer, and terminal.
3. Verify protobuf compatibility and compare behavior with the imported baseline.
4. Build Docker, Debian, and release artifacts from a fresh ordinary clone.
5. Verify CodeDesk and RustDesk coexist without sharing application IDs, services, storage, or deep links.
6. Configure self-hosted CodeDesk infrastructure and remove inherited public-service/update/privacy defaults.
7. Keep the optional Windows remote-printer component disabled until an independently signed driver and coexistence-safe install/uninstall behavior have been validated.
