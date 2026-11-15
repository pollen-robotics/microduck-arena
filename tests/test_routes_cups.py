from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from arena.cup import PREFETCH
from arena.manifest import load_event
from arena.web.app import create_app
from arena.web.config import ArenaConfig
from tests.test_cup_view import AIRS, REVEAL, START, START_ISO
from tests.test_cupworker import TUG, played_cup, store_cup
from tests.test_store import make_record


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("arena.web.routes_cups.load_event", lambda event_id: TUG if event_id == "tug-of-war" else load_event(event_id))
    app = create_app(ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie"))
    return TestClient(app), app


def at(monkeypatch, moment):
    monkeypatch.setattr("arena.web.routes_cups.now", lambda: moment)


def test_the_cups_list_names_the_open_cup_and_every_closed_one(client, monkeypatch):
    api, app = client
    for i in range(4):
        app.state.store.append(make_record(run_id=f"R{i}", event_id="tug-of-war", user=f"p{i}", score=float(4 - i),
                                           submitted_at="2026-10-29T09:00:00Z"), b"t")
    at(monkeypatch, datetime(2026, 10, 30, 15, 30, tzinfo=UTC))
    body = api.get("/api/events/tug-of-war/cups").json()
    assert (body["next"]["number"], body["next"]["premiere_at"]) == (2, "2026-11-06T17:00:00Z")
    assert [e["user"] for e in body["next"]["entrants"]] == ["p0", "p1", "p2", "p3"]
    assert body["next"]["close_at"] == "2026-11-06T15:00:00Z"
    assert body["cups"] == [{"number": 1, "premiere_at": "2026-10-30T17:00:00Z", "starts_at": None, "state": "drawn", "champion": None}]
    assert api.get("/api/events/sprint-2m/cups").status_code == 404


def test_a_cup_answers_as_of_now(client, monkeypatch):
    api, app = client
    cup = played_cup(4, starts_at=START_ISO)
    store_cup(app.state.store, cup)
    at(monkeypatch, START - timedelta(seconds=1))
    body = api.get("/api/events/tug-of-war/cups/1").json()
    assert (body["state"], body["event"]["id"], body["open"], body["min_entrants"]) == ("ready", "tug-of-war", 2, 4)
    assert "matches" not in body
    at(monkeypatch, REVEAL(6))
    assert api.get("/api/events/tug-of-war/cups/1").json()["secret"] == cup.secret
    assert api.get("/api/events/tug-of-war/cups/3").status_code == 404


def test_a_match_and_everything_of_it_is_a_404_until_its_reveal(client, monkeypatch):
    api, app = client
    cup = played_cup(4, starts_at=START_ISO)
    store_cup(app.state.store, cup)
    mid = cup.matches[0].match_id
    paths = [f"/api/matches/{mid}{tail}" for tail in ("", "/bouts/0/trace", "/bouts/0/settle", "/clip/landscape.mp4", "/bouts/0/string")]

    def codes(moment):
        at(monkeypatch, moment)
        return [api.get(p).status_code for p in paths]
    # The clip's media come 30 s before it airs, so the live can buffer them; the rest once it has aired.
    assert codes(AIRS(0) - PREFETCH - timedelta(milliseconds=1)) == [404] * 5
    assert codes(AIRS(0) - PREFETCH) == [404, 404, 404, 200, 404]
    assert codes(AIRS(0)) == [404, 404, 404, 200, 404]
    assert codes(REVEAL(0) - timedelta(milliseconds=1)) == [404, 404, 404, 200, 404]
    assert codes(REVEAL(0)) == [200] * 5
    # The match page reads its clip's render off the match, the live off its slot: no route says where a clip stands.
    assert api.get(f"/api/matches/{mid}/clip").status_code == 404
    body = api.get(paths[0]).json()
    assert (body["a"]["user"], body["b"]["user"], body["winner"], body["wins"], body["round"], body["group"]) == ("p0", "p3", "a", [2, 0], "group", "A")
    assert (body["title"], body["clip"]) == ("Group A · duck 0 (@p0) vs duck 3 (@p3)", "20261030T152000Z")
    trace = api.get(paths[1])
    assert (trace.headers["x-duck-count"], trace.headers["x-frame-count"]) == ("2", "2")
    string = api.get(paths[4])
    assert (string.headers["x-frame-count"], string.headers["x-settle-frame-count"], len(string.content)) == ("2", "3", 5 * 51 * 4)
    assert api.get(f"/api/matches/{mid}/bouts/2/trace").status_code == 404
    assert [r.headers["cache-control"] for r in (api.get("/api/events/tug-of-war/cups"), api.get("/api/events/tug-of-war/cups/1"), api.get(paths[0]), trace)] == ["no-store"] * 4
    assert api.get(paths[3]).headers["cache-control"] == "public, max-age=31536000, immutable"
    assert api.get("/api/matches/nope").status_code == 404 and api.get("/api/matches/tug-of-war-0009-000").status_code == 404


def test_the_clip_jobs_own_app_reads_every_match(tmp_path, monkeypatch):
    app = create_app(ArenaConfig.from_env(store_dir=tmp_path, reveal_all=True))
    cup = replace(played_cup(4), order=None)   # clips are rendered before there is an order
    store_cup(app.state.store, cup)
    api, mid = TestClient(app), cup.matches[6].match_id
    assert [api.get(f"/api/matches/{mid}{tail}").status_code for tail in ("", "/bouts/0/trace", "/bouts/0/settle")] == [200] * 3
