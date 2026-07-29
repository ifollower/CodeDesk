# CodeDesk Server

This directory contains CodeDesk's self-hostable ID/rendezvous server (`hbbs`), relay server (`hbbr`), and server utilities. It is derived from RustDesk Server OSS and remains licensed under GNU AGPL-3.0; see [../NOTICE](../NOTICE) and [LICENSE](LICENSE).

CodeDesk Server is part of the independent CodeDesk repository and is not an official RustDesk service or product.

## Shared source

The server uses the repository's only `hbb_common` source at `../libs/hbb_common`. The server remains a separate Cargo workspace with its own lockfile. No submodule checkout is required.

## Build

Run from the CodeDesk repository root:

```bash
DATABASE_URL=sqlite://./db_v2.sqlite3 \
  cargo build --manifest-path server/Cargo.toml --locked --release --bins
```

Generated binaries are placed in `server/target/release/`:

- `hbbs` — ID/rendezvous and NAT traversal coordination
- `hbbr` — relay service
- `codedesk-utils` — server administration utilities

The protocol-facing `hbbs` and `hbbr` names are retained for deployment compatibility.

## Containers and packages

Docker and Debian jobs must use a full CodeDesk clone. For Docker, use the repository root as context:

```bash
make package-server
make server-up
make server-logs
make server-down

# Export both supported architectures as Docker image tar files.
make package-server-all
```

The image runs `hbbs` and `hbbr` under s6-overlay and persists their data in
`/data`. Set `RELAY=<public-host>:21117` for deployments that advertise the
relay service. Using `server/` alone as a Docker build context will omit the
shared library and is unsupported.

## Security boundary

The server coordinates remote connectivity. Planned AI coding features must not turn it into a model proxy or send AI API keys, source files, or terminal content to rendezvous/relay infrastructure.
