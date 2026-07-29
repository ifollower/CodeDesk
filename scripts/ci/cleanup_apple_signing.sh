#!/usr/bin/env bash

set -u

if [[ -n "${CODEDESK_TEMP_PROFILE:-}" ]]; then
    rm -f "${CODEDESK_TEMP_PROFILE}"
fi
if [[ -n "${CODEDESK_ORIGINAL_KEYCHAIN:-}" ]]; then
    security list-keychains -d user -s "${CODEDESK_ORIGINAL_KEYCHAIN}" 2>/dev/null || true
    security default-keychain -d user -s "${CODEDESK_ORIGINAL_KEYCHAIN}" 2>/dev/null || true
fi
if [[ -n "${CODEDESK_TEMP_KEYCHAIN:-}" ]]; then
    security delete-keychain "${CODEDESK_TEMP_KEYCHAIN}" 2>/dev/null || true
fi
if [[ -n "${RUNNER_TEMP:-}" ]]; then
    rm -f \
        "${RUNNER_TEMP}/codedesk-developer-id.p12" \
        "${RUNNER_TEMP}/codedesk-distribution.p12" \
        "${RUNNER_TEMP}/codedesk.mobileprovision" \
        "${RUNNER_TEMP}/codedesk-profile.plist" \
        "${RUNNER_TEMP}/codedesk-notary.p8"
fi
