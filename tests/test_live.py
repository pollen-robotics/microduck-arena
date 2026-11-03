"""The grid is a pure function of the pool and the cycle number; the clock
only says which part of it to serve."""

import hashlib
import json
import random
import shutil
from collections import Counter
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import pairwise

import numpy as np
from fastapi.testclient import TestClient

from arena.broadcasts import BroadcastBook
from arena.commentary.show import show_outline
from arena.cup import ends_at, iso, parse_iso
from arena.cupworker import running_order
from arena.live import (
    BEHIND_MS,
    HEAD,
    KEEP_MS,
    PROMISED_MS,
    SHUTTER_MS,
    Entry,
    Programme,
    Show,
    cycle,
    pool,
    shows,
    slots_for,
)
from arena.manifest import load_event
from arena.store import LocalStore, Withdrawal
from arena.trace import encode
from arena.web.app import create_app
from arena.web.config import ArenaConfig
from tests.show_cups import played_cup as show_cup
from tests.test_cup_view import REVEAL, START, START_ISO
from tests.test_cupworker import drawn_cup, played_cup, store_cup
from tests.test_store import make_record
from tests.test_withdraw import sign_in, spaced  # noqa: F401 — spaced is a fixture


def entry(run_id, at="2026-09-10T10:00:00Z", replay_ms=8000, user="alice"):
    return Entry(run_id, user, "2 m Sprint", at, replay_ms, "20260916T100500Z")


def test_the_pool_is_ready_clips_that_are_not_withdrawn(tmp_path):
    store = LocalStore(tmp_path)
    for score, run_id in enumerate(("A", "B", "C", "D"), 20):
        store.append(make_record(run_id=run_id, event_id="sprint-2m", user=run_id.lower(), score=score), b"t")
    clip = lambda seconds: json.dumps({"rendered_at": "2026-09-16T10:05:00Z",
                                       "layouts": {"landscape": {"seconds": seconds}}}).encode()
    # A commentary file sitting in the clip folder is not read by the pool at
    # all any more: whether one is there changes nothing about what plays.
    store.put_clip("A", {"clip.json": clip(8.0),
                         "commentary.json": json.dumps({"plan": {"duration_ms": 20000}}).encode()})
    store.put_clip("B", {"clip.json": clip(13.8)})
    store.put_clip("C", {"clip.json": clip(8.0)})
    # A replay that is not a whole number of 40 ms frames cannot be laid on
    # the grid: D stays off the programme, like a run with no clip.
    store.put_clip("D", {"clip.json": clip(8.033)})
    store.withdraw(Withdrawal(run_id="C", event_id="sprint-2m", user="c",
                              withdrawn_at="2026-09-14T12:00:00Z"))
    entries = {e.run_id: e for e in pool(store, datetime(2026, 9, 16, tzinfo=UTC))}
    assert set(entries) == {"A", "B"}
    # The render's stamp travels with the entry: it versions the media URLs.
    assert entries["A"] == Entry("A", "a", "2 m Sprint", "2026-09-03T10:00:00Z", 8000,
                                 "20260916T100500Z")
    assert entries["B"].replay_ms == 13800


def test_a_copy_never_airs(tmp_path):
    """Nor does the booth write for it: off the board as if withdrawn, it is off the channel too."""
    store = LocalStore(tmp_path)
    store.append(make_record(run_id="A", user="rumezhak", submitted_at="2026-11-03T09:00:00Z"), b"t")
    store.append(make_record(run_id="B", user="jrubiosainz", submitted_at="2026-11-03T09:19:00Z"), b"t")
    for run_id in ("A", "B"):
        store.put_clip(run_id, {"clip.json": json.dumps({"rendered_at": "2026-11-03T10:05:00Z",
                                                         "layouts": {"landscape": {"seconds": 8.0}}}).encode()})
    assert [e.run_id for e in pool(store, datetime(2026, 11, 4, tzinfo=UTC))] == ["A"]


def test_a_cycle_opens_on_the_three_newest_and_shuffles_the_rest_by_its_number():
    entries = [entry(f"R{i}", at=f"2026-09-{i + 1:02d}T10:00:00Z") for i in range(8)]
    first = cycle(entries, 0)
    assert [e.run_id for e in first[:HEAD]] == ["R7", "R6", "R5"]
    assert sorted(e.run_id for e in first[HEAD:]) == ["R0", "R1", "R2", "R3", "R4"]
    assert cycle(entries, 0) == first
    # Deterministic, so this either always holds or never does; if seeds 0 and
    # 1 happen to shuffle five items alike, compare cycle 2 instead.
    assert [e.run_id for e in cycle(entries, 1)[HEAD:]] != [e.run_id for e in first[HEAD:]]
    assert cycle(entries[:2], 4) == sorted(entries[:2], key=lambda e: e.submitted_at, reverse=True)


def test_no_run_plays_twice_over_a_cycle_boundary():
    """The spec's rule for the shuffle: whatever the pool's size, the run that
    closes a cycle is not the run that opens the next."""
    for size in (2, 3, 8):
        entries = [entry(f"R{i}", at=f"2026-09-{i + 1:02d}T10:00:00Z") for i in range(size)]
        for k in range(20):
            assert cycle(entries, k)[-1].run_id != cycle(entries, k + 1)[0].run_id


def test_slots_are_shutter_replay_and_a_booth_only_with_a_broadcast_waiting(tmp_path):
    book = BroadcastBook(tmp_path)
    made = book.put("A", {"run_id": "A", "turns": [], "lore_refs": []},
                    {"duration_ms": 20000, "captions": [], "notes": [], "gestures": []},
                    "2026-09-18T09:00:00Z")
    slots = slots_for([entry("A"), entry("B")], 1_000_000, book)
    assert [s["kind"] for s in slots] == ["shutter", "replay", "shutter", "booth", "shutter", "replay"]
    assert slots[0] == {"kind": "shutter", "at_ms": 1_000_000, "duration_ms": SHUTTER_MS,
                        "next": {"run_id": "A", "event": "2 m Sprint", "user": "alice"}}
    # The slots that load a clip's media say which render of it: the screen
    # builds the URL from that, and a re-rendered clip is a new URL.
    assert slots[1] == {"kind": "replay", "at_ms": 1_001_600, "duration_ms": 8000, "run_id": "A",
                        "clip": "20260916T100500Z"}
    assert slots[2]["next"] is None
    assert slots[3] == {"kind": "booth", "at_ms": 1_011_200, "duration_ms": 20000,
                        "run_id": "A", "broadcast": made.id, "clip": "20260916T100500Z"}
    for a, b in pairwise(slots):
        assert b["at_ms"] == a["at_ms"] + a["duration_ms"]
    assert all(s["duration_ms"] % 40 == 0 for s in slots)


