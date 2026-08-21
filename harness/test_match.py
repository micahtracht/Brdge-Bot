"""Team-match runner test: two tables, eight scripted mock clients.

Both rooms use identical deterministic mock strategies, so every board must
score 0 IMPs and the DD decomposition must balance (bidding + play = total).

Run from repo root:  .venv/Scripts/python -m harness.test_match
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
from pathlib import Path

from .match import run_match
from .tm.mock_client import MockClient

SEATS = ("North", "East", "South", "West")


async def main() -> None:
    out_dir = Path("matches")
    name = "_test_mock_match"
    if (out_dir / name).exists():
        shutil.rmtree(out_dir / name)
    args = argparse.Namespace(
        name=name, boards=6, seed=11, pbn=None, team_a="MockA", team_b="MockB",
        port=20600, wb5_a=False, wb5_b=False, no_dd=False, out_dir=str(out_dir),
    )
    match_task = asyncio.create_task(run_match(args))
    await asyncio.sleep(1.0)
    clients = []
    for port, (ns, ew) in ((20600, ("MockA", "MockB")), (20601, ("MockB", "MockA"))):
        for seat in SEATS:
            team = ns if seat in ("North", "South") else ew
            clients.append(MockClient(seat, team, "127.0.0.1", port).run())
    results = await asyncio.gather(match_task, *clients, return_exceptions=True)
    for r in results:
        if isinstance(r, Exception):
            raise r
    summary = results[0]
    assert summary["boards_played"] == 6, summary
    assert summary["imps_a"]["total"] == 0, summary["imps_a"]
    assert summary["bidding_imps_a"]["total"] == 0, summary
    assert summary["play_imps_a"]["total"] == 0, summary
    report = (out_dir / name / "report.md").read_text(encoding="utf-8")
    assert "Double-dummy decomposition" in report
    print("OK: 6-board mock team match, 0 IMPs, DD decomposition balanced")
    print(report.splitlines()[6])
    shutil.rmtree(out_dir / name)


if __name__ == "__main__":
    asyncio.run(main())
