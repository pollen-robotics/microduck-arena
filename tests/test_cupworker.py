import hashlib
import json
import random
import threading
import time
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import numpy as np
import pytest

import arena
from arena import cupworker
from arena.commentary.generator import Rejected
from arena.commentary.show import show_outline
from arena.constants import NUM_JOINTS, OBS_SIZE, RUNNER_VERSION
from arena.cup import Cup, cup_times, draw_groups, ends_at, iso, match_label, parse_iso
from arena.cupworker import (
    BOOTH_PATIENCE,
    LOAD_PATIENCE,
    SHOW_RETRY,
    CupWorker,
    Standing,
    all_cups,
    compute_matches,
    entrants_at,
    load_cup,
    load_entrant,
    running_order,
)
from arena.hub_fetch import FetchError, PolicyGone
from arena.manifest import BoutRules, load_event
from arena.match import BoutResult, MatchOutcome, bout_seed
from arena.policy import load_policy
from arena.store import LocalStore, Withdrawal
from arena.trace import decode, decode_string, encode
from tests.test_cup import entrant
from tests.test_store import make_record
from tests.test_tug import straight

WALKER = Path(arena.__file__).parent / "assets/policies/BEST_alpha_walking.onnx"
# Cup #1 pinned to 2026-10-30: the owner sets the shipped date at release, and no test moves with it.
TUG = replace(load_event("tug-of-war"), cup=replace(load_event("tug-of-war").cup, first=date(2026, 10, 30)))
# A bout as a match leaves it: two frames and a three-frame settle, then the string of each.
TRACE, SETTLE = np.zeros((2, 2, 21), np.float32), np.zeros((2, 3, 21), np.float32)
BOUT = (TRACE, SETTLE, straight(TRACE), straight(SETTLE))


def fake_play(manifest, a, b, seeds, ratings, model=None):
    """No physics: the higher rating wins 2-0 on two-frame traces."""
    side = "a" if ratings[0] >= ratings[1] else "b"
    bouts = tuple(BoutResult(k, seeds[k], ("west", "east")[k], side, "pit", 4.0) for k in range(2))
    return MatchOutcome(bouts, (BOUT, BOUT), (2, 0) if side == "a" else (0, 2), side, "bouts")


def drawn_cup(n, number=1, secret="ab" * 16):
    close, premiere = cup_times(TUG.cup, number)
    ducks = tuple(entrant(i, rating=n - i) for i in range(n))
    return Cup("tug-of-war", number, iso(close), iso(premiere), secret, ducks,
               tuple(tuple(g) for g in draw_groups(ducks, secret)))


def played_cup(n, number=1, starts_at=None, seconds=10.0):
    """With `starts_at`, the cup's order is fixed from then, every match clip `seconds` long."""
    with patch("arena.cupworker.play_match", fake_play), patch("arena.cupworker.compile_tug", lambda *_: None):
        cup = compute_matches(TUG, drawn_cup(n, number), lambda e: e.user)[0]
    if starts_at is None:
        return cup
    return replace(cup, order=running_order(cup, {m.match_id: seconds for m in cup.matches}, parse_iso(starts_at)))


def test_a_cup_is_read_back_from_its_files(tmp_path):
    store = LocalStore(tmp_path)
    assert load_cup(store, "tug-of-war", 1) is None and all_cups(store) == []
    cup = Cup("tug-of-war", 1, "2026-10-30T15:00:00Z", "2026-10-30T17:00:00Z", "ab" * 16,
              tuple(entrant(i) for i in range(4)), ((0, 1, 2, 3),))
    store.put_cup_files("tug-of-war", 1, {"draw.json": cup.draw_json()})
    assert load_cup(store, "tug-of-war", 1) == cup and all_cups(store) == [cup]


def test_entrants_are_each_players_latest_entry_at_close():
    run = lambda user, at, score, **o: make_record(event_id="tug-of-war", user=user, submitted_at=at, score=score, **o)
    old, new = run("ann", "2026-10-20T09:00:00Z", 3.0), run("ann", "2026-10-29T09:00:00Z", 4.0)
    gone, kept = run("bob", "2026-10-29T10:00:00Z", 6.0), run("bob", "2026-10-28T10:00:00Z", 2.0)
    late = run("cat", "2026-10-30T15:00:01Z", 9.0)
    stale = run("cat", "2026-10-20T09:00:00Z", 9.0, runner_version=RUNNER_VERSION - 1)
    edge = run("dan", "2026-10-30T15:00:00Z", 5.0)
    got = entrants_at([old, new, gone, kept, late, stale, edge], frozenset({gone.run_id}), datetime(2026, 10, 30, 15, tzinfo=UTC))
    assert [(e.user, e.run_id, e.rating) for e in got] == [("dan", edge.run_id, 5.0), ("ann", new.run_id, 4.0), ("bob", kept.run_id, 2.0)]
    assert (got[0].source, got[0].model_sha256, got[0].livery) == (edge.source, edge.model_sha256, edge.livery)


def test_a_copy_is_never_entered_and_its_player_plays_their_own_latest_entry():
    run = lambda user, at, score: make_record(event_id="tug-of-war", user=user, submitted_at=at, score=score)
    own = run("dadudu", "2026-10-28T09:00:00Z", 160.0)
    leader, copy = run("jrubiosainz", "2026-10-29T09:00:00Z", 166.5), run("dadudu", "2026-10-29T10:00:00Z", 166.5)
    got = entrants_at([own, leader, copy], frozenset(), datetime(2026, 10, 30, 15, tzinfo=UTC))
    assert [(e.user, e.run_id) for e in got] == [("jrubiosainz", leader.run_id), ("dadudu", own.run_id)]


