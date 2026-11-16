"""A weekly cup's records and calendar. Pure: no I/O, no clock."""

import json
import random
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from arena.manifest import CupRules
from arena.match import BoutResult

GROUP_NAMES = "ABCDEFGHIJKLMNOP"
_STAMP = "%Y-%m-%dT%H:%M:%SZ"
_MATCH_ID = re.compile(r"^([a-z0-9-]+)-(\d{4})-(\d{3})$")


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime(_STAMP)


def parse_iso(stamp: str) -> datetime:
    return datetime.strptime(stamp, _STAMP).replace(tzinfo=UTC)


@dataclass(frozen=True)
class Entrant:
    user: str
    run_id: str
    policy_name: str
    livery: str
    rating: float
    model_sha256: str
    source: dict  # RunRecord.source: where the policy is fetched from
    name: str  # the duck's on-air name in this cup: policy_name, or "policy_name (@user)" on a clash

    def view(self) -> dict:
        return {"user": self.user, "policy_name": self.policy_name, "name": self.name,
                "livery": self.livery, "rating": self.rating, "run_id": self.run_id}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "Entrant":
        return cls(**raw)


@dataclass(frozen=True)
class MatchRecord:
    match_id: str
    index: int  # position in playing order
    round: str  # "group" | "round of 16" | "quarter-final" | "semi-final" | "final" | "round of 2n"
    group: str | None  # "A", "B", … on a group match
    a: int
    b: int  # entrant indices
    bouts: tuple[BoutResult, ...]
    wins: tuple[int, int]
    winner: int  # entrant index
    decided_by: str

    def to_dict(self) -> dict:
        return {"match_id": self.match_id, "index": self.index, "round": self.round, "group": self.group,
                "a": self.a, "b": self.b, "bouts": [bout.to_dict() for bout in self.bouts],
                "wins": list(self.wins), "winner": self.winner, "decided_by": self.decided_by}

    @classmethod
    def from_dict(cls, raw: dict) -> "MatchRecord":
        return cls(raw["match_id"], raw["index"], raw["round"], raw["group"], raw["a"], raw["b"],
                   tuple(BoutResult.from_dict(bout) for bout in raw["bouts"]), tuple(raw["wins"]),
                   raw["winner"], raw["decided_by"])


@dataclass(frozen=True)
class Cup:
    event_id: str
    number: int
    close_at: str  # ISO "…Z"
    premiere_at: str  # the scheduled premiere, ISO "…Z"
    secret: str  # 32 hex chars, drawn at close
    entrants: tuple[Entrant, ...]
    groups: tuple[tuple[int, ...], ...]  # () when skipped
    skipped: bool = False  # fewer than min_entrants
    matches: tuple[MatchRecord, ...] = ()  # group rounds, then the knockout, in playing order
    order: dict | None = None  # {"starts_at": ISO, "segments": [...]}, once fixed

    def draw_json(self) -> bytes:
        return json.dumps({
            "event_id": self.event_id, "number": self.number, "close_at": self.close_at,
            "premiere_at": self.premiere_at, "secret": self.secret,
            "entrants": [entrant.to_dict() for entrant in self.entrants],
            "groups": [list(group) for group in self.groups], "skipped": self.skipped,
        }).encode()

    def matches_json(self) -> bytes:
        return json.dumps({"matches": [match.to_dict() for match in self.matches]}).encode()

    @classmethod
    def from_json(cls, draw: bytes, matches: bytes | None = None, order: bytes | None = None) -> "Cup":
        raw = json.loads(draw)
        played = () if matches is None else tuple(MatchRecord.from_dict(m) for m in json.loads(matches)["matches"])
        return cls(raw["event_id"], raw["number"], raw["close_at"], raw["premiere_at"], raw["secret"],
                   tuple(Entrant.from_dict(e) for e in raw["entrants"]),
                   tuple(tuple(group) for group in raw["groups"]), raw["skipped"], played,
                   None if order is None else json.loads(order))


def match_id(event_id: str, number: int, index: int) -> str:
    return f"{event_id}-{number:04d}-{index:03d}"


def parse_match_id(text: str) -> tuple[str, int, int] | None:
    found = _MATCH_ID.match(text)
    return None if found is None else (found[1], int(found[2]), int(found[3]))


def is_match_id(clip_id: str) -> bool:
    return parse_match_id(clip_id) is not None


def cup_times(rules: CupRules, number: int) -> tuple[datetime, datetime]:
    """(close_at, premiere_at) of cup `number`: the local wall clock steps by weeks, the close is absolute."""
    day = rules.first + timedelta(weeks=number - 1)
    premiere = datetime.combine(day, rules.premiere, ZoneInfo(rules.timezone)).astimezone(UTC)
    return premiere - timedelta(hours=rules.close_before_h), premiere


