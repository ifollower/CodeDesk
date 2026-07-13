# Privacy Principles

CodeDesk is designed as a self-hostable remote workspace.

- Rendezvous and relay services must not receive AI API keys, source files, or terminal content as part of AI coding features.
- Future coding integrations must run on the controlled development machine and access only user-authorized workspaces.
- A local adapter failure must fall back to the general remote desktop or terminal instead of routing sensitive content through CodeDesk Server.
- Builds must clearly disclose the rendezvous, relay, update, and telemetry services they use.
- Public CodeDesk binaries must default to CodeDesk-controlled or user-configured infrastructure, not RustDesk public services.

The independent baseline currently preserves inherited connection defaults for compatibility testing. It is not a public-release privacy configuration. See [README.md](README.md#server-policy-during-the-baseline-phase).

Before collecting telemetry or operating a hosted service, the project must publish a service-specific privacy notice covering data categories, purpose, retention, processors, user controls, and contact details. This repository policy does not substitute for such a notice.
