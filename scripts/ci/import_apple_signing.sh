#!/usr/bin/env bash

set -euo pipefail

: "${RUNNER_TEMP:?RUNNER_TEMP is required}"
: "${GITHUB_ENV:?GITHUB_ENV is required}"
: "${APPLE_CERTIFICATE_PASSWORD:?APPLE_CERTIFICATE_PASSWORD is required}"
: "${APPLE_DEVELOPER_ID_P12_BASE64:?APPLE_DEVELOPER_ID_P12_BASE64 is required}"
: "${APPLE_DISTRIBUTION_P12_BASE64:?APPLE_DISTRIBUTION_P12_BASE64 is required}"
: "${APPLE_PROVISIONING_PROFILE_BASE64:?APPLE_PROVISIONING_PROFILE_BASE64 is required}"
: "${APPLE_NOTARY_PRIVATE_KEY_BASE64:?APPLE_NOTARY_PRIVATE_KEY_BASE64 is required}"

decode_secret() {
    SECRET_VALUE="$1" python3 - "$2" <<'PY'
import base64
import os
import sys
from pathlib import Path

Path(sys.argv[1]).write_bytes(base64.b64decode(os.environ["SECRET_VALUE"], validate=True))
PY
}

KEYCHAIN_PATH="${RUNNER_TEMP}/codedesk-signing.keychain-db"
ORIGINAL_KEYCHAIN="$(security default-keychain -d user | tr -d '"')"
KEYCHAIN_PASSWORD="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)"
DEVELOPER_P12="${RUNNER_TEMP}/codedesk-developer-id.p12"
DISTRIBUTION_P12="${RUNNER_TEMP}/codedesk-distribution.p12"
PROFILE_SOURCE="${RUNNER_TEMP}/codedesk.mobileprovision"
NOTARY_KEY="${RUNNER_TEMP}/codedesk-notary.p8"

decode_secret "${APPLE_DEVELOPER_ID_P12_BASE64}" "${DEVELOPER_P12}"
decode_secret "${APPLE_DISTRIBUTION_P12_BASE64}" "${DISTRIBUTION_P12}"
decode_secret "${APPLE_PROVISIONING_PROFILE_BASE64}" "${PROFILE_SOURCE}"
decode_secret "${APPLE_NOTARY_PRIVATE_KEY_BASE64}" "${NOTARY_KEY}"
chmod 600 "${DEVELOPER_P12}" "${DISTRIBUTION_P12}" "${PROFILE_SOURCE}" "${NOTARY_KEY}"

security create-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}"
security set-keychain-settings -lut 21600 "${KEYCHAIN_PATH}"
security unlock-keychain -p "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}"
security import "${DEVELOPER_P12}" -k "${KEYCHAIN_PATH}" \
    -P "${APPLE_CERTIFICATE_PASSWORD}" -T /usr/bin/codesign -T /usr/bin/security
security import "${DISTRIBUTION_P12}" -k "${KEYCHAIN_PATH}" \
    -P "${APPLE_CERTIFICATE_PASSWORD}" -T /usr/bin/codesign -T /usr/bin/security
security set-key-partition-list -S apple-tool:,apple:,codesign: \
    -s -k "${KEYCHAIN_PASSWORD}" "${KEYCHAIN_PATH}"
security list-keychains -d user -s "${KEYCHAIN_PATH}" "${ORIGINAL_KEYCHAIN}"
security default-keychain -d user -s "${KEYCHAIN_PATH}"

PROFILE_PLIST="${RUNNER_TEMP}/codedesk-profile.plist"
security cms -D -i "${PROFILE_SOURCE}" > "${PROFILE_PLIST}"
PROFILE_UUID="$(/usr/libexec/PlistBuddy -c 'Print :UUID' "${PROFILE_PLIST}")"
PROFILE_NAME="$(/usr/libexec/PlistBuddy -c 'Print :Name' "${PROFILE_PLIST}")"
PROFILE_DIR="${HOME}/Library/MobileDevice/Provisioning Profiles"
PROFILE_DESTINATION="${PROFILE_DIR}/${PROFILE_UUID}.mobileprovision"
mkdir -p "${PROFILE_DIR}"
cp "${PROFILE_SOURCE}" "${PROFILE_DESTINATION}"

{
    echo "CODEDESK_TEMP_KEYCHAIN=${KEYCHAIN_PATH}"
    echo "CODEDESK_ORIGINAL_KEYCHAIN=${ORIGINAL_KEYCHAIN}"
    echo "CODEDESK_TEMP_PROFILE=${PROFILE_DESTINATION}"
    echo "APPLE_PROVISIONING_PROFILE_NAME=${PROFILE_NAME}"
    echo "APPLE_NOTARY_PRIVATE_KEY=${NOTARY_KEY}"
} >> "${GITHUB_ENV}"
