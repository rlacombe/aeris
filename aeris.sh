#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="${PWD}"
python="${AERIS_PYTHON:-${root}/.venv/bin/python}"

if [[ ! -x "${python}" ]]; then
  python="python3"
fi

cd "${root}"
if [[ "${1:-}" == "exposure" ]]; then
  shift
  exec "${python}" -m aeris.agent.launcher exposure "$@"
fi
exec "${python}" -m aeris.agent.launcher --workspace "${workspace}" "$@"
