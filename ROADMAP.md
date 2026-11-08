# CatLedger: proposed development roadmap

Current release: **v0.1.0, prototype** (started 8 November 2026). Items below are **engineering estimates, not completed work or historical time records**. They form concrete potential follow-on sessions if the owner chooses to develop the project further. Estimates have not been measured against any paid-project timer.

| Milestone | Estimated time | Implementation and acceptance criteria |
| --- | ---: | --- |
| Material-compatibility model | 6–9 h | Introduce material/profile dimensions and prevent combining incompatible stock/pieces; schema upgrades and migration tests. |
| Saw workflow sequencing | 7–10 h | Model minimum clamp/offcut lengths, no-cut-last-piece option, per-stock trim and explicit sequence; prove invariants with tests. |
| Algorithm improvements | 8–12 h | Add a better exact lower bound and configurable solver budgets; benchmark against the independent oracle, document solver gaps and timeouts. |
| Offcut persistence and stock reconciliation | 7–10 h | Durable offcut IDs, usage history, cross-job allocation, conflict detection and rollback/backup tests without a server. |
| Local terminal interface | 6–9 h | Interactive cut-list browsing, material selection, warnings, validation previews and non-destructive editing. |
| Export reliability and recovery | 5–8 h | Stable machine-readable release schema, backward compatibility, checksum manifests, import/export round-trips and documented recovery. |
| User and contributor documentation | 4–6 h | Real-use feedback, structured tutorials, accessible diagrams and release checklist; no fabricated usage statistics. |
| **Total potential scope** | **43–64 h** | Subject to feedback, owner priorities and platform eligibility. |

## Priority and decision gates

1. Validate actual workshop constraints with a real owner-selected job before making stronger suitability claims.
2. Implement material compatibility and cutting-sequence constraints before exposing more aggressive optimisation objectives.
3. Compare exact and heuristic outputs on adversarial cases, retaining a trustworthy oracle and transparent search limits.
4. Add persistent inventory only after establishing data integrity and backup semantics.

Issues can be opened for selected milestones once the repository is published. Do not present this roadmap as a guarantee that every item will be implemented or that its estimate has already been billed.
