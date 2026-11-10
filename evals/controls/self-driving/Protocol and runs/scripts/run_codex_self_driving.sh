#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${AERIS_EXPERIMENT_IMAGE:-aeris-scientific-self-driving:2026-09-25-v8-4}"
schema_image="${AERIS_SCHEMA_IMAGE:-${image}}"
agent_host="${AERIS_AGENT_HOST:-codex}"
aeris_env_file="${AERIS_ENV_FILE:-${HOME}/Code/Research/aeris/.env}"
study_id="${1:?study id required}"
replicate="${2:?replicate required}"
study_dir="${root}/studies/${study_id}"
safety_envelope="${root}/config/AGENT_SAFETY_ENVELOPE.json"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
case "${agent_host}" in
  codex)
    run_prefix="codex"
    condition="codex-aeris-agent-authored-v1"
    host_label="Codex CLI"
    model="gpt-5.6-terra"
    auth_mounts=(--mount "type=bind,src=${HOME}/.codex/auth.json,dst=/root/credentials/codex-auth.json,readonly")
    agent_command=(bash -lc 'codex exec --ephemeral --ignore-user-config --ignore-rules --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox --model gpt-5.6-terra -c '\''model_reasoning_effort="medium"'\'' -c '\''mcp_servers.aeris.command="python3"'\'' -c '\''mcp_servers.aeris.args=["/run/contract/mcp-tcp-bridge.py","--host","aeris-sidecar","client"]'\'' -c '\''mcp_servers.aeris.tool_timeout_sec=3600'\'' --json "Read /opt/aeris/aeris/agent/skill.md, /opt/aeris/aeris/agent/profiles/reanalysis.md, and /run/contract/agent-authored-task.md. If /output/autonomous-review-feedback.txt exists, read it and the saved research notebook first, then resume without repeating completed work. The article materials are under /study. Execute the autonomous reanalysis now. Do not ask for human input." > "/output/transcript-attempt-${AERIS_ATTEMPT}.jsonl" 2> "/output/agent-attempt-${AERIS_ATTEMPT}.stderr.log"')
    ;;
  claude)
    run_prefix="claude-sonnet-5"
    condition="claude-sonnet-5-aeris-agent-authored-v1"
    host_label="Claude Code"
    model="claude-sonnet-5"
    auth_mounts=(--mount "type=bind,src=${root}/auth/claude/.credentials.json,dst=/root/credentials/claude-credentials.json,readonly")
    agent_command=(bash -lc 'claude --print --model claude-sonnet-5 --effort medium --disable-slash-commands --no-session-persistence --dangerously-skip-permissions --mcp-config /run/contract/claude-mcp.json --output-format stream-json --verbose "Read /opt/aeris/aeris/agent/skill.md, /opt/aeris/aeris/agent/profiles/reanalysis.md, and /run/contract/agent-authored-task.md. If /output/autonomous-review-feedback.txt exists, read it and the saved research notebook first, then resume without repeating completed work. The article materials are under /study. Execute the autonomous reanalysis now. Do not ask for human input." > "/output/transcript-attempt-${AERIS_ATTEMPT}.jsonl" 2> "/output/agent-attempt-${AERIS_ATTEMPT}.stderr.log"')
    ;;
  agy)
    run_prefix="agy-flash-3.8"
    condition="agy-flash-3.8-aeris-agent-authored-v1"
    host_label="Antigravity CLI"
    model="gemini-3.8-flash-medium"
    auth_mounts=(
      --mount "type=bind,src=${HOME}/.gemini/oauth_creds.json,dst=/root/credentials/agy-oauth-creds.json,readonly"
      --mount "type=bind,src=${HOME}/.gemini/google_accounts.json,dst=/root/credentials/agy-google-accounts.json,readonly"
      --mount "type=bind,src=${HOME}/.gemini/antigravity-cli/antigravity-oauth-token,dst=/root/credentials/agy-cli-oauth-token,readonly"
    )
    agent_command=(bash -lc 'agy mcp add aeris python3 /run/contract/mcp-tcp-bridge.py --host aeris-sidecar client >/output/agy-mcp-config.log 2>&1 && agy --model gemini-3.8-flash-medium --effort medium --mode accept-edits --dangerously-skip-permissions --disable-slash-commands --print-timeout 8h --output-format stream-json --log-file "/output/agy-attempt-${AERIS_ATTEMPT}.log" --print="Call AERIS tools directly with call_mcp_tool; do not create or delegate to subagents. Read /opt/aeris/aeris/agent/skill.md, /opt/aeris/aeris/agent/profiles/reanalysis.md, and /run/contract/agent-authored-task.md. If /output/autonomous-review-feedback.txt exists, read it and the saved research notebook first, then resume without repeating completed work. The article materials are under /study. Execute the autonomous reanalysis now. Do not ask for human input." > "/output/transcript-attempt-${AERIS_ATTEMPT}.jsonl" 2> "/output/agent-attempt-${AERIS_ATTEMPT}.stderr.log"')
    ;;
  *) printf 'unknown AERIS_AGENT_HOST: %s\n' "${agent_host}" >&2; exit 2 ;;
