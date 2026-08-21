# BridgeBot Roadmap v2 — Beat Miai

*v2 — 2026-08-21. Supersedes v1 (in git history). Companion reports: [Miai notes](research/miai.md), [BEN deep-dive](research/ben-engine-deep-dive.md), [literature review](research/literature-review.md), [tooling & evaluation](research/tooling-and-evaluation.md), [superhuman gap](research/superhuman-gap.md).*

## The goal

**Beat Miai** — the MIT (Fan/Farina) from-scratch self-play full-game bridge agent — and in doing so hold the strongest verifiable result in computer bridge. The superhuman north star stands, but every near-term decision is now judged by one question: does it get us past Miai faster?

## The target, precisely

What we know about Miai (details in [research/miai.md](research/miai.md)):

| Fact | Value | Implication |
|---|---|---|
| Deployed version | v7 "Level 0": raw policy net, **no search**, bidding + play | Searchless play is its soft spot |
| Full-game result vs WBridge5 | **+0.21 IMP/board, 1,024 duplicated boards** | SE ≈ 5.4/√1024 ≈ **0.17** → not even 2σ. The bar is low *and* loosely measured |
| Double-dummy value of contracts reached | **+0.59 IMP/board** | Bidding edge is real; play leaks ~0.4 IMP/board of it |
| Training | Self-play only, no human data; "regularization-aware"; two independently trained agents | Strong, principled method; paper likely soon |
| Unreleased | A "Level 1" search version exists; no paper, code, or table-manager interface yet | **The target will move.** Plan against the version they'll publish, not the one on the website |

### Victory conditions (in order of claim strength)

- **V1 — Exceed Miai's benchmark.** Full-game duplicated team match vs WBridge5 5.12 over **≥2,048 boards** with a margin **≥ +0.6 IMP/board at ≥2σ** (SE ≈ 0.12 at 2,048 boards, so +0.6 is ~5σ and cleanly separates from +0.21 ± 0.17). Same protocol they used, stricter statistics, published deals/logs/harness for reproduction.
- **V2 — Beat Miai head-to-head.** A duplicated team match, our pair vs their pair, ≥1,024 boards. Requires access (see Workstream E).
- **V3 — Stay ahead of their paper.** Whatever Level-1/search version they publish, re-run V1/V2 against it. This is why the architecture below keeps headroom (search in both phases) rather than optimizing for the current Level 0.

## Theory of victory

Three edges, each mapped to a workstream:

1. **Play through search (their biggest leak).** DDS-backed sampling play (GIB/BEN lineage, αμ refinements) is expert-level declarer play and is what WBridge5 itself does. A learned policy with no search gives back IMPs every board. If our play merely *breaks even* against WBridge5 while our bidding holds a +0.6 DD edge, we triple Miai's realized margin.
2. **Bidding from a stronger recipe.** The reproducible SOTA (Kita 2024: supervised warm-start on WBridge5 data, then PPO with fictitious self-play) reaches **+1.24 DD IMP/board** vs WBridge5 — 2× Miai's DD edge — and a belief-search layer (Qiu 2024's BMCS) adds ~+0.3 on top. Nobody has combined them or attached them to a real play engine. Miai deliberately forgoes human/WBridge5 data for purity; we have no such constraint.
3. **Evaluation rigor as a weapon.** Our harness already runs WBridge5 hands-free and invisibly; we can run 4× their board count unattended, report confidence intervals, and publish everything. A tight, reproducible number beats a loose one in any credibility contest.

The risk that cuts the other way: Miai adds search and warm-starting, closing both technical gaps. **Speed matters** — the plan front-loads the cheap, high-yield steps (play engine + reproduced bidder) and defers research bets.

## Workstreams

Workstreams A–C run in parallel; D integrates; E is diplomacy and runs throughout.

### A — Match infrastructure (finish Phase 0)

The harness is validated against real WBridge5 ([tm/server.py](../harness/tm/server.py), [wb5_launch.ps1](../harness/wb5_launch.ps1)). Remaining:

