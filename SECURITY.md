# Security Policy

## Supported versions

CodeDesk is currently establishing its first independent baseline. Until the first public release, security fixes are applied to the `main` branch only. A supported-release table will be published when versioned binaries are available.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or include exploit details, credentials, private keys, source code, terminal output, or user data in public discussions.

Use the repository host's private security-advisory reporting feature to contact the CodeDesk maintainers. If the repository is mirrored somewhere without private reporting, contact a maintainer privately and ask for a secure disclosure channel before sending details.

Please include:

- Affected commit or version and platform
- Impact and required attacker capabilities
- Minimal reproduction steps or a proof of concept
- Whether the issue affects the client, `hbbs`, `hbbr`, or shared protocol code
- Any suggested mitigation, if known

Maintainers will acknowledge a complete report, coordinate validation and remediation, and credit reporters who wish to be credited. Timelines depend on severity and cross-platform impact.

## Project responsibility

CodeDesk evolves independently and does not rely on RustDesk upstream monitoring or automatic merges. CodeDesk maintainers are responsible for assessing and addressing security issues in this repository.
