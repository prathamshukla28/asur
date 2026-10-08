# ASUR Design Documentation — Index

This is the complete architecture design for ASUR, a local-first, key-free AI
Content Creation OS. **No code yet** — these 9 documents are the design to be
reviewed before any implementation begins.

Start with the [project README](../README.md) for the overview, then read the
documents below in order.

---

## Reading order

| # | Document | What it covers |
|---|----------|----------------|
| 1 | [ARCHITECTURE.md](ARCHITECTURE.md) | The 4 layers, the 3 instruments (SCRIPT / GENERATION / VIRAL CHECK) + the EDITING environment + the ORCHESTRATOR, the firewall design, and the 8 founding invariants. |
| 2 | [DATA_MODELS.md](DATA_MODELS.md) | The universal versioned artifact envelope, per-asset provenance + license fields, the 17 artifact kinds, the timeline model (+ 15 editing primitives), and the persistent SCRIPT memory entities. |
| 3 | [STATE_MACHINE.md](STATE_MACHINE.md) | The 18-state project state machine, the 15 quality gates, dispositions (SHIP / HOLD / BLOCK), and local gate separation (producer ≠ approver, by local username). |
| 4 | [PIPELINE.md](PIPELINE.md) | The 26-stage generation pipeline and the firewall projections (GENERATION_VIEW / VIRAL_VIEW) in motion via the seal → claim → verdict → place hand-off. |
| 5 | [VIRAL_CHECK.md](VIRAL_CHECK.md) | The 12 scoring dimensions, evidence classes, the 3 honesty rules (no fake viral %), and the documented platform signal knowledge base (Instagram / TikTok / YT Shorts). |
| 6 | [GENERATION_STACK.md](GENERATION_STACK.md) | The local-first model stack (Wan 2.2 + SDXL + Kokoro + Stable Audio + FFmpeg), the license guards, the cost model, and the asset strategy. |
| 7 | [AGENTS.md](AGENTS.md) | The 14-agent roster, the orchestrator's responsibilities, and how each agent binds to the firewall. |
| 8 | [MVP.md](MVP.md) | The 5-phase build order, the 5-level testing strategy, security scope, cost discipline, and the V1→V7 roadmap. |

---

## The 8 founding invariants (quick reference)

- **ASUR-LOCAL-01** — 100% local, key-free; identity = local OS user + git config.
- **ASUR-HONEST-01** — no fake viral score; known vs unknown kept separate.
- **ASUR-FIREWALL-01** — GENERATION and VIRAL CHECK never talk; SCRIPT is the only bridge.
- **ASUR-GATE-01** — fail closed.
- **ASUR-HUMAN-01** — humans own inputs, approvals, and history.
- **ASUR-PROV-01** — every asset is provenance- and license-bound.
- **ASUR-EXPLAIN-01** — no black box; every decision is explainable.
- **ASUR-VERSION-01** — nothing is silently overwritten.
