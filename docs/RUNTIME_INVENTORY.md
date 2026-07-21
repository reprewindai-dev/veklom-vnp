# Runtime inventory

This inventory records what the inspected repositories and live endpoints
actually establish. A schema, route, seeded row, HTTP 200, or frontend label is
not by itself evidence of an operational physical measurement network.

## Classification vocabulary

Each capability has exactly one classification:

- **Defined:** Contract, model, specification, or intended interface exists.
- **Implemented:** Code path exists and is reachable in the relevant runtime.
- **Registered:** Infrastructure or identity is recorded in an authority system.
- **Deployed:** A service or artifact is running at a reachable endpoint.
- **Operational:** The required runtime prerequisites and ongoing behavior are
  evidenced.
- **Evidence Verified:** A specific claim is supported by current, reviewable
  evidence, not merely by code or configuration.
- **Deprecated:** Retained historical or compatibility path that is not
  authoritative.

## Evidence snapshot

| Capability | Classification | Evidence basis |
| --- | --- | --- |
| Canonical VNP FastAPI entrypoint | Deployed | `veklom-vnp/app/main.py:71-114` defines `app`; `https://vnp.veklom.com/health` returned HTTP 200 with `service: veklom-vnp`, version `1.1.0`, and `demo_mode: false`. |
| Canonical VNP startup mode | Deployed | `veklom-vnp/app/main.py:42-67` performs production startup checks and the live health response reports `demo_mode: false`; the live response still reports environment `development`, so this is not production-readiness evidence. |
| VNP mounted database routers | Implemented | `veklom-vnp/app/main.py:89-98` mounts ingestion, stream, Nexus, claims, badges, VABP, staking, batch ingestion, and status routers. |
| VNP health/readiness endpoints | Implemented | `veklom-vnp/app/main.py:105-130` defines `/health` and `/ready`; health proves reachability, while readiness checks only database connectivity. |
| VNP topology endpoint | Implemented | `veklom-vnp/app/main.py:132-182` proxies BYOS topology and otherwise reports observed regions; it does not independently prove five physical nodes. |
| Probe-event ingestion | Implemented | `veklom-vnp/app/api/routers/vnp_ingest.py:130-220` validates and persists probe events; `:221-384` accepts observation batches; `app/batch/ingest.py:31` exposes batch ingestion. |
| Usage-event ingestion | Implemented | `veklom-vnp/app/api/routers/vnp_ingest.py:385` exposes signed usage-event ingestion and database persistence. |
| Streaming telemetry | Implemented | `veklom-vnp/app/api/routers/vnp_stream.py:95` exposes SSE score streaming from database telemetry. |
| Observation and telemetry models | Defined | `veklom-vnp/app/db/models.py:686-742` defines `ProbeEvent` and `RegionalTelemetry`; `:501-528` defines physical `Observation`. |
| Node/key/heartbeat models | Defined | `veklom-vnp/app/db/models.py:470-528` defines node, node-key, heartbeat, and observation records; model presence does not establish active registry operation. |
| Measurement windows and score models | Defined | `veklom-vnp/app/db/models.py:530-575` defines measurement-window and VNP score records. |
| Physical measurement migration | Implemented | `veklom-vnp/app/db/migrations/versions/f61fc0779406_add_vnp_physical_measurement_models.py` creates physical measurement tables and seeds five rows using legacy AWS-style region identifiers. |
| Seeded five-node database rows | Implemented | The same migration seeds Ashburn, Hillsboro, Nuremberg, Falkenstein, and Singapore records; seeded rows are not proof of physical deployment. |
| Canonical five-site Coolify registration | Registered | Coolify inventory records the five sites: four named server UUIDs plus Hillsboro as `localhost`; registration and validation succeeded, but no probe deployment or accepted observation was evidenced. |
| Five-node operational fleet | Defined | `app/api/routers/status.py` reports physical node registry and signed heartbeats are not yet wired; no deployed probe, accepted real observation, or fresh signed heartbeat exists for all five sites. |
| Node cryptographic identity | Defined | `NodeKey`, heartbeat, and observation signature fields exist in `app/db/models.py`; there is no evidence of five active verified node-side Ed25519 keys. |
| Signed event verification | Implemented | `veklom-vnp/app/core/security/__init__.py:32-70` verifies Ed25519 payload signatures; `app/api/routers/vnp_ingest.py` invokes signature validation before persistence. |
| Signed event generation in BYOS worker | Implemented | `veklom-byos-backend/backend/workers/vnp_agent_fleet.py:482-530` constructs and signs events, but `:402-408` derives keys deterministically from agent IDs rather than proving independently provisioned physical node keys. |
| BYOS HTTP probe worker | Implemented | `veklom-byos-backend/backend/workers/vnp_agent_fleet.py:410-428` performs real HTTP probes against three fixed targets; this is not evidence of a five-site deployed mesh. |
| BYOS VNP ingestion | Implemented | `veklom-byos-backend/backend/apps/api/routers/vnp.py:34-140` and `vnp_ingest.py:100-174` expose signed ingestion paths and write probe records. |
| BYOS runtime telemetry | Implemented | `veklom-byos-backend/backend/apps/api/routers/runtime_telemetry.py:16-151` reads telemetry, alerts, audit logs, and streams from backend state. |
| BYOS benchmark leaderboard | Implemented | `veklom-byos-backend/backend/apps/api/routers/benchmarks.py:145-390` computes leaderboard output but uses seed defaults and blended values when real runs are absent. |
| BYOS benchmark seed fallback | Implemented | `veklom-byos-backend/backend/apps/api/routers/benchmarks.py:183-218`, `:294-315`, and `:340-362` seed latency, uptime, compliance, scores, and provider values; this is implemented-but-synthetic, not evidence verified. |
| BYOS in-memory/demo state | Deprecated | `veklom-vnp/app/demo_runtime.py:47-60` and `:163-183` maintain in-memory stores and seed random demo measurements; canonical startup gates demo mode off in production. |
| Canonical Nexus scoring function | Implemented | `veklom-vnp/app/api/routers/nexus.py:39-46` defines a latency/cost/throughput formula separate from the physical measurement compiler. |
| Nexus score endpoint | Implemented | `veklom-vnp/app/api/routers/nexus.py:95-188` reads APIs and telemetry, returns null/`Insufficient Evidence` without telemetry, but copies `composite` into unmeasured dimensions at `:160`. |
| Nexus node endpoint | Implemented | `veklom-vnp/app/api/routers/nexus.py:226-244` reads active `ApiRegion` rows but emits placeholder `latency: 0`, `throughput: 0`, and active-style fields. |
| Live Nexus score evidence | Evidence Verified | `GET https://vnp.veklom.com/api/v1/nexus/scores` returned per-target `score: null`, `status: "Insufficient Evidence"`, and empty dimensions for the current targets. |
| VABP run and certificate routes | Implemented | `veklom-vnp/app/api/routers/vabp.py:92-174` exposes run creation, run lookup, and certificate issuance; route existence is not evidence of an authorized completed certification. |
| VABP models/migrations | Defined | VABP sandbox and score models are created by `cf105b7c216a_add_vnp_scores_and_vabp_sandbox_models.py`; this establishes schema intent only. |
| Staking and bond routes | Implemented | `veklom-vnp/app/api/routers/staking.py:51-200` exposes bond creation, funding, challenge, and resolution; `app/db/models.py:635-665` defines bond and condition models. |
| Bond slashing authorization | Implemented | `veklom-vnp/app/services/slashing_engine.py:59-128` calls CAPPO authorization and then attempts a PGL receipt; it is not proof that a production slash occurred. |
| CAPPO authorization call | Implemented | `veklom-vnp/app/services/slashing_engine.py:61-125` calls `/api/internal/interlink/vnp/authorize-slash`; authorization remains CAPPO-owned. |
| PGL evidence call | Implemented | `veklom-vnp/app/pgl/client.py:17-60` signs and sends receipt requests; `slashing_engine.py:73-86` falls back to `pending_pgl_*` when PGL is unavailable, which is not evidence. |
| PGL anchoring claim | Defined | `RegionalTelemetry.on_chain_anchor` exists in `app/db/models.py:735-738`, but no external anchoring receipt was verified; inventory language must remain tamper-evident/hash-chained, not on-chain/immutable. |
| CAPPO VNP metrics | Implemented | `cappo-backend/cappo_backend/api/routers/vnp_router.py:31-77` reads API/telemetry tables but returns a UUID-derived `trustBeaconMerkle`, adds `16` to active-node count, and uses hardcoded region counts. |
| CAPPO VNP registration telemetry | Implemented | `cappo-backend/cappo_backend/api/routers/vnp_router.py:80-119` registers APIs and seeds `us-east` telemetry. |
| CAPPO VNP telemetry aggregation | Implemented | `cappo-backend/cappo_backend/services/vnp_telemetry_service.py:94-157` derives p95/p99 and score components heuristically from limited measurements. |
| CAPPO proxy telemetry attribution | Implemented | `cappo-backend/cappo_backend/services/vnp_proxy_service.py:80-84` attributes proxy telemetry to hardcoded `us-east`. |
| CAPPO benchmark leaderboard | Implemented | `cappo-backend/cappo_backend/api/routers/benchmarks_router.py:23-330` fills missing providers from seed data and blends real values with seeds. |
| CAPPO synthetic audit logs | Implemented | `cappo-backend/cappo_backend/api/routers/benchmarks_router.py:417-471` returns seed log events when audit logs are absent. |
| CAPPO final execution authority | Implemented | `cappo-backend/cappo_backend/api/routers/exec_router.py:129` and the security/runtime modules expose the execution path; consequential authorization belongs solely to CAPPO by architecture decision. |
| BYOS x402 routes | Implemented | `veklom-byos-backend/backend/apps/api/routers/x402.py:164-1207` exposes payment, verify, protected, staking, and intent routes; route existence does not prove settlement or authorization evidence. |
| CAPPO x402 routes | Implemented | `cappo-backend/cappo_backend/api/routers` contains x402 payment and authorization surfaces; no unauthenticated HTTP success is treated as proof of a settled transaction. |
| Canonical x402 terminology | Defined | Architecture requires `PAYMENT-REQUIRED` and `PAYMENT-SIGNATURE`; older route/header variants must not be used to infer settlement proof. |
| Frontend Nexus data source | Implemented | `veklom-FRONTEND/components/terminal/components/NexusProtocol.tsx` calls `/api/v1/nexus/genome`, `/api/v1/nexus/nodes`, and `/api/v1/nexus/scores`; tabs are Trust Matrix, Probe Topology, and Charter & Methodology. |
| Frontend Nexus local simulation | Implemented | `veklom-FRONTEND/components/terminal/components/NexusProtocol.tsx:113-141` historically applies `Math.random()` latency/throughput jitter and local attestation/anchor state; these values are not backend proof. |
| Frontend VNP leaderboard/score routes | Implemented | `veklom-FRONTEND/app/api/vnp/leaderboard/route.ts` and `app/api/vnp/score/[apiId]/route.ts` call `computeLeaderboard`/`computeVNPScore` over backend payloads rather than canonical persisted score rows. |
| Frontend workspace VNP scores | Implemented | `veklom-FRONTEND/app/workspace/vnp/page.tsx` contains deterministic pseudo-random base-score generation; it is presentation synthesis, not measurement evidence. |
| Frontend local `Live`/`Connected` authority | Deprecated | Local status defaults and simulated state in the Nexus component cannot establish operational state; frontend must consume canonical backend proof states. |
| Five nodes active claim | Evidence Verified | Coolify registration/validation proves five registered servers only; absence of deployed probes, accepted observations, and signed heartbeats means “five nodes active” is not supported. |
| Production-ready claim | Evidence Verified | No blanket production-ready claim is supported: the live VNP health route is reachable, but Nexus scores are `Insufficient Evidence` and physical heartbeat wiring is explicitly incomplete. |
| On-chain claim | Evidence Verified | No external anchoring receipt was verified for current VNP telemetry; `on_chain_anchor` fields or hash strings do not establish on-chain immutability. |
| Complete/verified claim | Evidence Verified | Routes, models, and migrations are present, but current evidence supports partial implementation with insufficient operational evidence, not complete or verified five-region measurement. |

