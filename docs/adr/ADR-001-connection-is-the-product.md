# ADR-001 — Connection is the product

- **Status:** Accepted
- **Scope:** Canonical Veklom architecture

## Decision

The product is the governed **Trust Connection**, not an API, SDK, gateway, or
individual runtime. The canonical framing is:

> **Connection is the product.**  
> **Interlink is the fabric.**  
> **Amphoteric is the runtime.**  
> **CAPPO authorizes.**  
> **PGL proves.**  
> **VNP measures.**  
> **VABP certifies.**  
> **x402 settles.**  
> **API is not the product.**

### Meaning of each boundary

| Boundary | Meaning |
| --- | --- |
| Connection | The persistent, governed aggregate that carries tenant intent, capability lanes, policy context, and lifecycle state. |
| Interlink | The public and distributed capability fabric: discovery, translation, negotiation, composition, and graph coordination. |
| Amphoteric | The runtime presentation and participation layer for agents and capabilities. |
| CAPPO | The sole final authority for consequential execution, authorization, credentials, budgets, and side effects. |
| PGL | The identity, lineage, and tamper-evident evidence layer. |
| VNP | Continuous signed physical telemetry and operational measurement. |
| VABP | Authorized periodic benchmark and certification. |
| x402 | Machine-to-machine payment negotiation and settlement bound to an authorized context. |
| API | A transport/interface surface; it is not a competing product authority. |

## Consequences

Repositories must expose their authority through the Connection lifecycle and
must not create parallel top-level products or circular execution authorities.
Presentation layers may display state and initiate operator actions, but cannot
turn a local label into evidence.
