# BEN (Bridge ENgine) — Technical Deep-Dive

> Research report, 2026-08-14. Repo: https://github.com/lorserker/ben · Docs: https://lorserker.github.io/ben/ · License: **GPL-3.0**

## 1. Architecture

**Overall design:** Hybrid neuro-symbolic. Small supervised neural nets provide policy priors and hand inference; final decisions are made by Monte-Carlo sampling of hidden hands (constrained/scored by the NNs) evaluated with the double-dummy solver (DDS 3.0.0 via python-dds wrapper). Core modules in `src/`: `botbidder.py`, `botopeninglead.py`, `botcardplayer.py`, `sample.py`, `nn/`, plus optional engines `pimc/`, `bba/`, `suitc/`, `alphamju/`, `ddsolver/`.

**Neural networks** (`src/nn/`: `bidder`, `bid_info` ("binfo"), `leader`, `lead_singledummy`, `player`, `trick`, `contract` — each in TF2/Keras and ONNX variants):

- **Bidder:** LSTM recurrent net. Input per bidding round: own 32-card hand encoding + normalized HCP/shape + vulnerability (2 booleans) + one-hot bids (40-dim each) for LHO/partner/RHO and (since "BEN 2.0") the robot's own previous bid; output = softmax over next bid. Auction state is held implicitly in the LSTM. Described by Dali in "Bridge AI: How Neural Networks Learn to Bid" (https://bridgewinners.com/article/view/bridge-ai-how-neural-networks-learn-to-bid/); input encoding documented in `scripts/training/bidding/README.md`.
- **Bid-info net:** predicts each hidden player's HCP and suit shape from the auction — used to constrain sampling.
- **Leader / lead_singledummy nets:** opening-lead policy plus a single-dummy trick estimator that predicts trick outcomes per candidate lead (fast approximation to rollouts).
- **Player / trick nets:** card-play policy (separate NT vs. suit variants) trained on human play; also used to score plausibility of already-played cards.
- **Contract net:** contract/trick evaluation.

**Sampling + DDS glue** (`src/sample.py`): generates random layouts for the three unseen hands biased by binfo-predicted HCP/shape (honors placed first), then replays the actual auction through the bidder net for each hidden player, keeping only samples whose observed bids exceed probability thresholds (`bidding_threshold_sampling` etc.); during play, samples are further filtered by lead-model and player-model plausibility of cards already played. Accepted samples get composite weights (bidding fit × lead consistency × play quality) and feed DDS evaluation.