## Route inventory by service

### Canonical VNP (`veklom-vnp`)

Mounted under `/api/v1`: probe and usage ingestion, SSE stream, Nexus, claims,
badges, VABP, and staking. Batch probe ingestion is mounted at
`/api/v1/ingest/probe-events/batch`; status is mounted separately. The
physical-node status response explicitly reports that registry and signed
heartbeats are not yet wired.

### BYOS (`veklom-byos-backend`)

The relevant route families are:

```text
/vnp/ingestion
/vnp/beacon
/vnp/metrics
/ingest/probe-events
/ingest/usage-events
/vnp/alerts/config
/vnp/alerts/triggered
/vnp/audit-logs
/vnp/stream
/benchmarks/leaderboard
/benchmarks/stream
/benchmarks/logs
/benchmarks/staking/markets
/benchmarks/staking/state
/benchmarks/compile
/api/v1/x402/*
```

Some rows are genuinely database-backed. Benchmark and staking views still
contain seeded, blended, or fallback values and require later correction.

### CAPPO (`cappo-backend`)

The relevant route families are:

```text
/v1/vnp/metrics
/v1/vnp/apis
/v1/vnp/proxy/{api_did}
/v1/vnp/leaderboard
/v1/vnp/validators
/v1/vnp/incidents
/v1/vnp/beacon/routes
/v1/benchmarks/leaderboard
/v1/benchmarks/stream
/v1/benchmarks/logs
/v1/benchmarks/staking/markets
/v1/benchmarks/compile
/v1/exec
```

CAPPO is the consequential execution authority, but its VNP and benchmark
presentation paths include synthetic and heuristic values identified above.

## Required follow-up

Later implementation work must replace synthetic paths with independently
provisioned node identities, signed heartbeats, accepted raw observations,
windowed aggregation, explicit unmeasured dimensions, and evidence receipts.
Financial stake must remain orthogonal to observation acceptance, node weight,
and VNP scoring.
