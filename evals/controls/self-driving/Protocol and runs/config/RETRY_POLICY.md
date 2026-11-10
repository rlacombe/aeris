# Retry and stopping policy

Version: 1.0. Freeze with each experimental campaign.

## Principle

Retries recover transport and infrastructure failures. They may not alter the
scientific task after an agent sees data or results. A change to the outcome,
pollutant, geography, period, model, covariates, assignment method, or coverage
standard is a disclosed substitution chosen within the original run or a new,
predeclared sensitivity analysis. It is never an infrastructure retry.

## Request-level retries

| Failure | Attempts | Schedule | Rule |
| --- | ---: | --- | --- |
| HTTP 429 | 6 total | `Retry-After`, otherwise 30, 60, 120, 240, 480 s | Shared per-domain limiter applies before retry. |
| HTTP 408, 425, 500, 502, 503, 504 | 6 total | 5, 15, 45, 120, 300 s plus 0--20% jitter | Retry the identical request. |
| DNS, connect reset, TLS interruption | 5 total | 5, 15, 45, 120 s plus jitter | Retry the identical request. |
| Other HTTP 4xx | 1 | none | Agent must inspect the response; no blind retry. |
| Empty valid response | 1 | none | Treat as data evidence, not transport failure. |

All requests, attempts, response codes, byte counts, and delays are logged. A
retry cannot modify query parameters except an expired authentication token.

After an endpoint reaches a terminal failure, search for another public release
of the same outcome construct or covariate. Preserve the failed-endpoint evidence
and record any source substitution. Do not change the target outcome merely to
obtain a downloadable file.

## Download and archive recovery

- Resume interrupted static downloads with HTTP Range only when the server
  reports range support and the final checksum is verified.
- Download to a temporary object and atomically promote it after checksum and
  decompression checks pass.
- Retry a corrupt or truncated object twice from byte zero.
- Process S3 archives in deterministic, checkpointed object order. Retry each
  object under the request-level policy; continue past a permanently failed
  object and report the missing object in coverage diagnostics.
- Checkpoints record completed object keys and checksums. They contain no
  scientific result and may survive an infrastructure restart.

## Agent-process recovery

- Each study receives one primary agent process.
- A process killed by host restart, CLI crash, or confirmed provider outage may
  receive one infrastructure restart from the same workspace and prompt.
- The restart instruction states only that the process stopped unexpectedly
  and should inspect its own saved work and continue.
- A timeout, analytical dead end, missing data conclusion, invalid model, or
  request for scientific guidance is not restartable.
- A third process failure ends the run as `infrastructure_failure`.

## Blocker review

The first semantically valid terminal blocker is provisional. One fresh agent
context must reload the same contract, notebook, code, and evidence, then try
to falsify every blocker. It inspects executable public clients, reporting
interfaces, legacy and successor endpoints, download libraries, archives, and
mirrors, and builds a minimal valid outcome-exposure slice when possible. The
review cannot change the scientific target, safety envelope, or resource
limits. A blocker becomes final only after this independent recovery review.

## Human intervention

Scientific intervention is prohibited. The runner automatically grants only
predeclared filesystem and network operations inside the isolated container.
If the agent asks a scientific or procedural question, no answer is supplied;
the event is logged and the agent must continue or declare a blocker. Humans
may stop a run for credential exposure, uncontrolled cost, security risk,
public-service abuse, or imminent disk exhaustion. Such a run is retained with
its termination reason.

## Campaign limits

- Studies run sequentially during the first campaign.
- Minimum free disk before a study: 14 GiB. The live 10 GiB termination floor
  remains authoritative and preserves evidence before storage is exhausted.
- Minimum free disk during a study: 10 GiB; crossing it terminates the run.
- Wall-clock limit per study: 8 hours.
- Maximum agent contexts per study: 3, including one independent recovery
  review when the first valid result is a blocker.
- Maximum live download for one previously unseen object: 10 GiB unless the
  registry predeclares a larger object.
- No paid data API may exceed its predeclared campaign budget.

## Outcomes

The manifest distinguishes:

- `completed_fit`;
- `completed_blocker`;
- `agent_failure`;
- `infrastructure_failure`;
- `policy_termination`; and
- `timeout`.

All categories count in completion-rate denominators.
