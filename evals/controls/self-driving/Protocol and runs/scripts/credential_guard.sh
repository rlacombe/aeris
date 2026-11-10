#!/usr/bin/env bash
set -euo pipefail

host="${1:?agent host required}"
shift
home=/home/runner
install -d -o 10001 -g 10001 -m 700 "${home}"
protected=()

case "${host}" in
  codex)
    install -d -o 10001 -g 10001 -m 700 "${home}/.codex"
    install -o 10001 -g 10001 -m 600 /root/credentials/codex-auth.json "${home}/.codex/auth.json"
    protected+=("${home}/.codex/auth.json")
    ;;
  claude)
    install -d -o 10001 -g 10001 -m 700 "${home}/.claude"
    install -o 10001 -g 10001 -m 600 /root/credentials/claude-credentials.json "${home}/.claude/.credentials.json"
    protected+=("${home}/.claude/.credentials.json")
    ;;
  agy)
    install -d -o 10001 -g 10001 -m 700 "${home}/.gemini" "${home}/.gemini/antigravity-cli"
    install -o 10001 -g 10001 -m 600 /root/credentials/agy-oauth-creds.json "${home}/.gemini/oauth_creds.json"
    install -o 10001 -g 10001 -m 600 /root/credentials/agy-google-accounts.json "${home}/.gemini/google_accounts.json"
    install -o 10001 -g 10001 -m 600 /root/credentials/agy-cli-oauth-token "${home}/.gemini/antigravity-cli/antigravity-oauth-token"
    protected+=(
      "${home}/.gemini/oauth_creds.json"
      "${home}/.gemini/google_accounts.json"
      "${home}/.gemini/antigravity-cli/antigravity-oauth-token"
    )
    ;;
  *) printf 'unknown agent host: %s\n' "${host}" >&2; exit 2 ;;
esac

setpriv --reuid=10001 --regid=10001 --clear-groups --inh-caps=-all --bounding-set=-all -- "$@" &
child=$!
transcript="${AERIS_TRANSCRIPT_PATH:-/output/transcript-attempt-${AERIS_ATTEMPT}.jsonl}"

# The first transcript event proves that the CLI has loaded its credentials and
# started the model request. Revoke filesystem access before any model-issued
# tool can run. The root-only source mounts remain outside the agent's reach.
for _ in $(seq 1 2400); do
  [[ -s "${transcript}" ]] && break
  kill -0 "${child}" 2>/dev/null || break
  sleep 0.05
done
chown root:root "${protected[@]}"
chmod 000 "${protected[@]}"

wait "${child}"
