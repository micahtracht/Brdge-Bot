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
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, wire_log=None):
        self.reader = reader
        self.writer = writer
        self.seat: str | None = None
        self.team: str | None = None
        self.wire_log = wire_log  # per-table file object (tables may share a process)

    def _log(self, direction: str, line: str) -> None:
        if self.wire_log:
            import datetime
            stamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.wire_log.write(f"{stamp} {direction} {self.seat or '?':<5} | {line}\n")
            self.wire_log.flush()

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
            # v18 alert relay (spec lines 177/191): the alert + info go to the
            # bidder's OPPONENTS ONLY, never the partner. And a dangling "Alert."
            # with no information (WBridge5's manual-alert style) makes the next
            # opponent wait forever for info that never comes, so we strip it —
            # opponents get the alert only when it carries actual information.
            partner = p.SEATS[(p.SEATS.index(actor) + 2) % 4]
            bare_line = p.format_bid(actor, bid.call, "")
            opp_line = p.format_bid(actor, bid.call, p.relay_suffix_for_opponent(bid.rest))
            for seat in p.SEATS:
                if seat == actor:
                    continue
                c = self.clients[seat]
                await c.expect(
                    lambda l: r if (r := p.parse_ready_for_bid(l)) and r[0] == seat and r[1] == actor else None,
                    f"{seat} ready for {actor}'s bid",
                )
                await c.send(bare_line if seat == partner else opp_line)

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


def board_meta(index: int) -> tuple[int, str, str]:
    """0-based deal index -> (board number, dealer seat, vulnerability key)."""
    return index + 1, p.SEATS[index % 4], VULN_CYCLE[index % 16]


def make_deals(n: int, seed: int) -> list:
    """Deterministic deal set: same (n, seed) -> same deals on every table."""
    return list(generate_deals(produce=n, seed=seed))


def load_pbn_deals(path: str) -> list:
    from endplay.parsers import pbn
    with open(path) as f:
        return [b.deal for b in pbn.load(f)]


async def run_table(
    deals: list,
    *,
    port: int,
    ns_name: str,
    ew_name: str,
    host: str = "127.0.0.1",
    out_path: str | None = None,
    wire_log_path: str | None = None,
    verbose: bool = False,
    start_board: int = 1,
    end_board: int | None = None,
    label: str = "",
    log=None,
) -> list[dict]:
    """Host one table: wait for 4 clients, play boards start_board..end_board
    (1-based, inclusive; end defaults to the last deal), then end the session.

    Records are appended to out_path as JSON lines *per board* so a crashed or
    killed run can be resumed with start_board = last completed board + 1.
    Board numbers/dealer/vulnerability are global (from the deal index), so
    several tables can each take a slice of one deal set.
    """
    end_board = len(deals) if end_board is None else min(end_board, len(deals))
    log = log or (lambda msg: print(msg, file=sys.stderr))
    tag = f"[{label}] " if label else ""
    wire_log = open(wire_log_path, "a") if wire_log_path else None
    out = open(out_path, "a") if out_path else None

    table = Table(ns_name, ew_name, verbose=verbose)
    ready = asyncio.Event()

    async def on_connect(reader, writer):
        client = Client(reader, writer, wire_log=wire_log)
        try:
            await table.seat_client(client)
        except ProtocolError as e:
            log(f"{tag}rejected connection: {e}")
            writer.close()
            return
        if len(table.clients) == 4:
            ready.set()

    server = await asyncio.start_server(on_connect, host, port)
    log(f"{tag}table manager listening on {host}:{port} "
        f"(boards {start_board}-{end_board}, NS={ns_name}, EW={ew_name})")
    try:
        await ready.wait()
        await table.start_session()
        for i in range(start_board - 1, end_board):
            board_no, dealer, vul = board_meta(i)
            record = await table.play_board(board_no, deals[i], vul, dealer)
            record["ns_team"], record["ew_team"] = ns_name, ew_name
            table.records.append(record)
            if out:
                out.write(json.dumps(record) + "\n")
                out.flush()
            log(f"{tag}board {board_no}: {record.get('contract')} NS {record['score_ns']:+d}")
        await table.end_session()
    finally:
        server.close()
        if out:
            out.close()
        if wire_log:
            wire_log.close()
    return table.records


async def run_server(args) -> list[dict]:
    deals = load_pbn_deals(args.pbn) if args.pbn else make_deals(args.boards, args.seed)
    return await run_table(
        deals, host=args.host, port=args.port, ns_name=args.ns_name, ew_name=args.ew_name,
        out_path=args.out, wire_log_path=getattr(args, "wire_log", None),
        verbose=args.verbose, start_board=getattr(args, "from_board", 1),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Blue Chip v18 table manager server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2000)
    ap.add_argument("--boards", type=int, default=2)
    ap.add_argument("--from-board", type=int, default=1, help="resume from this board number")
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
