FROM rust:1.85-bookworm AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends clang cmake libssl-dev libsodium-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /source
COPY server/Cargo.toml server/Cargo.lock server/build.rs ./server/
COPY server/src ./server/src
COPY server/db_v2.sqlite3 ./server/db_v2.sqlite3
COPY libs/hbb_common ./libs/hbb_common
RUN DATABASE_URL=sqlite://./db_v2.sqlite3 cargo build --manifest-path server/Cargo.toml --locked --release --bins

FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libsodium23 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /source/server/target/release/hbbs /usr/bin/hbbs
COPY --from=builder /source/server/target/release/hbbr /usr/bin/hbbr
WORKDIR /root
ENV HOME=/root
CMD ["hbbs"]