esac
run_id="${run_prefix}-aeris-self-driving-${study_id}-r${replicate}-${timestamp}"
output_dir="${root}/runs/scientific/${run_id}"

[[ -d "${study_dir}" ]] || { printf 'unknown study: %s\n' "${study_id}" >&2; exit 2; }
[[ -f "${safety_envelope}" ]] || { printf 'missing safety envelope: %s\n' "${safety_envelope}" >&2; exit 2; }
expected_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source_commit"])' \
  "${root}/frozen/aeris-self-driving/SNAPSHOT_MANIFEST.json")"
image_commit="$(docker run --rm "${image}" python3 -c \
  'import json; print(json.load(open("/opt/aeris/SNAPSHOT_MANIFEST.json"))["source_commit"])')"
if [[ "${image_commit}" != "${expected_commit}" ]]; then
  printf 'image commit %s does not match frozen snapshot %s\n' \
    "${image_commit}" "${expected_commit}" >&2
  exit 2
fi
mkdir -p "${root}/work"
python3 "${root}/scripts/validate_study_inputs.py" "${study_id}" \
  --output "${root}/work/${study_id}-input-validation.json"
MINIMUM_FREE_GIB=12 "${root}/scripts/check_disk.sh"
mkdir -p "${output_dir}"
frozen="${output_dir}/frozen-inputs"
mkdir -p "${frozen}/prompts" "${frozen}/config" "${frozen}/schemas" "${frozen}/scripts"
cp -R "${study_dir}" "${frozen}/study"
cp "${root}/prompts/common_task.md" "${frozen}/prompts/common-task.md"
cp "${root}/prompts/agent_authored_task.md" "${frozen}/prompts/agent-authored-task.md"
cp "${root}/config/SELF_DRIVING_REANALYSIS_POLICY.md" "${frozen}/config/self-driving-reanalysis-policy.md"
cp "${root}/config/RETRY_POLICY.md" "${frozen}/config/retry-policy.md"
cp "${root}/config/NETWORK_POLICY.md" "${frozen}/config/network-policy.md"
cp "${root}/config/PUBLIC_SOURCE_CAPABILITIES.json" "${frozen}/config/public-source-capabilities.json"
cp "${safety_envelope}" "${frozen}/config/agent-safety-envelope.json"
cp "${root}/schemas/agent_output_v2.schema.json" "${frozen}/schemas/output.schema.json"
cp "${root}/schemas/analysis_handoff.schema.json" "${frozen}/schemas/analysis-handoff.schema.json"
cp "${root}/schemas/run_manifest_v2.schema.json" "${frozen}/schemas/run-manifest.schema.json"
cp "${root}/scripts/validate_autonomous_result.py" "${frozen}/scripts/validate-autonomous-result.py"
cp "${root}/scripts/package_reanalysis_result.py" "${frozen}/scripts/package-reanalysis-result.py"
cp "${root}/scripts/build_phase_feedback.py" "${frozen}/scripts/build-phase-feedback.py"
cp "${root}/scripts/scan_artifacts_for_secrets.sh" "${frozen}/scripts/scan-artifacts-for-secrets.sh"
cp "${root}/scripts/mcp_tcp_bridge.py" "${frozen}/scripts/mcp-tcp-bridge.py"
cp "${root}/scripts/credential_guard.sh" "${frozen}/scripts/credential-guard.sh"
cp "${root}/scripts/prune_disposable_artifacts.py" "${frozen}/scripts/prune-disposable-artifacts.py"
python3 - "${root}/briefs/${study_id}.json" "${frozen}/config/study-target.json" <<'PY'
import json, pathlib, sys
source, target = map(pathlib.Path, sys.argv[1:])
brief = json.loads(source.read_text())
# Expose article-derived scientific dimensions, never prior routes, code, or results.
frozen = {
    "schema_version": 1,
    "study_id": brief["study_id"],
    "pmid": brief["pmid"],
    "target": brief["target"],
    "evidence": brief.get("evidence", []),
    "excluded_information": brief.get("excluded_information", []),
}
target.write_text(json.dumps(frozen, indent=2) + "\n")
PY
cat > "${frozen}/config/claude-mcp.json" <<'JSON'
{"mcpServers":{"aeris":{"command":"python3","args":["/run/contract/mcp-tcp-bridge.py","--host","aeris-sidecar","client"]}}}
JSON
docker image inspect "${image}" --format '{{.Id}}' > "${output_dir}/docker_image_id.txt"
preflight_dir="${root}/work/${run_id}-preflight"
mkdir -p "${preflight_dir}"
printf '{"public_sources": []}\n' > "${preflight_dir}/generic-brief.json"
python3 "${root}/scripts/network_preflight.py" --brief "${preflight_dir}/generic-brief.json" \
  --output "${preflight_dir}/network_preflight_host.json"
