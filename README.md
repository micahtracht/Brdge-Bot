# BridgeBot

A research project to build the strongest computer bridge player in the world.

**Goal 1 (SOTA):** Beat the reigning bots — WBridge5, Jack, and the World Computer Bridge Championship field — in long, verifiable IMP matches, claiming the (currently dormant) state of the art in complete-game computer bridge.

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
engine/              # (future) the bot itself: bidding policy, belief model, cardplay
eval/                # (future) match harness, table-manager protocol, baselines
data/                # (future) deal generation, hand records, training data
experiments/         # (future) training runs, ablations, results
```

## Status

- 2026-08-14: Project started. Research phase — see `docs/research/` and `docs/PLAN.md`.