def test_a_run_with_no_broadcast_gets_a_replay_and_no_booth(tmp_path):
    book = BroadcastBook(tmp_path)
    entries = [Entry("run-a", "nicolas", "Sprint", "2026-09-18", 8000, "20260918T000000Z")]
    laid = slots_for(entries, 0, book)
    assert [slot["kind"] for slot in laid] == ["shutter", "replay"]


def test_a_run_with_a_broadcast_gets_its_booth_at_the_plan_s_length(tmp_path):
    book = BroadcastBook(tmp_path)
    made = book.put("run-a", {"run_id": "run-a", "turns": [], "lore_refs": []},
                    {"duration_ms": 41400, "captions": [], "notes": [], "gestures": []},
                    "2026-09-18T09:00:00Z")
    entries = [Entry("run-a", "nicolas", "Sprint", "2026-09-18", 8000, "20260918T000000Z")]
    laid = slots_for(entries, 0, book)
    assert [slot["kind"] for slot in laid] == ["shutter", "replay", "shutter", "booth"]
    booth = laid[3]
    assert booth["duration_ms"] == 41400
    assert booth["broadcast"] == made.id
    assert booth["run_id"] == "run-a"


def test_one_broadcast_is_laid_once_even_when_the_run_comes_round_twice(tmp_path):
    book = BroadcastBook(tmp_path)
    book.put("run-a", {"run_id": "run-a", "turns": [], "lore_refs": []},
             {"duration_ms": 4000, "captions": [], "notes": [], "gestures": []},
             "2026-09-18T09:00:00Z")
    twice = Entry("run-a", "nicolas", "Sprint", "2026-09-18", 8000, "20260918T000000Z")
    laid = slots_for([twice, twice], 0, book)
    assert [slot["kind"] for slot in laid] == [
        "shutter", "replay", "shutter", "booth", "shutter", "replay"]


def test_a_playing_booth_is_never_handed_to_a_second_slot(tmp_path):
    """The bug this guards: a broadcast stays unaired until its slot ends, so a
    rebuild that re-reads the book would lay the playing booth again."""
    book = BroadcastBook(tmp_path)
    made = book.put("run-a", {"run_id": "run-a", "turns": [], "lore_refs": []},
                    {"duration_ms": 4000, "captions": [], "notes": [], "gestures": []},
                    "2026-09-18T09:00:00Z")
    entries = [Entry("run-a", "nicolas", "Sprint", "2026-09-18", 8000, "20260918T000000Z")]
    again = slots_for(entries, 0, book, claimed={made.id})
    assert [slot["kind"] for slot in again] == ["shutter", "replay"]


def test_invalidate_does_not_let_the_playing_booth_be_relaid_in_the_future(tmp_path):
    """The test above proves `slots_for` honours a claimed set; this proves
    `_extend` actually passes one through. Without `self._claimed()` in that
    call, `invalidate()` would re-offer to a future slot the booth a screen
    is playing right now — a broadcast stays unaired until its slot ends."""
    book = BroadcastBook(tmp_path)
    made = book.put("run-a", {"run_id": "run-a", "turns": [], "lore_refs": []},
                    {"duration_ms": 4000, "captions": [], "notes": [], "gestures": []},
                    "2026-09-18T09:00:00Z")
    at = [1_000_000]
    programme = Programme(lambda: [Entry("run-a", "nicolas", "Sprint", "2026-09-18", 8000, "20260918T000000Z")],
                          lambda: at[0], book)
    first = programme.slots()
    booth = next(s for s in first if s["kind"] == "booth")
    at[0] = booth["at_ms"] + booth["duration_ms"] // 2  # now sits inside the playing booth
    programme.invalidate()
    after = programme.slots()
    booths = [s for s in after if s["kind"] == "booth" and s.get("broadcast") == made.id]
    assert len(booths) == 1


def test_a_broadcast_is_laid_once_however_often_its_run_comes_round(tmp_path):
    """A small pool comes round several times inside the horizon, and the grid
    is laid one entry at a time: what a booth claims for one entry has to be
    claimed against the next, or one dialogue would be laid all afternoon."""
    book = BroadcastBook(tmp_path)
    made = book.put("run-a", {"run_id": "run-a", "turns": [], "lore_refs": []},
                    {"duration_ms": 4000, "captions": [], "notes": [], "gestures": []},
                    "2026-09-18T09:00:00Z")
    programme = Programme(lambda: [Entry("run-a", "nicolas", "Sprint", "2026-09-18", 8000, "20260918T000000Z")],
                          lambda: 1_000_000, book)
    booths = [slot for slot in programme.slots() if slot["kind"] == "booth"]
    assert [slot["broadcast"] for slot in booths] == [made.id]


class Clock:
    def __init__(self, ms):
        self.ms = ms

    def __call__(self):
        return self.ms


def test_the_programme_extends_to_the_horizon_and_serves_a_window_around_now(tmp_path):
    book = BroadcastBook(tmp_path)
    clock = Clock(10_000_000)
    entries = [entry("A"), entry("B")]
    programme = Programme(lambda: entries, clock, book)
    assert programme.origin_ms == 10_000_000
    slots = programme.slots()
    assert slots[0]["at_ms"] == 10_000_000
    assert slots[-1]["at_ms"] + slots[-1]["duration_ms"] >= 10_000_000 + 300_000
    # The window served reaches BEHIND_MS back, and a slot is served while any
    # of it is still inside that window — so the first one served can have
    # started up to its own length before the window opens. Neither run has a
    # broadcast waiting, so one cycle of these two is just their shutters and
    # replays, 19.2 s, and the longest slot in it is an 8 s replay.
    clock.ms += 400_000
    later = programme.slots()
    assert later[0]["at_ms"] >= clock.ms - BEHIND_MS - 8_000
    assert all(s["at_ms"] <= clock.ms + 300_000 for s in later)
    assert later[-1]["at_ms"] + later[-1]["duration_ms"] >= clock.ms + 300_000


