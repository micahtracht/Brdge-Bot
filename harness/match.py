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

from endplay.dds import calc_dd_table
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
    rows = []
    for b in sorted(set(by_board_o) & set(by_board_c)):
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
            table = calc_dd_table(deals[b - 1])
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

    open_path, closed_path = out_dir / "open.jsonl", out_dir / "closed.jsonl"
    open_done, closed_done = read_jsonl(open_path), read_jsonl(closed_path)
    open_start = (max((r["board"] for r in open_done), default=0)) + 1
    closed_start = (max((r["board"] for r in closed_done), default=0)) + 1
    log(f"match '{args.name}': {n} boards; open resumes at {open_start}, closed at {closed_start}")

    port_open, port_closed = args.port, args.port + 1
    tasks = []
    if open_start <= n:
        tasks.append(run_table(
            deals, port=port_open, ns_name=args.team_a, ew_name=args.team_b,
            out_path=str(open_path), wire_log_path=str(out_dir / "open.wire.log"),
            start_board=open_start, label="open", log=log))
    if closed_start <= n:
        tasks.append(run_table(
            deals, port=port_closed, ns_name=args.team_b, ew_name=args.team_a,
            out_path=str(closed_path), wire_log_path=str(out_dir / "closed.wire.log"),
            start_board=closed_start, label="closed", log=log))

    if tasks:
        servers = asyncio.gather(*tasks)
        await asyncio.sleep(0.5)  # let both tables bind before clients arrive
        # WBridge5 seats: team A is NS open / EW closed; team B the reverse.
        if args.wb5_a and open_start <= n:
            await asyncio.to_thread(launch_wb5, ["North", "South"], port_open)
        if args.wb5_b and open_start <= n:
            await asyncio.to_thread(launch_wb5, ["East", "West"], port_open)
        if args.wb5_b and closed_start <= n:
            await asyncio.to_thread(launch_wb5, ["North", "South"], port_closed)
        if args.wb5_a and closed_start <= n:
            await asyncio.to_thread(launch_wb5, ["East", "West"], port_closed)
        await servers

    rows = annotate_and_score(deals, read_jsonl(open_path), read_jsonl(closed_path), want_dd=not args.no_dd)
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
    ap.add_argument("--port", type=int, default=2000, help="open room port; closed room = port+1")
    ap.add_argument("--wb5-a", action="store_true", help="team A is WBridge5 (auto-launched)")
    ap.add_argument("--wb5-b", action="store_true", help="team B is WBridge5 (auto-launched)")
    ap.add_argument("--no-dd", action="store_true", help="skip double-dummy decomposition")
    ap.add_argument("--out-dir", default="matches")
    args = ap.parse_args()
    asyncio.run(run_match(args))


if __name__ == "__main__":
    main()