def test_two_entrants_with_one_policy_name_air_under_their_handles():
    run = lambda user, name, score: make_record(event_id="tug-of-war", user=user, policy_name=name, score=score,
                                                submitted_at="2026-10-29T09:00:00Z")
    got = entrants_at([run("ann", "microduck-tug-of-war", 3.0), run("bob", "microduck-tug-of-war", 2.0), run("cat", "Tank", 1.0)],
                      frozenset(), datetime(2026, 10, 30, 15, tzinfo=UTC))
    assert {e.user: e.name for e in got} == {
        "ann": "microduck-tug-of-war (@ann)", "bob": "microduck-tug-of-war (@bob)", "cat": "Tank"}
    assert {e.user: e.policy_name for e in got} == {"ann": "microduck-tug-of-war", "bob": "microduck-tug-of-war", "cat": "Tank"}


def test_an_entrant_is_loaded_from_the_hub_at_its_revision(monkeypatch):
    asked = []
    monkeypatch.setattr(cupworker, "fetch_policy", lambda ref, revision: asked.append((ref, revision)) or SimpleNamespace(path=WALKER))
    assert load_entrant(None, entrant(0)).sha256 == hashlib.sha256(WALKER.read_bytes()).hexdigest()
    assert asked == [("p0/tug:policy.onnx", "c" * 40)]


def test_an_entrant_kept_by_a_local_store_is_loaded_from_it(tmp_path):
    store, blob = LocalStore(tmp_path), WALKER.read_bytes()
    sha = hashlib.sha256(blob).hexdigest()
    store.append(make_record(run_id="R1", model_sha256=sha, model_stored=True), b"t", blob)
    assert load_entrant(store, replace(entrant(0), model_sha256=sha, source={"kind": "local", "path": "/gone.onnx"})).sha256 == sha


def test_groups_play_round_by_round_then_each_knockout_round(monkeypatch):
    calls = []
    monkeypatch.setattr(cupworker, "play_match", lambda m, a, b, seeds, ratings, model=None:
                        calls.append((a, b, seeds, model)) or fake_play(m, a, b, seeds, ratings))
    monkeypatch.setattr(cupworker, "compile_tug", lambda manifest: "model")
    cup = replace(drawn_cup(6), groups=((0, 2, 4), (1, 3, 5)))
    played, files = compute_matches(TUG, cup, lambda e: e.user)
    assert [(m.a, m.b, m.round, m.group) for m in played.matches] == [
        (2, 4, "group", "A"), (3, 5, "group", "B"), (0, 4, "group", "A"), (1, 5, "group", "B"), (0, 2, "group", "A"),
        (1, 3, "group", "B"), (0, 3, "semi-final", None), (1, 2, "semi-final", None), (0, 1, "final", None)]
    assert [m.match_id for m in played.matches] == [f"tug-of-war-0001-{i:03d}" for i in range(9)]
    assert played.matches[-1].winner == 0
    assert calls[0] == ("p2", "p4", [bout_seed("ab" * 16, "tug-of-war-0001-000", k) for k in range(5)], "model")
    assert sorted(files) == sorted(f"bouts/tug-of-war-0001-{i:03d}-{k}.npz" for i in range(9) for k in range(2))
    assert decode(files["bouts/tug-of-war-0001-000-0.npz"]).shape == (2, 2, 21)


def test_a_matchs_bout_file_holds_its_string():
    with patch("arena.cupworker.play_match", fake_play), patch("arena.cupworker.compile_tug", lambda *_: None):
        files = compute_matches(TUG, drawn_cup(4), lambda e: e.user)[1]
    assert decode_string(files["bouts/tug-of-war-0001-000-0.npz"])[1].shape[1:] == (17, 3)


def test_a_cup_plays_on_the_real_physics_and_replays_identically():
    manifest = replace(load_event("tug-of-war"), bout=BoutRules(time_limit_s=1.0, bouts_to_win=2, max_bouts=3))
    walker = load_policy(WALKER)
    first, files = compute_matches(manifest, drawn_cup(4), lambda e: walker)
    again, files_again = compute_matches(manifest, drawn_cup(4), lambda e: walker)
    assert len(first.matches) == 7 and first.matches[-1].round == "final" and first == again
    assert files.keys() == files_again.keys()
    assert all(np.array_equal(decode(files[k]), decode(files_again[k])) for k in files)


# Cup 1 closes 2026-10-23T14:00Z and premieres at 16:00Z; cup 2 closes 2026-10-30T15:00Z and premieres at 17:00Z.
EARLY = replace(TUG, cup=replace(TUG.cup, first=date(2026, 10, 23)))
T1 = datetime(2026, 10, 23, 14, 1, tzinfo=UTC)


class Clock:
    def __init__(self, at): self.at = at
    def __call__(self): return self.at


class FakeClips:
    def __init__(self): self.owed = []
    def enqueue(self, run_id, priority=0): self.owed.append(run_id)


class Crashing:
    """A store whose `at`-th write raises before it lands, as a Space restarting there would."""
    def __init__(self, store, at): self.store, self.at, self.writes = store, at, 0
    def __getattr__(self, name): return getattr(self.store, name)
    def _write(self):
        self.writes += 1
        if self.writes == self.at:
            raise RuntimeError("the Space restarted")
    def put_cup_files(self, *args): self._write(); self.store.put_cup_files(*args)
    def mark_clip_pending(self, *args): self._write(); self.store.mark_clip_pending(*args)


@pytest.fixture
def no_physics(monkeypatch):
    monkeypatch.setattr(cupworker, "play_match", fake_play)
    monkeypatch.setattr(cupworker, "compile_tug", lambda *_: None)
    monkeypatch.setattr(cupworker.secrets, "token_hex", lambda n: "ab" * n)


