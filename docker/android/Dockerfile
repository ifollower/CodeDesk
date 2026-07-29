FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
# The base image does not contain CA certificates yet, so the bootstrap mirror
# must use HTTP. Later downloads use HTTPS after ca-certificates is installed.
ARG UBUNTU_MIRROR=http://mirrors.aliyun.com
ARG RUSTUP_DIST_SERVER=https://rsproxy.cn
ARG RUSTUP_UPDATE_ROOT=https://rsproxy.cn/rustup
ARG CODEDESK_CARGO_MIRROR_INDEX=sparse+https://rsproxy.cn/index/
ARG RUST_VERSION=1.87.0
ARG FLUTTER_VERSION=3.24.5
ARG ANDROID_COMMAND_LINE_TOOLS=11076708
ARG ANDROID_PLATFORM=34
ARG ANDROID_BUILD_TOOLS=34.0.0
ARG ANDROID_NDK_VERSION=26.3.11579264
ARG CARGO_NDK_VERSION=3.5.4
ARG FLUTTER_RUST_BRIDGE_CODEGEN_VERSION=1.80.1
ARG VCPKG_COMMIT=120deac3062162151622ca4860575a33844ba10b
ARG BUNDLETOOL_VERSION=1.17.2

ENV ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    ANDROID_NDK_HOME=/opt/android-sdk/ndk/26.3.11579264 \
    RUSTUP_HOME=/opt/rustup \
    RUSTUP_DIST_SERVER=${RUSTUP_DIST_SERVER} \
    RUSTUP_UPDATE_ROOT=${RUSTUP_UPDATE_ROOT} \
    CARGO_HOME=/opt/cargo \
    VCPKG_ROOT=/opt/vcpkg \
    VCPKG_FORCE_SYSTEM_BINARIES=1 \
    FLUTTER_HOME=/opt/flutter \
    PATH=/opt/flutter/bin:/opt/cargo/bin:/opt/android-sdk/cmdline-tools/latest/bin:/opt/android-sdk/platform-tools:${PATH}

RUN architecture="$(dpkg --print-architecture)" \
    && if [ "${architecture}" = "amd64" ]; then \
        ubuntu_repository="${UBUNTU_MIRROR}/ubuntu"; \
    else \
        ubuntu_repository="${UBUNTU_MIRROR}/ubuntu-ports"; \
    fi \
    && sed -i \
        -e "s|http://archive.ubuntu.com/ubuntu|${ubuntu_repository}|g" \
        -e "s|http://security.ubuntu.com/ubuntu|${ubuntu_repository}|g" \
        -e "s|http://ports.ubuntu.com/ubuntu-ports|${ubuntu_repository}|g" \
        /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        autoconf automake bison build-essential ca-certificates clang cmake curl \
        file flex git libclang-dev libglu1-mesa libssl-dev libtool nasm ninja-build \
        openjdk-17-jdk-headless patch perl pkg-config python3 python3-pip \
        unzip wget xz-utils yasm zip \
    && git config --system --add safe.directory "${FLUTTER_HOME}" \
    && git config --system --add safe.directory "${VCPKG_ROOT}" \
    && git config --system --add safe.directory /workspace \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p "${ANDROID_HOME}/cmdline-tools" /opt/cargo /opt/rustup \
    && curl --fail --location --silent --show-error \
        "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_COMMAND_LINE_TOOLS}_latest.zip" \
        --output /tmp/android-tools.zip \
    && unzip -q /tmp/android-tools.zip -d "${ANDROID_HOME}/cmdline-tools" \
    && mv "${ANDROID_HOME}/cmdline-tools/cmdline-tools" "${ANDROID_HOME}/cmdline-tools/latest" \
    && rm /tmp/android-tools.zip \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager \
        "platform-tools" \
        "platforms;android-${ANDROID_PLATFORM}" \
        "build-tools;${ANDROID_BUILD_TOOLS}" \
        "ndk;${ANDROID_NDK_VERSION}" \
        "cmake;3.22.1"

COPY cargo-config.toml /opt/cargo/config.toml

RUN sed -i \
        "s|__CARGO_REGISTRY_INDEX__|${CODEDESK_CARGO_MIRROR_INDEX}|" \
        /opt/cargo/config.toml \
    && curl --proto '=https' --tlsv1.2 --fail --silent --show-error \
        https://sh.rustup.rs \
        | sh -s -- -y --no-modify-path --default-toolchain "${RUST_VERSION}" \
    && rustup target add aarch64-linux-android

RUN cargo install cargo-ndk --version "${CARGO_NDK_VERSION}" --locked

RUN cargo install flutter_rust_bridge_codegen \
    --version "${FLUTTER_RUST_BRIDGE_CODEGEN_VERSION}" \
    --features uuid --locked

ARG FLUTTER_GIT_URL=https://gitee.com/mirrors/Flutter.git
RUN git clone --depth 1 --branch "${FLUTTER_VERSION}" \
        "${FLUTTER_GIT_URL}" "${FLUTTER_HOME}" \
    && flutter config --no-analytics \
    && flutter precache --android

RUN git init "${VCPKG_ROOT}" \
    && git -C "${VCPKG_ROOT}" remote add origin https://github.com/microsoft/vcpkg.git \
    && git -C "${VCPKG_ROOT}" fetch --depth 1 origin "${VCPKG_COMMIT}" \
    && git -C "${VCPKG_ROOT}" checkout --detach FETCH_HEAD \
    && "${VCPKG_ROOT}/bootstrap-vcpkg.sh" -disableMetrics

RUN curl --fail --location --silent --show-error \
        "https://github.com/google/bundletool/releases/download/${BUNDLETOOL_VERSION}/bundletool-all-${BUNDLETOOL_VERSION}.jar" \
        --output /opt/bundletool.jar

COPY build-android.sh /opt/codedesk/build-android.sh
RUN chmod +x /opt/codedesk/build-android.sh \
    && chmod -R a+rX "${ANDROID_HOME}" "${RUSTUP_HOME}" "${CARGO_HOME}" "${VCPKG_ROOT}" \
    && chmod -R a+rwX "${FLUTTER_HOME}"

WORKDIR /workspace
ENTRYPOINT ["/opt/codedesk/build-android.sh"]