docker run --rm \
  --mount "type=bind,src=${preflight_dir}/generic-brief.json,dst=/run/generic-brief.json,readonly" \
  --mount "type=bind,src=${root}/scripts/network_preflight.py,dst=/run/network_preflight.py,readonly" \
  --mount "type=bind,src=${preflight_dir},dst=/preflight" \
  "${image}" \
  python3 /run/network_preflight.py --brief /run/generic-brief.json \
    --output /preflight/network_preflight_container.json
python3 "${root}/scripts/compare_network_preflight.py" \
  "${preflight_dir}/network_preflight_host.json" "${preflight_dir}/network_preflight_container.json" \
  > "${preflight_dir}/network_preflight_comparison.json"

host_version="$(docker run --rm "${image}" "${agent_host/agy/agy}" --version 2>/dev/null | head -1)"
python3 - "${root}" "${study_id}" "${run_id}" "${output_dir}" "${replicate}" "${image}" \
  "${condition}" "${host_label}" "${host_version}" "${model}" <<'PY'
import hashlib, json, pathlib, subprocess, sys
from datetime import datetime, timezone
root, study_id, run_id, output = map(pathlib.Path, sys.argv[1:5])
replicate = int(sys.argv[5])
image_name = sys.argv[6]
condition, host_label, host_version, model = sys.argv[7:11]
study = json.loads((root / "studies" / study_id / "study.json").read_text())
validation = json.loads((root / "work" / f"{study_id.name}-input-validation.json").read_text())["studies"][0]
image = subprocess.check_output(["docker", "image", "inspect", image_name, "--format", "{{.Id}}"], text=True).strip()
snapshot = json.loads((root / "frozen" / "aeris-self-driving" / "SNAPSHOT_MANIFEST.json").read_text())
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
def digest_tree(path):
    value = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        value.update(str(item.relative_to(path)).encode()); value.update(b"\0")
        value.update(hashlib.sha256(item.read_bytes()).digest())
    return value.hexdigest()
if digest_tree(output / "frozen-inputs" / "study") != validation["bundle_sha256"]:
    raise RuntimeError("Frozen study bundle differs from the validated input bundle.")