def test_invalidate_keeps_the_slot_playing_now_and_rebuilds_the_future(tmp_path):
    book = BroadcastBook(tmp_path)
    clock = Clock(10_000_000)
    entries = [entry("A"), entry("B")]
    programme = Programme(lambda: entries, clock, book)
    before = programme.slots()
    clock.ms += 5_000  # inside the first-laid entry's replay (1 600 + 8 000)
    entries.append(entry("C", at="2026-09-20T10:00:00Z"))
    programme.invalidate()
    after = programme.slots()
    current = next(s for s in before if s["at_ms"] <= clock.ms < s["at_ms"] + s["duration_ms"])
    assert current in after
    following = [s for s in after if s["at_ms"] >= current["at_ms"] + current["duration_ms"]]
    assert following[0]["at_ms"] == current["at_ms"] + current["duration_ms"]
    # The rebuilt future opens on the newest run, C.
    assert following[0]["kind"] == "shutter" and following[0]["next"]["run_id"] == "C"


def test_a_landing_every_minute_still_walks_the_cycle_to_its_end(tmp_path):
    """Every broadcast that lands invalidates the grid, some eighty times an
    hour. A rebuild that opened a fresh cycle would put the newest runs back on
    the screen each time and the rest of the pool would wait for ever; the grid
    keeps its place, so a cycle is walked to its end and every run comes round.
    """
    book = BroadcastBook(tmp_path)
    clock = Clock(10_000_000)
    entries = [entry(f"R{i}", at=f"2026-09-{i + 1:02d}T10:00:00Z") for i in range(8)]
    programme = Programme(lambda: entries, clock, book)
    walk = []  # the runs the screen shows, one entry per turn on it
    for _ in range(250):  # twelve minutes of channel, read every three seconds
        # The reserve keeps every run stocked, and each dialogue it lands tells
        # the programme to rebuild its future.
        for run_id in sorted({one.run_id for one in entries} - book.runs_stocked()):
            stocked(book, run_id)
            programme.landed()
        now = clock.ms
        playing = next(s for s in programme.slots()
                       if s["at_ms"] <= now < s["at_ms"] + s["duration_ms"])
        showing = playing.get("run_id")
        if showing is not None and (not walk or walk[-1] != showing):
            walk.append(showing)
        clock.ms += 3_000
    shown = Counter(walk)
    assert set(shown) == {one.run_id for one in entries}
    # Seven passes over the pool and a little more: every run has had seven or
    # eight turns on the screen, and none of them has taken it from the others.
    assert max(shown.values()) <= 2 * min(shown.values())
    # And the place the grid keeps is not a log of everything that has played:
    # it holds the cycle playing now and the entries laid ahead of it — some
    # thirty of them for eight runs and a five-minute horizon — whether the
    # process has been up twelve minutes or a fortnight.
    assert len(programme._laid) < 60


def stocked(book, run_id):
    book.put(run_id, {"run_id": run_id, "turns": [], "lore_refs": []},
             {"duration_ms": 4000, "captions": [], "notes": [], "gestures": []},
             "2026-09-18T09:00:00Z")


def test_a_landing_lays_again_nothing_a_screen_was_promised(tmp_path):
    """A screen reads the grid every ten seconds and enters each slot from the
    grid it holds. A landing that laid the next few seconds again had it enter
    one slot and be told, a poll later, that another was playing: the picture
    cut into the middle of something else. Seen on the Space the day dialogues
    first landed there, a landing falling on a run's announcing shutter: the
    replay it announced was gone from the grid a second later."""
    book = BroadcastBook(tmp_path)
    clock = Clock(10_000_000)
    entries = [entry(f"R{i}", at=f"2026-09-{i + 1:02d}T10:00:00Z") for i in range(6)]
    programme = Programme(lambda: entries, clock, book)
    for _ in range(180):  # three minutes of channel, a landing every second
        before = programme.slots()
        promised = [s for s in before if s["at_ms"] <= clock.ms + PROMISED_MS]
        for run_id in sorted({one.run_id for one in entries} - book.runs_stocked())[:1]:
            stocked(book, run_id)
        programme.landed()
        after = programme.slots()
        assert [s for s in promised if s not in after] == []
        clock.ms += 1_000


def test_an_entry_a_screen_was_promised_keeps_every_one_of_its_slots(tmp_path):
    """The promise is an entry's, not a slot's: a run announced keeps its replay,
    and a run whose replay is playing keeps the booth laid after it, however far
    past the promised window that booth starts."""
    book = BroadcastBook(tmp_path)
    clock = Clock(10_000_000)
    entries = [entry("A", replay_ms=40_000), entry("B", at="2026-09-09T10:00:00Z")]
    stocked(book, "A")
    programme = Programme(lambda: entries, clock, book)
    whole = [s for s in programme.slots() if s["at_ms"] < 10_000_000 + 1600 + 40_000 + 1600 + 4000]
    assert [s["kind"] for s in whole] == ["shutter", "replay", "shutter", "booth"]
    clock.ms += 800  # inside the shutter that announces A; its booth starts 42 s from here
    stocked(book, "B")
    programme.landed()
    assert [s for s in whole if s not in programme.slots()] == []


def test_what_lands_is_laid_from_the_first_entry_nobody_was_promised(tmp_path):
    book = BroadcastBook(tmp_path)
    clock = Clock(10_000_000)
    entries = [entry("A"), entry("B", at="2026-09-09T10:00:00Z")]
    programme = Programme(lambda: entries, clock, book)
    programme.slots()
    entries.append(entry("C", at="2026-09-20T10:00:00Z"))
    programme.landed()
    shutters = [s for s in programme.slots() if s["kind"] == "shutter"]
    first_c = next(s for s in shutters if s["next"]["run_id"] == "C")
    # Every entry begun within the promise stands; C opens the first one after it.
    assert first_c["at_ms"] > clock.ms + PROMISED_MS
    assert first_c == next(s for s in shutters if s["at_ms"] > clock.ms + PROMISED_MS)


