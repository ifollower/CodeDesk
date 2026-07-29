#!/usr/bin/env bash

set -euo pipefail

PROFILE=dev
FORMAT=apk
VERSION=
BUILD_NUMBER=

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile) PROFILE="$2"; shift 2 ;;
        --format) FORMAT="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        --build-number) BUILD_NUMBER="$2"; shift 2 ;;
        *) echo "Unknown Android build argument: $1" >&2; exit 2 ;;
    esac
done

if [[ "$PROFILE" != "dev" && "$PROFILE" != "release" ]]; then
    echo "PROFILE must be dev or release" >&2
    exit 2
fi
if [[ "$FORMAT" != "apk" && "$FORMAT" != "aab" && "$FORMAT" != "all" ]]; then
    echo "FORMAT must be apk, aab, or all" >&2
    exit 2
fi
if [[ -z "$VERSION" || -z "$BUILD_NUMBER" ]]; then
    echo "--version and --build-number are required" >&2
    exit 2
fi

export HOME="${CODEDESK_ANDROID_CACHE:-/workspace/target/docker-cache/android}/home"
export CARGO_HOME="${CODEDESK_ANDROID_CACHE:-/workspace/target/docker-cache/android}/cargo"
export GRADLE_USER_HOME="${CODEDESK_ANDROID_CACHE:-/workspace/target/docker-cache/android}/gradle"
export PUB_CACHE="${CODEDESK_ANDROID_CACHE:-/workspace/target/docker-cache/android}/pub"
export VCPKG_DOWNLOADS="${CODEDESK_ANDROID_CACHE:-/workspace/target/docker-cache/android}/vcpkg-downloads"
VCPKG_INSTALLED_ROOT="${VCPKG_ROOT}/installed"
VCPKG_BUILDTREES_ROOT="${CODEDESK_ANDROID_CACHE:-/workspace/target/docker-cache/android}/vcpkg-buildtrees"
VCPKG_PACKAGES_ROOT="${CODEDESK_ANDROID_CACHE:-/workspace/target/docker-cache/android}/vcpkg-packages"

mkdir -p \
    "$HOME" "$CARGO_HOME" "$GRADLE_USER_HOME" "$PUB_CACHE" \
    "$VCPKG_DOWNLOADS" "$VCPKG_INSTALLED_ROOT" \
    "$VCPKG_BUILDTREES_ROOT" "$VCPKG_PACKAGES_ROOT" \
    target/packages/android flutter/android/app/src/main/jniLibs/arm64-v8a

export VCPKG_INSTALLED_ROOT

"${VCPKG_ROOT}/vcpkg" install \
    --triplet arm64-android \
    --x-manifest-root=/workspace \
    --x-install-root="$VCPKG_INSTALLED_ROOT" \
    --x-buildtrees-root="$VCPKG_BUILDTREES_ROOT" \
    --x-packages-root="$VCPKG_PACKAGES_ROOT"

(cd flutter && flutter pub get)
flutter_rust_bridge_codegen \
    --rust-input ./src/flutter_ffi.rs \
    --dart-output ./flutter/lib/generated_bridge.dart \
    --c-output ./flutter/macos/Runner/bridge_generated.h \
    --class-name Rustdesk

RUST_BUILD_ARGS=(
    ndk --platform 21 --target aarch64-linux-android
    build --locked --features flutter,hwcodec
)
RUST_OUTPUT=debug
FLUTTER_MODE=debug
if [[ "$PROFILE" == "release" ]]; then
    RUST_BUILD_ARGS+=(--release)
    RUST_OUTPUT=release
    FLUTTER_MODE=release
fi
cargo "${RUST_BUILD_ARGS[@]}"

cp \
    "target/aarch64-linux-android/${RUST_OUTPUT}/liblibrustdesk.so" \
    flutter/android/app/src/main/jniLibs/arm64-v8a/librustdesk.so

