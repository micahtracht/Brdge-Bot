"""Blue Chip v18 table-manager server: hosts one table of four protocol clients.

Usage:
    python -m tm.server --port 2000 --boards 4 --seed 42 \
        --ns-name BridgeBot --ew-name WBridge5 --out results.jsonl

Deals are generated with endplay's dealer (uniform random, seeded) or read
from a PBN file with --pbn. Each connection is expected to speak protocol
version 18 as implemented by BEN's table_manager_client.py / WBridge5.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from endplay.dealer import generate_deals
from endplay.types import Denom, Player

from . import protocol as p
from .table import Auction, PlayState, score_board

VULN_CYCLE = ["none", "ns", "ew", "both", "ns", "ew", "both", "none",
              "ew", "both", "none", "ns", "both", "none", "ns", "ew"]

_DENOM_TO_CHAR = {Denom.spades: "S", Denom.hearts: "H", Denom.diamonds: "D", Denom.clubs: "C"}


class Client:
    wire_log = None  # file object shared by all clients, set by run_server

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.seat: str | None = None
        self.team: str | None = None

    def _log(self, direction: str, line: str) -> None:
        if Client.wire_log:
            import datetime
            stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            Client.wire_log.write(f"{stamp} {direction} {self.seat or '?':<5} | {line}\n")
            Client.wire_log.flush()

    async def send(self, line: str) -> None:
        self._log("->", line)
        self.writer.write((line + "\r\n").encode("ascii"))
        await self.writer.drain()

    async def recv(self) -> str:
        raw = await self.reader.readline()
        if not raw:
            self._log("!!", "<disconnected>")
            raise ConnectionError(f"{self.seat or '?'} disconnected")
        line = raw.decode("ascii", errors="replace").strip()
        self._log("<-", line)
        return line

    async def expect(self, predicate, what: str) -> object:
        """Read lines until predicate returns non-None; error on junk."""
        line = await self.recv()
        result = predicate(line)
        if result is None:
            raise ProtocolError(f"{self.seat}: expected {what}, got: {line!r}")
        return result


class ProtocolError(Exception):
    pass


def _ready_matcher(seat: str, suffix: str):
    expected = f"{seat} ready {suffix}".lower()
    return lambda line: True if line.strip().lower() == expected else None


class Table:
    def __init__(self, ns_name: str, ew_name: str, verbose: bool = False):
        self.clients: dict[str, Client] = {}
        self.ns_name = ns_name
        self.ew_name = ew_name
        self.verbose = verbose
        self.records: list[dict] = []

    def log(self, msg: str) -> None:
        if self.verbose:
            print(msg, file=sys.stderr)

    async def seat_client(self, client: Client) -> None:
        conn = await client.expect(p.parse_connect, "Connecting handshake")
        seat = conn.seat
        if seat in self.clients:
            await client.send(f"Error {seat} already seated")
            raise ProtocolError(f"duplicate seat {seat}")
        client.seat, client.team = seat, conn.team
        self.clients[seat] = client
        await client.send(p.format_seated(seat, conn.team))
        self.log(f"{seat} seated ({conn.team})")

    async def start_session(self) -> None:
        for seat in p.SEATS:
            c = self.clients[seat]
            await c.expect(_ready_matcher(seat, "for teams"), "ready for teams")
            await c.send(p.format_teams(self.ns_name, self.ew_name))
        for seat in p.SEATS:
            c = self.clients[seat]
            await c.expect(_ready_matcher(seat, "to start"), "ready to start")

    async def play_board(self, board_no: int, deal, vul: str, dealer: str) -> dict:
        # --- deal phase ---
        for seat in p.SEATS:
            await self.clients[seat].send("Start of board")
        for seat in p.SEATS:
            c = self.clients[seat]
            await c.expect(_ready_matcher(seat, "for deal"), "ready for deal")
            await c.send(p.format_board_info(board_no, dealer, p.VULN_STRINGS[vul]))
        hands = deal_to_hands(deal)
        for seat in p.SEATS:
            c = self.clients[seat]
            await c.expect(_ready_matcher(seat, "for cards"), "ready for cards")
            await c.send(p.format_hand(hands_to_suits(hands[seat]), seat))

        # --- auction ---
        auction = Auction(dealer)
        while not auction.finished:
            actor = auction.turn
            bid = await self.clients[actor].expect(
                lambda l: p.parse_bid(l) if (b := p.parse_bid(l)) and b.seat == actor else None,
                f"bid from {actor}",
            )
            auction.add(actor, bid.call, bid.rest)
            self.log(f"  {actor}: {bid.call}")
            line = p.format_bid(actor, bid.call, bid.rest)
            for seat in p.SEATS:
                if seat == actor:
                    continue
                c = self.clients[seat]
                await c.expect(
                    lambda l: r if (r := p.parse_ready_for_bid(l)) and r[0] == seat and r[1] == actor else None,
                    f"{seat} ready for {actor}'s bid",
                )
                await c.send(line)

        result = auction.contract()
        if result is None:
            self.log("  passed out")
            return {
                "board": board_no, "dealer": dealer, "vuln": vul,
                "deal": deal.to_pbn(), "auction": [c for _, c, _ in auction.calls],
                "contract": None, "score_ns": 0,
            }

        contract, doubled, declarer = result
        play = PlayState(contract, doubled, declarer, {s: set(h) for s, h in hands.items()})
        dummy = play.dummy
        self.log(f"  contract: {contract}{doubled} by {declarer}")

        # --- play: 13 tricks; opening lead precedes dummy reveal ---
        for trick_i in range(13):
            for pos in range(4):
                actor = play.turn
                controller = declarer if actor == dummy else actor
                if pos == 0:
                    # v18: the controller of the leading hand gets a prompt first
                    # (only the controller — other clients would misparse it).
                    prompt = "Dummy to lead" if actor == dummy else f"{actor} to lead"
                    await self.clients[controller].send(prompt)
                move = await self.clients[controller].expect(
                    lambda l: m if (m := p.parse_play(l)) and m.seat == actor else None,
                    f"{actor}'s card (from {controller})",
                )
                play.play(actor, move.card)
                line = p.format_play(actor, move.card)
                for seat in p.SEATS:
                    if seat == controller:
                        continue
                    c = self.clients[seat]
                    expected_actor = "dummy" if actor == dummy else actor

                    def match(l, seat=seat, expected_actor=expected_actor, trick_i=trick_i):
                        r = p.parse_ready_for_card(l)
                        if r and r[0] == seat and r[2] == trick_i + 1 and (
                            r[1] == expected_actor or r[1] == actor
                        ):
                            return r
                        return None

                    await c.expect(match, f"{seat} ready for {expected_actor}'s card trick {trick_i + 1}")
                    await c.send(line)
                # dummy reveal after the opening lead
                if trick_i == 0 and pos == 0:
                    dummy_line = p.format_hand(hands_to_suits(hands[dummy]), "Dummy")
                    for seat in p.SEATS:
                        if seat == dummy:
                            continue
                        c = self.clients[seat]
                        await c.expect(_ready_matcher(seat, "for dummy"), "ready for dummy")
                        await c.send(dummy_line)

        tricks = play.declarer_tricks()
        score_ns = score_board(contract, doubled, declarer, tricks, vul)
        self.log(f"  result: {tricks} tricks, NS {score_ns:+d}")
        timing = ("Timing - N/S : this board  0:00,  total  0:00."
                  "  E/W : this board  0:00,  total  0:00.")
        for seat in p.SEATS:
            await self.clients[seat].send(timing)
        return {
            "board": board_no, "dealer": dealer, "vuln": vul,
            "deal": deal.to_pbn(),
            "auction": [c for _, c, _ in auction.calls],
            "contract": f"{contract}{doubled}", "declarer": declarer,
            "tricks": tricks, "score_ns": score_ns,
        }

    async def end_session(self) -> None:
        for seat in p.SEATS:
            try:
                await self.clients[seat].send("End of session")
                self.clients[seat].writer.close()
            except Exception:
                pass


def deal_to_hands(deal) -> dict[str, list[str]]:
    """endplay Deal -> {seat: [internal cards 'SQ', ...]}"""
    out: dict[str, list[str]] = {}
    for seat, player in zip(p.SEATS, [Player.north, Player.east, Player.south, Player.west]):
        cards = []
        for card in deal[player]:
            suit = _DENOM_TO_CHAR[card.suit]
            rank = card.rank.abbr.upper()
            cards.append(suit + rank)
        out[seat] = cards
    return out


def hands_to_suits(cards: list[str]) -> dict[str, str]:
    suits: dict[str, str] = {s: "" for s in p.SUITS}
    for s in p.SUITS:
        ranks = [c[1] for c in cards if c[0] == s]
        suits[s] = "".join(sorted(ranks, key=p.RANKS.index))
    return suits


async def run_server(args) -> list[dict]:
    if args.pbn:
        from endplay.parsers import pbn
        with open(args.pbn) as f:
            boards = pbn.load(f)
        deals = [b.deal for b in boards]
    else:
        deals = list(generate_deals(produce=args.boards, seed=args.seed))

    if getattr(args, "wire_log", None):
        Client.wire_log = open(args.wire_log, "w")

    table = Table(args.ns_name, args.ew_name, verbose=args.verbose)
    ready = asyncio.Event()

    async def on_connect(reader, writer):
        client = Client(reader, writer)
        try:
            await table.seat_client(client)
        except ProtocolError as e:
            print(f"rejected connection: {e}", file=sys.stderr)
            writer.close()
            return
        if len(table.clients) == 4:
            ready.set()

    server = await asyncio.start_server(on_connect, args.host, args.port)
    print(f"table manager listening on {args.host}:{args.port}", file=sys.stderr)
    await ready.wait()

    await table.start_session()
    for i, deal in enumerate(deals):
        board_no = i + 1
        dealer = p.SEATS[i % 4]
        vul = VULN_CYCLE[i % 16]
        record = await table.play_board(board_no, deal, vul, dealer)
        table.records.append(record)
        print(f"board {board_no}: {record.get('contract')} "
              f"NS {record['score_ns']:+d}", file=sys.stderr)
    await table.end_session()
    server.close()

    if args.out:
        with open(args.out, "w") as f:
            for r in table.records:
                f.write(json.dumps(r) + "\n")
        print(f"wrote {len(table.records)} board records to {args.out}", file=sys.stderr)
    return table.records


def main() -> None:
    ap = argparse.ArgumentParser(description="Blue Chip v18 table manager server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--boards", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--pbn", help="PBN file to deal from instead of random deals")
    ap.add_argument("--ns-name", default="NS")
    ap.add_argument("--ew-name", default="EW")
    ap.add_argument("--out", help="write board records as JSON lines")
    ap.add_argument("--wire-log", help="log raw protocol lines to this file")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    asyncio.run(run_server(args))


if __name__ == "__main__":
    main()