def test_an_idle_gap_is_not_built_cycle_by_cycle(tmp_path):
    """An hour nobody read through is an hour of slots pruned as they are
    built, the pool read once per cycle, all under the lock."""
    book = BroadcastBook(tmp_path)
    clock = Clock(10_000_000)
    entries = [entry("A"), entry("B")]
    reads = []

    def source():
        reads.append(clock.ms)
        return entries

    programme = Programme(source, clock, book)
    programme.slots()
    read_once = len(reads)
    clock.ms += 3_600_000
    served = programme.slots()
    # Neither run ever has a broadcast waiting, so one cycle of these two is
    # 19.2 s and an hour is ~188 of them; the six minutes of window this read
    # has to serve are about nineteen.
    assert len(reads) - read_once <= 24
    assert len(served) <= 84
    assert served[0]["at_ms"] >= clock.ms - 60_000
    assert served[-1]["at_ms"] + served[-1]["duration_ms"] >= clock.ms + 300_000


def test_an_empty_pool_is_off_air_until_something_lands(tmp_path):
    book = BroadcastBook(tmp_path)
    clock = Clock(10_000_000)
    entries = []
    programme = Programme(lambda: entries, clock, book)
    assert programme.slots() == []
    entries.append(entry("A"))
    assert programme.slots()[0]["at_ms"] == 10_000_000


def test_a_booth_whose_slot_has_passed_is_marked_aired(tmp_path):
    book = BroadcastBook(tmp_path)
    made = book.put("run-a", {"run_id": "run-a", "turns": [], "lore_refs": []},
                    {"duration_ms": 4000, "captions": [], "notes": [], "gestures": []},
                    "2026-09-18T09:00:00Z")
    at = [1_000_000]
    programme = Programme(lambda: [Entry("run-a", "nicolas", "Sprint", "2026-09-18", 8000, "20260918T000000Z")],
                          lambda: at[0], book)
    programme.slots()
    assert book.get(made.id).aired_at is None

    at[0] += 60_000
    programme.slots()
    assert book.get(made.id).aired_at is not None


def test_a_booth_is_marked_aired_even_though_its_slot_would_have_been_pruned(tmp_path):
    """KEEP_MS is 120 000. A jump past the booth's end by more than that would
    let `slots()` prune the slot before it is marked, if `_mark_aired` ran
    after the prune instead of before it."""
    book = BroadcastBook(tmp_path)
    made = book.put("run-a", {"run_id": "run-a", "turns": [], "lore_refs": []},
                    {"duration_ms": 4000, "captions": [], "notes": [], "gestures": []},
                    "2026-09-18T09:00:00Z")
    at = [1_000_000]
    programme = Programme(lambda: [Entry("run-a", "nicolas", "Sprint", "2026-09-18", 8000, "20260918T000000Z")],
                          lambda: at[0], book)
    programme.slots()
    assert book.get(made.id).aired_at is None

    at[0] += KEEP_MS + 60_000  # past the booth's end, and past KEEP_MS beyond that
    programme.slots()
    assert book.get(made.id).aired_at is not None


def test_a_mark_that_cannot_be_written_does_not_take_the_grid_down(tmp_path, monkeypatch):
    """The mark happens inside the read every screen is waiting on, so a full
    or read-only disk there would answer /api/live with a 500 for all of them.
    It costs the mark instead: the broadcast stays unaired and may be laid
    once more, which is a repeat, not an outage."""
    book = BroadcastBook(tmp_path)
    made = book.put("run-a", {"run_id": "run-a", "turns": [], "lore_refs": []},
                    {"duration_ms": 4000, "captions": [], "notes": [], "gestures": []},
                    "2026-09-18T09:00:00Z")
    at = [1_000_000]
    programme = Programme(lambda: [Entry("run-a", "nicolas", "Sprint", "2026-09-18", 8000, "20260918T000000Z")],
                          lambda: at[0], book)
    programme.slots()

    def full_disk(_broadcast):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(book, "_write", full_disk)
    at[0] += 60_000  # past the booth's end: this read is the one that marks it
    assert programme.slots()
    assert book.get(made.id).aired_at is None


# A cup of one match: its shutter at 10 030 000, its premiere, its clip until 10 041 600.
SHOW = Show(10_030_000, 10_030_000, 10_041_600, (
    {"kind": "shutter", "at_ms": 10_030_000, "duration_ms": 1600, "next": {"match_id": "m", "title": "Final"}},
    {"kind": "replay", "at_ms": 10_031_600, "duration_ms": 10000, "run_id": "m", "clip": "v", "media": "match"}),
    {"title": "Cup #1"})
TITLE = load_event("tug-of-war").title


def test_a_match_entry_is_announced_by_its_title_and_plays_its_match_clip_with_no_booth(tmp_path):
    match = Entry("tug-of-war-0001-008", "p0", TITLE, "2026-10-30T17:01:34Z", 10000, "v1", title="Final · x vs y")
    book = BroadcastBook(tmp_path)
    book.put(match.run_id, {"run_id": match.run_id, "turns": [], "lore_refs": []},
             {"duration_ms": 20000, "captions": [], "notes": [], "gestures": []}, "2026-10-30T18:00:00Z")
    shutter, replay = slots_for([match], 1_000_000, book)
    assert shutter["next"] == {"match_id": "tug-of-war-0001-008", "title": "Final · x vs y"}
    assert replay == {"kind": "replay", "at_ms": 1_001_600, "duration_ms": 10000, "run_id": "tug-of-war-0001-008",
                      "clip": "v1", "media": "match"}