def enter(store, n, at="2026-10-22T09:00:00Z"):
    for i in range(n):
        store.append(make_record(run_id=f"R{i}", event_id="tug-of-war", user=f"p{i}", score=float(n - i), submitted_at=at), b"t")


def clip_json(seconds=10.0):
    return json.dumps({"rendered_at": "2026-10-23T14:30:00Z", "layouts": {"landscape": {"seconds": seconds}}}).encode()


def store_cup(store, cup, seconds=10.0):
    """The cup as the worker leaves it, every match with a ready clip."""
    files = {"draw.json": cup.draw_json(), **{f"bouts/{m.match_id}-{b.k}.npz": encode(*BOUT)
                                               for m in cup.matches for b in m.bouts}}
    if cup.matches:
        files["matches.json"] = cup.matches_json()
    if cup.order:
        files["order.json"] = json.dumps(cup.order).encode()
    store.put_cup_files(cup.event_id, cup.number, files)
    clip = {"rendered_at": "2026-10-30T15:20:00Z", "poster": "poster.png",
            "layouts": {"landscape": {"file": "landscape.mp4", "width": 1920, "height": 1080, "seconds": seconds}}}
    for m in cup.matches:
        store.put_clip(m.match_id, {"clip.json": json.dumps(clip).encode(), "landscape.mp4": b"mp4", "poster.png": b"png"})


def render(store, number=1, seconds=10.0):
    """What the clip jobs leave behind for every clip this cup owes."""
    for m in load_cup(store, "tug-of-war", number).matches:
        if store.clip_state(m.match_id)[0] == "pending":
            store.put_clip(m.match_id, {"clip.json": clip_json(seconds)})


def worker(store, clock, clips=None, load=lambda e: e.user, show=None, log=lambda _: None):
    return CupWorker(store, clips or FakeClips(), events=[EARLY], load=load, now=clock, log=log, show=show)


def gone(user):
    """A load for which the Hub answers 404 for `user`'s policy: private or deleted."""
    def load(entrant):
        if entrant.user == user:
            raise PolicyGone(f"could not read {user}/tug: 404")
        return entrant.user
    return load


def down(user):
    """A load for which `user`'s policy keeps failing, as on a Hub away for longer than a moment."""
    def load(entrant):
        if entrant.user == user:
            raise FetchError(f"could not read {user}/tug: 503")
        return entrant.user
    return load


def flaky(user):
    """A load for which `user`'s policy fails once, as on a Hub away for a moment."""
    failed = []

    def load(entrant):
        if entrant.user == user and not failed:
            failed.append(entrant.user)
            raise FetchError(f"could not read {user}/tug: 503")
        return entrant.user
    return load


def written(root):
    """Every cup file and every clip's pending marker, by path."""
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and (p.relative_to(root).parts[0] == "cups" or p.name == "pending.json")}


def test_a_cup_goes_from_close_to_its_running_order(tmp_path, no_physics):
    store, clips, clock = LocalStore(tmp_path), FakeClips(), Clock(T1)
    enter(store, 6)
    cups = worker(store, clock, clips)
    cups.tick()
    cup = load_cup(store, "tug-of-war", 1)
    assert cup.secret == "ab" * 16 and len(cup.matches) == 9 and cup.order is None
    assert clips.owed == [m.match_id for m in cup.matches]
    assert all(store.clip_state(m.match_id)[0] == "pending" for m in cup.matches)
    assert json.loads((tmp_path / "clips" / cup.matches[0].match_id / "pending.json").read_text()) == {
        "run_id": "tug-of-war-0001-000", "user": "arena", "event_id": "tug-of-war", "queued_at": "2026-10-23T14:01:00Z"}
    render(store)
    clock.at = datetime(2026, 10, 23, 15, tzinfo=UTC)
    cups.tick()
    assert load_cup(store, "tug-of-war", 1).order["starts_at"] == "2026-10-23T16:00:00Z"


def ready_cup(tmp_path):
    """A cup drawn and played at T1, every match clip rendered since: all its order waits on now is its show."""
    store = LocalStore(tmp_path)
    enter(store, 6)
    worker(store, Clock(T1)).tick()
    render(store)
    return store


def written_show(cup):
    """A whole show as the running order reads it: every desk segment of the cup's outline, each plan 12.04 s long,
    and every match called."""
    return {"desk": {s["id"]: {"kind": s["kind"], "after": s["after"], "plan": {"duration_ms": 12040}}
                     for s in show_outline(cup)}, "calls": {m.match_id: {"lines": []} for m in cup.matches}}


def test_with_a_show_the_order_puts_the_desk_around_every_match():
    from tests.show_cups import played_cup as show_cup  # show_cups reads this module's TUG

    cup = show_cup()
    order = running_order(cup, {m.match_id: 30.0 for m in cup.matches}, parse_iso(cup.premiere_at),
                          show=written_show(cup))
    segments = order["segments"]
    assert order["starts_at"] == cup.premiere_at
    recaps = (1, 3, 5)  # after each group round
    assert [s["kind"] for s in segments] == ["desk"] + [
        kind for i in range(len(cup.matches))
        for kind in ["desk", "shutter", "match"] + (["shutter", "desk"] if i in recaps else [])
    ] + ["shutter", "desk", "desk"]
    assert segments[0] == {"kind": "desk", "at_ms": 0, "duration_ms": 12040, "segment": "opening", "after": -1}
    desks = [s for s in segments if s["kind"] == "desk"]
    assert [(s["segment"], s["after"]) for s in desks] == [(s["id"], s["after"]) for s in show_outline(cup)]
    assert all(s["duration_ms"] == 12040 for s in desks)
    played = {m.match_id: m for m in cup.matches}
    for segment, following in pairwise(segments):
        if segment["kind"] == "shutter":
            match = played.get(following.get("match_id"))
            assert segment["next"] == (None if match is None else
                                       {"match_id": match.match_id, "title": match_label(cup, match)})
    assert [(s["match_id"], s["duration_ms"], s["call"]) for s in segments if s["kind"] == "match"] == [
        (m.match_id, 30000, True) for m in cup.matches]
    assert all(after["at_ms"] == before["at_ms"] + before["duration_ms"] for before, after in pairwise(segments))
    assert all(s["at_ms"] % 40 == 0 and s["duration_ms"] % 40 == 0 for s in segments)


