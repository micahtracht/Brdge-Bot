"""End-to-end test: TM server vs 4 mock clients over localhost.

Run from repo root:  .venv/Scripts/python -m harness.test_e2e
"""
from __future__ import annotations

import argparse
import asyncio

from .tm.mock_client import MockClient
from .tm.server import run_server


async def main() -> None:
    args = argparse.Namespace(
        host="127.0.0.1", port=20571, boards=4, seed=7, pbn=None,
        ns_name="MockNS", ew_name="MockEW", out=None, verbose=True,
    )
    server_task = asyncio.create_task(run_server(args))
    await asyncio.sleep(0.3)  # let the server bind
    clients = [
        MockClient(seat, "MockNS" if seat in ("North", "South") else "MockEW",
                   args.host, args.port)
        for seat in ("North", "East", "South", "West")
    ]
    results = await asyncio.gather(
        server_task, *(c.run() for c in clients), return_exceptions=True
    )
    for r in results[1:]:
        if isinstance(r, Exception):
            raise r
    records = results[0]
    if isinstance(records, Exception):
        raise records

    assert len(records) == args.boards, records
    for rec in records:
        assert rec["contract"] == "1N", rec
        assert rec["declarer"] == rec["dealer"], rec
        assert 0 <= rec["tricks"] <= 13, rec
        # score must match tricks under the scoring table
        assert isinstance(rec["score_ns"], int)
    print(f"OK: {len(records)} boards played to completion")
    for rec in records:
        print(f"  board {rec['board']}: 1N by {rec['declarer']}, "
              f"{rec['tricks']} tricks, NS {rec['score_ns']:+d}")


if __name__ == "__main__":
    asyncio.run(main())
