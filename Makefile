CARGO ?= cargo
DOCKER ?= docker
SERVER_MANIFEST := server/Cargo.toml
SERVER_IMAGE ?= codedesk-server
DATABASE_URL ?= sqlite://$(abspath server/db_v2.sqlite3)
VCPKG_ROOT ?= $(HOME)/.local/share/vcpkg
VCPKG_INSTALLED_ROOT ?= $(VCPKG_ROOT)/installed
ENV_FILE ?= .env

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

.DEFAULT_GOAL := help

.PHONY: help check check-client check-server test test-common test-server build build-client build-server package-macos package-windows docker-server release-config-check

help:
	@echo "make check           Check the client and all server binaries"
	@echo "make test            Test hbb_common and the server workspace"
	@echo "make build           Build the client and release server binaries"
	@echo "make check-client    Check the CodeDesk client"
	@echo "make check-server    Check hbbs, hbbr, and server utilities"
	@echo "make test-common     Test the shared hbb_common library"
	@echo "make test-server     Test the server workspace"
	@echo "make build-client    Build the Rust core and legacy client"
	@echo "make build-server    Build release server binaries"
	@echo "make package-macos   Build the Flutter macOS app and DMG"
	@echo "make package-windows Build the Flutter Windows installer EXE"
	@echo "make docker-server   Build the CodeDesk server Docker image"
	@echo "make release-config-check Validate .env for a public release"

check: check-client check-server

check-client:
	$(ENV_RUN) $(CARGO) check --package codedesk --locked

check-server:
	$(CARGO) check --manifest-path $(SERVER_MANIFEST) --locked --bins

test: test-common test-server

test-common:
	$(ENV_RUN) $(CARGO) test --package hbb_common --locked

test-server:
	$(CARGO) test --manifest-path $(SERVER_MANIFEST) --locked

build: build-client build-server

build-client:
	$(ENV_RUN) $(CARGO) build --package codedesk --locked

build-server:
	$(CARGO) build --manifest-path $(SERVER_MANIFEST) --locked --release --bins

package-macos:
ifeq ($(HOST_SYSTEM),Darwin)
	$(ENV_RUN) $(PYTHON) build.py --flutter
else
	$(error package-macos must run on macOS)
endif

package-windows:
ifeq ($(HOST_SYSTEM),Windows)
	$(ENV_RUN) $(PYTHON) build.py --flutter
else
	$(error package-windows must run on Windows)
endif

docker-server:
	$(DOCKER) build -f server/docker/Dockerfile -t $(SERVER_IMAGE) .

release-config-check:
	$(PYTHON) scripts/codedesk_env.py check --env-file $(ENV_FILE)
