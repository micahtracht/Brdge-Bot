"""Duplicated team match: open room (A sits NS) + closed room (B sits NS),
same deals, scored in IMPs with confidence intervals and a double-dummy
decomposition (bidding edge vs play conversion).

Usage (WBridge5 vs WBridge5 noise-floor control, 16 boards):
    .venv/Scripts/python -m harness.match --name wb5-control --boards 16 --seed 1 \
        --team-a WBridge5 --team-b WBridge5 --wb5-a --wb5-b

Usage (our bot as team A, WBridge5 as team B; our clients connect themselves):
    .venv/Scripts/python -m harness.match --name bot-vs-wb5 --boards 2048 --seed 7 \
        --team-a BridgeBot --team-b WBridge5 --wb5-b

Ports: open room on --port, closed room on --port+1. Team A sits NS in the open
room and EW in the closed room. Output under matches/<name>/: deals.pbn,
open.jsonl, closed.jsonl, wire logs, report.md, results.json. Re-running with
the same --name resumes both rooms from their last completed board.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from endplay.dds import calc_all_tables
from endplay.types import Denom, Player

from .tm.server import board_meta, load_pbn_deals, make_deals, run_table
from .tm.table import score_board
from .stats import summarize, team_imps, boards_needed

HERE = Path(__file__).resolve().parent
WB5_LAUNCHER = HERE / "wb5_launch.ps1"
WB5_STOPPER = HERE / "wb5_stop.ps1"

_STRAIN = {"C": Denom.clubs, "D": Denom.diamonds, "H": Denom.hearts, "S": Denom.spades, "N": Denom.nt}
_PLAYER = {"North": Player.north, "East": Player.east, "South": Player.south, "West": Player.west}


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", file=sys.stderr, flush=True)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def launch_wb5(seats: list[str], port: int) -> None:
    cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(WB5_LAUNCHER),
           "-Seats", ",".join(seats), "-Port", str(port)]
    log(f"launching WBridge5 {seats} on port {port}")
    subprocess.run(cmd, check=True)


def dd_score_ns(record: dict, dd_table) -> int | None:
    """NS score if the contract reached were played double-dummy."""
    if not record.get("contract"):
        return 0
    contract = record["contract"]  # e.g. "4Sx"
    doubled = contract[2:]
    base = contract[:2]
    declarer = record["declarer"]
    tricks = dd_table[_STRAIN[base[1]], _PLAYER[declarer]]
    return score_board(base, doubled, declarer, tricks, record["vuln"])


def annotate_and_score(deals, open_recs: list[dict], closed_recs: list[dict], want_dd: bool) -> list[dict]:
    by_board_o = {r["board"]: r for r in open_recs}
    by_board_c = {r["board"]: r for r in closed_recs}
    boards = sorted(set(by_board_o) & set(by_board_c))
    tables = {}
    if want_dd and boards:
        # batch, multithreaded DD solve (endplay/DDS) — far faster than per-deal
        dd_list = calc_all_tables([deals[b - 1] for b in boards])
        tables = dict(zip(boards, dd_list))
    rows = []
    for b in boards:
        o, c = by_board_o[b], by_board_c[b]
        row = {
            "board": b,
            "open": {"contract": o.get("contract"), "declarer": o.get("declarer"),
                     "tricks": o.get("tricks"), "score_ns": o["score_ns"]},
            "closed": {"contract": c.get("contract"), "declarer": c.get("declarer"),
                       "tricks": c.get("tricks"), "score_ns": c["score_ns"]},
            "imps_a": team_imps(o["score_ns"], c["score_ns"]),
        }
        if want_dd:
            table = tables[b]
            dd_o, dd_c = dd_score_ns(o, table), dd_score_ns(c, table)
            row["dd"] = {
                "open_score_ns": dd_o, "closed_score_ns": dd_c,
                "bidding_imps_a": team_imps(dd_o, dd_c),  # edge from contracts reached
            }
            row["dd"]["play_imps_a"] = row["imps_a"] - row["dd"]["bidding_imps_a"]
        rows.append(row)
    return rows


def write_report(path: Path, name: str, team_a: str, team_b: str, rows: list[dict],
                 n_deals: int, want_dd: bool) -> dict:
    imps_a = [r["imps_a"] for r in rows]
    s = summarize(imps_a)
    results = {"name": name, "team_a": team_a, "team_b": team_b, "boards_played": len(rows),
               "boards_planned": n_deals, "imps_a": s.as_dict()}
    lines = [f"# Match report: {name}", "",
             f"**{team_a}** (NS open / EW closed) vs **{team_b}** — duplicated teams, IMPs.",
             f"Boards: {len(rows)} of {n_deals}.", "",
             f"## Result for {team_a}", "", f"- {s.fmt()}"]
    if s.n > 1:
        lines.append(f"- Boards needed to resolve an edge of this size at 2σ (using observed SD): "
                     f"{boards_needed(abs(s.mean) or 0.01, s.sd)}")
    if want_dd and rows and "dd" in rows[0]:
        bid = summarize([r["dd"]["bidding_imps_a"] for r in rows])
        play = summarize([r["dd"]["play_imps_a"] for r in rows])
        results["bidding_imps_a"] = bid.as_dict()
        results["play_imps_a"] = play.as_dict()
        lines += ["", "## Double-dummy decomposition", "",
                  f"- Bidding edge (DD value of contracts reached): {bid.fmt()}",
                  f"- Play conversion (realized minus DD): {play.fmt()}"]
    lines += ["", "## Boards", "", "| # | Open | Closed | IMPs A |" + (" Bid | Play |" if want_dd else ""),
              "|---|---|---|---|" + ("---|---|" if want_dd else "")]
    for r in rows:
        o, c = r["open"], r["closed"]
        fo = f"{o['contract'] or 'Pass'} {o['declarer'] or ''} {o['tricks'] if o['tricks'] is not None else ''} ({o['score_ns']:+d})"
        fc = f"{c['contract'] or 'Pass'} {c['declarer'] or ''} {c['tricks'] if c['tricks'] is not None else ''} ({c['score_ns']:+d})"
        line = f"| {r['board']} | {fo} | {fc} | {r['imps_a']:+d} |"
        if want_dd:
            line += f" {r['dd']['bidding_imps_a']:+d} | {r['dd']['play_imps_a']:+d} |"
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return results


async def run_match(args) -> dict:
    out_dir = Path(args.out_dir) / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    pbn_path = out_dir / "deals.pbn"

    if args.pbn:
        deals = load_pbn_deals(args.pbn)
    elif pbn_path.exists():
        deals = load_pbn_deals(str(pbn_path))
    else:
        deals = make_deals(args.boards, args.seed)
        from endplay.parsers import pbn as pbn_mod
        from endplay.types import Board
        with open(pbn_path, "w") as f:
            pbn_mod.dump([Board(deal=d, board_num=i + 1) for i, d in enumerate(deals)], f)
    n = len(deals)

    # --- shard the deal set across K table-pairs (open+closed room each) ---
    # Shard k plays boards [lo_k, hi_k] on ports base+2k (open) / base+2k+1
    # (closed). Each room appends to its own JSONL and resumes independently.
    k_tables = max(1, args.tables)
    chunk = -(-n // k_tables)  # ceil
    shards = []
    for k in range(k_tables):
        lo, hi = k * chunk + 1, min((k + 1) * chunk, n)
        if lo > hi:
            break
        shards.append((k, lo, hi))

    def room_path(room: str, k: int) -> Path:
        return out_dir / (f"{room}.jsonl" if k_tables == 1 else f"{room}.{k}.jsonl")

    def room_start(room: str, k: int, lo: int) -> int:
        done = [r["board"] for r in read_jsonl(room_path(room, k))]
        return max(done, default=lo - 1) + 1

    plan = []  # (room, k, port, ns, ew, start, hi)
    for k, lo, hi in shards:
        plan.append(("open", k, args.port + 2 * k, args.team_a, args.team_b, room_start("open", k, lo), hi))
        plan.append(("closed", k, args.port + 2 * k + 1, args.team_b, args.team_a, room_start("closed", k, lo), hi))
    log(f"match '{args.name}': {n} boards over {len(shards)} table-pair(s); "
        + ", ".join(f"{room}{k}@{port} {start}-{hi}" for room, k, port, _, _, start, hi in plan))

    tasks = [
        run_table(deals, port=port, ns_name=ns, ew_name=ew,
                  out_path=str(room_path(room, k)),
                  wire_log_path=str(out_dir / (f"{room}.wire.log" if k_tables == 1 else f"{room}.{k}.wire.log")),
                  start_board=start, end_board=hi, label=f"{room}{k if k_tables > 1 else ''}", log=log)
        for room, k, port, ns, ew, start, hi in plan if start <= hi
    ]

    if tasks:
        servers = asyncio.gather(*tasks)
        await asyncio.sleep(0.5)  # let the tables bind before clients arrive
        # WBridge5 seats: team A is NS in open rooms / EW in closed rooms; B the
        # reverse. Launches are sequential (shared INI carries the port), but
        # each table starts playing as soon as its four seats fill.
        for room, k, port, ns, ew, start, hi in plan:
            if start > hi:
                continue
            a_seats, b_seats = (["North", "South"], ["East", "West"]) if room == "open" else (["East", "West"], ["North", "South"])
            if args.wb5_a:
                await asyncio.to_thread(launch_wb5, a_seats, port)
            if args.wb5_b:
                await asyncio.to_thread(launch_wb5, b_seats, port)
        await servers

    open_recs = [r for k, _, _ in shards for r in read_jsonl(room_path("open", k))]
    closed_recs = [r for k, _, _ in shards for r in read_jsonl(room_path("closed", k))]
    rows = annotate_and_score(deals, open_recs, closed_recs, want_dd=not args.no_dd)
    results = write_report(out_dir / "report.md", args.name, args.team_a, args.team_b, rows, n, not args.no_dd)
    (out_dir / "results.json").write_text(json.dumps({"boards": rows, **results}, indent=1))
    log(f"report: {out_dir / 'report.md'}")
    log(f"{args.team_a}: {summarize([r['imps_a'] for r in rows]).fmt()}")
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="Duplicated team match runner")
    ap.add_argument("--name", required=True, help="match name (directory under --out-dir)")
    ap.add_argument("--boards", type=int, default=16)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--pbn", help="use these deals instead of generating")
    ap.add_argument("--team-a", default="A")
    ap.add_argument("--team-b", default="B")
    ap.add_argument("--port", type=int, default=2000, help="base port; shard k uses port+2k (open) and port+2k+1 (closed)")
    ap.add_argument("--tables", type=int, default=1, help="number of parallel table-pairs (deal set is sharded across them)")
    ap.add_argument("--wb5-a", action="store_true", help="team A is WBridge5 (auto-launched)")
    ap.add_argument("--wb5-b", action="store_true", help="team B is WBridge5 (auto-launched)")
    ap.add_argument("--no-dd", action="store_true", help="skip double-dummy decomposition")
    ap.add_argument("--out-dir", default="matches")
    args = ap.parse_args()
    asyncio.run(run_match(args))


if __name__ == "__main__":
    main()
