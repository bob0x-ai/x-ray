#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd)
HERMES_ENV_FILE="${HERMES_ENV_FILE:-${HOME}/.hermes/.env}"

if [[ -f "${HERMES_ENV_FILE}" ]]; then
  while IFS= read -r line; do
    [[ -z "${line}" || "${line}" == \#* ]] && continue
    [[ "${line}" != *=* ]] && continue
    key=${line%%=*}
    value=${line#*=}
    case "${key}" in
      SOCIALDATA_API_KEY|X_OAUTH2_CLIENT_ID|X_OAUTH2_CLIENT_SECRET|X_OAUTH2_ACCESS_TOKEN|X_OAUTH2_REFRESH_TOKEN|X_CLIENT_ID|X_CLIENT_SECRET|X_ACCESS_TOKEN|X_REFRESH_TOKEN)
        export "${key}=${value}"
        ;;
    esac
  done < "${HERMES_ENV_FILE}"
fi

cd "${REPO_ROOT}"
exec python3 -m src.server