if [[ "$PROFILE" == "release" ]]; then
    if [[ ! -r /run/secrets/android-keystore || ! -r /run/secrets/android-signing.properties ]]; then
        echo "Android release signing secrets were not mounted" >&2
        exit 1
    fi
    export ANDROID_KEY_PROPERTIES_FILE=/run/secrets/android-signing.properties
fi

DART_DEFINES=()
BUILD_KEYS=(
    CODEDESK_SOURCE_URL CODEDESK_ISSUES_URL CODEDESK_WEBSITE_URL
    CODEDESK_DOWNLOAD_URL CODEDESK_PRIVACY_URL CODEDESK_DOCS_URL
    CODEDESK_DOCS_MOBILE_URL CODEDESK_DOCS_LINUX_PERMISSIONS_URL
    CODEDESK_DOCS_X11_URL CODEDESK_DOCS_LINUX_LOGIN_URL
    CODEDESK_DOCS_HEADLESS_URL CODEDESK_DOCS_WHITELIST_URL
    CODEDESK_API_URL CODEDESK_UPDATE_API_URL
    CODEDESK_RENDEZVOUS_SERVERS CODEDESK_RENDEZVOUS_PUBLIC_KEY
)
for key in "${BUILD_KEYS[@]}"; do
    DART_DEFINES+=("--dart-define=${key}=${!key:-}")
done

COMMON_ARGS=(
    "--${FLUTTER_MODE}"
    --target-platform android-arm64
    --build-name "$VERSION"
    --build-number "$BUILD_NUMBER"
    "${DART_DEFINES[@]}"
)
DART_SYMBOL_ROOT="/workspace/target/android-symbols/dart-${VERSION}"
if [[ "$PROFILE" == "release" ]]; then
    rm -rf "$DART_SYMBOL_ROOT"
fi

if [[ "$FORMAT" == "apk" || "$FORMAT" == "all" ]]; then
    APK_ARGS=("${COMMON_ARGS[@]}")
    if [[ "$PROFILE" == "release" ]]; then
        APK_ARGS+=(--obfuscate "--split-debug-info=${DART_SYMBOL_ROOT}/apk")
    fi
    (cd flutter && flutter build apk "${APK_ARGS[@]}")
    cp \
        "flutter/build/app/outputs/flutter-apk/app-${FLUTTER_MODE}.apk" \
        "target/packages/android/codedesk-${VERSION}-android-arm64.apk"
fi

if [[ "$FORMAT" == "aab" || "$FORMAT" == "all" ]]; then
    if [[ "$PROFILE" != "release" ]]; then
        echo "AAB packaging requires PROFILE=release" >&2
        exit 2
    fi
    AAB_ARGS=("${COMMON_ARGS[@]}")
    AAB_ARGS+=(--obfuscate "--split-debug-info=${DART_SYMBOL_ROOT}/aab")
    (cd flutter && flutter build appbundle "${AAB_ARGS[@]}")
    cp \
        flutter/build/app/outputs/bundle/release/app-release.aab \
        "target/packages/android/codedesk-${VERSION}-android-arm64.aab"
    java -jar /opt/bundletool.jar validate \
        --bundle "target/packages/android/codedesk-${VERSION}-android-arm64.aab"
fi

SYMBOL_DIR="target/packages/android/symbols-${VERSION}"
rm -rf "$SYMBOL_DIR"
mkdir -p "$SYMBOL_DIR"
cp "target/aarch64-linux-android/${RUST_OUTPUT}/liblibrustdesk.so" "$SYMBOL_DIR/"
if [[ -d "$DART_SYMBOL_ROOT" ]]; then
    cp -R "$DART_SYMBOL_ROOT" "$SYMBOL_DIR/dart"
fi
(cd "$SYMBOL_DIR/.." && zip -qr "codedesk-${VERSION}-android-symbols.zip" "symbols-${VERSION}")
rm -rf "$SYMBOL_DIR"

echo "Android packages:"
find target/packages/android -maxdepth 1 -type f -print