def test_the_worker_writes_the_show_once_then_fixes_the_order(tmp_path, no_physics):
    store, asked, said = ready_cup(tmp_path / "on-time"), [], []

    def write(cup, done):
        asked.append(cup)
        return written_show(cup)

    cups = worker(store, Clock(datetime(2026, 10, 23, 15, tzinfo=UTC)), show=write, log=said.append)
    cups.tick()
    cups.tick()
    cup = load_cup(store, "tug-of-war", 1)
    assert asked == [replace(cup, order=None)]
    assert json.loads(store.cup_file("tug-of-war", 1, "show.json")) == written_show(cup)
    assert [s["segment"] for s in cup.order["segments"] if s["kind"] == "desk"] == list(written_show(cup)["desk"])
    assert cup.order == running_order(cup, {m.match_id: 10.0 for m in cup.matches},
                                      datetime(2026, 10, 23, 16, tzinfo=UTC), show=written_show(cup))
    assert said == ["cups: writing the show of Tug of War · Cup #1", "cups: the show of Tug of War · Cup #1 is written",
                    "cups: tug-of-war #1 airs from 2026-10-23T16:00:00Z"]

    # A show takes minutes to write: one done past the premiere is still aired ORDER_LEAD after it is fixed.
    late, clock = ready_cup(tmp_path / "late"), Clock(datetime(2026, 10, 23, 15, tzinfo=UTC))

    def slow(cup, done):
        clock.at = datetime(2026, 10, 23, 16, 5, 7, tzinfo=UTC)
        return written_show(cup)

    worker(late, clock, show=slow).tick()
    assert load_cup(late, "tug-of-war", 1).order["starts_at"] == "2026-10-23T16:15:07Z"


def test_an_unwritten_show_holds_the_order_and_resumes_on_the_next_tick(tmp_path, no_physics):
    store, given, said = ready_cup(tmp_path), [], []

    def write(cup, done):
        given.append((done, dict(done["desk"])))
        if len(given) == 1:
            done["desk"]["opening"] = {"kind": "opening"}
            raise httpx.ConnectError("router down")
        return written_show(cup)

    cups = worker(store, Clock(datetime(2026, 10, 23, 15, tzinfo=UTC)), show=write, log=said.append)
    cups.tick()
    assert load_cup(store, "tug-of-war", 1).order is None and store.cup_file("tug-of-war", 1, "show.json") is None
    assert said == ["cups: writing the show of Tug of War · Cup #1",
                    "cups: the show of Tug of War · Cup #1 waits (ConnectError: router down)"]
    cups.tick()
    assert given[1][0] is given[0][0] and (given[0][1], given[1][1]) == ({}, {"opening": {"kind": "opening"}})
    assert load_cup(store, "tug-of-war", 1).order is not None


def test_a_show_unwritten_half_an_hour_past_the_premiere_airs_the_matches_alone(tmp_path, no_physics):
    """The live stands by from the premiere until the order: a router down for hours must not hold it, races and
    Got a Talent included, for hours."""
    store, said = ready_cup(tmp_path), []
    clock = Clock(datetime(2026, 10, 23, 16, tzinfo=UTC) + BOOTH_PATIENCE - timedelta(seconds=1))

    def down(cup, done):
        raise httpx.ConnectError("router down")

    cups = worker(store, clock, show=down, log=said.append)
    cups.tick()
    assert BOOTH_PATIENCE == timedelta(minutes=30) and load_cup(store, "tug-of-war", 1).order is None
    clock.at += timedelta(seconds=1)
    cups.tick()
    cup = load_cup(store, "tug-of-war", 1)
    assert cup.order == running_order(cup, {m.match_id: 10.0 for m in cup.matches},
                                      datetime(2026, 10, 23, 16, 40, tzinfo=UTC))
    assert store.cup_file("tug-of-war", 1, "show.json") is None
    assert said[-1] == "cups: tug-of-war #1 airs from 2026-10-23T16:40:00Z without the booth"


def test_a_restarted_worker_reads_the_show_it_wrote(tmp_path, no_physics):
    store, clock = ready_cup(tmp_path), Clock(datetime(2026, 10, 23, 15, tzinfo=UTC))
    worker(Crashing(store, 2), clock, show=lambda cup, done: written_show(cup)).tick()  # the show lands, not the order
    cup = load_cup(store, "tug-of-war", 1)
    assert cup.order is None and json.loads(store.cup_file("tug-of-war", 1, "show.json")) == written_show(cup)
    asked, said = [], []

    def down(cup, done):
        asked.append(cup)
        raise RuntimeError("router down")

    worker(store, clock, show=down, log=said.append).tick()
    assert asked == [] and said == ["cups: tug-of-war #1 airs from 2026-10-23T16:00:00Z"]
    assert load_cup(store, "tug-of-war", 1).order == running_order(
        cup, {m.match_id: 10.0 for m in cup.matches}, datetime(2026, 10, 23, 16, tzinfo=UTC), show=written_show(cup))