manifest = {
  "schema_version": 3, "run_id": run_id.name, "condition": condition,
  "study": {
    "pmid": study["pmid"], "slug": study_id.name.split("-", 1)[1],
    "bundle_sha256": validation["bundle_sha256"], "input_mode": validation["input_mode"],
  }, "replicate": replicate,
  "agent": {"host": host_label, "host_version": host_version, "model": model, "reasoning_effort": "medium"},
  "environment": {
    "container_image_digest": image, "aeris_commit": snapshot["source_commit"],
    "network_policy_sha256": digest(output / "frozen-inputs" / "config" / "network-policy.md"),
    "retry_policy_sha256": digest(output / "frozen-inputs" / "config" / "retry-policy.md"),
    "reanalysis_policy_sha256": digest(output / "frozen-inputs" / "config" / "self-driving-reanalysis-policy.md"),
    "result_schema_sha256": digest(output / "frozen-inputs" / "schemas" / "output.schema.json"),
    "semantic_validator_sha256": digest(output / "frozen-inputs" / "scripts" / "validate-autonomous-result.py"),
    "safety_envelope_sha256": digest(output / "frozen-inputs" / "config" / "agent-safety-envelope.json"),
  },
  "started_at": datetime.now(timezone.utc).isoformat(), "ended_at": None, "status": "running",
  "infrastructure_restarts": 0, "autonomous_continuations": 0,
  "autonomous_review_passes": 0,
  "human_scientific_interventions": 0, "artifacts": {}, "termination_reason": None,
  "safety_checks": {"secret_scan": "pending"},
}
(output / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

exit_code=1
max_attempts=4
for attempt in $(seq 1 "${max_attempts}"); do
  name="${run_id}-a${attempt}"
  network="${name}-network"
  sidecar="${name}-aeris-sidecar"
  set +e
  docker network create "${network}" > "${output_dir}/attempt-${attempt}-network.log" 2>&1
  docker run --rm -d --name "${sidecar}" --network "${network}" --network-alias aeris-sidecar \
    --mount "type=bind,src=${aeris_env_file},dst=/run/secrets/aeris.env,readonly" \
    --mount "type=bind,src=${frozen}/study,dst=/study,readonly" \
    --mount "type=bind,src=${frozen}/config/agent-safety-envelope.json,dst=/run/contract/agent-safety-envelope.json,readonly" \
    --mount "type=bind,src=${frozen}/scripts/mcp-tcp-bridge.py,dst=/run/contract/mcp-tcp-bridge.py,readonly" \
    --mount "type=bind,src=${output_dir},dst=/output" \
    -e AERIS_EXECUTION_MODE=self-driving \
    -e AERIS_PROFILE=reanalysis \
    -e AERIS_SAFETY_ENVELOPE=/run/contract/agent-safety-envelope.json \
    -e AERIS_WORKSPACE=/output/aeris-workspace \
    -e AERIS_ENV_FILE=/run/secrets/aeris.env \
    "${image}" \
    python3 /run/contract/mcp-tcp-bridge.py --host 0.0.0.0 server \
    > "${output_dir}/attempt-${attempt}-sidecar-id.txt" 2> "${output_dir}/attempt-${attempt}-sidecar-start.log"
  sidecar_code=$?
  if [[ "${sidecar_code}" -ne 0 ]]; then
    docker network rm "${network}" >/dev/null 2>&1 || true
    exit_code="${sidecar_code}"
    set -e
    break
  fi
  docker run --rm --name "${name}" \
    --user root \
    --entrypoint /bin/bash \
    --network "${network}" \
    --tmpfs /home/runner:rw,nosuid,nodev,size=2g,uid=10001,gid=10001 \
    --tmpfs /work:rw,nosuid,nodev,size=8g,uid=10001,gid=10001 \
    "${auth_mounts[@]}" \
    --mount "type=bind,src=${frozen}/study,dst=/study,readonly" \
    --mount "type=bind,src=${frozen}/prompts/common-task.md,dst=/run/contract/common-task.md,readonly" \
    --mount "type=bind,src=${frozen}/prompts/agent-authored-task.md,dst=/run/contract/agent-authored-task.md,readonly" \
    --mount "type=bind,src=${frozen}/config/self-driving-reanalysis-policy.md,dst=/run/contract/self-driving-reanalysis-policy.md,readonly" \
    --mount "type=bind,src=${frozen}/config/retry-policy.md,dst=/run/contract/retry-policy.md,readonly" \
    --mount "type=bind,src=${frozen}/config/agent-safety-envelope.json,dst=/run/contract/agent-safety-envelope.json,readonly" \
    --mount "type=bind,src=${frozen}/config/study-target.json,dst=/run/contract/study-target.json,readonly" \
    --mount "type=bind,src=${frozen}/config/public-source-capabilities.json,dst=/run/contract/public-source-capabilities.json,readonly" \
    --mount "type=bind,src=${frozen}/schemas/analysis-handoff.schema.json,dst=/run/contract/analysis-handoff.schema.json,readonly" \
    --mount "type=bind,src=${frozen}/schemas/output.schema.json,dst=/run/contract/output.schema.json,readonly" \
    --mount "type=bind,src=${frozen}/scripts/mcp-tcp-bridge.py,dst=/run/contract/mcp-tcp-bridge.py,readonly" \
    --mount "type=bind,src=${frozen}/scripts/credential-guard.sh,dst=/run/contract/credential-guard.sh,readonly" \
    --mount "type=bind,src=${frozen}/config/claude-mcp.json,dst=/run/contract/claude-mcp.json,readonly" \
    --mount "type=bind,src=${root}/frozen/aeris-self-driving/aeris/agent/skill.md,dst=/opt/aeris/aeris/agent/skill.md,readonly" \
    --mount "type=bind,src=${root}/frozen/aeris-self-driving/aeris/agent/profiles/reanalysis.md,dst=/opt/aeris/aeris/agent/profiles/reanalysis.md,readonly" \
    --mount "type=bind,src=${output_dir},dst=/output" \
    --mount "type=bind,src=${output_dir}/run_manifest.json,dst=/output/run_manifest.json,readonly" \
    --workdir /work \
    -e AERIS_EXECUTION_MODE=self-driving \
    -e AERIS_PROFILE=reanalysis \
    -e AERIS_SAFETY_ENVELOPE=/run/contract/agent-safety-envelope.json \
    -e AERIS_WORKSPACE=/output/aeris-workspace \
    -e AERIS_ATTEMPT="${attempt}" \
    -e MCP_TIMEOUT=3600000 \
    "${image}" \
    /run/contract/credential-guard.sh "${agent_host}" "${agent_command[@]}" &
  docker_pid=$!
  (
    deadline=$((SECONDS + 28800))
    while kill -0 "${docker_pid}" 2>/dev/null; do
      if (( SECONDS >= deadline )); then
        printf 'wall-clock limit reached\n' > "${output_dir}/timeout.marker"
        docker stop --time 30 "${name}" > "${output_dir}/attempt-${attempt}-timeout-stop.log" 2>&1 || true
        break
      fi
      if ! MINIMUM_FREE_GIB=10 "${root}/scripts/check_disk.sh" "${output_dir}" \
        > "${output_dir}/disk-monitor.log" 2>&1; then
        printf 'free disk fell below 10 GiB\n' > "${output_dir}/policy-termination.marker"
        docker stop --time 30 "${name}" > "${output_dir}/attempt-${attempt}-disk-stop.log" 2>&1 || true
        break
      fi
      sleep 60
    done
  ) </dev/null >/dev/null 2>&1 &
  watchdog_pid=$!
  wait "${docker_pid}"
  exit_code=$?
  kill "${watchdog_pid}" 2>/dev/null || true
  wait "${watchdog_pid}" 2>/dev/null || true
  docker stop --time 10 "${sidecar}" > "${output_dir}/attempt-${attempt}-sidecar-stop.log" 2>&1 || true
  docker network rm "${network}" > "${output_dir}/attempt-${attempt}-network-remove.log" 2>&1 || true
  set -e
  printf '%s\n' "${exit_code}" > "${output_dir}/attempt-${attempt}-exit-code.txt"
  rm -f "${output_dir}/result.json"
  package_code=1
  if [[ -s "${output_dir}/analysis_handoff.json" ]]; then
    set +e
    python3 "${frozen}/scripts/package-reanalysis-result.py" "${output_dir}" \
      > "${output_dir}/attempt-${attempt}-packaging.json"
    package_code=$?
    set -e
  fi
  if [[ "${package_code}" -eq 0 && -s "${output_dir}/result.json" ]]; then
    attempt_schema_code=1
    attempt_semantic_code=1
    set +e
    docker run --rm \
      --mount "type=bind,src=${output_dir}/result.json,dst=/run/result.json,readonly" \
      --mount "type=bind,src=${frozen}/schemas/output.schema.json,dst=/run/schema.json,readonly" \
      "${schema_image}" \
      python3 -c 'import json,jsonschema; jsonschema.validate(json.load(open("/run/result.json")),json.load(open("/run/schema.json")))' \
      > "${output_dir}/attempt-${attempt}-schema-validation.log" 2>&1
    attempt_schema_code=$?
    if [[ "${attempt_schema_code}" -eq 0 ]]; then
      python3 "${frozen}/scripts/validate-autonomous-result.py" "${output_dir}" \
        > "${output_dir}/attempt-${attempt}-semantic-validation.json"
      attempt_semantic_code=$?
    fi
    if [[ "${AERIS_FORCE_RESTART_TEST:-0}" == "1" && "${attempt}" -eq 1 \
          && "${attempt_schema_code}" -eq 0 && "${attempt_semantic_code}" -eq 0 ]]; then
      printf '{"valid": false, "errors": ["Forced restart-resumption test: reload the durable contract and notebook, preserve the finalized scientific design, and revalidate the result."]}\n' \
        > "${output_dir}/attempt-${attempt}-semantic-validation.json"
      printf 'forced after valid first result\n' > "${output_dir}/forced-restart-test.marker"
      attempt_semantic_code=86
    fi
    set -e
    if [[ "${attempt_schema_code}" -eq 0 && "${attempt_semantic_code}" -eq 0 ]]; then
      result_status="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${output_dir}/result.json")"
      if [[ "${result_status}" == "completed_blocker" && ! -e "${output_dir}/blocker-review.marker" \
            && "${attempt}" -lt "${max_attempts}" ]]; then
        mv "${output_dir}/result.json" "${output_dir}/result-attempt-${attempt}.provisional-blocker.json"
        printf 'required after valid provisional blocker\n' > "${output_dir}/blocker-review.marker"
        cat > "${output_dir}/autonomous-review-feedback.txt" <<'EOF'
