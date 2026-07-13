# Contributing to CodeDesk

Thank you for helping build CodeDesk. The project accepts focused bug fixes, portability work, tests, documentation, and features that fit the published roadmap.

## Before opening a pull request

- Search existing issues and discuss large behavioral, protocol, security, or product changes first.
- Base work on `main` and keep each commit reviewable.
- Avoid unrelated refactors or formatting-only changes.
- Preserve protocol compatibility: never delete, renumber, or reuse an existing protobuf field number.
- Do not change mature capture, input, audio/video, authentication, hole-punching, or relay behavior without a scoped issue and regression evidence.
- Add or update tests for the changed behavior.
- Do not commit credentials, AI API keys, production server keys, personal configuration, logs, or captured user content.

## Development checks

Run the checks relevant to your change from the repository root:

```bash
cargo fmt --all -- --check
cargo test -p hbb_common --locked
cargo build --locked
cargo fmt --manifest-path server/Cargo.toml --all -- --check
cargo test --manifest-path server/Cargo.toml --locked
```

Platform and Flutter changes also need the appropriate native and Flutter checks described in [docs/BUILDING.md](docs/BUILDING.md).

## Pull request checklist

- Explain the user-visible outcome and compatibility impact.
- Identify platforms tested and checks run.
- Separate current behavior from planned behavior in documentation.
- Retain relevant upstream copyright and attribution notices.
- Add `Signed-off-by` to every commit.

## Developer Certificate of Origin

CodeDesk uses the [Developer Certificate of Origin 1.1](https://developercertificate.org/) (DCO). By adding a sign-off, you certify that you have the right to submit the contribution under the project's license.

Create signed-off commits with:

```bash
git commit -s -m "describe the change"
```

The sign-off must use your real name and an email address you control:

```text
Signed-off-by: Your Name <you@example.com>
```

## Conduct and security

Participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report vulnerabilities privately according to [SECURITY.md](SECURITY.md), not in a public issue.
