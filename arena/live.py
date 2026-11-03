"""The channel's programme: an infinite grid every screen reads its place in.

Nothing is broadcast. The grid is a list of slots at absolute wall-clock
milliseconds, laid entry by entry, a cycle at a time, from the ready clips; a
screen reads the server's clock once, finds the slot that contains now, and
plays it from the right offset. Two screens agree because they read the same
grid and the same clock, not because a stream was pushed at them.
"""

import random
import threading
from dataclasses import dataclass
from datetime import datetime

from .broadcasts import BroadcastBook, utcnow
from .cup import cup_title, ends_at, iso, match_title, parse_iso, revealed_at
from .index import copies
from .manifest import all_events
from .store import clip_version

SHUTTER_MS = 1600
HORIZON_MS = 5 * 60_000  # how far ahead the grid is built and served
BEHIND_MS = 60_000  # how far back it is served, so a late poll still finds now
KEEP_MS = 120_000  # slots older than this are forgotten
# How long a screen trusts the grid it holds: it reads a new one every ten seconds
# and forgives a lost read for thirty. What starts within this of now is never laid
# again, or a screen would enter one slot and be told, a read later, that another
# was playing — and cut into the middle of it.
PROMISED_MS = 30_000
HEAD = 3  # the newest runs open every cycle
# A cup late on its premiere has no start until its running order lands: its standby
# is laid a minute at a time. The order is fixed at least ten minutes ahead
# (cupworker.ORDER_LEAD), beyond the grid's reach of HORIZON_MS and one of these.
LATE_STANDBY_MS = 60_000


@dataclass(frozen=True)
class Entry:
    run_id: str
    user: str
    event_title: str
    submitted_at: str
    replay_ms: int
    # Which render of the clip: the screens build its media URLs from this.
    clip: str
    # A cup match's, which announces it: "Tug of War · Cup #1 · Final · duck 0 vs duck 1".
    title: str | None = None


@dataclass(frozen=True)
class Show:
    """A cup on the grid. From its premiere the channel airs it and nothing else: its running order at
    its own times, whatever the cycle is doing, and its standby until then, however late the order is."""
    premiere_ms: int
    starts_ms: int | None  # None while the cup has no running order
    ends_ms: int | None
    # each shutter, each desk segment of the cup's show by its name, and each match as a replay slot with its clip
    # version, called when the show has its call
    slots: tuple[dict, ...]
    standby: dict  # {"title"}: what the screen waits for


def _ready(store, clip_id: str) -> tuple[int, str] | None:
    """The clip's length and render, once it is ready to be laid."""
    state, clip = store.clip_state(clip_id)
    if state != "ready":
        return None
    replay_ms = round(clip["layouts"]["landscape"]["seconds"] * 1000)
    # A length that is not a whole number of frames cannot be laid on the
    # grid; such a clip stays off the programme rather than breaking the
    # channel for everyone.
    if replay_ms % 40:
        return None
    return replay_ms, clip_version(clip)


def pool(store, now: datetime) -> list[Entry]:
    """Every run with a ready clip, not withdrawn and not a copy, and the matches of each
    event's last cup once it has aired, until the event's next cup starts."""
    from .cupworker import all_cups  # not at the top: cupworker reads SHUTTER_MS from this module

    withdrawn = {w.run_id for w in store.withdrawals()}
    cups = all_cups(store)
    entries = []
    for manifest in all_events():
        records = store.runs(manifest.id)
        off = withdrawn | copies(records).keys()
        for record in records:
            ready = None if record.run_id in off else _ready(store, record.run_id)
            if ready is not None:
                entries.append(Entry(record.run_id, record.user, manifest.title, record.submitted_at, *ready))
        started = [cup for cup in cups if cup.event_id == manifest.id
                   and cup.order is not None and parse_iso(cup.order["starts_at"]) <= now]
        if not started:
            continue
        cup = max(started, key=lambda one: one.number)
        if ends_at(cup) > now:
            continue
        for match in cup.matches:
            ready = _ready(store, match.match_id)
            if ready is not None:
                entries.append(Entry(match.match_id, cup.entrants[match.winner].user, manifest.title,
                                     iso(revealed_at(cup, match.match_id)), *ready,
                                     title=f"{cup_title(manifest.title, cup.number)} · {match_title(cup, match)}"))
    return entries


