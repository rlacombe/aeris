#!/usr/bin/env bash
set -euo pipefail

root="${1:?usage: scan_artifacts_for_secrets.sh RUN_DIRECTORY}"
if [[ ! -d "${root}" ]]; then
  printf 'missing run directory: %s\n' "${root}" >&2
  exit 2
fi

# Match credential values rather than harmless references to credential names.
# Matching lines are never emitted. Exclude this frozen scanner so its regular
# expressions cannot cause a self-match.
patterns='((^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~+/-]{20,}|"(access_token|refresh_token)"[[:space:]]*:[[:space:]]*"[^"[:space:]]{12,}"|(ANTHROPIC_API_KEY|CODEX_API_KEY|OPENAI_API_KEY|GEMINI_API_KEY|AERIS_R2_ACCESS_KEY|AERIS_R2_SECRET_KEY|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY)[[:space:]]*=[[:space:]]*['"'"']?[A-Za-z0-9._~+/-]{12,})'

if grep -RIlE --binary-files=without-match \
  --exclude-dir='venv' \
  --exclude-dir='.venv' \
  --exclude-dir='raw' \
  --exclude-dir='data' \
  --exclude-dir='evidence' \
  --exclude-dir='sources' \
  --exclude='scan-artifacts-for-secrets.sh' \
  "${patterns}" "${root}" >/dev/null 2>&1; then
  printf 'secret scan failed: credential-shaped content detected under %s\n' "${root}" >&2
  exit 1
fi

printf 'secret scan passed for %s\n' "${root}"
