# CodeDesk Roadmap

This document describes direction, not a promise that every item is implemented.

## Baseline: independent repository

- Consolidate client, server, and one `libs/hbb_common` into ordinary repository directories.
- Preserve separate client and server Cargo workspaces and lockfiles.
- Establish CodeDesk branding, independent system identifiers, attribution, governance, and build checks.
- Verify remote-control behavior against the imported baseline.
- Prepare self-hosted-server onboarding before distributing public binaries.

## Phase 1: reliable mobile coding control

- Preserve and harden the general remote desktop and persistent terminal.
- Improve mobile Chinese input, multiline prompt composition, coding shortcuts, and voice-to-text input.
- Improve terminal/session reconnection and recovery after phone backgrounding or network changes.

## Phase 2: Coding Workspace

- Combine terminal, desktop, file navigation, and forwarded development-service previews.
- Add configurable launch entries for Codex, Claude Code, ZCode, and ordinary shells.
- Keep every workflow usable through general remote control when specialized integration is absent.

## Phase 3: authorized development context

- Show Git status and changed files inside a user-selected workspace.
- Provide explicit diff viewing, test commands, and local development-service previews.
- Make workspace boundaries and every command/action visible and user-controlled.

## Phase 4: local AI task adapters

- Report waiting-for-input, approval-required, completed, and failed states from supported tools.
- Keep adapters local to the controlled host and narrowly scoped.
- Fall back automatically to the ordinary terminal if an adapter is unavailable or incompatible.

## Non-goals and constraints

- CodeDesk remains a general remote-control product, not a controller limited to selected AI tools.
- CodeDesk Server will not proxy model APIs or store AI API keys, source code, or terminal content.
- Core remote-control behavior is changed only with compatibility tests and a specific need.
- The project evolves independently; it does not maintain automated RustDesk upstream synchronization.
