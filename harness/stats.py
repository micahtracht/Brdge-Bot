"""Match statistics: IMP summaries with confidence intervals, and the
double-dummy decomposition of a board into bidding edge vs play conversion."""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from .scoring import imps


@dataclass
class Summary:
    n: int
    total: int
    mean: float
    sd: float
    se: float
    ci95_lo: float
    ci95_hi: float
    z: float  # mean / se (0 if undefined)

    def as_dict(self) -> dict:
        return asdict(self)

    def fmt(self, unit: str = "IMP/board") -> str:
        if self.n == 0:
            return "n=0"
        return (f"{self.mean:+.3f} {unit} (95% CI {self.ci95_lo:+.3f} to {self.ci95_hi:+.3f}, "
                f"SE {self.se:.3f}, SD {self.sd:.2f}, z={self.z:.2f}, n={self.n}, total {self.total:+d})")


def summarize(values: list[int | float]) -> Summary:
    n = len(values)
    if n == 0:
        return Summary(0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    total = sum(values)
    mean = total / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else 0.0
    z = mean / se if se > 0 else 0.0
    return Summary(n, int(round(total)), mean, sd, se, mean - 1.96 * se, mean + 1.96 * se, z)


def team_imps(open_score_ns: int, closed_score_ns: int) -> int:
    """IMPs to the team sitting NS in the open room (and EW in the closed room)."""
    return imps(open_score_ns - closed_score_ns)


def boards_needed(edge: float, sd: float = 5.4, sigmas: float = 2.0) -> int:
    """Boards needed to resolve a true edge (IMP/board) at the given sigma level."""
    if edge <= 0:
        return 0
    return math.ceil((sigmas * sd / edge) ** 2)
