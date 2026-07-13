#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
VERSION=$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$ROOT/server/Cargo.toml" | head -n 1)
ARCH=${DEB_BUILD_ARCH:-$(dpkg-architecture -qDEB_BUILD_ARCH)}
OUT="$ROOT/target/debian"
STAGE="$OUT/codedesk-server-$VERSION"

rm -rf "$STAGE"
mkdir -p "$STAGE/server" "$STAGE/libs" "$OUT"

(cd "$ROOT" && tar cf - \
    server/Cargo.toml server/Cargo.lock server/build.rs server/src \
    server/db_v2.sqlite3 server/rcd server/systemd libs/hbb_common) \
    | (cd "$STAGE" && tar xf -)
cp -a "$ROOT/server/debian" "$STAGE/debian"
sed "s/{{ ARCH }}/$ARCH/g" "$STAGE/debian/control.tpl" > "$STAGE/debian/control"

cd "$STAGE"
dpkg-buildpackage -us -uc -b
