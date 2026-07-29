FROM rust:1.87.0-bookworm AS builder

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

ARG S6_OVERLAY_VERSION=3.2.0.0
ARG TARGETARCH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl libsodium23 xz-utils \
    && case "${TARGETARCH}" in \
        amd64) S6_ARCH=x86_64 ;; \
        arm64) S6_ARCH=aarch64 ;; \
        *) echo "Unsupported Docker architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl --fail --location --silent --show-error \
        "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz" \
        --output /tmp/s6-overlay-noarch.tar.xz \
    && curl --fail --location --silent --show-error \
        "https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_ARCH}.tar.xz" \
        --output /tmp/s6-overlay-arch.tar.xz \
    && tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz \
    && tar -C / -Jxpf /tmp/s6-overlay-arch.tar.xz \
    && rm /tmp/s6-overlay*.tar.xz \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /run /var/run

COPY --from=builder /source/server/target/release/hbbs /usr/bin/hbbs
COPY --from=builder /source/server/target/release/hbbr /usr/bin/hbbr
COPY --from=builder /source/server/target/release/codedesk-utils /usr/bin/codedesk-utils
COPY server/docker/rootfs /

ENV RELAY=""
ENV ENCRYPTED_ONLY=0

EXPOSE 21115 21116 21116/udp 21117 21118 21119

HEALTHCHECK --interval=10s --timeout=5s CMD /usr/bin/healthcheck.sh

WORKDIR /data
VOLUME /data
ENTRYPOINT ["/init"]