def closed_cups(rules: CupRules, now: datetime) -> int:
    number = 0
    while cup_times(rules, number + 1)[0] <= now:
        number += 1
    return number


def group_count(entrants: int) -> int:
    """The largest power of two G >= 1 that leaves at least three ducks a group."""
    count = 1
    while entrants // (count * 2) >= 3:
        count *= 2
    return count


def draw_groups(entrants: Sequence[Entrant], secret: str) -> list[list[int]]:
    """Pots of G by rating (best first, ties by user), each shuffled by the secret; pot p's i-th duck goes to group i."""
    count = group_count(len(entrants))
    ranked = sorted(range(len(entrants)), key=lambda i: (-entrants[i].rating, entrants[i].user))
    groups: list[list[int]] = [[] for _ in range(count)]
    for p, start in enumerate(range(0, len(ranked), count)):
        pot = ranked[start:start + count]
        random.Random(secret + str(p)).shuffle(pot)
        for g, i in enumerate(pot):
            groups[g].append(i)
    return groups


def group_fixtures(group: Sequence[int]) -> list[tuple[int, int]]:
    """The circle method, rounds in order; a bye pads an odd group and plays nobody."""
    ring = list(group) + ([None] if len(group) % 2 else [])
    out = []
    for _ in range(len(ring) - 1):
        out += [(ring[i], ring[-1 - i]) for i in range(len(ring) // 2) if None not in (ring[i], ring[-1 - i])]
        ring = [ring[0], ring[-1], *ring[1:-1]]
    return out


def group_table(group: Sequence[int], matches: Sequence[MatchRecord], ratings: Sequence[float]) -> list[int]:
    """The group ranked on matches won, bouts won minus lost, head-to-head among the tied, rating, then draw order."""
    played = [m for m in matches if m.a in group and m.b in group]
    wins = {i: sum(m.winner == i for m in played) for i in group}
    diff = {i: sum((m.wins[0] - m.wins[1]) * (1 if m.a == i else -1) for m in played if i in (m.a, m.b)) for i in group}

    def head_to_head(i: int) -> int:
        tied = {j for j in group if (wins[j], diff[j]) == (wins[i], diff[i])}
        return sum(m.winner == i for m in played if {m.a, m.b} <= tied)

    return sorted(group, key=lambda i: (-wins[i], -diff[i], -head_to_head(i), -ratings[i], list(group).index(i)))


def first_knockout(tables: Sequence[Sequence[int]]) -> list[tuple[int, int]]:
    """The first knockout round as the bracket's two halves (winners are paired in order each round).

    Groups are paired (A, B), (C, D)...: every pair's X1-Y2 first, then every pair's Y1-X2, so a group's first and
    second sit in different halves and group-mates meet at the earliest in the final.
    """
    if len(tables) == 1:
        return [(tables[0][0], tables[0][1])]
    pairs = range(len(tables) // 2)
    return [(tables[2 * p][0], tables[2 * p + 1][1]) for p in pairs] + [(tables[2 * p + 1][0], tables[2 * p][1]) for p in pairs]


def round_name(matches_in_round: int) -> str:
    return {1: "final", 2: "semi-final", 4: "quarter-final"}.get(matches_in_round, f"round of {2 * matches_in_round}")


def cup_title(event_title: str, number: int) -> str:
    """The cup as it is named on air, on the standby card, the desk's screen and a match's card."""
    return f"{event_title} · Cup #{number}"


def _stage(match: MatchRecord) -> str:
    return f"Group {match.group}" if match.group else match.round.capitalize()


def duck(entrant: Entrant) -> str:
    """A duck billed with its player, "<policy name> (@<user>)": from its policy's name, not its on-air `name`, which
    on a clash carries the handle already."""
    return f"{entrant.policy_name} (@{entrant.user})"


def match_billing(cup: Cup, match: MatchRecord) -> str:
    """Who meets whom, both ducks billed with their players."""
    return f"{duck(cup.entrants[match.a])} vs {duck(cup.entrants[match.b])}"


def match_title(cup: Cup, match: MatchRecord) -> str:
    """The match as it is announced on air: its stage and its billing."""
    return f"{_stage(match)} · {match_billing(cup, match)}"


def match_label(cup: Cup, match: MatchRecord) -> str:
    """The stage alone, naming no duck, numbered by its place when its round holds several matches."""
    same = [m for m in cup.matches if m.round == match.round]
    if match.group or len(same) == 1:
        return _stage(match)
    return f"{_stage(match)} {same.index(match) + 1}"


def reached(cup: Cup) -> list[str]:
    """Per entrant: "champion", "final", the knockout round it lost in, or "group"."""
    out = ["group"] * len(cup.entrants)
    for match in cup.matches:
        if match.group:
            continue
        loser = match.b if match.winner == match.a else match.a
        out[loser] = match.round
        if match.round == "final":
            out[match.winner] = "champion"
    return out


# A match's clip media are served from airs_at - PREFETCH, so the live can buffer it before its slot.
PREFETCH = timedelta(seconds=30)


def _on_air(cup: Cup, match_id: str) -> tuple[datetime, datetime] | None:
    """When the match's clip starts airing, and when it has finished."""
    if cup.order is None:
        return None
    for segment in cup.order["segments"]:
        if segment["kind"] == "match" and segment["match_id"] == match_id:
            airs = parse_iso(cup.order["starts_at"]) + timedelta(milliseconds=segment["at_ms"])
            return airs, airs + timedelta(milliseconds=segment["duration_ms"])
    return None


def airs_at(cup: Cup, match_id: str) -> datetime | None:
    span = _on_air(cup, match_id)
    return None if span is None else span[0]


def revealed_at(cup: Cup, match_id: str) -> datetime | None:
    """The match's result is public once its clip has finished airing, not while it airs."""
    span = _on_air(cup, match_id)
    return None if span is None else span[1]


def ends_at(cup: Cup) -> datetime | None:
    if cup.order is None:
        return None
    last = cup.order["segments"][-1]
    return parse_iso(cup.order["starts_at"]) + timedelta(milliseconds=last["at_ms"] + last["duration_ms"])


def cup_state(cup: Cup, now: datetime) -> str:
    if cup.skipped:
        return "skipped"
    if now < parse_iso(cup.close_at):
        return "open"
    if cup.order is None:
        return "drawn"
    if now < parse_iso(cup.order["starts_at"]):
        return "ready"
    return "airing" if now < ends_at(cup) else "aired"


def _row(entrant: int, matches: Sequence[MatchRecord]) -> dict:
    mine = [m for m in matches if entrant in (m.a, m.b)]
    bouts = [m.wins if m.a == entrant else m.wins[::-1] for m in mine]
    won = sum(m.winner == entrant for m in mine)
    return {"entrant": entrant, "played": len(mine), "won": won, "lost": len(mine) - won,
            "bouts_for": sum(f for f, _ in bouts), "bouts_against": sum(a for _, a in bouts)}


def cup_view(cup: Cup, now: datetime) -> dict:
    """What is public at `now`: every API, page and the live ask here, so nothing is told before it has aired.

    Before the start, the field alone. From the start, the groups and their pairs; a knockout pair once the round before
    it is revealed; each result, and its weight in the tables, from its reveal; the champion and the secret from the
    final's. No reveal is timed: a tug clip grows with each bout, so a match's reveal time would tell how it went.
    """
    state = cup_state(cup, now)
    view = {"event_id": cup.event_id, "number": cup.number, "state": state, "close_at": cup.close_at,
            "premiere_at": cup.premiere_at, "starts_at": None if cup.order is None else cup.order["starts_at"],
            "entrants": [entrant.view() for entrant in cup.entrants]}
    if state not in ("airing", "aired"):
        return view
    shown = {m.match_id for m in cup.matches if revealed_at(cup, m.match_id) <= now}
    ratings = [entrant.rating for entrant in cup.entrants]

    def paired(match: MatchRecord) -> bool:
        if match.group:
            return True
        first = next(m for m in cup.matches if m.round == match.round)
        return cup.matches[first.index - 1].match_id in shown

    def public(match: MatchRecord) -> dict:
        out = {"match_id": match.match_id, "index": match.index, "round": match.round, "group": match.group,
               "a": None, "b": None, "title": match_label(cup, match)}
        if paired(match):
            out.update(a=match.a, b=match.b, title=match_title(cup, match))
        if match.match_id in shown:
            out.update(bouts=[bout.to_dict() for bout in match.bouts], wins=list(match.wins), winner=match.winner,
                       decided_by=match.decided_by)
        return out

    groups = []
    for name, group in zip(GROUP_NAMES, cup.groups):
        # By its name, not its members: a knockout rematch of two group-mates is not the group's.
        played = [m for m in cup.matches if m.group == name and m.match_id in shown]
        groups.append({"name": name, "table": [_row(i, played) for i in group_table(group, played, ratings)]})
    final = cup.matches[-1]
    view.update(groups=groups, matches=[public(m) for m in cup.matches],
                champion=final.winner if final.match_id in shown else None)
    if final.match_id in shown:
        view["secret"] = cup.secret
    return view