Act as an independent recovery critic. The prior blocker is a hypothesis, not a conclusion.
Start from the locked scientific target and retained raw evidence. Do not adopt the prior route assessment until you have tried to falsify it. Search by dataset name, publisher, schema fields, filenames, and release identifiers across official catalogs, maintained clients, package registries, public data hosts, verified mirrors, legacy and successor endpoints, archives, and regulator interfaces. Query machine-readable catalogs on research repositories, dataset hubs, code-host releases, and public object stores directly; general web search alone is insufficient. Execute promising client or transport code against a minimal partition; documentation alone is not a route test. For interactive archives, enumerate selectors and run a bounded scan across candidate stations, target pollutants, and representative dates throughout the study period. Choose outcome and exposure probes for temporal overlap; an empty early slice does not characterize the full window.

Your objective is a defensible fit. As soon as usable outcome and exposure records overlap, build and execute a minimal valid slice, inspect joins and variation, then expand it while resources permit. Prefer an explicitly labeled bounded fit when it preserves the outcome, pollutant, contrast, and analytic meaning. Keep the locked scientific target and safety limits. Accept a final blocker only if this fresh counterexample search cannot produce any identifiable fit.
EOF
        python3 - "${output_dir}/run_manifest.json" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text())
d["autonomous_review_passes"] += 1
p.write_text(json.dumps(d, indent=2)+"\n")
PY
        continue
      fi
      break
    fi
    if [[ "${attempt_schema_code}" -eq 0 && "${attempt_semantic_code}" -ne 0 \
          && "${attempt}" -lt "${max_attempts}" ]]; then
      mv "${output_dir}/result.json" "${output_dir}/result-attempt-${attempt}.rejected.json"
      result_status="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("status", ""))' "${output_dir}/result-attempt-${attempt}.rejected.json")"
      python3 - "${output_dir}/attempt-${attempt}-semantic-validation.json" \
        "${output_dir}/autonomous-review-feedback.txt" "${result_status}" <<'PY'
