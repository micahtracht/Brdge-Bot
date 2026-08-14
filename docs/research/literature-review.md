# AI for Contract Bridge: A Literature Review

> Research report, 2026-08-14. Scope: academic and research literature on bridge AI with emphasis on bidding, mapped for a research effort aiming first to beat existing bots, then reach superhuman play. Benchmark note up front: nearly every modern bidding paper evaluates against **WBridge5** (Yves Costel's rule-based program, multiple-time World Computer-Bridge Champion), in a protocol where the neural agents replace one pair and duplicate scoring in IMPs is used.

---

## 1. Classic foundations (1996–2010)

**Partition Search — Matthew L. Ginsberg (AAAI 1996).**
Introduced the core efficiency trick behind fast double-dummy solving: instead of caching single positions in a transposition table, cache *sets* of positions (partitions) that provably share the same minimax value — e.g., hands equivalent up to small-card permutation. This collapses the double-dummy search space dramatically (GIB reports ~18,000 nodes per deal) and is the ancestor of the techniques inside modern double-dummy solvers (e.g., Bo Haglund's open-source DDS, which is the workhorse of nearly all later RL papers' reward functions).

**GIB: Steps Toward an Expert-Level Bridge-Playing Program — M. L. Ginsberg (IJCAI 1999).** [PDF](https://www.ijcai.org/Proceedings/99-1/Papers/084.pdf)
**GIB: Imperfect Information in a Computationally Challenging Game — M. L. Ginsberg (JAIR 14, 2001).** [arXiv:1106.0669](https://arxiv.org/abs/1106.0669), [JAIR](https://www.jair.org/index.php/jair/article/view/10279)
The canonical bridge AI papers. Method: Perfect Information Monte Carlo (PIMC) — sample deals consistent with the bidding/play so far, solve each double-dummy with partition search, choose the action with the best expected score across samples (an idea due to Levy, first made practical here). Applied to both cardplay and bidding: for bidding, GIB samples hands, consults a large hand-constructed bid-meaning database, and simulates auctions forward to evaluate candidate bids. Five contributions: partition search, practical Monte Carlo, "achievable sets" to mitigate Monte Carlo pathologies, alpha-beta over distributive lattices, and squeaky-wheel optimization for cardplay. GIB reached roughly expert (not world-class) level and was the strongest program of its era. Key limitations acknowledged: PIMC's structural errors (below), and the bidding database's incompleteness/ambiguity — GIB's bidding was its weakest phase, a pattern that persists across all successors.

**Finding Optimal Strategies for Imperfect Information Games — Ian Frank & David Basin (AAAI 1998; also AIJ 1998 "Search in games with incomplete information").** [PDF](https://cdn.aaai.org/AAAI/1998/AAAI98-071.pdf)
The theoretical critique that frames everything since: PIMC suffers from **strategy fusion** (assumes the agent can act differently in states it cannot distinguish — i.e., it "peeks" by choosing per-world best moves) and **non-locality** (the value of a subtree depends on opponents' inferences formed elsewhere in the tree, so local analysis is wrong). Every serious bridge search paper since (GIB, αμ, NooK) is an attempt to repair these two errors.

**Understanding the Success of Perfect Information Monte Carlo Sampling in Game Tree Search — J. Long, N. Sturtevant, M. Buro, T. Furtak (AAAI 2010).** [PDF](https://webdocs.cs.ualberta.ca/~nathanst/papers/pimc.pdf)
Explains *why* PIMC works well in trick-taking games despite being theoretically unsound: introduces game properties (leaf correlation, bias, disambiguation) under which PIMC's errors are small. Bridge cardplay scores favorably; this is the standing justification for double-dummy-based evaluation and also a warning about where it breaks (deceptive/defensive carding situations).

**Information Set MCTS — P. Cowling, E. Powley, D. Whitehouse (IEEE TCIAIG 2012).** [PDF](https://eprints.whiterose.ac.uk/id/eprint/75048/1/CowlingPowleyWhitehouse2012.pdf)
ISMCTS searches over information sets rather than determinized worlds, partially addressing strategy fusion. Not bridge-specific but widely applied to trick-taking games; relevant as the standard alternative to PIMC for the play phase.

**Learning to Bid in Bridge — Asaf Amit & Shaul Markovitch (Machine Learning 63:287–327, 2006).** [Springer](https://link.springer.com/article/10.1007/s10994-006-6225-2)
The first substantial *learning* approach to bidding. Method: a bidding decision network (tree of bidding rules), model-based Monte Carlo sampling that uses explicit models of both partner and opponents to sample consistent hands, and a co-training loop where the partnership refines rule-selection strategies from accumulated conflict examples. Pre-deep-learning, but notable for taking partnership modeling seriously — something several modern self-play papers arguably regress on.

**The State of Automated Bridge Play — Paul M. Bethe (NYU tech report, 2010; MS thesis 2021 "Advances in Computer Bridge").** [2010 review](https://cs.nyu.edu/~pbethe/bridgeReview200908.pdf), [thesis](https://cs.nyu.edu/media/publications/bethe_pm_thesis_final.pdf)
Useful survey of the pre-neural era (GIB, Jack, WBridge5, Bridge Baron) and of the persistent gap: programs at strong-club-player level, world-class only in constrained cardplay settings. Also documents that WCBC winners (Jack, WBridge5) were commercial and largely unpublished — a reason the academic literature under-describes the actual strongest classical bots.

Minor classics worth knowing: **Sarkar et al., "Neural networks for contract bridge bidding" (Sādhanā, 1995)** — earliest NN bidding attempt; **DeLooze & Downey (2007)** — self-organizing maps for bidding.

---

## 2. Neural / RL bidding line (2016–2024)

**Automatic Bridge Bidding Using Deep Reinforcement Learning — Chih-Kuan Yeh, Cheng-Yu Hsieh, Hsuan-Tien Lin (ECAI 2016; IEEE TCIAIG 2018).** [arXiv:1607.03290](https://arxiv.org/abs/1607.03290), [code](https://github.com/chihkuanyeh/Automatic-Bridge-Bidding-by-Deep-Reinforcement-Learning)
The NTU paper that started the modern line. Method: layered Q-learning networks (one per bidding round) learning a bidding "language" from raw cards with **no human bidding-system knowledge**, UCB-style exploration, double-dummy rewards. Crucial simplification: **collaborative/uncontested bidding only** (opponents always pass), capped auction length. Result: beat a champion rule-based program *in this restricted setting*. Limitation: the restriction is severe — competitive interference is most of what makes real bidding hard — and the learned language is opaque to humans.

**Competitive Bridge Bidding with Deep Neural Networks — Jiang Rong, Tao Qin, Bo An (AAMAS 2019).** [arXiv:1903.00900](https://arxiv.org/abs/1903.00900)
First full *competitive* bidding system via deep learning. Method: compact card/auction encoding; an **Estimation Neural Network (ENN)** that infers partner's hand distribution from the auction, and a **Policy Neural Network (PNN)** that takes ENN output as input to choose bids; both ~10-layer MLPs with skip connections; supervised pre-training on human expert data (Vugraph records), then RL self-play fine-tuning. Result: reported superiority over Yeh & Lin's model and over **WBridge5 by ~0.25 IMPs/board** (the number cited by follow-up work). Limitations: explicit belief modeling only of partner (not opponents); evaluation protocol later criticized (bidding-only with double-dummy playout scoring, modest sample sizes); human-data dependence anchors it to human conventions.

**Simple is Better: Training an End-to-end Contract Bridge Bidding Agent without Human Knowledge — Qucheng Gong, Yu Jiang, Yuandong Tian (Facebook AI; ICML RWSDM workshop 2019).** [PDF](https://realworld-sdm.github.io/paper/42.pdf), [OpenReview](https://openreview.net/forum?id=SklViCEFPH)
A2C self-play from scratch (no human data), simple MLP, double-dummy rewards; also released a large double-dummy-solved deal dataset. Reported **+0.41 IMPs/board vs WBridge5**. Notable because it claimed pure self-play beats supervised approaches — a claim Kita et al. (2024) later **failed to reproduce** without supervised pre-training. Treat with caution; reproducibility is a known problem in this subfield.

**Joint Policy Search for Multi-agent Collaboration with Imperfect Information — Yuandong Tian, Qucheng Gong, Tina Jiang (Facebook AI; NeurIPS 2020).** [arXiv:2008.06495](https://arxiv.org/abs/2008.06495), [code](https://github.com/facebookresearch/jps)
The theoretical centerpiece of the FAIR line. Insight: in collaborative imperfect-information games, unilateral (per-agent) policy improvement can decrease joint value; JPS proves a **policy-change decomposition** allowing *joint* tabular policy updates of the partnership evaluated locally (without re-evaluating the whole game), with guaranteed non-decrease in value. Applied on top of a trained A2C baseline for bridge bidding: **+0.63 IMPs/board vs WBridge5 over 1,000 boards**. Limitations: JPS itself is tabular/local (scales via sampled situations), bidding evaluated with double-dummy playouts, and the improvement is on top of a self-play policy whose conventions are non-human-readable. Follow-up interest fizzled at FAIR after 2020; no published JPS-2.

**Human-Agent Cooperation in Bridge Bidding — Edward Lockhart, Neil Burch, Nolan Bard, Sebastian Borgeaud, Tom Eccles, Lucas Smaira, Ray Smith (DeepMind; arXiv 2020, Cooperative AI workshop).** [arXiv:2011.14124](https://arxiv.org/abs/2011.14124)
The most practically influential paper for "human-compatible" bidding. Method: imitation learning from data generated by a hand-coded human-convention bot (WBridge5-style SAYC), then **policy iteration with search**: at each state sample deals consistent with the auction from the current policy's implied beliefs, evaluate candidate bids by rollouts (test-time search ≈ GIB's simulation idea, but with learned policies as the model of all four players), distill back into the network. Results: state of the art in three settings — self-partnership (**+0.85 IMPs/board vs WBridge5**, the long-standing SOTA number), partnering WBridge5 itself, and partnering a human expert. This is the "PI + search" baseline later papers chase. Limitations: anchored to an existing human system (by design); search quality bounded by belief-consistency sampling; play phase still delegated to double-dummy.

**The Synergy of Double Neural Networks for Bridge Bidding — (MDPI Mathematics 10(17):3187, 2022).** [MDPI](https://www.mdpi.com/2227-7390/10/17/3187)
Bidding-selection + evaluation network pair; incremental; mainly useful as evidence of continued activity outside the main labs.

**AI Enabled Bridge Bidding Supporting Interactive Visualization — (Sensors 22(5):1877, 2022; Warsaw group).** [DOI](https://doi.org/10.3390/s22051877)
Applied/engineering paper from the Polish group (same ecosystem as BridgeHand2Vec); bidding models plus visualization tooling for humans.

**BridgeHand2Vec: Bridge Hand Representation — Anna Sztyber-Betley et al. (ECAI 2023).** [arXiv:2310.06624](https://arxiv.org/abs/2310.06624)
Embeds a 13-card hand into a small vector space by training a network to predict tricks taken by a pair (SOTA on the double-dummy-prediction DDBP2 task); distances in the space are interpretable (hand strength/shape). Demonstrated uses: RL feature input, opening-bid classification. Relevant as a candidate learned representation and as a fast learned stand-in for double-dummy evaluation.

**Alternate Inference-Decision Reinforcement Learning with Generative Adversarial Inferring for Bridge Bidding — (Neural Computing & Applications, 2024).** [Springer](https://link.springer.com/article/10.1007/s00521-024-09860-2)
Chinese-group paper making partner-hand inference a first-class citizen: a **generative adversarial inference module** (models stochasticity/noise in hand inference rather than point estimates) alternating with policy learning (AID-RL). Continuation of the Rong et al. ENN idea with better-calibrated beliefs. Modest visibility; worth reading for the belief-modeling architecture.

**A Simple, Solid, and Reproducible Baseline for Bridge Bidding AI — Haruka Kita, Sotetsu Koyamada, Yotaro Yamaguchi, Shin Ishii (Kyoto U.; IEEE CoG 2024).** [arXiv:2406.10306](https://arxiv.org/abs/2406.10306), [IEEE](https://ieeexplore.ieee.org/document/10645547/)
The current reproducibility anchor. Method: deliberately vanilla — 4-layer MLP (1024 units), supervised pre-training on OpenSpiel's 12.8M WBridge5-generated state-action pairs, then **PPO with fictitious self-play** (to damp policy cycling), double-dummy rewards, massively vectorized environments (their PGX/JAX ecosystem). Result: **+1.24 ± 0.19 IMPs/board vs WBridge5 over 1,000 boards**, vs prior reported numbers of +0.41 (Gong), +0.63 (JPS), +0.85 (Lockhart). No test-time search at all. Key findings for planning: (a) they could **not** get pure-RL-from-scratch to beat WBridge5, contradicting Gong et al.; (b) SL warm-start + plain PPO/FSP beats all the fancier published pipelines; (c) code and models are open source. Limitations (stated): nothing bridge-specific in the design; evaluation still bidding-phase-only with double-dummy playouts.

**Bridge Bidding via Deep Reinforcement Learning and Belief Monte Carlo Search — Zizhang Qiu, Shouguang Wang, Dan You, MengChu Zhou (IEEE/CAA Journal of Automatica Sinica 11(10):2111–2122, 2024).** [IEEE](https://ieeexplore.ieee.org/document/10664606/), [JAS page](https://www.ieee-jas.net/article/doi/10.1109/JAS.2024.124488)
The strongest fully-described pipeline in a journal venue: SL policy network on WBridge5 data → self-play deep RL with **Diverse PPO Ensembling** (ensemble of PPO updates with different clipping/entropy regularizers to avoid local optima) → **Belief Monte Carlo Search (BMCS)** at test time: sample hidden hands from a learned belief network conditioned on the auction, then Monte Carlo evaluate candidate bids. Result: **+0.98 IMPs/deal vs WBridge5 over 10,000 deals** (they cite +0.85 as prior SOTA); the BMCS component alone adds +0.30 IMPs/deal vs +0.28 for Lockhart-style PI-search. Limitations: belief network trained from self-play policy (belief mismatch vs other partners/opponents); still double-dummy-scored bidding-only evaluation.

---

## 3. NukkAI's NooK (2022)

**What is claimed.** French lab NukkAI's NooK beat 8 world champions in a March 2022 challenge. Public technical description (no full technical paper was ever released): a **hybrid neuro-symbolic system** — human bridge expertise encoded as relational-logic background knowledge, probabilistic **inductive logic programming** (lineage: Stephen Muggleton's group at Imperial) plus neural modules, with human-readable explanations for each decision. The game-tree search over possible worlds is an optimized extension of **αμ** (below). Coverage: [Imperial College announcement](https://www.imperial.ac.uk/news/235238/ai-based-imperial-research-beats-world/), [Singularity Hub](https://singularityhub.com/2022/04/03/a-hybrid-ai-just-beat-eight-world-champions-at-bridge-and-explained-how-it-did-it/), [computerbridge.se writeup](https://www.computerbridge.se/nukkai/).

**The published substrate (Cazenave & Ventos line):**

- **The αμ Search Algorithm for the Game of Bridge — Tristan Cazenave, Véronique Ventos (2019).** [arXiv:1911.07960](https://arxiv.org/abs/1911.07960) — anytime search that keeps a *vector of outcomes across sampled worlds* (Pareto fronts over possible worlds) rather than per-world scalars, explicitly repairing PIMC's strategy fusion and (partially) non-locality for declarer play.
- **Optimizing αμ — Cazenave & Ventos (2021).** [arXiv:2101.12639](https://arxiv.org/abs/2101.12639) — transposition tables and pruning to make αμ practical.
- **Construction and Elicitation of a Black Box Model in the Game of Bridge — Ventos et al. (2020).** [arXiv:2002.01080](https://arxiv.org/abs/2002.01080v1) — extracting symbolic explanations from a neural bridge decision model.
- **Bridge: New Challenge for Artificial Intelligence — Ventos & Cazenave (Revue d'IA, 2017).** [IIETA](https://www.iieta.org/journals/ria/paper/10.3166/RIA.31.249-279) — position paper arguing bridge as the post-Go AI challenge.

**Informed critiques of the challenge design** (best single source: ["So has AI conquered Bridge?" on LessWrong](https://www.lesswrong.com/posts/yHxmJch8dJoH6dwwz/so-has-ai-conquered-bridge); see also the BridgeWinners ["Conclusions"](https://bridgewinners.com/article/view/conclusions/) thread):

1. **Declarer play only** — no bidding, no defense. The contract was fixed at **3NT on every one of the 800 hands** (8 humans × 100 hands); humans and NooK declared the same deals.
2. **Defenders were bots** (WBridge5-class). WBridge5's defenders signal honest count deterministically; NooK, trained against these exact opponents, learned to *exploit their leaks* (e.g., dropping offside doubleton queens read from carding), while human declarers unfamiliar with bot-defense quirks played "normal" lines and went down. So part of the margin is opponent-exploitation, not superhuman declarer technique.
3. **No partnership/communication element at all** — the hard, unsolved part of bridge (bidding + defensive signaling) was excluded; "AI beats world champions at bridge" headlines substantially overstate the result.
4. No peer-reviewed technical paper describes NooK end-to-end; claims about PILP+RL internals are not independently verifiable. NukkAI has since pivoted commercially (crew scheduling etc.).

---

## 4. Recent and adjacent work (2023–2026)

**Student of Games — M. Schmid, M. Moravčík, N. Burch, ... M. Bowling (Science Advances 2023).** [arXiv:2112.03178](https://arxiv.org/abs/2112.03178), [Science Advances](https://www.science.org/doi/10.1126/sciadv.adg3256)
Unified sound search+learning for perfect and imperfect information games (growing-tree CFR with public-belief-state value networks; lineage DeepStack→SoG). Strong in chess, Go, HUNL poker, Scotland Yard. **Not applied to bridge**, and the obstacle is instructive: bridge's public belief state ranges over C(52,13)-scale hidden-hand joint distributions with *cooperative* signaling, and 4 players in 2 teams breaks the 2-player zero-sum guarantees that make CFR-style search sound. Same story for **ReBeL** (Brown et al., NeurIPS 2020): the recipe (RL + search on public belief states) is the obvious "north star" architecture for bridge, but no published bridge instantiation exists — arguably the biggest open opportunity in the space.

**AlphaZe\*\*: AlphaZero-like baselines for imperfect information games are surprisingly strong — (Frontiers in AI / PMC 2023).** [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC10213697/)
Perfect-information-style AlphaZero training applied naively to imperfect-info games works better than expected — relevant sanity check for "just AlphaZero it" approaches to bridge play.

**Transformer-Based Planning in the Observation Space for Trick-Taking Card Games — (2024).** [arXiv:2404.13150](https://arxiv.org/abs/2404.13150)
Transformer world-model planning for trick-taking games (Skat family); the nearest published "transformer for trick-taking" work. Also **Outer-Learning Framework for Multi-Player Trick-Taking Games: Skat** ([arXiv:2512.15435](https://arxiv.org/pdf/2512.15435)) continues the Skat line (Buro/Edelkamp school) — methodologically transferable to bridge play.

**PGX: Hardware-accelerated parallel game simulators — Koyamada et al. (NeurIPS 2023 D&B).**
JAX-based vectorized environments **including bridge bidding**; the infrastructure behind Kita et al. 2024. Together with **OpenSpiel** (which ships a bridge environment, the 12.8M-hand WBridge5 SL dataset, and a WBridge5 interconnect), this is the de facto tooling stack for new efforts.

**LLMs and bridge.** No serious academic paper yet shows LLMs bidding competently. The main artifact is the open **bridge-llm-bench** ([GitHub](https://github.com/albertogerli/bridge-llm-bench), [BridgeWinners writeup](https://bridgewinners.com/article/view/can-llms-actually-bid-bridge-building-an-open-benchmark-for-sayc-and-where-i-want-to-take-it-next-2-vknv0ls637/), 2025–26): frontier LLMs graded against a SAYC oracle reach ~70–80% call accuracy with heavy prompting — useful as a probe, nowhere near bot strength. Interesting negative finding there: **WBridge5 agrees with dedicated SAYC engines only ~44% of the time**, underscoring how mushy "the baseline" is. General LLM-game benchmarks ([Game Reasoning Arena, arXiv:2508.03368](https://arxiv.org/pdf/2508.03368)) point the same direction. Also practically important though non-academic: **Ben** (Lorand Dali's open-source neural bridge engine), used as oracle infrastructure in the LLM benchmark and popular in the computer-bridge community.

**Human-compatibility research relevant to bidding conventions:** DeepMind's Lockhart et al. is the only bridge-specific entry, but the Hanabi line (Other-Play, Off-Belief Learning — Hu et al. 2020/2021) is the standard toolkit for "don't invent alien conventions" and has not yet been published as applied to bridge — another visible gap.

---

## 5. Theoretical framing: why bridge is hard (and different from poker)

Recurring points across the literature (Frank & Basin 1998; Ginsberg 2001; Ventos & Cazenave 2017; Tian et al. 2020; Lockhart et al. 2020):

1. **Cooperative communication under a constrained channel.** Bidding is simultaneously *communication to partner* and *concealment/interference vs opponents*, through a monotonically-rising, ~38-token shared channel. Poker methods optimize against adversaries; bridge additionally requires a *jointly learned code*. This makes the equilibrium concept itself murky: 2-team zero-sum games are not 2-player zero-sum; CFR/ReBeL soundness guarantees do not directly transfer, and unilateral best-response improvement can hurt the partnership (the JPS motivation).
2. **Convention/equilibrium multiplicity.** Many mutually-incompatible bidding systems are near-optimal. Self-play converges to arbitrary "alien" conventions; human-compatible play requires anchoring (imitation, regularization) — the bridge version of the Hanabi coordination problem. Related open problem: the **disclosure rule** — in real bridge, your system must be *explained to opponents* (alertable conventions), a constraint no published agent models; a superhuman claim arguably requires handling it.
3. **Belief-state scale and non-locality.** Hidden information is three 13-card hands (~10^16 deals prior); beliefs are conditioned on a growing public auction whose *meaning is policy-dependent* (partner's and opponents' inferences), which is exactly Frank & Basin's non-locality. Learned belief networks (Rong ENN; Qiu BMCS; GAI) are point-in-time fixes, all vulnerable to belief mismatch off-policy.
4. **Evaluation is unsolved.** Nearly every "beats WBridge5" number is (a) bidding-only, (b) scored by **double-dummy playout**, which systematically mis-scores contracts whose real value depends on single-dummy play and defense (Long et al. 2010 explains when this is benign); (c) computed over 1k–10k deals with high per-board variance; (d) against a baseline (WBridge5) that is itself ambiguous (see 44% SAYC-agreement finding) and frozen (last WCBC ~2019, program development largely stopped). No public head-to-head protocol covers full deals (bidding + play + defense) against strong humans.
5. **Full-game integration.** Bidding, declarer play, and defense (with defensive signaling — a second covert communication channel) have never been unified in one learned agent in the published literature. NooK did declarer-only; all RL bidding papers delegate play to double-dummy. Defensive signaling is essentially untouched by modern methods.

---

## 6. What's the strongest published bidding result vs WBridge5?

All numbers are IMPs/board, agent pair vs WBridge5 pair, bidding phase with double-dummy playout scoring:

| Paper | Year | Method | Result | Sample |
|---|---|---|---|---|
| Rong, Qin & An | 2019 | SL + RL, ENN+PNN | ~+0.25 | (paper's protocol) |
| Gong, Jiang & Tian | 2019 | A2C self-play, no human data | +0.41 (not reproduced) | 1k |
| Tian et al. (JPS) | 2020 | A2C + joint policy search | +0.63 | 1k |
| Lockhart et al. (DeepMind) | 2020 | Imitation + policy iteration + search | +0.85 | — |
| Qiu et al. (BMCS) | 2024 | SL + Diverse PPO + belief MC search | **+0.98** | **10k deals** |
| Kita et al. | 2024 | SL + PPO/FSP, no search | **+1.24 ± 0.19** | 1k deals |

**Answer:** the strongest published number is **Kita et al. 2024's +1.24 ± 0.19 IMPs/board** (open source, no test-time search), with **Qiu et al. 2024's +0.98 over 10,000 deals** the strongest large-sample result — and the two are roughly contemporaneous and not cross-evaluated against each other. Two implications for this effort: (1) the bar to "beat existing published bots" is a simple SL+PPO pipeline on open tooling (PGX/OpenSpiel) plus ideally a belief-search layer, and the two 2024 papers are the ones to reproduce first; (2) "superhuman" is unclaimed and essentially undefined in the literature — no published system plays full bridge (competitive bidding + declarer play + defense with signaling and disclosure) against humans, and the WBridge5-relative metric is saturating in credibility. The open lane is a ReBeL/SoG-style belief-state search architecture adapted to the 2-team cooperative setting, human-compatibility training à la Lockhart/OBL, and a full-game evaluation protocol.