def test_an_aired_cup_joins_the_pool_until_the_next_cup_starts(tmp_path):
    store, cup = LocalStore(tmp_path), played_cup(4, starts_at=START_ISO)
    store_cup(store, cup)
    assert pool(store, ends_at(cup) - timedelta(seconds=1)) == []
    entries = pool(store, ends_at(cup))
    assert len(entries) == 7 and entries[-1].title == f"{TITLE} · Cup #1 · Final · duck 0 vs duck 1"
    assert (entries[-1].submitted_at, entries[-1].replay_ms, entries[-1].clip) == (iso(REVEAL(6)), 10000, "20261030T152000Z")
    store_cup(store, played_cup(4, number=2, starts_at="2026-11-06T17:00:00Z"))
    assert len(pool(store, datetime(2026, 11, 6, 16, 59, tzinfo=UTC))) == 7
    assert pool(store, datetime(2026, 11, 6, 17, tzinfo=UTC)) == []


def test_shows_lay_a_cup_at_its_absolute_times(tmp_path):
    store, cup = LocalStore(tmp_path), played_cup(4, starts_at=START_ISO)
    store_cup(store, cup)
    start = int(START.timestamp() * 1000)
    [show] = shows(store, START - timedelta(hours=1))
    assert (show.premiere_ms, show.starts_ms, show.ends_ms, len(show.slots)) == (start, start, start + 7 * 11600, 14)
    assert show.slots[0]["next"] == {"match_id": cup.matches[0].match_id, "title": "Group A"}
    assert show.slots[1] == {"kind": "replay", "at_ms": start + 1600, "duration_ms": 10000,
                             "run_id": cup.matches[0].match_id, "clip": "20261030T152000Z", "media": "match"}
    assert show.standby == {"title": f"{TITLE} · Cup #1"}
    assert shows(store, ends_at(cup)) == []


def test_the_cycle_stands_by_for_a_show_then_plays_it_at_its_times(tmp_path):
    programme = Programme(lambda: [entry("A"), entry("B")], Clock(10_000_000), BroadcastBook(tmp_path), cups=lambda: [SHOW])
    slots = programme.slots()
    assert [(s["kind"], s["at_ms"]) for s in slots[:8]] == [
        ("shutter", 10_000_000), ("replay", 10_001_600), ("shutter", 10_009_600), ("replay", 10_011_200),
        ("shutter", 10_019_200), ("replay", 10_020_800), ("standby", 10_028_800), ("shutter", 10_030_000)]
    assert slots[6] == {"kind": "standby", "at_ms": 10_028_800, "duration_ms": 1200, "cup": SHOW.standby}
    assert slots[8] == SHOW.slots[1] and slots[9]["at_ms"] == 10_041_600
    for a, b in pairwise(slots):
        assert b["at_ms"] == a["at_ms"] + a["duration_ms"]


def test_a_match_whose_clip_is_rendered_again_is_laid_with_no_render(tmp_path):
    """Its clip deleted to be rendered again, its slot fails to load on the screens, which hold the shutter's panel
    over it as over a withdrawn run's: the channel never fails for it."""
    store, cup = LocalStore(tmp_path), played_cup(4, starts_at=START_ISO)
    store_cup(store, cup)
    shutil.rmtree(tmp_path / "clips" / cup.matches[1].match_id)
    [show] = shows(store, START)
    assert [slot["clip"] for slot in show.slots if slot["kind"] == "replay"] == \
        ["20261030T152000Z", None] + ["20261030T152000Z"] * 5


def test_a_cup_with_no_running_order_yet_is_a_show_with_no_start(tmp_path):
    store, cup = LocalStore(tmp_path), played_cup(4)
    store_cup(store, cup)
    store_cup(store, replace(drawn_cup(3, number=2), groups=(), skipped=True))
    premiere = int(START.timestamp() * 1000)
    assert shows(store, START + timedelta(hours=1)) == [Show(premiere, None, None, (), {"title": f"{TITLE} · Cup #1"})]


def test_a_cup_late_on_its_premiere_stands_by_until_its_order_lands_then_until_it_starts(tmp_path):
    """From its premiere the channel airs the cup and nothing else: with no order it only says that the cup is
    coming. The order is fixed at least ten minutes ahead, beyond the grid's reach, and the show airs at its start."""
    start = 10_660_000  # the order lands at 10 060 000
    late = Show(10_000_000, None, None, (), {"title": "Cup #1"})
    ordered = Show(10_000_000, start, start + 11_600, tuple({**slot, "at_ms": slot["at_ms"] + start - SHOW.starts_ms}
                                                             for slot in SHOW.slots), {"title": "Cup #1"})
    clock, cups = Clock(10_020_000), [late]
    programme = Programme(lambda: [entry("A"), entry("B")], clock, BroadcastBook(tmp_path), cups=lambda: cups)
    first = programme.slots()
    assert first[0]["at_ms"] == 10_020_000 and {(s["kind"], s.get("late")) for s in first} == {("standby", True)}
    laid = {}
    for now in range(10_020_000, start + 20_000, 10_000):
        clock.ms, cups[:] = now, [late if now < 10_060_000 else ordered]
        laid |= {slot["at_ms"]: slot for slot in programme.slots()}
    laid = [laid[at] for at in sorted(laid)]
    waiting = [slot for slot in laid if slot["at_ms"] < start]
    assert {slot["kind"] for slot in waiting} == {"standby"} and "late" not in waiting[-1]
    assert laid[len(waiting):len(waiting) + 2] == list(ordered.slots)
    for a, b in pairwise(laid):
        assert b["at_ms"] == a["at_ms"] + a["duration_ms"]


def test_a_restart_mid_show_joins_the_segment_airing_now(tmp_path):
    slots = Programme(lambda: [entry("A")], Clock(10_035_000), BroadcastBook(tmp_path), cups=lambda: [SHOW]).slots()
    assert slots[0] == SHOW.slots[1] and (slots[1]["kind"], slots[1]["at_ms"]) == ("shutter", 10_041_600)


