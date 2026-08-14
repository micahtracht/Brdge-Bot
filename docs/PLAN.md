# BridgeBot Research Plan

*v1 — 2026-08-14. Companion reports: [BEN deep-dive](research/ben-engine-deep-dive.md), [literature review](research/literature-review.md), [tooling & evaluation](research/tooling-and-evaluation.md), [superhuman gap](research/superhuman-gap.md).*

## Goals

**Tier 1 — claim SOTA in computer bridge.** Be demonstrably the strongest *complete* bridge program (bidding + declarer play + defense), verified by long full-game IMP matches against the reigning engines — WBridge5 first, then Q-Plus/Jack/Micro Bridge — and by entering the active unofficial championships (Goulden UK, Hjalmarsson/computerbridge.se).

**North star — superhuman.** Beat top human partnerships at full bridge under tournament conditions with legal disclosure. No system has ever done this; the closest attempt (Jack vs. top Dutch pairs, 2005–06) lost 359–385 IMPs, and NooK 2022 tested only declarer play against bot defenders.

## What the research established (load-bearing facts)

1. **The published bidding SOTA is beatable-with-known-methods.** Kita et al. 2024 ([arXiv:2406.10306](https://arxiv.org/abs/2406.10306)): supervised warm-start on OpenSpiel's 12.8M WBridge5 dataset + PPO with fictitious self-play, 4-layer MLP, no search → **+1.24 ± 0.19 IMPs/board vs WBridge5**, open source (PGX/JAX). Qiu et al. 2024 (BMCS): +0.98 over 10k deals with a belief-network Monte Carlo search layer that adds ~+0.30 on its own. These two are uncombined — an SL+FSP policy *plus* belief search is the obvious first-novel-result.
2. **But bidding-only + double-dummy scoring is a lab metric, not a SOTA claim.** Every published number carves out the play phase. The credible claim requires full-game matches over the Blue Chip table-manager protocol — which is exactly how WCBC ran and how the unofficial events still run.
3. **BEN is the full-game scaffold.** Open source (GPL-3.0), actively maintained, ships a Blue Chip v18 client, full retraining pipeline, and already came within 12 IMPs of WBridge5 over 160 boards. Its known losses: declarer-play blunders (~50 IMPs in one 4-set match), no RL, imitation-capped bidding, no defensive-signal understanding.
4. **Evaluation math**: per-board net-IMP SD ≈ 5.4, so detecting a δ IMP/board edge at 2σ needs ≈ (10.8/δ)² boards — ~470 boards for δ=0.5, ~1,200 for δ=0.3. Championship matches (16–128 boards) are far too short to prove superiority; our claims must rest on 1,000+ board automated matches with duplicated deals.
5. **Nobody is defending the throne.** WBridge5 frozen since ~2014; official WCBC dormant since 2019; NukkAI exited bridge; FAIR/DeepMind moved on. The active frontier is one Kyoto lab, one journal group, and the BEN/BBO community.

## Strategy

Two tracks, in order, with a shared evaluation backbone:

- **Track A (engineering, Tier 1):** stand on BEN's shoulders — replace its imitation-learned bidding with a modern SL+RL+belief-search policy, and fix its declarer-play blunder classes — then beat WBridge5 and the championship field at full bridge.
- **Track B (research, north star):** the open-lane problems no one has published: belief-state search for the 2-team cooperative setting (ReBeL/Student-of-Games adapted), defense with signaling, and disclosable learned bidding. Track A's infrastructure (env, belief models, match harness) is Track B's substrate.

### Phase 0 — Infrastructure (the evaluation backbone)

*Everything else is meaningless without a trustworthy harness.*

- [x] Python env; **endplay** (MIT: DDS solving, dealer, PBN/LIN parsing, scoring) as the core library; verify DDS batch throughput on this machine. *(2026-08-14: endplay 0.5.12, ~730 ms/deal full DD tables single-threaded; endplay has no IMP table — implemented in `harness/scoring.py`.)*
- [ ] Get **WBridge5 5.12** running on Windows 11; get **BEN** running locally (Docker or native). *(WBridge5 installer must be user-downloaded: exe over plain HTTP from wbridge5.com.)*
- [~] **Match harness**: implement a clean, open-source **Blue Chip v18 table-manager server** (spec: [archived v18 gist](https://gist.github.com/ed2k/f62f4e5cf418fa3eef9ac06ea36be5b3); conformance targets: BEN's `table_manager_client.py`, WBridge5, Bridge Moniteur). Headless, scriptable, duplicated-board team matches, PBN in/out, IMP scoring, resumable. *This doesn't exist as a polished open project — it's a small, well-bounded contribution the community will adopt, and it makes our results reproducible by anyone.* *(2026-08-14: skeleton working in `harness/tm/` — full board cycle incl. auction relay, dummy control, scoring; e2e-tested against scripted mock clients (`harness/test_e2e.py`). Wire format grounded in BEN's client source (vendored sparse clone in `vendor/ben`, gitignored). Still to do: conformance vs real BEN/WBridge5, alerts passthrough polish, restart/timeout handling, duplicated-board team-match orchestration + IMP totals.)*
- [ ] **Baseline matches** to validate the rig and set the bar: BEN vs WBridge5, 1,000+ boards, published PBNs. This reproduces/extends the community's 2024 results and gives us the variance constants for our own deals.
- [ ] Stats module: IMP variance, confidence intervals, cross-imping; every reported result carries error bars.

**Exit criteria:** unattended 1,000-board BEN-vs-WBridge5 match completes overnight with scored PBN output.

### Phase 1 — Reproduce and combine the published bidding SOTA

- [ ] Reproduce **Kita et al.** from their open code ([harukaki/brl](https://github.com/harukaki/brl), PGX env, OpenSpiel WBridge5 dataset): SL warm-start → PPO/FSP. Target: confirm ≈ +1.2 IMPs/board bidding-only vs WBridge5.
- [ ] Add a **belief network + Belief Monte Carlo Search** layer (Qiu et al.'s recipe) on top of the reproduced policy — the first plausibly-novel result, since the two 2024 papers were never combined.
- [ ] Cross-evaluate: our policy vs Kita's released models, vs BEN's bidder, bidding-only and (via Phase 0 harness) full-game with a fixed play engine.
- [ ] Ablate what actually matters (FSP vs plain PPO, belief-search sample counts, network scale — nobody has published a scaling study for bridge bidding).

**Exit criteria:** bidding policy ≥ +1.5 IMPs/board bidding-only vs WBridge5 over ≥10k deals, and measurably better than BEN's bidder inside a full-game engine.

### Phase 2 — The full-game engine

- [ ] **Integration**: our bidding policy inside a BEN-derived full engine (GPL-compatible; we're open source anyway). BEN's sampling/DDS play stack is the starting point.
- [ ] **Declarer play**: attack BEN's documented blunder classes. Candidates: more/better-weighted samples, PIMC→αμ-style search (repairs strategy fusion; NukkAI's substrate, published at [arXiv:1911.07960](https://arxiv.org/abs/1911.07960)), learned play policy for sample plausibility, opening-lead retraining.
- [ ] **Defense**: the weakest phase of every engine and the least published — even a modest learned signaling model (partner-consistent carding + inference from partner's signals in the sampler) is headroom nobody has claimed.
- [ ] Continuous regression matches vs WBridge5 + BEN-stock via the Phase 0 harness; every change gates on full-game IMPs, not proxy metrics.

**Exit criteria (the SOTA claim):** beat WBridge5 at full bridge over ≥1,000 duplicated boards by a statistically significant margin (≥2σ), and beat stock BEN likewise. Publish deals, logs, and harness for reproduction.

### Phase 3 — Make the claim stick

- [ ] Acquire and beat the commercial field under the same protocol: **Q-Plus** (2023 unofficial champion), **Jack** (€89, 10 WCBC titles), **Micro Bridge** (2019 official champion).
- [ ] Enter the **Goulden** and **computerbridge.se** events (they accept TM-protocol bots; BEN entered exactly this way in 2024).
- [ ] Write it up — the combination of (reproducible full-game harness + combined SL/RL/BMCS bidding + defense results) is a publishable systems paper; IEEE CoG / journal venues are where this literature lives.

### Phase 4 — Toward superhuman (research program, parallel once Phase 2 is stable)

The three open problems, in rough order of expected IMP yield:

1. **Full-game belief-state search.** No published bridge instantiation of the ReBeL/Student-of-Games recipe exists; the 2-team cooperative setting breaks its 2p0s guarantees, and making a sound-enough variant is the core research bet. Start with play (defense especially), where the cooperative-communication complication is smaller than in bidding.
2. **Human-compatible, disclosable bidding.** Self-play invents illegal-to-play alien conventions (Law 40 / WBF Systems Policy: implicit agreements must be disclosable; wrong explanations = misinformation). Research line: constrain RL to stay near a filed human system (Lockhart-style anchoring, Hanabi Off-Belief Learning applied to bridge — unpublished gap), and auto-generate convention cards/alerts from the learned policy. Prerequisite for any human match, and independently publishable.
3. **Anti-exploitation robustness.** The NooK lesson in reverse: our engine must not be tuned to one deterministic opponent. Opponent-model ensembles in the sampler (WBridge5-ish, GIB-ish, human-Vugraph-ish defenders) and evaluation against held-out opponent styles.
- **Human evaluation ladder:** BBO robot-field percentages (public monthly rankings give a yardstick vs Advanced GIB/Big Ben) → expert pairs online with pre-registered stats → formal challenge match (hundreds of boards, duplicated teams format, named partnership, agreed disclosure). Per the variance math, a credible human match is ≥500 boards — a multi-session event that needs partners in the bridge world; start those conversations only after Phase 3.

## Risks and open questions

- **WBridge5 saturation**: "beats WBridge5" is necessary but weakening as a headline; that's why Phase 3 covers the whole field and Phase 4 defines the human ladder.
- **Bidding-only metrics can mislead**: double-dummy playout scoring mis-values contracts that depend on single-dummy play; the harness (full-game) is the source of truth, lab metrics are for iteration speed.
- **GPL-3.0** (BEN-derived code): fine for an open research project; would constrain a future closed product. Decision deferred; the harness and training code we write from scratch can be MIT/Apache.
- **Compute**: Kita-scale training ran on a single modern GPU-class budget; Phase 4 search methods may need real money. Revisit at Phase 4 entry.
- **Bot disclosure in bot events**: the TM protocol carries alerts; championship bots disclose via convention cards. Our RL bidder's system must be documentable even for bot-vs-bot events — a soft forcing function toward problem 2.

## Directory layout (target)

```
docs/            # this plan + research reports
harness/         # Blue Chip v18 table manager server + match orchestration, stats  [Phase 0]
engine/          # the bot: bidding policy, belief models, play engine              [Phase 1-2]
training/        # SL/RL pipelines, configs, ablations                              [Phase 1+]
data/            # deal sets, PBN archives, published match records                 [Phase 0+]
experiments/     # run logs, results, error-bar reports                             [Phase 1+]
```

## Immediate next actions

1. Phase 0 bootstrap: Python env + endplay + DDS smoke test; download WBridge5 and BEN and play a manual-config match to see the moving parts.
2. Start the table-manager server against the v18 spec with BEN's client as the conformance test.
3. Reproduce Kita et al. training while the harness work proceeds (independent tracks).