def shows(store, now: datetime) -> list[Show]:
    """Every cup that has not finished airing, by premiere; one with no running order yet, still
    drawn, played or rendered, has no start and no end."""
    from .cupworker import all_cups  # not at the top: cupworker reads SHUTTER_MS from this module

    titles = {manifest.id: manifest.title for manifest in all_events()}
    laid = []
    for cup in all_cups(store):
        if cup.skipped or (cup.order is not None and ends_at(cup) <= now):
            continue
        premiere = int(parse_iso(cup.premiere_at).timestamp() * 1000)
        standby = {"title": cup_title(titles[cup.event_id], cup.number)}
        if cup.order is None:
            laid.append(Show(premiere, None, None, (), standby))
            continue
        start = int(parse_iso(cup.order["starts_at"]).timestamp() * 1000)
        slots = []
        for segment in cup.order["segments"]:
            at, duration = start + segment["at_ms"], segment["duration_ms"]
            if segment["kind"] == "shutter":
                slots.append({"kind": "shutter", "at_ms": at, "duration_ms": duration, "next": segment["next"]})
            elif segment["kind"] == "desk":
                # Peter and Ray at the desk: the screens fetch the segment from the cup's show by its name.
                slots.append({"kind": "desk", "at_ms": at, "duration_ms": duration, "show": {
                    "event": cup.event_id, "number": cup.number, "segment": segment["segment"]}})
            else:
                # The order carries each clip's length, not its render: that is read here. A clip
                # deleted to be rendered again has none: its media fail to load, and the screens hold
                # the shutter's panel over its slot, as over a withdrawn run's.
                state, clip = store.clip_state(segment["match_id"])
                slots.append({"kind": "replay", "at_ms": at, "duration_ms": duration, "run_id": segment["match_id"],
                              "clip": clip_version(clip) if state == "ready" else None, "media": "match",
                              **({"call": True} if segment.get("call") else {})})
        laid.append(Show(premiere, start, slots[-1]["at_ms"] + slots[-1]["duration_ms"], tuple(slots), standby))
    return sorted(laid, key=lambda show: show.premiere_ms)


def cycle(entries: list[Entry], k: int) -> list[Entry]:
    """One pass over the pool: the newest runs first, the rest shuffled by the
    cycle number, so every screen computes the same order. A cup's matches are
    in the rest: dated by their reveal, they would otherwise be the newest and
    open every cycle until the next cup, with no booth, the final before its
    semi-finals."""
    newest = sorted(entries, key=lambda e: (e.submitted_at, e.run_id), reverse=True)
    runs = [e for e in newest if e.title is None]
    head, rest = runs[:HEAD], runs[HEAD:] + [e for e in newest if e.title is not None]
    random.Random(k).shuffle(rest)
    return head + rest


def slots_for(entries: list[Entry], start_ms: int, book: BroadcastBook,
              claimed: set[str] | None = None) -> list[dict]:
    slots: list[dict] = []
    at = start_ms
    # One waiting dialogue is one booth. `claimed` carries the broadcasts the
    # slots already laid are using, so a rebuild cannot hand a screen's playing
    # booth to a second slot in the future: a broadcast is unaired right up to
    # the moment its slot ends.
    claimed = set() if claimed is None else set(claimed)

    def add(slot: dict) -> None:
        nonlocal at
        if slot["duration_ms"] % 40:
            raise ValueError(f"{slot['kind']} for {slot.get('run_id')} is not a whole number of frames")
        slots.append({**slot, "at_ms": at})
        at += slot["duration_ms"]

    for entry in entries:
        match = entry.title is not None
        add({"kind": "shutter", "duration_ms": SHUTTER_MS,
             "next": {"match_id": entry.run_id, "title": entry.title} if match
             else {"run_id": entry.run_id, "event": entry.event_title, "user": entry.user}})
        add({"kind": "replay", "duration_ms": entry.replay_ms, "run_id": entry.run_id,
             "clip": entry.clip, **({"media": "match"} if match else {})})
        # Peter and Ray's writer writes about runs: a match never has a booth.
        waiting = None if match else book.unaired(entry.run_id)
        if waiting is not None and waiting.id not in claimed:
            claimed.add(waiting.id)
            add({"kind": "shutter", "duration_ms": SHUTTER_MS, "next": None})
            add({"kind": "booth", "duration_ms": waiting.plan["duration_ms"],
                 "run_id": entry.run_id, "broadcast": waiting.id, "clip": entry.clip})
    return slots