**Card play** (`src/botcardplayer.py`): NN softmax proposes/filters legal candidates → each candidate evaluated by DDS across the weighted sample set → expected tricks, expected IMP/MP score, and make-probability computed; ranking is primarily 5×make-probability, then expected tricks/score, then NN confidence, with heuristic adjustments (trump-drawing bonus, SuitC single-suit analysis in NT, carding conventions in `carding.py`). Optional engines: **PIMC** (perfect-information Monte Carlo, C#/BGA-style, in `src/pimc/`, results merged with DDS via configurable weights) and **AlphaMju** (α-μ style search for declarer). Bidding decisions similarly combine bidder-net candidates with DDS-scored simulated auctions; **BBA** (Edward Piwowar's Bridge Bidding Analyzer/EPBot, `src/bba/`) is integrated as an alternative rule-based bidder and for convention enforcement.

## 2. Training

- **Paradigm:** Pure supervised imitation learning — no self-play/RL in the repo. Original 2022 model: LSTM trained on ~500k boards with complete 2/1 auctions, batches of 100, ~1M updates, "a few hours" on CPU (GPU gives little speedup for this architecture) (https://bridgewinners.com/article/view/bridge-ai-how-neural-networks-learn-to-bid/).
- **Data:** Current models are trained on **machine-generated auctions from BBA** (Piwowar's Bidding Analyzer), not human data — e.g., the 2024 Camrose model used ~0.5M curated deals + sequences from 5M more, plus scenario deals from Practice Bidding Scenarios (https://bridgewinners.com/article/view/ben-vs-wbridge5-in-the-camrose-trophy-2024/). Datasets of ~1M deals each for SAYC, 2/1, Polish Club, Precision are referenced from the training docs. Play models were trained on master-level human play data.
- **Pipeline** (`scripts/training/` with subdirs `bidding`, `bidding_info`, `contract`, `opening lead`, `playing`, `single dummy`, `data`): text deals → `*_binary*.py` converts to numpy `x.npy/y.npy` → `*_nn_keras.py` trains with checkpoints (`bidding_nn_continue.py` resumes) → `testrun*.py` evaluates without search → `scripts/convert_all_to_onnx.py` exports ONNX. **Full from-scratch retraining is supported and documented**, and model filenames encode system + sample count (e.g., `NS1EW99-bidding-1494000`).

## 3. Strength

- **vs WBridge5:** On Camrose Trophy 2024 boards (160 deals), BEN (SAYC) lost to WBridge5 5.12 by only **12 IMPs**; maintainer Thorvald Aagaard cites an earlier BEN win by ~300 IMPs on a different set (https://bridgewinners.com/article/view/ben-vs-wbridge5-in-the-camrose-trophy-2024/). computerbridge.se's 2024 four-set match vs WBridge5 5.2 had BEN losing all four sets (e.g., 157-192), with ~50 IMPs attributed to simple declarer-play mistakes; BEN out-bid WBridge5 on several slams. BEN beat **Q-Plus Bridge** 3 of 4 sets in 2024 (245-151, 149-131, 225-204, 147-148 loss) (https://www.computerbridge.se/ben/).
- **vs GIB/humans on BBO:** Dali reports Ben ~1 IMP/board better than GIB Basic and slightly better than GIB Advanced in internal testing (https://www.bridgebase.com/forums/topic/89237-ben-on-bbo-feedback-thread/). BBO's Nov 2024 published matchpoint stats: Advanced GIB still highest overall; "Big Ben" nearly equal and better in some formats (https://www.bridgebase.com/forums/topic/90195-gib-vs-ben-vs-humans-latest-robot-performance-stats/).
- **Known weaknesses:** cannot interpret opponents' bid explanations; no defensive signaling understanding (README); user-reported slam/keycard accidents, inconsistent competitive bids, occasional suit-blocking plays; declarer-play blunders vs WBridge5. No World Computer Bridge Championship title (event dormant since 2019; Micro Bridge won 2019, WBridge5 2018 — https://www.computerbridge.se/).

## 4. Code state

- **Language/stack:** Python 3.12; TensorFlow 2.18.1/Keras 3.5 and ONNX runtime inference paths; DDS 3.0.0 C++ solver (pre-built per platform); C# components (PIMC/BBA/SuitC interop); Bottle+gevent web server; runs on Linux/Windows/macOS ARM; Docker image `ghcr.io/lorserker/ben`.
- **License:** GPL-3.0 (copyleft — relevant if we ever want a proprietary product; fine for a research effort).
- **Activity:** ~73 stars, 48 forks, 616+ commits; actively maintained through **July 2026** (v0.8.8.x), but effectively a one-maintainer project now — nearly all recent commits are **Thorvald Aagaard**, with Dali largely at BBO. Active Discord community.
- **Model packaging:** checked-in pre-trained models under `models/TF2models` and `models/onnx`, selected via config files; multiple model "versions" (v0–v3; only v3 currently supported) and per-partnership system codes (e.g., NS=SAYC, EW=WBridge5-SAYC).
- **Interoperability:** **Blue Chip Bridge table-manager protocol v18 client** (`src/table_manager_client.py` + `TMCGUI` GUI), so it can play organized matches against WBridge5, Q-Plus, etc.; also a web app, REST API/WebSocket server, and self-play scripts.
- **Forks:** no notable public feature forks; BBO's production variants are developed privately (Aagaard's work is committed upstream directly).

## 5. The BBO connection

- Dali joined BBO as backend engineer in 2023; BBO's "Ben" robot was retrained on **~100M hands from ACBL pair games on BBO** for human-like bidding/leads, uses GIB's bidding system/explanations for compatibility, and has a **card-play engine that does not rely on double-dummy analysis** plus a faster proprietary simulation algorithm (https://news.bridgebase.com/about-ben-on-bbo/). "Big Ben" is the stronger paid tier.
- In Jan 2026 BBO launched **GIBBO**, a GIB upgrade adding neural networks (trained on hundreds of millions of human deals) as a "second opinion" alongside simulations for bidding, leads, and card play — effectively Ben-derived tech folded into GIB (https://www.bridgerama-plus.com/en/2026/01/21/meet-gibbo/, https://www.bridgebase.com/forums/topic/91484-introducing-gibbo-a-revolutionary-upgrade-to-our-gib-robot/).
- **Those BBO-trained models/weights are NOT public.** The open repo ships only models trained on BBA-generated synthetic auctions and public play data; nothing trained on the 100M BBO hands has been released, and the BBO card-play engine is closed.

## Build-on-it assessment

Pros: only serious open-source full-engine (bidding+lead+play) with competitive results vs WBridge5, working table-manager interface, complete retraining pipeline, ONNX export, active maintenance. Cons: GPL-3.0; supervised-only training capped by teacher quality (BBA-generated auctions); small legacy LSTM architecture; one-maintainer bus factor; best models (BBO's) are proprietary; no RL/self-play infrastructure — for state-of-the-art bidding we'd likely add RL (cf. the open-source bidding baseline that beats WBridge5: https://www.arxiv.org/abs/2406.10306).