def test_a_show_refused_every_time_is_asked_again_ten_minutes_later_not_every_tick(tmp_path, no_physics):
    """The answer the model refused TRIES times would most likely be refused on the next tick too."""
    store, refused_at, given, said = ready_cup(tmp_path), datetime(2026, 10, 23, 15, tzinfo=UTC), [], []
    clock = Clock(refused_at)

    def write(cup, done):
        given.append((clock.at, dict(done["desk"])))
        if len(given) == 1:
            done["desk"]["opening"] = {"kind": "opening"}
            raise Rejected("model answer is not JSON")
        return written_show(cup)

    cups = worker(store, clock, show=write, log=said.append)
    cups.tick()
    for later in (timedelta(seconds=30), timedelta(seconds=60), SHOW_RETRY - timedelta(seconds=1)):
        clock.at = refused_at + later
        cups.tick()
    assert [at for at, _ in given] == [refused_at] and load_cup(store, "tug-of-war", 1).order is None
    assert said == ["cups: writing the show of Tug of War · Cup #1",
                    "cups: the show of Tug of War · Cup #1 waits (Rejected: model answer is not JSON)"]
    clock.at = refused_at + SHOW_RETRY
    cups.tick()
    assert given[1] == (refused_at + SHOW_RETRY, {"opening": {"kind": "opening"}})
    assert load_cup(store, "tug-of-war", 1).order is not None


def test_a_refusal_waits_from_when_it_came_not_from_when_the_tick_began(tmp_path, no_physics):
    """Writing the desk can take twenty minutes: a refusal at its end still waits SHOW_RETRY."""
    store, began, given = ready_cup(tmp_path), datetime(2026, 10, 23, 15, tzinfo=UTC), []
    clock = Clock(began)

    def write(cup, done):
        given.append(clock.at)
        if len(given) == 1:
            clock.at = began + timedelta(minutes=20)   # the router took its time, then refused
            raise Rejected("model answer is not JSON")
        return written_show(cup)

    cups = worker(store, clock, show=write)
    cups.tick()
    clock.at = began + timedelta(minutes=20, seconds=30)
    cups.tick()
    assert given == [began]
    clock.at = began + timedelta(minutes=20) + SHOW_RETRY
    cups.tick()
    assert given[1] == began + timedelta(minutes=20) + SHOW_RETRY


def test_a_show_the_plan_page_cannot_time_is_not_bought_again_on_every_tick(tmp_path, no_physics):
    """An answer is bought before the plan page times it: a page that throws over it would have it bought again on
    every tick, for ever, and the cup would never air. Only a router that is down is asked again on the next tick."""
    b = booth(tmp_path)

    def broken(dialogue):
        raise RuntimeError("Error: a plan page that throws")

    b.tab.prepare = broken
    b.cups.tick()
    failed_at, bought = b.clock.at, len(b.router.asked)
    assert bought == 1
    for later in (timedelta(seconds=30), timedelta(seconds=60), SHOW_RETRY - timedelta(seconds=1)):
        b.clock.at = failed_at + later
        b.cups.tick()
    assert len(b.router.asked) == bought
    b.clock.at = failed_at + SHOW_RETRY
    b.cups.tick()
    assert len(b.router.asked) == bought + 1


class Stale:
    """A store whose snapshot misses show.json on its first read, as a Hub slow to show its last commit."""
    def __init__(self, store): self.store, self.reads = store, 0
    def __getattr__(self, name): return getattr(self.store, name)
    def cup_file(self, event_id, number, name):
        self.reads += name == "show.json"
        return None if name == "show.json" and self.reads == 1 else self.store.cup_file(event_id, number, name)


def test_a_show_found_stored_after_all_drops_what_was_written_of_it(tmp_path, no_physics):
    """The commit of show.json landed but its call raised (a timeout), or the snapshot was stale: the next tick
    finds it stored."""
    store, clock, asked = ready_cup(tmp_path), Clock(datetime(2026, 10, 23, 15, tzinfo=UTC)), []
    store.put_cup_files("tug-of-war", 1, {"show.json": json.dumps(written_show(load_cup(store, "tug-of-war", 1))).encode()})

    def write(cup, done):
        asked.append(cup)
        done["desk"]["opening"] = {"kind": "opening"}
        return written_show(cup)

    cups = worker(Stale(store), clock, show=write)
    cups.tick()  # writes it again, and the store refuses a second show.json
    assert len(asked) == 1 and load_cup(store, "tug-of-war", 1).order is None
    cups.tick()
    assert len(asked) == 1 and load_cup(store, "tug-of-war", 1).order is not None
    assert cups._shows == {}


def booth(tmp_path):
    """Six entries past the close and a worker with the real show writer: a fake router, each answer 10 s of the
    worker's clock, and a fake plan page that keeps what it timed."""
    from arena.commentary.show import compose_show
    from tests.test_commentary_show import LORE, FakeTab, Router  # it reads this module

    store, clock, router, tab, said = LocalStore(tmp_path), Clock(T1), Router(), FakeTab(), []
    enter(store, 6)

    def provider(messages, max_tokens):
        clock.at += timedelta(seconds=10)
        return router(messages, max_tokens)

    def show(cup, done):
        return compose_show(store, cup, lore=LORE, provider=provider, model="fake/model", tab=tab,
                            rng=random.Random(7), done=done)

    return SimpleNamespace(store=store, clock=clock, router=router, tab=tab, said=said,
                           cups=worker(store, clock, show=show, log=said.append))


def timed(tab):
    """What the plan page timed, in order: the desk segments' ids and the called matches' ids."""
    return ([asked["run_id"] for kind, asked in tab.asked if kind == "prepare"],
            [asked["id"] for kind, asked in tab.asked if kind == "prepare_call"])


def land(store, matches):
    """The clip jobs render these matches' clips, with where each clip tapes each bout."""
    from tests.test_commentary_show import taped_clip

    for match in matches:
        store.put_clip(match.match_id, {"clip.json": taped_clip([bout.k for bout in match.bouts])})