import json, pathlib, sys
source, target = map(pathlib.Path, sys.argv[1:3])
status = sys.argv[3]
try:
    errors = json.loads(source.read_text()).get("errors", [])
except (OSError, json.JSONDecodeError):
    errors = ["The retained result failed independent semantic review."]
if status == "completed_blocker":
    lines = [
        "Act as an independent recovery critic. The prior blocker remains unproven.",
        "Start from the locked target and retained evidence, but treat the prior conclusion as a hypothesis to falsify.",
        "Search across official catalogs, maintained clients, package registries, public data hosts, verified mirrors, legacy endpoints, archives, and regulator interfaces. Query machine-readable catalogs on research repositories, dataset hubs, code-host releases, and public object stores directly; general web search alone is insufficient. Execute promising transport code and probe a minimal partition. For interactive archives, enumerate selectors and run a bounded scan across candidate stations, target pollutants, and representative dates throughout the study period. Choose outcome and exposure probes for temporal overlap; an empty early slice does not characterize the full window.",
        "If outcome and exposure records overlap, build and fit a minimal valid slice before doing more route paperwork. Expand it while resources permit and label any bounded substitution.",
        "The host found these evidence gaps; use them to direct research rather than merely editing the handoff:",
    ]
    lines.extend(f"- {error}" for error in errors)
    lines.append("Accept a blocker only after this fresh counterexample search cannot produce an identifiable fit.")
