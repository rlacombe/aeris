#!/usr/bin/env bash
set -euo pipefail

path="${1:-.}"
minimum_gib="${MINIMUM_FREE_GIB:-20}"
available_kib="$(df -Pk "${path}" | awk 'NR==2 {print $4}')"
required_kib="$((minimum_gib * 1024 * 1024))"

if (( available_kib < required_kib )); then
  printf 'insufficient disk: %.1f GiB available; %s GiB required\n' \
    "$(awk -v k="${available_kib}" 'BEGIN {print k/1024/1024}')" "${minimum_gib}" >&2
  exit 1
fi

printf 'disk gate passed: %.1f GiB available; %s GiB required\n' \
  "$(awk -v k="${available_kib}" 'BEGIN {print k/1024/1024}')" "${minimum_gib}"
