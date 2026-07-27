# Privacy Principles

CodeDesk is designed as a self-hostable remote workspace.

- Rendezvous and relay services must not receive AI API keys, source files, or terminal content as part of AI coding features.
- Future coding integrations must run on the controlled development machine and access only user-authorized workspaces.
- A local adapter failure must fall back to the general remote desktop or terminal instead of routing sensitive content through CodeDesk Server.
- Builds must clearly disclose the rendezvous, relay, update, and telemetry services they use.
- Public CodeDesk binaries must default to CodeDesk-controlled or user-configured infrastructure, not RustDesk public services.

The repository defaults leave vendor rendezvous, API, update, documentation, and privacy endpoints empty. A build distributor must configure and disclose any hosted services it enables. User-configured self-hosted servers continue to take precedence over build defaults.

Before collecting telemetry or operating a hosted service, the project must publish a service-specific privacy notice covering data categories, purpose, retention, processors, user controls, and contact details. This repository policy does not substitute for such a notice.