def test_the_desk_is_written_as_soon_as_the_matches_are_computed(tmp_path, no_physics):
    """It needs the results, never the clips: written while they render, it is not left for after the last one."""
    b = booth(tmp_path)
    b.cups.tick()
    cup = load_cup(b.store, "tug-of-war", 1)
    assert all(b.store.clip_state(m.match_id)[0] == "pending" for m in cup.matches)
    assert timed(b.tab) == ([f"tug-of-war-0001-{s['id']}" for s in show_outline(cup)], [])
    assert len(b.router.asked) == 15 and b.router.calls() == []  # 15 desk segments, no bout
    assert b.store.cup_file("tug-of-war", 1, "show.json") is None and cup.order is None


def test_a_match_is_called_on_the_first_tick_its_clip_is_ready(tmp_path, no_physics):
    b = booth(tmp_path)
    b.cups.tick()
    cup, (desk, _) = load_cup(b.store, "tug-of-war", 1), timed(b.tab)
    land(b.store, [cup.matches[3], cup.matches[5]])
    asked = len(b.router.asked)
    b.cups.tick()
    assert timed(b.tab) == (desk, [cup.matches[3].match_id, cup.matches[5].match_id])
    assert len(b.router.asked) - asked == len(b.router.calls()) == 4  # their two bouts each, no desk segment again
    b.cups.tick()
    assert len(b.router.asked) == asked + 4  # nothing new to write
    assert b.store.cup_file("tug-of-war", 1, "show.json") is None and load_cup(b.store, "tug-of-war", 1).order is None


def test_the_last_match_called_stores_the_show_and_fixes_the_order_from_a_fresh_clock(tmp_path, no_physics):
    b = booth(tmp_path)
    b.cups.tick()
    cup = load_cup(b.store, "tug-of-war", 1)
    land(b.store, cup.matches[:-1])
    b.cups.tick()
    assert b.store.cup_file("tug-of-war", 1, "show.json") is None and load_cup(b.store, "tug-of-war", 1).order is None
    land(b.store, cup.matches[-1:])
    b.clock.at = datetime(2026, 10, 23, 16, tzinfo=UTC)  # the premiere; the final's two bouts take 20 s to call
    b.cups.tick()
    assert len(b.router.asked) == 15 + 18 and timed(b.tab)[1] == [m.match_id for m in cup.matches]
    show = json.loads(b.store.cup_file("tug-of-war", 1, "show.json"))
    assert list(show["desk"]) == [s["id"] for s in show_outline(cup)]
    assert list(show["calls"]) == [m.match_id for m in cup.matches]
    order = load_cup(b.store, "tug-of-war", 1).order
    assert order["starts_at"] == "2026-10-23T16:10:20Z"  # ORDER_LEAD after the show was written, not before
    assert order == running_order(cup, {m.match_id: 30.0 for m in cup.matches},
                                  datetime(2026, 10, 23, 16, 10, 20, tzinfo=UTC), show=show)
    assert b.said[2:] == ["cups: writing the show of Tug of War · Cup #1", "cups: the show of Tug of War · Cup #1 is written",
                          "cups: tug-of-war #1 airs from 2026-10-23T16:10:20Z"]  # one line, not one per tick


def test_the_draw_waits_a_minute_past_the_close_for_an_entry_stamped_before_it(tmp_path, no_physics):
    """An entry is stamped when it is evaluated and lands in the dataset a few seconds later."""
    store = LocalStore(tmp_path)
    enter(store, 5)
    cups = worker(store, Clock(datetime(2026, 10, 23, 14, 0, 30, tzinfo=UTC)))
    cups.tick()
    assert load_cup(store, "tug-of-war", 1) is None
    store.append(make_record(run_id="R5", event_id="tug-of-war", user="p5", submitted_at="2026-10-23T13:59:59Z"), b"t")
    store.append(make_record(run_id="R6", event_id="tug-of-war", user="p6", submitted_at="2026-10-23T14:00:01Z"), b"t")
    cups.now = Clock(T1)
    cups.tick()
    assert sorted(e.user for e in load_cup(store, "tug-of-war", 1).entrants) == ["p0", "p1", "p2", "p3", "p4", "p5"]


def test_a_pending_clip_is_owed_once(tmp_path, no_physics):
    """The clip jobs follow a pending clip themselves: queued again every tick, it could race a launch into a second job."""
    store, clips, clock = LocalStore(tmp_path), FakeClips(), Clock(T1)
    enter(store, 6)
    cups = worker(store, clock, clips)
    cups.tick()
    clock.at = T1 + timedelta(minutes=30)
    cups.tick()
    assert clips.owed == [m.match_id for m in load_cup(store, "tug-of-war", 1).matches]


def test_a_late_order_starts_ten_minutes_after_it_is_fixed(tmp_path, no_physics):
    store, clock = LocalStore(tmp_path), Clock(T1)
    enter(store, 6)
    cups = worker(store, clock)
    cups.tick()
    render(store)
    clock.at = datetime(2026, 10, 23, 16, 30, 25, tzinfo=UTC)
    cups.tick()
    assert load_cup(store, "tug-of-war", 1).order["starts_at"] == "2026-10-23T16:40:25Z"