else:
    lines = [
        "Independent review rejected the prior scientific handoff.",
        "Resume from the durable notebook, code, downloads, and checkpoints.",
        "Address each actionable issue with executable evidence; do not restart completed work:",
    ]
    lines.extend(f"- {error}" for error in errors)
    lines.append("Then repeat the skeptical audit and write a corrected scientific handoff.")
target.write_text("\n".join(lines) + "\n")
PY
      python3 - "${output_dir}/run_manifest.json" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text())
d["autonomous_continuations"] += 1
d["autonomous_review_passes"] += 1
p.write_text(json.dumps(d, indent=2)+"\n")
PY
      continue
    fi
    # A complete scientific handoff is never sent back to the research agent
    # to repair a host schema or packaging defect. Preserve that distinction.
    printf '{"research_complete": true, "packaging_valid": false}\n' \
      > "${output_dir}/research-complete-packaging-failure.json"
    break
  fi
  [[ -e "${output_dir}/timeout.marker" || -e "${output_dir}/policy-termination.marker" ]] && break
  [[ "${attempt}" -lt "${max_attempts}" ]] || break
  packaging_reason=""
  if [[ -s "${output_dir}/attempt-${attempt}-packaging.json" ]]; then
    packaging_reason="$(cat "${output_dir}/attempt-${attempt}-packaging.json")"
  elif [[ ! -s "${output_dir}/analysis_handoff.json" ]]; then
    packaging_reason="The run has not produced analysis_handoff.json."
  fi
  python3 "${frozen}/scripts/build-phase-feedback.py" "${output_dir}" \
    --reason "${packaging_reason}" --write "${output_dir}/autonomous-review-feedback.txt"
  python3 - "${output_dir}/run_manifest.json" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text()); d["autonomous_continuations"] += 1; p.write_text(json.dumps(d, indent=2)+"\n")
PY
done

# Keep scientific artifacts and generated code, but discard reproducible package
# environments and caches that otherwise dominate retained run size.
python3 "${frozen}/scripts/prune-disposable-artifacts.py" "${output_dir}"

# Preserve infrastructure diagnostics only after the scientific process exits,
# so study-specific execution cannot inspect preflight artifacts.
cp "${preflight_dir}/network_preflight_host.json" "${output_dir}/network_preflight_host.json"
cp "${preflight_dir}/network_preflight_container.json" "${output_dir}/network_preflight_container.json"
cp "${preflight_dir}/network_preflight_comparison.json" "${output_dir}/network_preflight_comparison.json"

python3 - "${output_dir}" "${exit_code}" <<'PY'
import json, pathlib, sys
from datetime import datetime, timezone
output=pathlib.Path(sys.argv[1]); exit_code=int(sys.argv[2])
p=output/"run_manifest.json"; d=json.loads(p.read_text()); d["ended_at"]=datetime.now(timezone.utc).isoformat()
if (output/"policy-termination.marker").exists():
    d["status"]="policy_termination"
    d["termination_reason"]=(output/"policy-termination.marker").read_text().strip()
elif (output/"timeout.marker").exists():
    d["status"]="timeout"
    d["termination_reason"]=(output/"timeout.marker").read_text().strip()
elif (output/"result.json").exists():
    try:
        d["status"]=json.loads((output/"result.json").read_text()).get("status", "agent_failure")
    except (json.JSONDecodeError, OSError):
        d["status"]="agent_failure"
        d["termination_reason"]="malformed result.json"
else:
    d["status"]="agent_failure" if exit_code == 0 else "infrastructure_failure"
    d["termination_reason"]="missing result.json"
