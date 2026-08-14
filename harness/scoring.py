"""IMP conversion (standard WBF IMP table) and match aggregation helpers."""

_IMP_BOUNDS = [
    20, 50, 90, 130, 170, 220, 270, 320, 370, 430, 500, 600, 750, 900,
    1100, 1300, 1500, 1750, 2000, 2250, 2500, 3000, 3500, 4000,
]


def imps(score_diff: int) -> int:
    """Convert a net score difference (this side minus other side) to IMPs."""
    magnitude = abs(score_diff)
    imp = 0
    for bound in _IMP_BOUNDS:
        if magnitude >= bound:
            imp += 1
        else:
            break
    return imp if score_diff >= 0 else -imp
