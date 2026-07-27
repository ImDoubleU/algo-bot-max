#!/usr/bin/env bash
set -euo pipefail

certificate_url="https://gu-st.ru/content/Other/doc/russian_trusted_root_ca.cer"
expected_fingerprint="D26D2D0231B7C39F92CC738512BA54103519E4405D68B5BD703E9788CA8ECF31"
target="/usr/local/share/ca-certificates/russian-trusted-root-ca.crt"
temporary_file="$(mktemp)"

cleanup() {
    rm -f "$temporary_file"
}
trap cleanup EXIT

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi

# The issuer is not in Ubuntu's default trust store yet, so the pinned
# fingerprint authenticates this one-time certificate download.
curl --fail --silent --show-error --location --insecure \
    "$certificate_url" \
    --output "$temporary_file"

actual_fingerprint="$(
    openssl x509 -in "$temporary_file" -noout -fingerprint -sha256 \
        | cut -d= -f2 \
        | tr -d ':'
)"
if [[ "$actual_fingerprint" != "$expected_fingerprint" ]]; then
    echo "Unexpected Russian Trusted Root CA fingerprint: $actual_fingerprint" >&2
    exit 1
fi

openssl verify -CAfile "$temporary_file" "$temporary_file" >/dev/null
install -m 0644 "$temporary_file" "$target"
update-ca-certificates

echo "Russian Trusted Root CA installed."