def test_a_cups_matches_join_the_shuffled_rest_and_the_newest_runs_still_open_the_cycle(tmp_path):
    """A match enters the pool at its reveal, later than every run: as the newest it would open every
    cycle for a week with no booth, the final before its semi-finals."""
    store, cup = LocalStore(tmp_path), played_cup(4, starts_at=START_ISO)
    store_cup(store, cup)
    for i in range(5):
        store.append(make_record(run_id=f"S{i}", user=f"u{i}", score=10.0 + i,
                                 submitted_at=f"2026-10-2{i}T10:00:00Z"), b"t")
        store.put_clip(f"S{i}", {"clip.json": json.dumps({"layouts": {"landscape": {"seconds": 8.0}}}).encode()})
    entries = pool(store, ends_at(cup))
    matches = [e for e in entries if e.title is not None]
    assert len(matches) == 7 and min(e.submitted_at for e in matches) > max(e.submitted_at for e in entries if e.title is None)
    for k in range(5):
        order = [e.run_id for e in cycle(entries, k)]
        assert order[:HEAD] == ["S4", "S3", "S2"]
        assert sorted(order) == sorted(e.run_id for e in entries)


def written_show(cup):
    """A show.json: every desk segment of the cup's outline 12 s long, every match called, each turn and line its own."""
    return {"desk": {s["id"]: {"kind": s["kind"], "after": s["after"],
                               "dialogue": {"turns": [{"speaker": "peter", "text": f"Cup #{cup.number}, {s['id']}."}]},
                               "plan": {"duration_ms": 12000}, "screen": {"next": s["after"] + 1}}
                     for s in show_outline(cup)},
            "calls": {m.match_id: {"lines": [{"at_ms": 0, "speaker": "ray", "text": f"{m.match_id} is on."}],
                                   "plan": {"duration_ms": 30000}} for m in cup.matches}}


def with_its_show(cup):
    """The cup and its show, its running order fixed from its premiere around 30 s match clips."""
    show = written_show(cup)
    order = running_order(cup, {m.match_id: 30.0 for m in cup.matches}, parse_iso(cup.premiere_at), show=show)
    return replace(cup, order=order), show


(CUP, WRITTEN), (CUP2, WRITTEN2) = with_its_show(show_cup()), with_its_show(show_cup(number=2))
START_MS = int(START.timestamp() * 1000)


def on_air(match):
    """When one of CUP's matches airs and when it is revealed, in ms."""
    segment = next(s for s in CUP.order["segments"] if s.get("match_id") == match.match_id)
    return START_MS + segment["at_ms"], START_MS + segment["at_ms"] + segment["duration_ms"]