def test_a_crash_after_any_step_ends_in_the_same_cup(tmp_path, no_physics):
    reference = LocalStore(tmp_path / "reference")
    enter(reference, 6)
    cups = worker(reference, Clock(T1))
    cups.tick()
    render(reference)
    cups.tick()
    expected = written(reference.root)
    assert "cups/tug-of-war/0001/order.json" in expected
    for k in range(1, 13):  # the draw, the matches, nine pending markers, the order
        store = LocalStore(tmp_path / f"crash-{k}")
        enter(store, 6)
        flaky = Crashing(store, k)
        crashing = worker(flaky, Clock(T1))
        crashing.tick()
        cup = load_cup(store, "tug-of-war", 1)
        if cup is not None and cup.matches:
            render(store)
        crashing.tick()
        assert flaky.writes >= k, k
        fresh = worker(store, Clock(T1))
        fresh.tick()
        render(store)
        fresh.tick()
        assert written(store.root) == expected, k


def test_a_failed_match_clip_is_relaunched_every_ten_minutes_and_holds_the_order(tmp_path, no_physics):
    store, clips, clock = LocalStore(tmp_path), FakeClips(), Clock(T1)
    enter(store, 6)
    cups = worker(store, clock, clips)
    cups.tick()
    first = load_cup(store, "tug-of-war", 1).matches[0].match_id
    store.fail_clip(first, "2026-10-23T14:05:00Z", "ffmpeg exited 1")
    render(store)
    clips.owed.clear()
    for minutes, owed in ((5, [first]), (10, [first]), (15, [first, first])):
        clock.at = T1 + timedelta(minutes=minutes)
        cups.tick()
        assert clips.owed == owed, minutes
        assert load_cup(store, "tug-of-war", 1).order is None
    store.put_clip(first, {"clip.json": clip_json()})
    cups.tick()
    assert load_cup(store, "tug-of-war", 1).order is not None


def test_a_withdrawal_after_close_changes_nothing(tmp_path, no_physics):
    store = LocalStore(tmp_path)
    enter(store, 6)
    store.withdraw(Withdrawal("R5", "tug-of-war", "p5", "2026-10-23T14:00:01Z"))
    store.withdraw(Withdrawal("R4", "tug-of-war", "p4", "2026-10-23T13:59:59Z"))
    worker(store, Clock(T1)).tick()
    assert [e.user for e in load_cup(store, "tug-of-war", 1).entrants] == ["p0", "p1", "p2", "p3", "p5"]


def test_an_entrant_whose_policy_will_not_load_is_left_out_after_ten_minutes(tmp_path, no_physics):
    store, clock, said = LocalStore(tmp_path), Clock(T1), []  # the draw's first moment, a minute past the close
    enter(store, 6)
    cups = CupWorker(store, FakeClips(), events=[EARLY], load=down("p2"), now=clock, log=said.append)
    cups.tick()
    assert load_cup(store, "tug-of-war", 1) is None
    assert any("waits for p2 (FetchError: could not read p2/tug: 503)" in line for line in said)
    clock.at = T1 + LOAD_PATIENCE
    cups.tick()
    assert [e.user for e in load_cup(store, "tug-of-war", 1).entrants] == ["p0", "p1", "p3", "p4", "p5"]
    assert any("without p2" in line for line in said)


def test_an_entrant_whose_policy_is_gone_from_the_hub_is_left_out_at_once(tmp_path, no_physics):
    store, said = LocalStore(tmp_path), []
    enter(store, 6)
    CupWorker(store, FakeClips(), events=[EARLY], load=gone("p2"), now=Clock(T1), log=said.append).tick()
    assert [e.user for e in load_cup(store, "tug-of-war", 1).entrants] == ["p0", "p1", "p3", "p4", "p5"]
    assert any("without p2 (PolicyGone: could not read p2/tug: 404)" in line for line in said)


def test_a_drawn_duck_whose_policy_is_gone_from_the_hub_stands_still_at_once(tmp_path, no_physics):
    store = LocalStore(tmp_path)
    enter(store, 6)
    worker(Crashing(store, 2), Clock(T1)).tick()  # the draw lands, the matches do not
    worker(store, Clock(T1), load=gone("p2")).tick()
    assert [e.user for e in load_cup(store, "tug-of-war", 1).entrants] == ["p0", "p1", "p2", "p3", "p4", "p5"]
    assert len(load_cup(store, "tug-of-war", 1).matches) == 9


def test_a_drawn_duck_whose_policy_will_not_load_stands_still_after_ten_minutes(tmp_path, no_physics, monkeypatch):
    """The draw landed, the Space restarted before the matches, and p2's policy has not loaded since: the draw is
    frozen, so p2 keeps its place and its matches are played by a duck holding its standing pose, rather than the cup
    held forever."""
    store = LocalStore(tmp_path)
    enter(store, 6)
    worker(Crashing(store, 2), Clock(T1)).tick()
    assert load_cup(store, "tug-of-war", 1).matches == ()
    played = []
    monkeypatch.setattr(cupworker, "play_match", lambda m, a, b, seeds, ratings, model=None:
                        played.append((a, b)) or fake_play(m, a, b, seeds, ratings))
    clock, said = Clock(T1), []
    restarted = CupWorker(store, FakeClips(), events=[EARLY], load=down("p2"), now=clock, log=said.append)
    restarted.tick()
    assert load_cup(store, "tug-of-war", 1).matches == () and played == []
    clock.at = T1 + LOAD_PATIENCE - timedelta(seconds=1)
    restarted.tick()
    assert load_cup(store, "tug-of-war", 1).matches == () and played == []
    clock.at = T1 + LOAD_PATIENCE
    restarted.tick()
    assert any("p2 (FetchError: could not read p2/tug: 503)" in line and "standing still" in line for line in said)
    cup = load_cup(store, "tug-of-war", 1)
    assert [e.user for e in cup.entrants] == ["p0", "p1", "p2", "p3", "p4", "p5"] and len(cup.matches) == 9
    duck = lambda i: "standing" if cup.entrants[i].user == "p2" else cup.entrants[i].user
    assert [tuple("standing" if isinstance(p, Standing) else p for p in pair) for pair in played] == [
        (duck(m.a), duck(m.b)) for m in cup.matches]
    assert any("standing" in (duck(m.a), duck(m.b)) for m in cup.matches)
    assert np.array_equal(Standing().act(np.zeros(OBS_SIZE, np.float32)), np.zeros(NUM_JOINTS, np.float32))


