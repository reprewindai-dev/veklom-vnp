# Veklom Canonical Architecture

## 1. Overview
This document represents the unified architectural truth lock for the Veklom platform. It establishes the mandatory boundaries for components across all repositories, enforcing that "Connection is the Product" and ensuring that no single component attempts to bypass the strict separation of concerns.

## 2. Component Authority

### 2.1 The Product: Trust Connection
- The Trust Connection is the top-level aggregate and product.
- It is managed persistently in `veklom-byos-backend`.
- It dictates capability lane assignments and execution boundaries.
- The SDK is strictly a generated machine-native embodiment of a connection, not an independent layer.

### 2.2 The Fabric: Interlink
- **Component:** Ambient Interlink cAPI (`reprewindai-dev/cAPI`)
- **Role:** The distributed operating fabric. It handles intent classification, negotiation, capability composition, and public-facing gateway duties.
- **Rules:** Interlink cannot invent capabilities; it only discovers and routes them based on persistent truths stored in BYOS.

### 2.3 The Runtime: Amphoteric
- **Component:** Amphoteric Runtime
- **Role:** The local participation runtime that represents agents connecting to the fabric.

### 2.4 The Authority: CAPPO
- **Component:** CAPPO Backend (`reprewindai-dev/cappo-backend`)
- **Role:** The sole final authority for consequential execution (LAW 0).
- **Rules:** It controls all Execution Authorization Tokens (EAT) and side-effect releases. Lane 3 executions CANNOT proceed without explicit CAPPO approval. It is purely deterministic and acts without circular authority logic.

### 2.5 The Evidence: PGL & Genome Ledger
- **Component:** IdentityRAG / Genome Ledger
- **Role:** Manages identity, lineage, and canonical evidence.
- **Rules:** Requires persistent signing keys (no simulated fallback). Seals the cryptographic proof of all transactions and connection states.

### 2.6 The Measurement: VNP
- **Component:** Veklom Network Protocol (`reprewindai-dev/veklom-vnp`)
- **Role:** Publishes signed physical telemetry and measures operational behavior across exactly five canonical Hetzner nodes.
- **Rules:** Cannot slash wallets directly. Proposes evidence and evaluates bounded states through the deterministic compiler.

### 2.7 The Certification: VABP
- **Component:** Veklom Authorized Benchmark Protocol
- **Role:** Certifies authorized benchmark outcomes across 4 pillars. Distinct and strictly decoupled from VNP.

### 2.8 The Settlement: x402
- **Component:** x402
- **Role:** Handles machine-to-machine settlement strictly bound to connection and execution identifiers.

## 3. Maturity Framework: API-m-FAMM
API-m-FAMM is the research-backed maturity baseline used to assess connection-management practices (lifecycle, security, performance, observability). It signals `connection_maturity` exclusively and must never alter VNP physical performance measurements or VABP benchmark scores.

## 4. Status Namespaces
All repositories must adopt and strictly adhere to the following namespaces. Frontend interfaces are forbidden from hardcoding arbitrary statuses.

- `readiness_status`
- `connection_state`
- `execution_state`
- `policy_decision`
- `measurement_state`
- `settlement_stage`
- `verification_result`

## 5. Deployment Mandate
All infrastructure must target Dockerized services on Hetzner via Coolify. Previous mixed-cloud deployment models are deprecated and superseded by this document.
# Veklom canonical architecture

This document is the architecture truth lock for the Veklom product family.
It describes authority and evidence boundaries; it does not turn a deployed
route, seeded row, or UI label into operational proof.

## Product doctrine

> **Connection is the product.**  
> **Interlink is the fabric.**  
> **Amphoteric is the runtime.**  
> **CAPPO authorizes.**  
> **PGL proves.**  
> **VNP measures.**  
> **VABP certifies.**  
> **x402 settles.**  
> **API is not the product.**

The Trust Connection is the persistent governed aggregate. Interlink discovers,
translates, negotiates, and composes capabilities. Amphoteric presents and
participates in that fabric. CAPPO is the final consequential-execution gate.
PGL records identity, lineage, and evidence. VNP measures physical operational
behavior. VABP performs authorized periodic certification. x402 settles
machine-to-machine obligations in an authorized context.

## Authority boundaries

| System | Authority |
| --- | --- |
| BYOS backend | Workspace/tenant data, persistent Trust Connection, connection saga, RLS data plane, capability lanes. |
| cAPI / Interlink | Public capability gateway, discovery, OpenAPI→MCP translation, negotiation/composition, Amphoteric presentation, capability graph coordination. |
| CAPPO | Sole final consequential-execution authority: LAW 0, ExecutionIdentity, authorization tokens, credential/side-effect release, budgets, approval/quarantine, attestation, failure evidence. |
| VNP | Signed physical telemetry, canonical node registry/heartbeats, operational measurement, evidence confidence, VABP assessments, five-node compiler, Performance Assurance, bonds. |
| Frontend | Presentation and operator actions only; Interlink and CAPPO are separate surfaces, and local status fabrication is prohibited. |

“Covenant” is a historical codename, compatibility alias, or internal lifecycle
profile only. It is not a competing product or execution authority. The
canonical public name is **Interlink-cAPI**.

## Score-family separation

These are five distinct score families. They must never be blended into one
universal trust score:

1. **VNP Operational** — continuous measured operational performance.
2. **Evidence Confidence** — confidence in the completeness, freshness, and
   integrity of the evidence set.
3. **M2M Readiness** — machine-to-machine integration readiness.
4. **Connection Maturity** — connection lifecycle and governance maturity;
   **API-m-FAMM populates this family only**.
5. **Economic Assurance** — financial or assurance posture; this family is
   nullable when no authorized economic evidence exists.

Economic stake must never influence node weight, observation acceptance, or any
operational score.

## VNP and VABP are different

- **VNP** is continuous, windowed operational measurement from accepted signed
  observations.
- **VABP** is an authorized periodic benchmark/certification process with its
  own authorization, scope, and evidence requirements.

VABP certification does not retroactively make an unmeasured VNP window
operational, and VNP telemetry is not by itself a VABP certification.

## Truth lock

For every operational score:

```text
Zero accepted observations => {
  score: null,
  operational_state: "Insufficient Evidence"
}
```

The implementation and presentation layers must also obey these rules:

- Never seed `100`, `0`, or a provider baseline as operational proof.
- Missing measurements remain unmeasured, provisional, disconnected, or
  insufficient evidence.
- A seeded node row is not proof of a physical node.
- HTTP 200 from a route proves reachability only, not measurement integrity.
- Frontend `Live`, `Connected`, `Attesting`, and `Anchor Committed` labels are
  not backend evidence.
- PGL claims must say **tamper-evident** or **hash-chained** unless a real
  external anchoring receipt exists. Do not call evidence “on-chain” or
  “immutable” without that receipt.
- CAPPO alone authorizes consequential economic side effects.
- x402 terminology uses the canonical `PAYMENT-REQUIRED` and
  `PAYMENT-SIGNATURE` headers.

## Physical topology

The five-site topology and its liveness criteria are normative in
[ADR-003](adr/ADR-003-hetzner-coolify-topology.md). Coolify registration,
container reachability, or a server health check does not independently prove
an operational VNP node.
