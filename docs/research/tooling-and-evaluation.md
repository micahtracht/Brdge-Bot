# Computer Bridge: Tooling and Evaluation Landscape (as of Aug 2026)

> Research report, 2026-08-14.

## 1. WBridge5

- **What/where**: Free Windows bridge engine by Yves Costel, download at [wbridge5.com](http://www.wbridge5.com/) (site is HTTP-only; HTTPS handshake fails, so fetch over plain HTTP or a browser). Current public version is **5.12**; the core engine has [not been publicly updated since ~2014](https://www.computerbridge.se/wbridge5/), though an unpublished minor update and an AI-enhanced championship build exist.
- **Track record**: 6-time World Computer-Bridge Champion (2005–2008, 2016–2018), 7-time runner-up; won the round robin of the 2023 unofficial bot championship and won the [2024 Machine vs Machine event](https://www.computerbridge.se/man-vs-machine-2024/) (beat PowerShark 2024 in a 128-board final). It is still the de facto strength benchmark.
- **Modern Windows**: Community reports (computerbridge.se) indicate it runs on Windows 10/11 as a legacy Win32 app; no Mac build. Systems: WBridge5's own system, SEF, SAYC, custom + ~25 conventions.
- **Automated play**: Yes — WBridge5 supports the **Blue Chip Bridge Table Manager protocol** as an external client, which is exactly how it played in the championships and how [Ben plays against it today](https://github.com/lorserker/ben). WBridge5's site also distributes **Bridge Moniteur** ([wbridge5.com/bm.htm](http://www.wbridge5.com/bm.htm)), a free table-manager-style server (written in Rebol, source included) that can host networked tables with WBridge5 robots and replay PBN deals.

### Blue Chip protocol (the lingua franca for bot-vs-bot)

- Invented by **Ian Trackman** (Blue Chip Bridge) for WCBC network play. Spec: originally at bluechipbridge.co.uk/protocol.htm (site now essentially dead); a full archived copy of the **Version 18 spec (Aug 2005)** is preserved in [this gist mirroring the Wayback Machine capture](https://gist.github.com/ed2k/f62f4e5cf418fa3eef9ac06ea36be5b3).
- **Mechanics**: plain **ASCII lines terminated CRLF over TCP/IP**; Table Manager listens on a port "within the standard range 1024–5000" (2000 is the conventional default). Handshake:
  - Client: `Connecting "TEAMNAME" as NORTH using protocol version 18`
  - TM: `NORTH ("TEAMNAME") seated` → client: `NORTH ready for teams` → TM: `Teams : N/S : "X". E/W : "Y"` → `NORTH ready to start`
  - Per board: TM `Start of board` → `NORTH ready for deal` → `Board number 7. Dealer NORTH. Neither vulnerable.` → hand messages → bidding as `NORTH bids 3NT` / `passes` / `doubles` / `redoubles` (with optional `Alert. ...` info) → play as `NORTH plays QS` (rank char + suit char, ranks AKQJT98765432, suits SHDC).
- The TM source itself was never open (commercial Blue Chip package), but the protocol is simple enough that multiple reimplementations exist (see §6).

## 2. World Computer-Bridge Championship (WCBC)

- **Official era 1997–2019**: founded by the ACBL in 1996, run jointly with the WBF from 1999, organized/coordinated throughout by **Al Levy**. History and results: [bridgebotchampionship.com](https://bridgebotchampionship.com/home/world-computer-bridge-championship/) (Levy's archive site, states "official championships have ended"), [bridgerobotchampionship.wordpress.com](https://bridgerobotchampionship.wordpress.com/computerbridge-com/), and [Wikipedia](https://en.wikipedia.org/wiki/Computer_bridge).
- **Format (official era)**: typically 8–10 bots; ~32-board round robin (IMPs→VPs) then 64-board knockout semifinals/final (2016 example: WBridge5 beat Micro Bridge 162–156 over 64 boards). Bots had to play fully autonomously through the Blue Chip Table Manager. Last official event: **23rd WCBC, San Francisco 2019 — Micro Bridge beat Synrey Bridge 120–35**. 2020–2021 cancelled (COVID); no official event since.
- **Unofficial era since 2022**: two threads —
  - **Christine Goulden's (unofficial) Computer Bridge Championship** (UK): 2022 edition run manually with 16-board matches (QF/SF/final on [YouTube](https://www.youtube.com/watch?v=RaaJfrG6fbA)); participants: WBridge5, Jack, GIB, Q-Plus, Micro Bridge, Bridge Baron. **2022 winner: WBridge5 5.12**; **2023 winner: Q-Plus 15.3** (field: WBridge5 5.12 silver, Shark 2.1 bronze, Jack 6.11, Micro Bridge 13.3, GIB 6.2.0, Blue Chip 6.6.5), per [Wikipedia](https://en.wikipedia.org/wiki/Computer_bridge) and [computerbridge.se](https://www.computerbridge.se/christine-gouldens-computer-bridge-championship/). From 2023 play was automated via Table Manager to allow more boards.
  - **Björn Hjalmarsson's events** ([computerbridge.se](https://www.computerbridge.se/), Sweden): **[Man vs Machine & Machine vs Machine 2024](https://www.computerbridge.se/man-vs-machine-2024/)** — bots Q-Plus 15.7, Micro Bridge 13.40, WBridge5 5.12, GIB 6.20, PowerShark 2024, Lia 0.12.4, Ben 0.2 (Argine online-only). M-v-M: 64-board round robin + 128-board SF/final, IMPs/VP, deals from BridgeComposer, videos on YouTube (NetBridgeVu). **WBridge5 beat PowerShark 2024 in the final**; the human (Björn Wenneberg) won 5 of 8 16-board bot challenge matches. Further "Machine vs Machine Teams / Pairs / Goulash Dec 2024" events are documented in the [news area](https://www.computerbridge.se/member-area/); no 2025/2026 edition was announced there as of the last update.
- **Practical takeaway**: there is no official sanctioned championship to enter right now; the active venues are these hobbyist-run round robins, all mediated by Blue Chip-protocol table managers, IMPs scoring, 16–128 board matches. **Ben** (entered as "Ben 0.2", competition-tuned by Thorvald Aagaard and Eamon Galligan) is the reference for how a new engine gets into these events ([robot-bridge.co.uk bot bios](https://robot-bridge.co.uk/more-about-the-bots-2024)).

## 3. Double-dummy tooling

- **DDS (Bo Haglund)**: canonical repo [github.com/dds-bridge/dds](https://github.com/dds-bridge/dds), **Apache-2.0**, C++ with C API. Functions: SolveBoard (single position), CalcDDtable (all 20 declarer/strain results), par calculation, batch/multithreaded variants (SolveAllBoards). Originated 2006 (Haglund), heavily modernized by Søren Hein 2014; a successor **DDS3** by Martin Nygren (maintained as of May 2026) modernizes the build (macOS/Linux/Windows) and improves parallel solving with shared transposition tables; bindings documented for Python, .NET, C++. Speed: batch full-deal DD tables run in the ~10ms-per-deal ballpark on modern multicore hardware (thousands of deals/minute) — fast enough for MC-rollout play engines (this is what Ben, GIB-style samplers, and endplay all use).
- **Python**:
  - **endplay** ([github.com/dominicprice/endplay](https://github.com/dominicprice/endplay), [PyPI](https://pypi.org/project/endplay/), [docs](https://endplay.readthedocs.io)) — MIT, v0.5.12 (Mar 2025), Python 3.9–3.13, wheels for Win/Linux/macOS. Bundles DDS solving, a dealer with constraint syntax, hand evaluation, par/contract scoring, and **PBN + LIN + JSON parsing** — the best one-stop Python library for this project.
  - Others: [py-dds](https://github.com/kcyan96/py-dds), [ddstable](https://pypi.org/project/ddstable/), .NET wrapper [dds.net](https://github.com/anorsich/dds.net), and Anthony Lee's `redeal` (dealer + DDS) — endplay largely supersedes them.

## 4. Data

- **BBO Vugraph archive** — the largest source of expert play: 20+ years of broadcast world/national championship matches as **.lin files**, downloadable per-session from BBO's vugraph archive ([forum discussion of bulk access](https://www.bridgebase.com/forums/topic/44425-any-way-to-download-whole-vugraph-archives-/)). The **Vugraph Project** ([sarantakos.com/bridge/vugraph.html](https://www.sarantakos.com/bridge/vugraph.html)) curates archives in PBN/LIN. Academic precedent: the deep-bidding paper [arXiv:1903.00900](https://arxiv.org/pdf/1903.00900) trained on **>1M expert games from the Vugraph Project** (cards, vulnerability, dealer, auction, play, tricks).
- **Formats**: **PBN** (Portable Bridge Notation — the interchange standard; tools list at [tistis.nl/pbn](https://www.tistis.nl/pbn/pbn_software.htm)) and **LIN** (BBO's format). endplay parses both.
- **Tools**: [OneTrickPony82/Bridge-Tools](https://github.com/OneTrickPony82/Bridge-Tools) — Python for bulk-downloading and parsing vugraph .lin files, computing minimax/DD metrics, reverse-engineering bidding systems.
- **Synthetic data**: because expert data is small by ML standards, Ben and the academic RL work (e.g. [harukaki/brl](https://github.com/harukaki/brl)) rely heavily on self-generated deals scored with DDS; deal generators: endplay's dealer, BridgeComposer, Hans van Staveren's `dealer`. OpenSpiel ships the 12.8M-hand WBridge5 SL dataset.

## 5. Other engines

| Engine | Availability | Programmatic play |
|---|---|---|
| **Jack** ([jackbridge.com](https://www.jackbridge.com/)) | Commercial, Jack 6.x, **€89** incl. VAT via resellers ([order page](https://www.jackbridge.com/eordr.htm)); runs on Windows 11. 10-time WCBC champion. | Yes — Blue Chip TM protocol (played in TM-automated 2023 unofficial championship as Jack 6.11). |
| **Micro Bridge** (Tomio & Yumiko Uchida, JP) | Shareware from the author's site; current ~13.40 beta ([computerbridge.se page](https://www.computerbridge.se/micro-bridge-13/)). 2019 WCBC champion. | Yes — TM protocol (long-time WCBC entrant). |
| **Shark Bridge / PowerShark** | Rebranded **PowerShark 2024** ([wbtbridge.com/about](https://www.wbtbridge.com/about)); runs as robot on World Bridge Tour online; not a retail desktop product. | Plays via TM in the Swedish events; no public API. |
| **GIB** | Ships inside BBO (robot rentals); old desktop GIB 6.x circulates and still enters unofficial events. | Old desktop GIB speaks the TM protocol; BBO robots not externally scriptable. |
| **Argine** (Funbridge, [funbridge.com AI page](https://funbridge.com/bridge-artificial-intelligence)) | Online-only inside Funbridge apps. | **No public API**; it joined the 2024 event online-only, manually operated. NukkAI's **NooK** ([2022 challenge](https://challenge.nukk.ai/)) is research software, not available. |
| **Q-Plus Bridge** (DE) | Commercial Windows program, ~15.7; 2023 unofficial champion. | Yes — TM protocol. |
| **Blue Chip Bridge** | UK commercial package incl. the original Table Manager; website moribund. | It *is* the protocol's origin. |

## 6. Table manager software (hosting bot matches)

- **Original**: Ian Trackman's Table Manager — closed-source, part of Blue Chip Bridge; effectively abandonware with the site dead.
- **Bridge Moniteur** (free, from [wbridge5.com/bm.htm](http://www.wbridge5.com/bm.htm)) — network server that hosts tables with WBridge5 robots, PBN deal replay; Rebol source included.
- **Ben's ecosystem (most practical today)**: [lorserker/ben](https://github.com/lorserker/ben) documents the exact workflow: run a table manager server, then connect via Blue Chip protocol v18 — the repo ships a TM client (`table_manager_client.py`) and the community uses a TM server ("Bridge Monitor") to pit Ben against WBridge5 and others. This is the closest thing to a turnkey bot-vs-bot rig and the setup used in the 2023/2024 automated championships.
- **Node.js protocol implementations** (Richard Schneider, older but useful as reference): [bridge-player](https://github.com/richardschneider/bridge-player) (a protocol-speaking player), [table-master-parser](https://github.com/richardschneider/table-master-parser) (message → AST, [docs](https://richardschneider.github.io/table-master-parser/index.html)), [table-master-stream](https://github.com/richardschneider/table-master-stream) (streaming transform). **No full open-source TM *server* exists as a polished standalone project** — writing one from the v18 spec (+ these parsers + Ben's client as a conformance target) is a small, well-bounded piece of work.

## Practical implications for our milestone

1. The evaluation harness is essentially fixed: **Blue Chip protocol v18 over TCP, IMPs over 64–128 board matches with duplicated deals** — implement a TM client (and ideally our own TM server for headless batch runs) and we can play WBridge5, and with purchases, Jack/Q-Plus/Micro Bridge.
2. WBridge5 is free and still the community benchmark; Ben's repo gives a working reference for driving it automatically on Windows.
3. Use endplay + DDS for rollouts/scoring; BBO vugraph LIN + the Vugraph Project (~1M expert games) is the standard supervised-learning corpus.
4. There is no official championship to enter; visibility comes from the Goulden (UK) and Hjalmarsson ([computerbridge.se](https://www.computerbridge.se/)) events, both of which accept new TM-protocol-speaking bots (Ben and Lia entered exactly this way in 2024).