- [ ] **Team-match orchestration**: duplicated boards across two tables (NS/EW swapped), per-board IMP diff, running totals, resumable from PBN + JSONL, final report with mean ± SE and 95% CI.
- [x] **Parallel tables**: `match.py --tables K` shards the deal set across K table-pairs (ports base+2k / base+2k+1), per-room JSONL + wire logs, independent resume per shard, batch multithreaded DD annotation. *Measured 2026-08-21: single table-pair ≈ 1 board/min per room (occasional ~4-min board). K=2: 8 boards in 9 min 54 s wall-clock incl. ~3.5 min launching 16 instances — steady-state ≈ 2 boards/min. Extrapolation: 2,048 boards at K=4 ≈ 8.5–9 h, K=8 ≈ 4.5 h (16 logical cores; WBridge5 is light, so K=8 is plausible — verify CPU headroom before the first long run).*
- [ ] **Protocol fidelity**: relay alerts to opponents only; restart/timeout handling; the one unreproduced board-2 stall — keep wire logs on in every run.
- [ ] **Double-dummy annotation** of every played board (endplay): lets us decompose every margin into *bidding edge* (DD value of contracts) and *play conversion* (realized minus DD) — the same decomposition Miai reported, and our main diagnostic.
- [x] **Pipeline-fidelity control**: WBridge5 vs WBridge5, identical deals both rooms → must score exactly 0 IMPs. *(2026-08-21: 8-board run, all boards push, 0 IMP / 0 SD — validates the full match pipeline incl. duplicated-board swap, doubled-contract scoring, and DD decomposition. Finding: **WBridge5 is deterministic** under identical config + deals, so this control cannot estimate deal variance — it's a regression check, not a noise floor. Keep it as a cheap end-to-end CI assertion.)*
- [ ] **Per-board variance estimate**: comes from a *differing-strategy* match (BEN vs WBridge5 below), not the WB5-vs-WB5 control. Use SD ≈ 5.4 as the planning constant until measured.
- [ ] **Baselines on record**: BEN vs WBridge5 (2,048 boards) — also our first real per-board SD measurement.

**Exit:** an unattended 2,048-board duplicated match completes overnight with a CI'd report and DD decomposition.

### B — Bidding: reproduce, then exceed, the published SOTA

- [ ] Reproduce **Kita et al.** from [harukaki/brl](https://github.com/harukaki/brl) (PGX/JAX env, OpenSpiel's 12.8M WBridge5 hands): confirm ≈ +1.2 DD IMP/board bidding-only. *Compute: this is a cloud-GPU job, not a laptop job — see Compute.*
- [ ] Add a **belief network + Belief Monte Carlo Search** at decision time (Qiu recipe). Target ≥ +1.4 DD.
- [ ] **Export for the engine**: ONNX policy + belief heads; a deterministic, self-consistent system (both seats run the same nets, so partnership consistency is free — the thing Miai had to engineer via regularization).
- [ ] **Auto-generated system card** by policy probing (Miai's technique; also our Phase 4 disclosure prototype) — needed anyway for bot events, and makes the bidder inspectable.
- [ ] Sanity: bid-agreement and DD-value comparison vs Miai's public `v7a/v7b` bid-query API on a few hundred hands (politely rate-limited, or with the author's blessing).

**Exit:** bidding-only DD edge vs WBridge5 ≥ +1.0 over ≥10k deals, with the policy packaged for the engine.

### C — Play: convert the bidding edge

- [ ] **Engine scaffold**: BEN's play stack (sampling → DDS → candidate scoring) as the starting point, with *our* bidder and belief model constraining the hand samples (belief-consistent sampling is where most play strength comes from).
- [ ] **Declarer play**: fix BEN's documented blunder classes; evaluate αμ-style search vs plain PIMC on our boards; tune sample counts for time budget.
- [ ] **Defense**: the least-published phase and where Level-0 Miai is weakest — a learned signaling/carding model for partner-consistent defense plus inference from partner's cards in the sampler.
- [ ] **Opening lead**: retrain/replace BEN's lead model using our belief model.
- [ ] **Measure conversion**: on fixed auctions, our play vs WBridge5's play on identical contracts (play-only duplicated matches). Target: realized ≥ 85% of DD edge (Miai converts ~35%).

**Exit:** play-only match vs WBridge5 ≥ break-even at 2σ over 1,024 boards; declarer and defense measured separately.

### D — Integration, regression, and the V1 match

- [ ] Full engine = B's bidder + C's play engine behind our TM client; every change gated by a 512-board regression vs WBridge5 with DD decomposition.
- [ ] **The V1 match**: ≥2,048 duplicated boards vs WBridge5 5.12, pre-registered protocol (deals generated from a committed seed, fixed settings, wire logs), published report. Then the commercial field (Q-Plus, Jack, Micro Bridge) for completeness.
- [ ] Write-up: systems paper / arXiv preprint — "full-game learned-plus-search agent, reproducible WBridge5 benchmark, open harness." Getting a number on the record before or alongside Miai's paper matters.

### E — Miai access and the head-to-head (V2)

- [ ] **Outreach** (user decision): reply to the author's open invitation — offer the harness and zero-click WBridge5 automation, propose a shared benchmark protocol, and a head-to-head. Collaboration beats cold competition here: a joint benchmark with MIT's name on it is worth more than a unilateral claim.
- [ ] **Technical paths to a match if they're willing**: (a) they expose a Blue Chip client (our TM server is the venue), or (b) they run their agent against our released engine; (c) fallback — a thin proxy client that drives their multiplayer room WebSocket, *only with permission*.
- [ ] **Track** arXiv/their site for the Miai paper, Level 1, and any released weights; re-baseline immediately when anything lands.

## Sequencing and milestones

Rough order, assuming part-time effort and cloud GPU for training:

| # | Milestone | Depends on | Exit signal |
|---|---|---|---|
| M1 | 2,048-board harness run + BEN & WB5-vs-WB5 baselines with CIs | A | report with DD decomposition |
| M2 | Kita reproduced; bidder exported | B | ≥ +1.0 DD vs WB5 |
| M3 | Play engine break-even vs WB5 on fixed auctions | C | play-only match ≥ 0 at 2σ |
| M4 | Integrated engine beats Miai's margin in regression | D | ≥ +0.6 on 512 boards |
| M5 | **V1 match + public report** | M1–M4 | ≥ +0.6 at 2σ over ≥2,048 |
| M6 | **V2 head-to-head** | E | match played, result published |
| M7 | Belief search in play (ReBeL/SoG-style), human ladder | M5 | — north star work resumes |

M1 and M2 can start now and are independent; M3 starts as soon as M1's engine scaffold runs.

## Compute plan

- **Local (this machine): evaluation only** — WBridge5 instances, the TM server, DDS scoring. Light and already proven. Overnight unattended runs are the norm.
- **Cloud GPU for training (B)**: Kita-scale PPO/FSP is a single-GPU, ~days job; budget one A100/H100-class instance for the reproduction and another round for belief-net + ablations. Decide provider when M2 starts.
- **Inference** for the engine is CPU-friendly (ONNX, small nets); DDS sampling is the cost — measure and tune sample counts against boards/hour in M1.

## Risks

- **Moving target**: Miai's paper/Level 1 could post a much bigger margin. Mitigation: keep search headroom in both phases; publish early; pursue V2 so the comparison is direct rather than a numbers race.
- **Bidding-only metrics mislead**: DD-scored bidding overstates; the harness's full-game number is the only one we claim.
- **Warm-start dependence**: bidding on WBridge5 data inherits its conventions and quirks (44% agreement with pure SAYC engines). Acceptable for bot matches; human-compatibility is Phase-4 work.
- **Licensing**: BEN-derived play code is GPL-3.0 — fine for an open research engine; harness and training code remain ours (MIT/Apache). Re-evaluate only if a closed product is ever contemplated.
- **Variance underestimation**: use the WB5-vs-WB5 control to measure per-board SD on *our* deals before claiming significance.

## What this changes from v1

- Goal reframed from "claim a dormant SOTA" to "beat a named, active competitor" with quantified victory conditions.
- Play engine promoted from Phase 2 afterthought to a co-equal workstream — it is the largest measurable gap in the competitor.
- Board counts doubled (≥2,048) and a WB5-vs-WB5 control added; DD decomposition made standard.
- Outreach to MIT added as a first-class workstream.
- Superhuman research (belief-state search, disclosure, human ladder) sequenced after M5 rather than run in parallel.