def show_api(tmp_path, *shown, unwritten=(), reveal_all=False):
    """The app over `shown` cups, each stored with its show.json, and `unwritten` ones stored with none."""
    app = create_app(ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie", reveal_all=reveal_all))
    for cup, show in shown:
        store_cup(app.state.store, cup)
        app.state.store.put_cup_files(cup.event_id, cup.number, {"show.json": json.dumps(show).encode()})
    for cup in unwritten:
        store_cup(app.state.store, cup)
    return TestClient(app)


def at(monkeypatch, ms):
    """The live's clock, which gates a desk segment, and the cups' clock, which gates a call (its match's), at `ms`."""
    monkeypatch.setattr("arena.web.routes_live.now_ms", lambda: ms)
    monkeypatch.setattr("arena.web.routes_cups.now", lambda: START + timedelta(milliseconds=ms - START_MS))


def test_a_cup_with_its_show_lays_desk_slots_and_called_matches(tmp_path):
    store = LocalStore(tmp_path)
    store_cup(store, CUP)
    [show] = shows(store, START - timedelta(hours=1))
    first = CUP.matches[0].match_id
    assert show.slots[:4] == (
        {"kind": "desk", "at_ms": START_MS, "duration_ms": 12000,
         "show": {"event": "tug-of-war", "number": 1, "segment": "opening"}},
        {"kind": "desk", "at_ms": START_MS + 12000, "duration_ms": 12000,
         "show": {"event": "tug-of-war", "number": 1, "segment": f"intro-{first}"}},
        {"kind": "shutter", "at_ms": START_MS + 24000, "duration_ms": SHUTTER_MS,
         "next": {"match_id": first, "title": "Group A"}},
        {"kind": "replay", "at_ms": START_MS + 25600, "duration_ms": 30000, "run_id": first,
         "clip": "20261030T152000Z", "media": "match", "call": True})
    replays = [slot for slot in show.slots if slot["kind"] == "replay"]
    assert len(replays) == len(CUP.matches) and all(slot["call"] for slot in replays)
    recap = next(i for i, slot in enumerate(show.slots) if slot.get("show", {}).get("segment") == "recap-1")
    assert show.slots[recap - 1]["kind"] == "shutter" and show.slots[recap - 1]["next"] is None
    for a, b in pairwise(show.slots):
        assert b["at_ms"] == a["at_ms"] + a["duration_ms"]
    assert show.ends_ms == int(ends_at(CUP).timestamp() * 1000)


def test_a_desk_segment_is_served_from_thirty_seconds_before_the_reveal_it_mentions(tmp_path, monkeypatch):
    api = show_api(tmp_path, (CUP, WRITTEN))
    opening = "/api/live/show/tug-of-war/1/opening"
    at(monkeypatch, START_MS - 30_040)
    early = api.get(opening)   # a 404 that turns 200 at a set time is never cached
    assert early.status_code == 404 and early.headers["cache-control"] == "no-store"
    at(monkeypatch, START_MS - 30_000)
    answer = api.get(opening)
    assert answer.status_code == 200 and answer.headers["cache-control"] == "no-store"
    assert answer.json() == {key: WRITTEN["desk"]["opening"][key] for key in ("dialogue", "plan", "screen")}
    m0, m1 = CUP.matches[:2]
    intro = f"/api/live/show/tug-of-war/1/intro-{m1.match_id}"  # it may react to m0's result
    at(monkeypatch, on_air(m0)[1] - 30_040)
    assert api.get(intro).status_code == 404
    at(monkeypatch, on_air(m0)[1] - 30_000)
    assert api.get(intro).json()["dialogue"] == WRITTEN["desk"][f"intro-{m1.match_id}"]["dialogue"]


def test_a_call_is_served_from_thirty_seconds_before_its_match_airs(tmp_path, monkeypatch):
    api = show_api(tmp_path, (CUP, WRITTEN))
    m3 = CUP.matches[3]
    call = f"/api/live/call/{m3.match_id}"
    at(monkeypatch, on_air(m3)[0] - 30_040)
    early = api.get(call)
    assert early.status_code == 404 and early.headers["cache-control"] == "no-store"
    at(monkeypatch, on_air(m3)[0] - 30_000)
    answer = api.get(call)
    assert answer.status_code == 200 and answer.headers["cache-control"] == "no-store"
    assert answer.json() == {"lines": WRITTEN["calls"][m3.match_id]["lines"], "plan": WRITTEN["calls"][m3.match_id]["plan"]}


def test_what_the_show_does_not_hold_is_a_404(tmp_path, monkeypatch):
    unordered = show_cup(number=2)
    unwritten = with_its_show(show_cup(number=3))[0]
    api = show_api(tmp_path, (CUP, WRITTEN), (unordered, written_show(unordered)), unwritten=[unwritten])
    at(monkeypatch, int(ends_at(unwritten).timestamp() * 1000) + 86_400_000)
    assert api.get("/api/live/show/tug-of-war/1/opening").status_code == 200
    for path in ("/api/live/show/tug-of-war/1/nope", "/api/live/call/nope", "/api/live/call/tug-of-war-0001-099",
                 "/api/live/show/tug-of-war/2/opening", f"/api/live/call/{unordered.matches[0].match_id}",
                 "/api/live/show/tug-of-war/3/opening", f"/api/live/call/{unwritten.matches[0].match_id}"):
        assert api.get(path).status_code == 404, path


def test_a_match_the_show_has_no_call_for_is_a_404(tmp_path, monkeypatch):
    first = CUP.matches[0]
    uncalled = {**WRITTEN, "calls": {k: v for k, v in WRITTEN["calls"].items() if k != first.match_id}}
    api = show_api(tmp_path, (CUP, uncalled))
    at(monkeypatch, on_air(first)[0])
    answer = api.get(f"/api/live/call/{first.match_id}")
    assert answer.status_code == 404 and answer.headers["cache-control"] == "no-store"


def test_a_desk_segment_is_told_by_the_call_s_rule(tmp_path, monkeypatch):
    """A cup's event only, and the whole show to the clip job's own app (`reveal_all`), as a match's call."""
    at(monkeypatch, START_MS - 3_600_000)
    revealed = show_api(tmp_path / "reveal-all", (CUP, WRITTEN), reveal_all=True)
    assert revealed.get("/api/live/show/tug-of-war/1/ceremony").json()["dialogue"] == WRITTEN["desk"]["ceremony"]["dialogue"]
    assert revealed.get(f"/api/live/call/{CUP.matches[-1].match_id}").status_code == 200
    api = show_api(tmp_path / "sprint", (CUP, WRITTEN))
    api.app.state.store.put_cup_files("sprint-2m", 1, {
        "draw.json": CUP.draw_json(), "matches.json": CUP.matches_json(),
        "order.json": json.dumps(CUP.order).encode(), "show.json": json.dumps(WRITTEN).encode()})
    at(monkeypatch, int(ends_at(CUP).timestamp() * 1000))
    assert api.get("/api/live/show/tug-of-war/1/opening").status_code == 200
    assert api.get("/api/live/show/sprint-2m/1/opening").status_code == 404  # a race has no cup


def test_two_cups_of_one_event_serve_their_own_show(tmp_path, monkeypatch):
    api = show_api(tmp_path, (CUP, WRITTEN), (CUP2, WRITTEN2))
    at(monkeypatch, int(ends_at(CUP2).timestamp() * 1000) + 86_400_000)
    for number, show in ((1, WRITTEN), (2, WRITTEN2)):
        answer = api.get(f"/api/live/show/tug-of-war/{number}/ceremony").json()
        assert answer["dialogue"]["turns"][0] == show["desk"]["ceremony"]["dialogue"]["turns"][0]
    assert WRITTEN["desk"]["ceremony"]["dialogue"] != WRITTEN2["desk"]["ceremony"]["dialogue"]


def ready(app, run_id, user="alice", seconds=8.0):
    # Each in a time of its own: two players' runs that raced alike would be one policy, copied.
    score = 10.0 + len(app.state.store.runs("sprint-2m"))
    app.state.store.append(make_record(run_id=run_id, user=user, score=score), encode(np.zeros((5, 21), "f4")))
    app.state.store.put_clip(run_id, {"clip.json": json.dumps({"layouts": {"landscape": {"seconds": seconds}}}).encode()})


def test_the_route_serves_the_clock_the_build_and_the_window(tmp_path):
    config = ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")
    app = create_app(config)
    api = TestClient(app)
    empty = api.get("/api/live")
    assert empty.status_code == 200
    assert empty.headers["cache-control"] == "no-store"
    body = empty.json()
    assert body["version"] == 1 and body["slots"] == []
    assert isinstance(body["now_ms"], int) and body["build"]
    ready(app, "A")
    app.state.broadcasts.put("A", {"run_id": "A", "turns": [], "lore_refs": []},
                             {"duration_ms": 20000, "captions": [], "notes": [], "gestures": []},
                             "2026-09-18T09:00:00Z")
    app.state.programme.invalidate()
    body = api.get("/api/live").json()
    assert [s["kind"] for s in body["slots"][:4]] == ["shutter", "replay", "shutter", "booth"]
    assert body["slots"][0]["at_ms"] <= body["now_ms"]


def test_a_broadcast_is_served_by_its_id(tmp_path):
    config = ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")
    app = create_app(config)
    api = TestClient(app)
    made = app.state.broadcasts.put(
        "run-a", {"run_id": "run-a", "turns": [{"speaker": "peter", "text": "Well.",
                                                "fact_refs": []}], "lore_refs": []},
        {"duration_ms": 4000, "captions": [], "notes": [], "gestures": []},
        "2026-09-18T09:00:00Z")
    answer = api.get(f"/api/live/broadcast/{made.id}")
    assert answer.status_code == 200
    assert answer.json()["plan"]["duration_ms"] == 4000
    assert answer.json()["dialogue"]["turns"][0]["text"] == "Well."


def test_an_unknown_broadcast_is_a_404(tmp_path):
    config = ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")
    api = TestClient(create_app(config))
    assert api.get("/api/live/broadcast/nope").status_code == 404


def test_an_id_the_filesystem_cannot_even_look_up_is_a_404_not_a_500(tmp_path):
    """The book's own lookup can raise for an id no filesystem will accept as
    a filename; the route must still answer the page's contract — gone is
    404, never 500."""
    config = ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")
    api = TestClient(create_app(config))
    assert api.get(f"/api/live/broadcast/{'a' * 300}").status_code == 404


def test_an_app_holds_a_broadcast_book(tmp_path):
    config = ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")
    app = create_app(config)
    assert isinstance(app.state.broadcasts, BroadcastBook)


def test_the_broadcast_book_lives_where_arena_broadcasts_says(tmp_path, monkeypatch):
    home = tmp_path / "elsewhere"
    monkeypatch.setenv("ARENA_BROADCASTS", str(home))
    config = ArenaConfig.from_env(store_dir=tmp_path / "store", dev_user="coralie")
    app = create_app(config)
    assert app.state.broadcasts.directory == home


def test_an_app_holds_a_reserve(tmp_path):
    config = ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")
    app = create_app(config)
    assert app.state.commentary is not None


def test_the_reserve_is_closed_when_the_app_stops(tmp_path, monkeypatch):
    """`arena serve` on a developer machine is stopped with a Ctrl-C, and the
    reserve's Chrome and its profile directory would outlive it."""
    import arena.commentary as booth
    from arena import recorder

    bundle = tmp_path / "dist"
    bundle.mkdir()
    (bundle / "index.html").write_text("<!doctype html><title>arena</title>")
    (bundle / "plan.html").write_text("<!doctype html><title>plan</title>")
    monkeypatch.setenv("ARENA_COMMENTARY", "1")  # conftest turns the booth off
    monkeypatch.setattr(booth, "hub_token", lambda config: "a token")
    monkeypatch.setattr(recorder, "find_chrome", lambda: "/chrome")
    app = create_app(ArenaConfig.from_env(store_dir=tmp_path / "store", frontend_dir=bundle))
    assert app.state.commentary.available

    class Reserve:
        def __init__(self):
            self.stopped = False

        def start(self):
            pass

        def stop(self):
            self.stopped = True

    # Stood in after the wiring, so no thread and no browser is started here;
    # the hooks read app.state when they run.
    app.state.commentary = Reserve()
    with TestClient(app):
        pass
    assert app.state.commentary.stopped


def test_the_cup_worker_gets_the_show_writer_only_with_the_booth_on(tmp_path, monkeypatch):
    import arena.commentary as booth
    from arena import recorder
    from arena.commentary import show

    bundle = tmp_path / "dist"
    bundle.mkdir()
    (bundle / "index.html").write_text("<!doctype html><title>arena</title>")
    (bundle / "plan.html").write_text("<!doctype html><title>plan</title>")
    monkeypatch.setenv("ARENA_COMMENTARY", "1")  # conftest turns the booth off
    monkeypatch.setattr(booth, "hub_token", lambda config: "a token")
    monkeypatch.setattr(recorder, "find_chrome", lambda: "/chrome")
    asked = []
    monkeypatch.setattr(show, "compose_show", lambda store, cup, **kwargs: asked.append((store, cup, kwargs)) or {})
    app = create_app(ArenaConfig.from_env(store_dir=tmp_path / "store", frontend_dir=bundle))
    done = {"desk": {}, "calls": {}}
    app.state.cups.show("the cup", done)
    [(store, cup, kwargs)] = asked
    assert (store, cup, kwargs["tab"]) == (app.state.store, "the cup", app.state.commentary.tab)
    assert kwargs["done"] is done
    assert kwargs["log"] is app.state.cups.log
    assert kwargs["model"] == app.state.config.commentary_model
    assert kwargs["provider"] is not None and kwargs["lore"] is not None
    assert type(kwargs["rng"]) is random.Random   # its own draws, not the module's shared state

    monkeypatch.setenv("ARENA_COMMENTARY", "0")
    assert create_app(ArenaConfig.from_env(store_dir=tmp_path / "off", frontend_dir=bundle)).state.cups.show is None


def test_the_reserve_is_not_available_when_writing_is_off(tmp_path, monkeypatch):
    monkeypatch.setenv("ARENA_COMMENTARY", "0")
    config = ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")
    app = create_app(config)
    assert app.state.booth_off == "ARENA_COMMENTARY=0"
    assert not app.state.commentary.available


def test_the_build_is_the_hash_of_the_index_it_serves(tmp_path):
    """A page that has run for days reloads when this changes, so it must be
    the bundle's own identity and not merely something truthy."""
    bundle = tmp_path / "dist"
    bundle.mkdir()
    (bundle / "index.html").write_text("<!doctype html><title>arena</title>")
    api = TestClient(create_app(ArenaConfig.from_env(store_dir=tmp_path, frontend_dir=bundle)))
    served = api.get("/").content
    assert api.get("/api/live").json()["build"] == hashlib.sha256(served).hexdigest()[:12]


def test_a_landed_clip_and_a_withdrawal_rebuild_the_future(spaced):  # noqa: F811
    api, app = spaced
    ready(app, "A")
    app.state.clips.landed("A")
    assert {s.get("run_id") for s in api.get("/api/live").json()["slots"]} >= {"A"}
    ready(app, "B", user="bob")
    app.state.clips.landed("B")
    assert {s.get("run_id") for s in api.get("/api/live").json()["slots"]} >= {"A", "B"}
    # Three more, so the horizon is reached with the cycle being walked only
    # part laid: a withdrawal has to reach the entries still to come as well as
    # the slots already on the grid.
    for run_id in ("C", "D", "E"):
        ready(app, run_id)
        app.state.clips.landed(run_id)
    served = {s.get("run_id") for s in api.get("/api/live").json()["slots"]}
    assert served >= {"A", "B", "C", "D", "E"}
    sign_in(api, app, "bob")
    assert api.post("/api/runs/B/withdraw").status_code == 200
    slots = api.get("/api/live").json()["slots"]
    future = [s for s in slots if s["at_ms"] > slots[0]["at_ms"] + slots[0]["duration_ms"]]
    assert "B" not in {s.get("run_id") for s in future}
