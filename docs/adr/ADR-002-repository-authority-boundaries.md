# ADR-002 — Repository authority boundaries

- **Status:** Accepted
- **Scope:** Canonical repository and service ownership

## Decision

Each repository owns a bounded authority. The matrix below is normative; a
route, model, or local helper in another repository does not transfer authority
across these boundaries.

| Repository/system | Canonical authority |
| --- | --- |
| `veklom-byos-backend` | Workspace and tenant data; the persistent Trust Connection aggregate; connection saga; RLS data plane; and capability-lane assignments. |
| cAPI | The Interlink cAPI public gateway; capability discovery; OpenAPI→MCP translation; negotiation and composition; Amphoteric presentation; and global capability-graph coordination. |
| `cappo-backend` | **Sole final consequential-execution authority:** LAW 0, `ExecutionIdentity`, execution authorization tokens, credential and side-effect release, budgets, approval and quarantine, attestation, and failure evidence. |
| `veklom-vnp` | Signed physical telemetry; node registry and heartbeats; operational measurements; VABP authorized assessments; five-node state compiler; evidence confidence; Performance Assurance; and bonds. |
| `veklom-FRONTEND` | Presentation and operator actions only. It **must** display Interlink and CAPPO separately and **must not** create local `Live` or `Connected` statuses. |

## Terminology guardrail

**Covenant** is only a historical codename, compatibility alias, or internal
lifecycle profile. It is **not** a competing top-level product or execution
authority. The canonical public name is **Interlink-cAPI**.

## Consequences

- BYOS persists Connection truth but cannot authorize consequential side effects.
- cAPI may discover, translate, negotiate, and compose, but does not become the
  owner of tenant truth or execution authorization.
- CAPPO is the final gate for consequential execution and economic side effects.
- VNP can measure, assess, and propose evidence outcomes, but cannot directly
  move funds or slash a wallet without the governed CAPPO path.
- The frontend must render backend proof states rather than infer them from
  HTTP reachability, timers, or local defaults.
