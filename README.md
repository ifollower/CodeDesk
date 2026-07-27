# CodeDesk

CodeDesk is an independent, open-source remote workspace for controlling a primary development machine from a phone or another Windows/macOS device. It keeps a general-purpose remote desktop at its core and will add workflows for AI-assisted coding tools such as Codex, Claude Code, ZCode, and ordinary shells.

> CodeDesk is based on the open-source [RustDesk](https://github.com/rustdesk/rustdesk) client and [RustDesk Server OSS](https://github.com/rustdesk/rustdesk-server). CodeDesk is not affiliated with, endorsed by, or officially partnered with the RustDesk project or its commercial entities.

[中文说明](docs/README-ZH.md) · [Roadmap](docs/ROADMAP.md) · [Architecture](docs/ARCHITECTURE.md) · [Build guide](docs/BUILDING.md)

## Current status

This repository is at the independent-baseline stage.

Available today through the inherited and integrated remote-control stack:

- Cross-platform remote desktop and input control
- File transfer and clipboard synchronization
- TCP port forwarding
- Persistent remote terminal
- Self-hosted ID/rendezvous and relay services (`hbbs` and `hbbr`)

Planned, not implemented yet:

- Mobile-first prompt editing, coding shortcuts, voice input, and resilient reconnection
- A Coding Workspace combining terminal, desktop, files, and service previews
- Configurable launchers for Codex, Claude Code, ZCode, and normal shells
- User-authorized Git status, diffs, tests, and local development previews
- Local adapters for AI task states, approvals, and completion notifications

See the [roadmap](docs/ROADMAP.md) for boundaries and milestones. In particular, CodeDesk Server is not intended to become a model proxy: API keys, source code, and terminal content must not be sent to rendezvous or relay services.

## Repository layout

```text
.
├── src/                 # Rust client and remote-control services
├── flutter/             # Current desktop and mobile UI
├── libs/hbb_common/     # The single shared protocol/configuration library
├── libs/scrap/          # Screen capture
├── libs/enigo/          # Input control
├── libs/clipboard/      # Clipboard integration
└── server/              # hbbs, hbbr, and server utilities
```

The client and server share `libs/hbb_common` as ordinary repository source. They intentionally remain separate Cargo workspaces with separate lockfiles. There are no Git submodules, upstream synchronization jobs, or required files outside this repository.

## Build

Prerequisites vary by target platform. The canonical commands are run from the repository root:

```bash
# Shared library
make test-common

# Client (additional native/Flutter prerequisites are required)
make build-client

# Server workspace
make build-server
```

Read [docs/BUILDING.md](docs/BUILDING.md) before building packages or container images.

## Network defaults

CodeDesk does not embed RustDesk public rendezvous, update, API, documentation, or privacy endpoints. Development builds work with empty vendor defaults and require the user to configure an ID Server. Distributors provide CodeDesk-controlled public defaults at build time through the root `.env`; see [`.env.example`](.env.example) and the [build guide](docs/BUILDING.md#codedesk-build-configuration).

## Security and responsible use

Use CodeDesk only on devices and networks you own or are authorized to administer. Unauthorized access, monitoring, or control is prohibited. See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Contributing

Contributions are accepted under the [Developer Certificate of Origin](CONTRIBUTING.md#developer-certificate-of-origin). Please also read the [Code of Conduct](CODE_OF_CONDUCT.md).

## License and attribution

CodeDesk is distributed under the GNU Affero General Public License v3.0. The client and server license texts are available in [LICENSE](LICENSE) and [server/LICENSE](server/LICENSE).

The repository contains code derived from RustDesk, RustDesk Server OSS, and other third-party projects. Existing copyright notices remain with their respective owners; new CodeDesk work is attributed to CodeDesk Contributors. See [NOTICE](NOTICE) for details.