d["artifacts"]={str(x.relative_to(output)):str(x.relative_to(output)) for x in sorted(output.rglob("*")) if x.is_file()}
p.write_text(json.dumps(d, indent=2)+"\n")
PY

schema_code=1
semantic_code=1
manifest_code=1
if [[ -s "${output_dir}/result.json" ]]; then
  set +e
  docker run --rm \
    --mount "type=bind,src=${output_dir}/result.json,dst=/run/result.json,readonly" \
    --mount "type=bind,src=${frozen}/schemas/output.schema.json,dst=/run/schema.json,readonly" \
    "${schema_image}" \
    python3 -c 'import json,jsonschema; jsonschema.validate(json.load(open("/run/result.json")),json.load(open("/run/schema.json")))' \
    > "${output_dir}/schema_validation.log" 2>&1
  schema_code=$?
  set -e
  if [[ "${schema_code}" -eq 0 ]]; then
    set +e
    python3 "${frozen}/scripts/validate-autonomous-result.py" "${output_dir}" \
      > "${output_dir}/semantic_validation.json"
    semantic_code=$?
    set -e
  fi
fi
printf '%s\n' "${schema_code}" > "${output_dir}/schema_validation_exit_code.txt"
printf '%s\n' "${semantic_code}" > "${output_dir}/semantic_validation_exit_code.txt"

terminal_wrapper_status="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "${output_dir}/run_manifest.json")"
if [[ "${terminal_wrapper_status}" != "policy_termination" && "${terminal_wrapper_status}" != "timeout" \
      && ( "${schema_code}" -ne 0 || "${semantic_code}" -ne 0 ) ]]; then
  python3 - "${output_dir}/run_manifest.json" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); d=json.loads(p.read_text()); d["status"]="agent_failure"
d["termination_reason"]="result failed schema or autonomous-completion validation"
p.write_text(json.dumps(d, indent=2)+"\n")
PY
fi

# Scan before finalizing the manifest so a safety failure becomes part of the
# machine-readable run outcome.
set +e
"${frozen}/scripts/scan-artifacts-for-secrets.sh" "${output_dir}" \
  > "${output_dir}/secret_scan.log" 2>&1
secret_code=$?
set -e
printf '%s\n' "${secret_code}" > "${output_dir}/secret_scan_exit_code.txt"
python3 - "${output_dir}/run_manifest.json" "${secret_code}" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); code=int(sys.argv[2]); d=json.loads(p.read_text())
d["safety_checks"]["secret_scan"] = "passed" if code == 0 else "failed"
if code != 0:
    d["status"] = "policy_termination"
    d["termination_reason"] = "credential-shaped content detected in retained artifacts"
p.write_text(json.dumps(d, indent=2)+"\n")
PY

# Refresh the inventory after validation so the manifest names every retained
# trace and diagnostic generated by the wrapper.
python3 - "${output_dir}/run_manifest.json" "${output_dir}" <<'PY'
import json, pathlib, sys
p=pathlib.Path(sys.argv[1]); output=pathlib.Path(sys.argv[2]); d=json.loads(p.read_text())
d["artifacts"]={str(x.relative_to(output)):str(x.relative_to(output)) for x in sorted(output.rglob("*")) if x.is_file() and x != p}
p.write_text(json.dumps(d, indent=2)+"\n")
PY

set +e
docker run --rm \
  --mount "type=bind,src=${output_dir}/run_manifest.json,dst=/run/manifest.json,readonly" \
  --mount "type=bind,src=${frozen}/schemas/run-manifest.schema.json,dst=/run/schema.json,readonly" \
  "${schema_image}" \
  python3 -c 'import json,jsonschema; jsonschema.validate(json.load(open("/run/manifest.json")),json.load(open("/run/schema.json")))' \
  > "${output_dir}/manifest_validation.log" 2>&1
manifest_code=$?
set -e
printf '%s\n' "${manifest_code}" > "${output_dir}/manifest_validation_exit_code.txt"
[[ "${manifest_code}" -eq 0 ]] || { cat "${output_dir}/manifest_validation.log" >&2; exit 2; }
[[ "${secret_code}" -eq 0 ]] || { cat "${output_dir}/secret_scan.log" >&2; exit 3; }
printf '%s\n' "${output_dir}"
