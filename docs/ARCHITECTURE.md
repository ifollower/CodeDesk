# CodeDesk Architecture

## Repository boundary

CodeDesk is one source repository with two Cargo workspaces:

```text
client workspace (./Cargo.toml)       server workspace (server/Cargo.toml)
              \                         /
               \                       /
                libs/hbb_common (shared)
```

The root workspace owns the client and supporting libraries. It explicitly excludes `server/` and `server/ui/`. The server workspace has its own `Cargo.lock`, but both normal and build dependencies resolve `hbb_common` from `../libs/hbb_common`.

This arrangement lets the server remain independently buildable and publishable while guaranteeing that protocol/configuration code has one source in the repository. `libs/hbb_common` is an ordinary directory, not a submodule or subtree.

## Existing remote-control stack

- `src/rendezvous_mediator.rs`: registration and direct/relayed connection setup
- `src/server/`: remote desktop, input, clipboard, audio/video, terminal, and network services
- `libs/scrap/`: platform screen capture
- `libs/enigo/`: platform input simulation
- `libs/clipboard/`: clipboard integration
- `flutter/`: current desktop and mobile UI
- `server/`: `hbbs`, `hbbr`, and administration utilities

Repository integration and branding changes must not alter protocol field numbers, authentication, NAT traversal, relay behavior, media pipelines, or input semantics without a separately reviewed change.

## Planned coding layer

The planned coding experience sits above the general remote-control stack:

```text
Phone / secondary desktop
        |
Coding Workspace UI
        |
Desktop | terminal | files | port previews
        |
Local host adapters (optional, least privilege)
        |
Codex | Claude Code | ZCode | ordinary shell
```

Adapters run on the controlled development machine. They expose small, user-authorized state such as waiting-for-input, approval-required, completed, failed, Git status, selected diffs, or explicit test commands. If an adapter is unavailable, the session remains usable through the ordinary terminal and desktop.

The rendezvous and relay services coordinate connectivity; they are not model gateways and must not receive AI credentials or workspace contents from the coding layer.

## Compatibility rules

- Existing protobuf field numbers are immutable; additions use new numbers.
- Client/server behavior before common-library consolidation is the regression baseline.
- CodeDesk and RustDesk use separate application IDs, services, storage directories, and deep-link schemes.
- Internal names such as `librustdesk` and stable FFI symbols may remain until changing them has a concrete compatibility benefit.
