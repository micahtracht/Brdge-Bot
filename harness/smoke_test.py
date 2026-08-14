"""Phase 0 smoke test: deal generation, double-dummy solving, scoring.

Run:  .venv/Scripts/python harness/smoke_test.py
"""
import time

from endplay.dealer import generate_deals
from endplay.dds import calc_dd_table, par
from endplay.types import Vul, Player, Contract

from scoring import imps


def main() -> None:
    n = 10
    t0 = time.perf_counter()
    deals = list(generate_deals(produce=n, seed=42))
    t1 = time.perf_counter()
    print(f"generated {n} deals in {t1 - t0:.3f}s")

    t0 = time.perf_counter()
    for i, deal in enumerate(deals):
        table = calc_dd_table(deal)
        pr = par(table, Vul.none, Player.north)
        if i < 3:
            print(f"deal {i}: par {pr.score:+d} ({', '.join(str(c) for c in pr)})")
    t1 = time.perf_counter()
    print(f"solved {n} full DD tables in {t1 - t0:.3f}s ({(t1 - t0) / n * 1000:.0f} ms/deal)")

    # Contract scoring + IMP scale sanity checks
    assert Contract("4SN=").score(Vul.none) == 420
    assert Contract("3NTSx-2").score(Vul.ns) == -500
    # 4S= (+420) vs 3NT-1 (+50 for us at other table) -> 470 -> 10 IMPs
    assert imps(420 + 50) == 10, imps(420 + 50)
    assert imps(-(1100 + 620)) == -17
    assert imps(0) == 0 and imps(10) == 0 and imps(20) == 1
    print("contract scoring + IMP conversion OK")


if __name__ == "__main__":
    main()
