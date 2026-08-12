CARGO ?= cargo
DOCKER ?= docker
SERVER_MANIFEST := server/Cargo.toml
SERVER_IMAGE ?= codedesk-server
DATABASE_URL ?= sqlite://$(abspath server/db_v2.sqlite3)
ifeq ($(OS),Windows_NT)
CODEDESK_USER_HOME := $(USERPROFILE)
else
CODEDESK_USER_HOME := $(HOME)
endif
VCPKG_ROOT ?= $(CODEDESK_USER_HOME)/.local/share/vcpkg
VCPKG_INSTALLED_ROOT ?= $(VCPKG_ROOT)/installed
ENV_FILE ?= .env
PROFILE ?= dev
FORMAT ?= apk
DISTRIBUTION ?= app-store
VERSION ?=

ifeq ($(OS),Windows_NT)
FLUTTER ?= flutter
PYTHON ?= python
HOST_SYSTEM := Windows
else
LOCAL_FLUTTER := $(HOME)/.local/share/flutter/bin/flutter
FLUTTER ?= $(if $(wildcard $(LOCAL_FLUTTER)),$(LOCAL_FLUTTER),flutter)
PYTHON ?= python3
HOST_SYSTEM := $(shell uname -s)
endif

export DATABASE_URL
export FLUTTER
export PYTHON
export VCPKG_ROOT
export VCPKG_INSTALLED_ROOT

ENV_RUN := $(PYTHON) scripts/codedesk_env.py run --env-file $(ENV_FILE) --
RELEASE := $(PYTHON) scripts/release.py
VERSION_ARG = $(if $(strip $(VERSION)),--version $(VERSION),)

.DEFAULT_GOAL := help

.PHONY: help check check-client check-server check-local-deps test test-common test-server test-release build build-client build-server doctor package-local package-server package-server-all docker-android-builder package-android install-android package-macos package-ios package-windows docker-server server-up server-logs server-down release-check release-config-check

help:
	@echo "make check           Check the client and all server binaries"
	@echo "make test            Test hbb_common and the server workspace"
	@echo "make build           Build the client and release server binaries"
	@echo "make doctor          Check build tools for the current host"
	@echo "make check-client    Check the CodeDesk client"
	@echo "make check-server    Check hbbs, hbbr, and server utilities"
	@echo "make check-local-deps Reject Cargo dependencies that fetch Git repositories"
	@echo "make test-common     Test the shared hbb_common library"
	@echo "make test-server     Test the server workspace"
	@echo "make test-release    Test the unified packaging script"
	@echo "make build-client    Build the Rust core and legacy client"
	@echo "make build-server    Build release server binaries"
	@echo "make package-local   Package every target supported by this host"
	@echo "make package-server  Build and load the host-architecture server image"
	@echo "make package-server-all Export amd64 and arm64 server image tar files"
	@echo "make docker-android-builder Build the pinned Android builder image"
	@echo "make package-android Build Android in Docker (PROFILE=dev|release FORMAT=apk|aab|all)"
	@echo "make install-android Install the packaged APK on an adb device"
	@echo "make package-macos   Build a Universal 2 DMG on macOS"
	@echo "make package-ios     Build an iOS IPA on macOS"
	@echo "make package-windows Build the Windows x64 installer EXE"
	@echo "make server-up       Build and start the local server container"
	@echo "make server-logs     Follow local server logs"
	@echo "make server-down     Stop the local server container"
	@echo "make release-check VERSION=X.Y.Z Validate versions and public release config"
	@echo "make release-config-check Validate .env for a public release"

check: check-client check-server

check-client:
	$(ENV_RUN) $(CARGO) check --package codedesk --locked

check-server:
	$(CARGO) check --manifest-path $(SERVER_MANIFEST) --locked --bins

check-local-deps:
	$(PYTHON) scripts/check_local_dependencies.py

test: test-common test-server test-release

test-common:
	$(ENV_RUN) $(CARGO) test --package hbb_common --locked

test-server:
	$(CARGO) test --manifest-path $(SERVER_MANIFEST) --locked

test-release:
	$(PYTHON) -m unittest discover -s scripts -p 'test_*.py'

build: build-client build-server

build-client:
	$(ENV_RUN) $(CARGO) build --package codedesk --locked

build-server:
	$(CARGO) build --manifest-path $(SERVER_MANIFEST) --locked --release --bins

doctor:
	$(RELEASE) doctor

package-local:
ifeq ($(HOST_SYSTEM),Darwin)
	$(MAKE) package-server PROFILE=$(PROFILE)
	$(MAKE) package-android PROFILE=$(PROFILE) FORMAT=$(FORMAT)
	$(MAKE) package-macos PROFILE=$(PROFILE)
	$(MAKE) package-ios PROFILE=$(PROFILE) DISTRIBUTION=$(DISTRIBUTION)
else ifeq ($(HOST_SYSTEM),Windows)
	$(MAKE) package-server PROFILE=$(PROFILE)
	$(MAKE) package-android PROFILE=$(PROFILE) FORMAT=$(FORMAT)
	$(MAKE) package-windows PROFILE=$(PROFILE)
else
	$(MAKE) package-server PROFILE=$(PROFILE)
	$(MAKE) package-android PROFILE=$(PROFILE) FORMAT=$(FORMAT)
endif

package-server:
	$(RELEASE) package server $(VERSION_ARG)

package-server-all:
	$(RELEASE) package server --all-architectures $(VERSION_ARG)

docker-android-builder:
	$(RELEASE) build-image android

package-android:
	$(ENV_RUN) $(RELEASE) package android --profile $(PROFILE) --format $(FORMAT) $(VERSION_ARG)

install-android:
	$(RELEASE) install-android $(VERSION_ARG)

package-macos:
ifeq ($(HOST_SYSTEM),Darwin)
	$(ENV_RUN) $(RELEASE) package macos --profile $(PROFILE) $(VERSION_ARG)
else
	$(error package-macos must run on macOS)
endif

package-ios:
ifeq ($(HOST_SYSTEM),Darwin)
	$(ENV_RUN) $(RELEASE) package ios --profile $(PROFILE) --distribution $(DISTRIBUTION) $(VERSION_ARG)
else
	$(error package-ios must run on macOS)
endif

package-windows:
ifeq ($(HOST_SYSTEM),Windows)
	$(ENV_RUN) $(RELEASE) package windows --profile $(PROFILE) $(VERSION_ARG)
else
	$(error package-windows must run on Windows)
endif

docker-server: package-server

server-up: package-server
	CODEDESK_SERVER_IMAGE=$(SERVER_IMAGE):local $(DOCKER) compose -f server/docker-compose.yml up -d --no-build

server-logs:
	$(DOCKER) compose -f server/docker-compose.yml logs -f

server-down:
	$(DOCKER) compose -f server/docker-compose.yml down

release-check:
	$(ENV_RUN) $(RELEASE) release-check --version $(VERSION)

release-config-check:
	$(PYTHON) scripts/codedesk_env.py check --env-file $(ENV_FILE)
