# BridgeBot

A research project to build the strongest computer bridge player in the world.

**Goal (as of Aug 2026): beat Miai.** [Miai](https://bridge.miai.moe) (Zhiyuan Fan, Gabriele Farina's group at MIT) is a from-scratch self-play full-game bridge agent that scores +0.21 IMP/board vs WBridge5 over 1,024 duplicated boards. We aim to exceed that margin by a wide, statistically clean gap under a stricter public protocol (≥2,048 boards, ≥2σ), then beat it head-to-head. See [docs/PLAN.md](docs/PLAN.md).

**North star (superhuman):** Beat top human partnerships at full contract bridge — bidding and play — under tournament conditions with legal disclosure.

## Why this is winnable

Bridge is the last classic game where the best humans still beat the best machines, and the gap exists mostly because almost no modern effort has been aimed at it:

- The reigning champion programs (WBridge5, Jack, Micro Bridge) are decades-old, largely hand-crafted systems maintained by one or two people each.
- No major lab has attempted bridge with post-2020 techniques; NukkAI's NooK (2022) only addressed declarer play, not the full game.
- The open tooling is mature: perfect double-dummy solving (DDS), an open-source neural engine to build on (BEN), cheap deal generation, and an established bot-vs-bot match protocol.
- The hard unsolved core is **bidding as constrained-bandwidth cooperative communication** — squarely the kind of problem modern self-play RL and belief modeling are good at.

## Repository layout

```
docs/
  PLAN.md            # research roadmap: phases, milestones, evaluation criteria
  research/          # deep-dive reports (prior work, tooling, evaluation landscape)
harness/             # (future) Blue Chip v18 table manager + match orchestration
engine/              # (future) the bot itself: bidding policy, belief model, cardplay
training/            # (future) SL/RL pipelines, configs, ablations
data/                # (future) deal generation, hand records, training data
experiments/         # (future) training runs, ablations, results
```

## Status

- 2026-08-21: Goal reframed around beating Miai; roadmap v2 in `docs/PLAN.md`.
  Harness validated against real WBridge5 (zero-click, invisible automation).
- 2026-08-14: Project started. Research phase complete — four deep-dive reports in
  `docs/research/` and a phased roadmap in `docs/PLAN.md`. Next up: Phase 0
  (evaluation harness — endplay/DDS env, WBridge5 + BEN locally, Blue Chip v18
  table-manager server, 1,000-board baseline matches).