class Programme:
    """The grid, built lazily as far as the horizon, and laid again when the
    pool or the book changes: past what screens were promised when something
    lands, from the slot playing now when a run is withdrawn — keeping its place
    in the cycle it is walking either way, so the rebuild carries on from there
    instead of opening a new cycle on the newest runs. A cup's show airs at its
    running order's own times: the cycle stands by for it, from its premiere at
    the latest, then resumes."""

    def __init__(self, source, now_ms, book, cups=list):
        self._source = source
        self._now = now_ms
        self._book = book
        self._cups = cups  # the shows to air, as `shows` reads them
        self._lock = threading.Lock()
        self.origin_ms = now_ms()
        self._slots: list[dict] = []
        self._cursor = self.origin_ms  # where the next entry starts
        self._cycle = 0  # the cycle being walked
        self._pending: list[Entry] = []  # what is left of it to lay
        # (start, cycle, run) of every entry laid since the cycle playing now
        # opened: the grid's place in it, which a rebuild picks up from.
        self._laid: list[tuple[int, int, str]] = []

    def _claimed(self) -> set[str]:
        return {slot["broadcast"] for slot in self._slots if slot["kind"] == "booth"}

    def _walking(self, now: int) -> int:
        """The cycle the screen is in: the one the last entry it has reached
        was laid for."""
        return next((k for at, k, _ in reversed(self._laid) if at <= now), self._cycle)

    def _take_up_the_cycle(self) -> bool:
        """Read the pool into the cycle being walked, minus the runs it has
        already laid: a run withdrawn since has gone from it, one that landed
        since is in it. False when nothing is on the channel at all."""
        entries = cycle(self._source(), self._cycle)
        walked = {run for _, k, run in self._laid if k == self._cycle}
        self._pending = [one for one in entries if one.run_id not in walked]
        if entries and not self._pending:
            # The entry playing is the cycle's last one, or a withdrawal took
            # the only run it had left: the next cycle is laid whole.
            self._cycle += 1
            self._pending = cycle(self._source(), self._cycle)
        return bool(self._pending)

    def _extend(self, until_ms: int) -> None:
        # A process nobody read from for days leaves the cursor far behind, and
        # everything built from there is pruned the moment it is built: start at
        # the edge of the window that is actually served.
        self._cursor = max(self._cursor, until_ms - HORIZON_MS - BEHIND_MS)
        # What the kept slots are playing is claimed before anything is laid,
        # and the claims grow with the grid: a booth laid for one entry is
        # claimed against the next. No booth is ever handed to two slots.
        #
        # A show is laid where its order says, so the grid must not have
        # reached its start before the order is known, or its slots would
        # overlap what was laid there. The cup worker fixes an order at least
        # ORDER_LEAD (10 minutes) ahead, and the grid reaches no further than
        # HORIZON_MS plus one entry, or one LATE_STANDBY_MS.
        claimed, shows = self._claimed(), None
        while self._cursor < until_ms:
            shows = self._cups() if shows is None else shows  # read once per extension that lays something
            show = next((one for one in shows if one.ends_ms is None or one.ends_ms > self._cursor), None)
            if show is not None and show.starts_ms is not None and show.starts_ms <= self._cursor:
                # Inside a show: its slots at their own times. A restart in the
                # middle of one joins the segment airing now.
                self._slots.extend(slot for slot in show.slots if slot["at_ms"] + slot["duration_ms"] > self._cursor)
                self._cursor = show.ends_ms
                continue
            if show is not None and show.premiere_ms <= self._cursor:
                self._stand_by(show)  # past its premiere, the cup is all the channel waits for
                continue
            if not self._pending and not self._take_up_the_cycle():
                if show is None:
                    return
                self._stand_by(show)
                continue
            made = slots_for([self._pending[0]], self._cursor, self._book, claimed)
            if show is not None and made[-1]["at_ms"] + made[-1]["duration_ms"] > show.premiere_ms:
                self._stand_by(show)  # the entry waits for after the show
                continue
            entry = self._pending.pop(0)
            claimed |= {slot["broadcast"] for slot in made if slot["kind"] == "booth"}
            self._laid.append((self._cursor, self._cycle, entry.run_id))
            self._slots.extend(made)
            self._cursor = made[-1]["at_ms"] + made[-1]["duration_ms"]
            if not self._pending:
                self._cycle += 1  # walked to its end; the next one is whole

    def _stand_by(self, show: Show) -> None:
        """Fill to the show's start with its standby: the one slot of any
        length, since it plays no frames. A cup with no running order has no
        start: its standby is laid LATE_STANDBY_MS at a time, and gives no time."""
        if show.starts_ms is None:
            self._slots.append({"kind": "standby", "at_ms": self._cursor, "duration_ms": LATE_STANDBY_MS,
                                "cup": show.standby, "late": True})
            self._cursor += LATE_STANDBY_MS
            return
        self._slots.append({"kind": "standby", "at_ms": self._cursor,
                            "duration_ms": show.starts_ms - self._cursor, "cup": show.standby})
        self._cursor = show.starts_ms

    def _mark_aired(self, now: int) -> None:
        """A booth whose slot has ended has been heard, wherever a screen was.
        The server knows the grid and the clock; no screen reports anything."""
        for slot in self._slots:
            if slot["kind"] != "booth" or slot["at_ms"] + slot["duration_ms"] > now:
                continue
            self._book.mark_aired(slot["broadcast"], utcnow())

    def slots(self) -> list[dict]:
        now = self._now()
        with self._lock:
            self._extend(now + HORIZON_MS)
            # Before the prune below: a booth whose slot has ended is dropped
            # from `self._slots` after KEEP_MS, and marking after that would
            # lose it — the broadcast would stay unaired for ever and be laid
            # again.
            self._mark_aired(now)
            self._slots = [s for s in self._slots if s["at_ms"] + s["duration_ms"] > now - KEEP_MS]
            # The place a rebuild picks up from is in the cycle playing now;
            # what the cycles before it laid is nobody's business any more.
            walking = self._walking(now)
            self._laid = [(at, k, run) for at, k, run in self._laid if k >= walking]
            return [s for s in self._slots
                    if s["at_ms"] + s["duration_ms"] > now - BEHIND_MS and s["at_ms"] <= now + HORIZON_MS]

    def _forget_from(self, edge: int, now: int) -> None:
        """Forget every slot from `edge` on, and keep the grid's place: the cycle
        being walked is the last kept entry's, and the next read lays the rest of
        it from a fresh pool."""
        self._slots = [s for s in self._slots if s["at_ms"] < edge]
        self._laid = [(at, k, run) for at, k, run in self._laid if at < edge]
        if self._laid:
            self._cycle = self._laid[-1][1]
        self._pending = []
        self._cursor = ((self._slots[-1]["at_ms"] + self._slots[-1]["duration_ms"])
                        if self._slots else now)

    def landed(self) -> None:
        """Something new can be laid, a clip or a dialogue: lay the future again
        from the first entry no screen has been promised.

        An entry that has begun, or begins within PROMISED_MS, keeps every one of
        its slots — a run announced keeps its replay, a replay playing keeps the
        booth after it — and what landed is offered to the entries after those. A
        dialogue lands some seventy times an hour: laying the very next slots
        again each time is what made the picture cut into the middle of another.
        The grid keeps its place in the cycle too, or a rebuild would open a new
        cycle on the newest runs each time and never reach the rest of the pool.
        """
        now = self._now()
        with self._lock:
            edge = next((at for at, _, _ in self._laid if at > now + PROMISED_MS), self._cursor)
            self._forget_from(edge, now)

    def invalidate(self) -> None:
        """A run was taken off the board: keep the slot playing now and nothing
        else, whatever was promised — the channel must not play a run its author
        withdrew. A restart is the same thing with nothing kept.

        An entry already announced stays walked, because laying it again would
        repeat a replay the screen has just seen.
        """
        now = self._now()
        with self._lock:
            self._forget_from(now + 1, now)
