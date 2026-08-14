"""One table: board state machine (deal -> auction -> play -> score).

Bridge rules implemented here: auction legality and contract determination,
follow-suit enforcement, trick winners, and scoring via endplay's Contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from endplay.types import Contract, Vul

from . import protocol as p

CALLS = ["PASS", "X", "XX"] + [f"{l}{s}" for l in "1234567" for s in "CDHSN"]
STRAIN_ORDER = "CDHSN"


def seat_i(seat: str) -> int:
    return p.SEATS.index(seat)


@dataclass
class Auction:
    dealer: str
    calls: list[tuple[str, str, str]] = field(default_factory=list)  # (seat, call, rest)

    @property
    def turn(self) -> str:
        return p.SEATS[(seat_i(self.dealer) + len(self.calls)) % 4]

    def _last_bid(self) -> tuple[int, str] | None:
        """(index, call) of the last real bid, if any."""
        for i in range(len(self.calls) - 1, -1, -1):
            if self.calls[i][1] not in ("PASS", "X", "XX"):
                return i, self.calls[i][1]
        return None

    def is_legal(self, call: str) -> bool:
        if call not in CALLS:
            return False
        last = self._last_bid()
        if call == "PASS":
            return True
        if call in ("X", "XX"):
            if last is None:
                return False
            i, _ = last
            later = [c for _, c, _ in self.calls[i + 1 :] if c != "PASS"]
            bidder_side = seat_i(self.calls[i][0]) % 2
            turn_side = seat_i(self.turn) % 2
            if call == "X":
                return later == [] and bidder_side != turn_side
            return later == ["X"] and bidder_side == turn_side
        if last is None:
            return True
        _, prev = last
        if int(call[0]) != int(prev[0]):
            return int(call[0]) > int(prev[0])
        return STRAIN_ORDER.index(call[1]) > STRAIN_ORDER.index(prev[1])

    def add(self, seat: str, call: str, rest: str = "") -> None:
        assert seat == self.turn, f"not {seat}'s turn (turn: {self.turn})"
        assert self.is_legal(call), f"illegal call {call} after {self.calls}"
        self.calls.append((seat, call, rest))

    @property
    def finished(self) -> bool:
        n = len(self.calls)
        if n < 4:
            return False
        return all(c == "PASS" for _, c, _ in self.calls[-3:])

    def contract(self) -> tuple[str, str, str] | None:
        """Returns (contract e.g. '4SN', doubled '' | 'x' | 'xx', declarer seat)
        or None for a pass-out."""
        last = self._last_bid()
        if last is None:
            return None
        i, bid = last
        doubled = ""
        for _, c, _ in self.calls[i + 1 :]:
            if c == "X":
                doubled = "x"
            elif c == "XX":
                doubled = "xx"
        strain = bid[1]
        side = seat_i(self.calls[i][0]) % 2
        # declarer: first player of that side to have bid this strain
        declarer = None
        for s, c, _ in self.calls:
            if c not in ("PASS", "X", "XX") and c[1] == strain and seat_i(s) % 2 == side:
                declarer = s
                break
        assert declarer is not None
        return bid, doubled, declarer


@dataclass
class PlayState:
    contract: str  # e.g. "4S"
    doubled: str
    declarer: str
    hands: dict[str, set[str]]  # seat -> set of internal cards "SQ"
    tricks: list[list[tuple[str, str]]] = field(default_factory=list)  # (seat, card)
    current: list[tuple[str, str]] = field(default_factory=list)
    leader: str = ""

    def __post_init__(self) -> None:
        self.trump = self.contract[1] if self.contract[1] != "N" else None
        self.leader = p.SEATS[(seat_i(self.declarer) + 1) % 4]

    @property
    def dummy(self) -> str:
        return p.SEATS[(seat_i(self.declarer) + 2) % 4]

    @property
    def turn(self) -> str:
        return p.SEATS[(seat_i(self.leader) + len(self.current)) % 4]

    def is_legal(self, seat: str, card: str) -> bool:
        if card not in self.hands[seat]:
            return False
        if not self.current:
            return True
        led = self.current[0][1][0]
        if card[0] == led:
            return True
        return not any(c[0] == led for c in self.hands[seat])

    def play(self, seat: str, card: str) -> None:
        assert seat == self.turn, f"not {seat}'s turn (turn: {self.turn})"
        assert self.is_legal(seat, card), f"illegal card {card} from {seat}"
        self.hands[seat].discard(card)
        self.current.append((seat, card))
        if len(self.current) == 4:
            self.leader = self._winner()
            self.tricks.append(self.current)
            self.current = []

    def _winner(self) -> str:
        led = self.current[0][1][0]
        best_seat, best_card = self.current[0]
        for seat, card in self.current[1:]:
            if self.trump and card[0] == self.trump and best_card[0] != self.trump:
                best_seat, best_card = seat, card
            elif card[0] == best_card[0] and p.RANKS.index(card[1]) < p.RANKS.index(best_card[1]):
                best_seat, best_card = seat, card
        return best_seat

    @property
    def finished(self) -> bool:
        return len(self.tricks) == 13

    def declarer_tricks(self) -> int:
        decl_side = seat_i(self.declarer) % 2
        return sum(1 for t in self.tricks if seat_i(self._trick_winner(t)) % 2 == decl_side)

    def _trick_winner(self, trick: list[tuple[str, str]]) -> str:
        saved = self.current
        self.current = trick
        w = self._winner()
        self.current = saved
        return w


def score_board(contract: str, doubled: str, declarer: str, tricks: int, vul: str) -> int:
    """NS score for the board. vul: 'none'|'ns'|'ew'|'both'."""
    level = int(contract[0])
    target = 6 + level
    res = tricks - target
    res_str = "=" if res == 0 else f"{res:+d}"
    c = Contract(f"{contract}{declarer[0]}{doubled}{res_str}")
    vul_map = {"none": Vul.none, "ns": Vul.ns, "ew": Vul.ew, "both": Vul.both}
    score = c.score(vul_map[vul])  # from declarer's perspective
    return score if seat_i(declarer) % 2 == 0 else -score
