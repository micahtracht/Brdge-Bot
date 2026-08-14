"""Blue Chip Bridge Table Manager protocol v18: message formats.

Wire format: ASCII lines terminated CRLF over TCP. Spec: archived v18 spec
(Aug 2005); conformance targets are BEN's table_manager_client.py and WBridge5.

Conventions used here:
- Seats are the full capitalised names "North", "East", "South", "West"
  (BEN sends/expects these; WBridge5 accepts either case — TODO verify).
- Bids on the wire: "1C".."7NT" (NT spelled out), or the verbs
  "passes"/"doubles"/"redoubles". Internally we use "PASS"/"X"/"XX".
- Cards on the wire: rank then suit, e.g. "QS", "4C", ranks AKQJT98765432.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SEATS = ["North", "East", "South", "West"]  # protocol order, index % 4
VULN_STRINGS = {"none": "Neither", "ns": "N/S", "ew": "E/W", "both": "Both"}

RANKS = "AKQJT98765432"
SUITS = "SHDC"

_BID_RX = re.compile(
    r"^(?P<seat>North|East|South|West)\s+"
    r"(?:(?P<verb>passes|doubles|redoubles)|bids\s+(?P<bid>[1-7](?:C|D|H|S|NT)))"
    r"(?P<rest>\s+.*)?$",
    re.IGNORECASE,
)
_PLAY_RX = re.compile(
    r"^(?P<seat>North|East|South|West)\s+plays\s+(?P<card>[AKQJT2-9][SHDC])(?P<rest>[.\s].*)?$",
    re.IGNORECASE,
)
_CONNECT_RX = re.compile(
    r'^Connecting\s+"(?P<team>[^"]*)"\s+as\s+(?P<seat>North|East|South|West)'
    r"\s+using\s+protocol\s+version\s+(?P<version>\d+)",
    re.IGNORECASE,
)
_READY_FOR_BID_RX = re.compile(
    r"^(?P<seat>North|East|South|West)\s+ready\s+for\s+(?P<actor>North|East|South|West)'s\s+bid$",
    re.IGNORECASE,
)
_READY_FOR_CARD_RX = re.compile(
    r"^(?P<seat>North|East|South|West)\s+ready\s+for\s+(?P<actor>North|East|South|West|dummy)'s\s+"
    r"card\s+to\s+trick\s+(?P<trick>\d+)$",
    re.IGNORECASE,
)


def norm_seat(s: str) -> str:
    return s.capitalize()


@dataclass
class Connect:
    team: str
    seat: str
    version: int


def parse_connect(line: str) -> Connect | None:
    m = _CONNECT_RX.match(line.strip())
    if not m:
        return None
    return Connect(m["team"], norm_seat(m["seat"]), int(m["version"]))


@dataclass
class BidMsg:
    seat: str
    call: str  # internal: "PASS", "X", "XX", or "1C".."7N"
    rest: str  # trailing Alert./Infos. text, verbatim (leading space included)


def parse_bid(line: str) -> BidMsg | None:
    m = _BID_RX.match(line.strip())
    if not m:
        return None
    if m["verb"]:
        call = {"passes": "PASS", "doubles": "X", "redoubles": "XX"}[m["verb"].lower()]
    else:
        call = m["bid"].upper().replace("NT", "N")
    return BidMsg(norm_seat(m["seat"]), call, m["rest"] or "")


def format_bid(seat: str, call: str, rest: str = "") -> str:
    if call == "PASS":
        body = f"{seat} passes"
    elif call == "X":
        body = f"{seat} doubles"
    elif call == "XX":
        body = f"{seat} redoubles"
    else:
        body = f"{seat} bids {call.replace('N', 'NT')}"
    return body + rest


@dataclass
class PlayMsg:
    seat: str  # the seat whose card this is (dummy's seat for dummy plays)
    card: str  # suit+rank internally, e.g. "SQ"


def parse_play(line: str) -> PlayMsg | None:
    m = _PLAY_RX.match(line.strip())
    if not m:
        return None
    card = m["card"].upper()
    return PlayMsg(norm_seat(m["seat"]), card[1] + card[0])  # wire "QS" -> internal "SQ"


def format_play(seat: str, card: str) -> str:
    return f"{seat} plays {card[1] + card[0]}"  # internal "SQ" -> wire "QS"


def parse_ready_for_bid(line: str) -> tuple[str, str] | None:
    m = _READY_FOR_BID_RX.match(line.strip())
    if not m:
        return None
    return norm_seat(m["seat"]), norm_seat(m["actor"])


def parse_ready_for_card(line: str) -> tuple[str, str, int] | None:
    """Returns (seat, actor, trick). actor is a seat name or 'dummy'."""
    m = _READY_FOR_CARD_RX.match(line.strip())
    if not m:
        return None
    actor = m["actor"]
    actor = "dummy" if actor.lower() == "dummy" else norm_seat(actor)
    return norm_seat(m["seat"]), actor, int(m["trick"])


def format_hand(suits: dict[str, str], possessive: str) -> str:
    """suits maps 'S'/'H'/'D'/'C' to rank strings (may be empty).

    Output: ``North's cards : S A Q T 8 2. H K 7. D K 5 2. C A 7 6.``
    Voids are rendered as ``-`` per the spec.
    """
    parts = []
    for s in SUITS:
        ranks = suits.get(s, "")
        body = " ".join(ranks) if ranks else "-"
        parts.append(f"{s} {body}.")
    return f"{possessive}'s cards : " + " ".join(parts)


def format_board_info(board_no: int, dealer: str, vuln: str) -> str:
    return f"Board number {board_no}. Dealer {dealer.upper()}. {vuln} vulnerable."


def format_teams(ns: str, ew: str) -> str:
    # NOTE: BEN's regex requires no period between the quoted names:
    #   N/S : "x" E/W : "y"
    # while the archived spec shows a period after "x". We emit the BEN-compatible
    # form; verify against WBridge5 when it is installed (it may need the period).
    return f'Teams : N/S : "{ns}" E/W : "{ew}". Playing IMPS'


def format_seated(seat: str, team: str) -> str:
    return f'{seat} ("{team}") seated'
