"""Scripted Blue Chip v18 client for conformance-testing the table manager.

Strategy: the dealer opens 1NT, everyone else passes; every card played is the
lowest legal one. Exercises the full protocol including dummy control.
"""
from __future__ import annotations

import asyncio
import re

from . import protocol as p


def lowest(cards: set[str], suit: str | None = None) -> str:
    pool = [c for c in cards if suit is None or c[0] == suit] or list(cards)
    return max(pool, key=lambda c: p.RANKS.index(c[1]))


def parse_hand_line(line: str) -> set[str]:
    body = line[line.index(":") + 1 :]
    cards: set[str] = set()
    current_suit = None
    for token in body.replace(".", " ").split():
        if token in ("S", "H", "D", "C"):
            current_suit = token
        elif token == "-":
            continue
        elif current_suit and all(ch in p.RANKS for ch in token):
            for ch in token:
                cards.add(current_suit + ch)
    return cards


class MockClient:
    def __init__(self, seat: str, team: str, host: str, port: int):
        self.seat = seat
        self.team = team
        self.host = host
        self.port = port

    async def send(self, line: str) -> None:
        self.writer.write((line + "\r\n").encode("ascii"))
        await self.writer.drain()

    async def recv(self) -> str:
        raw = await self.reader.readline()
        if not raw:
            raise ConnectionError(f"{self.seat}: server closed")
        return raw.decode("ascii").strip()

    async def run(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
        await self.send(f'Connecting "{self.team}" as {self.seat} using protocol version 18')
        await self.recv()  # seated
        await self.send(f"{self.seat} ready for teams")
        await self.recv()  # teams
        await self.send(f"{self.seat} ready to start")

        while True:
            line = await self.recv()
            if line == "End of session":
                self.writer.close()
                return
            assert line.lower() == "start of board", f"{self.seat}: expected board start, got {line!r}"
            await self.play_board()

    async def play_board(self) -> None:
        await self.send(f"{self.seat} ready for deal")
        info = await self.recv()
        dealer = re.search(r"Dealer (\w+)\.", info).group(1).capitalize()
        await self.send(f"{self.seat} ready for cards")
        self.hand = parse_hand_line(await self.recv())

        # --- auction: dealer bids 1NT, everyone else passes ---
        calls = []
        turn_i = p.SEATS.index(dealer)
        while not (len(calls) >= 4 and all(c == "PASS" for c in calls[-3:])):
            actor = p.SEATS[turn_i % 4]
            if actor == self.seat:
                call = "1N" if not calls else "PASS"
                await self.send(p.format_bid(self.seat, call))
                calls.append(call)
            else:
                await self.send(f"{self.seat} ready for {actor}'s bid")
                bid = p.parse_bid(await self.recv())
                calls.append(bid.call)
            turn_i += 1

        declarer = dealer  # 1NT by dealer, all pass
        dummy = p.SEATS[(p.SEATS.index(declarer) + 2) % 4]
        dummy_hand: set[str] = set()
        leader = p.SEATS[(p.SEATS.index(declarer) + 1) % 4]

        # --- play ---
        for trick_i in range(13):
            trick: list[tuple[str, str]] = []
            for pos in range(4):
                actor = p.SEATS[(p.SEATS.index(leader) + pos) % 4]
                controller = declarer if actor == dummy else actor
                led = trick[0][1][0] if trick else None
                if controller == self.seat:
                    if pos == 0:
                        prompt = await self.recv()  # "... to lead"
                        assert "to lead" in prompt, f"{self.seat}: expected lead prompt, got {prompt!r}"
                    source = self.hand if actor == self.seat else dummy_hand
                    card = lowest(source, led)
                    source.discard(card)
                    await self.send(p.format_play(actor, card))
                    trick.append((actor, card))
                else:
                    name = "dummy" if actor == dummy else actor
                    await self.send(f"{self.seat} ready for {name}'s card to trick {trick_i + 1}")
                    move = p.parse_play(await self.recv())
                    trick.append((actor, move.card))
                    if actor == dummy:
                        dummy_hand.discard(move.card)
                    elif actor == self.seat:
                        self.hand.discard(move.card)
                if trick_i == 0 and pos == 0 and self.seat != dummy:
                    await self.send(f"{self.seat} ready for dummy")
                    dummy_hand = parse_hand_line(await self.recv())
                    if self.seat == dummy:  # unreachable; kept for clarity
                        pass
            leader = winner_nt(trick)

        await self.recv()  # timing line


def winner_nt(trick: list[tuple[str, str]]) -> str:
    led = trick[0][1][0]
    best_seat, best_card = trick[0]
    for seat, card in trick[1:]:
        if card[0] == led and p.RANKS.index(card[1]) < p.RANKS.index(best_card[1]):
            best_seat, best_card = seat, card
    return best_seat
