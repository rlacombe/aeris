#!/usr/bin/env bash
set -euo pipefail
export MPLCONFIGDIR="${MPLCONFIGDIR:-/private/tmp/aeris-mpl}"
exec python "$(cd "$(dirname "$0")" && pwd)/run_reconstruction.py"