def test_a_policy_that_fails_once_hours_after_the_close_still_plays(tmp_path, no_physics, monkeypatch):
    """A process whose first look at a cup comes hours after its close (a deploy across it, a crash while it played)
    still gives every policy LOAD_PATIENCE, at the draw and at the matches."""
    late = datetime(2026, 10, 23, 17, tzinfo=UTC)
    drawn = LocalStore(tmp_path / "draw")
    enter(drawn, 6)
    cups = worker(drawn, Clock(late), load=flaky("p2"))
    cups.tick()
    assert load_cup(drawn, "tug-of-war", 1) is None
    cups.now.at = late + timedelta(seconds=30)
    cups.tick()
    assert [e.user for e in load_cup(drawn, "tug-of-war", 1).entrants] == ["p0", "p1", "p2", "p3", "p4", "p5"]

    resumed = LocalStore(tmp_path / "play")
    enter(resumed, 6)
    worker(Crashing(resumed, 2), Clock(T1)).tick()  # the draw lands, the matches do not
    played = []
    monkeypatch.setattr(cupworker, "play_match", lambda m, a, b, seeds, ratings, model=None:
                        played.append((a, b)) or fake_play(m, a, b, seeds, ratings))
    cups = worker(resumed, Clock(late), load=flaky("p2"))
    cups.tick()
    assert load_cup(resumed, "tug-of-war", 1).matches == () and played == []
    cups.now.at = late + timedelta(seconds=30)
    cups.tick()
    assert len(load_cup(resumed, "tug-of-war", 1).matches) == 9
    assert "p2" in {duck for pair in played for duck in pair} and not any(isinstance(d, Standing) for p in played for d in p)


def test_cups_whose_closes_passed_while_the_space_was_down_are_drawn_as_at_their_close_and_aired_in_order(
        tmp_path, no_physics):
    store, clock = LocalStore(tmp_path), Clock(datetime(2026, 10, 30, 15, 1, tzinfo=UTC))
    enter(store, 6)
    store.append(make_record(run_id="R6", event_id="tug-of-war", user="p0", score=9.0,
                             submitted_at="2026-10-25T09:00:00Z"), b"t")
    store.append(make_record(run_id="R7", event_id="tug-of-war", user="p6", score=0.5,
                             submitted_at="2026-10-26T09:00:00Z"), b"t")
    cups = worker(store, clock)
    cups.tick()
    first, second = load_cup(store, "tug-of-war", 1), load_cup(store, "tug-of-war", 2)
    assert [e.run_id for e in first.entrants] == ["R0", "R1", "R2", "R3", "R4", "R5"]
    assert [e.run_id for e in second.entrants] == ["R6", "R1", "R2", "R3", "R4", "R5", "R7"]
    assert len(first.matches) == 9 and len(second.matches) == 12
    render(store, 1)
    render(store, 2)
    cups.tick()
    first = load_cup(store, "tug-of-war", 1)
    assert first.order["starts_at"] == "2026-10-30T15:11:00Z" and load_cup(store, "tug-of-war", 2).order is None
    clock.at = ends_at(first) - timedelta(seconds=1)
    cups.tick()
    assert load_cup(store, "tug-of-war", 2).order is None
    clock.at = ends_at(first)
    cups.tick()
    assert load_cup(store, "tug-of-war", 2).order["starts_at"] == "2026-10-30T17:00:00Z"


def test_too_few_entrants_skip_the_week(tmp_path, no_physics):
    store, clips = LocalStore(tmp_path), FakeClips()
    enter(store, 3)
    cups = worker(store, Clock(T1), clips)
    cups.tick()
    cup = load_cup(store, "tug-of-war", 1)
    assert cup.skipped is True and cup.groups == () and cup.matches == ()
    assert clips.owed == []
    before = sorted(tmp_path.rglob("*"))
    cups.tick()
    assert sorted(tmp_path.rglob("*")) == before


def test_a_cup_gets_no_order_while_the_previous_one_has_not_aired(tmp_path, no_physics):
    store, clock = LocalStore(tmp_path), Clock(T1)
    enter(store, 6)
    cups = worker(store, clock)
    cups.tick()
    clock.at = datetime(2026, 10, 30, 15, 1, tzinfo=UTC)
    render(store, 1)
    cups.tick()
    first = load_cup(store, "tug-of-war", 1)
    assert first.order["starts_at"] == "2026-10-30T15:11:00Z"
    render(store, 2)
    clock.at = ends_at(first) - timedelta(seconds=1)
    cups.tick()
    assert load_cup(store, "tug-of-war", 2).order is None
    clock.at = ends_at(first)
    cups.tick()
    assert load_cup(store, "tug-of-war", 2).order["starts_at"] == "2026-10-30T17:00:00Z"


def test_the_worker_ticks_at_once_in_its_own_thread_until_stopped(tmp_path, no_physics):
    store = LocalStore(tmp_path)
    enter(store, 3)
    cups = worker(store, Clock(T1))
    cups.start()
    deadline = time.monotonic() + 10
    while load_cup(store, "tug-of-war", 1) is None and time.monotonic() < deadline:
        time.sleep(0.01)
    threads = [t for t in threading.enumerate() if t.name == "arena-cups"]
    cups.stop()
    assert load_cup(store, "tug-of-war", 1).skipped and len(threads) == 1 and threads[0].daemon
    threads[0].join(5)
    assert not threads[0].is_alive()
