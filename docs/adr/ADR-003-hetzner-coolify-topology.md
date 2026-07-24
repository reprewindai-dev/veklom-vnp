# ADR-003 — Hetzner/Coolify topology

- **Status:** Accepted
- **Scope:** Canonical physical VNP measurement topology

## Decision

The canonical physical topology contains exactly the following five sites.
Provider and platform are uniform: Hetzner servers managed through Coolify.

| Server | City/country | `location_code` | Provider | Platform | IP | Coolify server UUID |
| --- | --- | --- | --- | --- | --- | --- |
| `veklom-edge-us-east` | Ashburn, VA, US | `us-ashburn` | Hetzner | Coolify | `87.99.154.166` | `q12oryfd1plt357b0550x0f5` |
| `veklom-prod-1` | Hillsboro, OR, US | `us-hillsboro` | Hetzner | Coolify | `5.78.135.11` | `localhost` |
| `veklom-edge-eu-north2` | Nuremberg, DE | `de-nuremberg` | Hetzner | Coolify | `91.98.78.218` | `xbqgn9v7jqgzycynzc6xgcyi` |
| `veklom-edge-eu-central` | Falkenstein, DE | `de-falkenstein` | Hetzner | Coolify | `167.233.202.195` | `pjepy7fyr3unc0sl36if38vt` |
| `veklom-edge-ap-southeast` | Singapore | `sg-singapore` | Hetzner | Coolify | `5.223.90.12` | `zls3c5cx8f3jngp5rlp0os0g` |

## Topology rules

1. There are no AWS, GCP, Oracle, Lambda, Tokyo, Helsinki, or mixed-cloud
   physical VNP nodes.
2. AWS-style region codes such as `us-east-1` are not canonical. Use the
   location codes in the table above.
3. A hostname is not a cryptographic node identity. Each node requires a stable
   UUID and a registered Ed25519 key; the private key stays node-side.
4. Approximately 120 Amphoteric agents are logical capability participants,
   never physical probe locations.
5. A Hetzner server is not automatically operationally **Live**. A node becomes
   operationally Live only after all of the following are true:
   - registration is complete;
   - an active Ed25519 key is verified;
   - a fresh signed heartbeat is accepted;
   - probe software is deployed;
   - at least one real observation is accepted; and
   - the freshness threshold is satisfied.
6. The topology API and frontend must derive every entry from the canonical node
   registry. They must not use a hardcoded five-region list.
7. Missing, stale, or unregistered nodes must be represented honestly as
   `Disconnected`, `Config Incomplete`, or `Insufficient Evidence`.

## Consequences

Coolify registration and SSH reachability establish infrastructure registration
only. They do not establish node operation, measurement integrity, or five-node
VNP evidence.
