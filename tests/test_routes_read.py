import numpy as np
import pytest
from fastapi.testclient import TestClient

from arena.evaluate import SeedResult
from arena.lights import served
from arena.manifest import load_event
from arena.timeline import EDGE_MARGIN_M, MIN_SPACING_M
from arena.trace import encode
from arena.web.app import create_app
from arena.web.config import ArenaConfig
from tests.test_cupworker import played_cup, store_cup
from tests.test_store import ALONE, WALKER, make_record


@pytest.fixture
def client(tmp_path):
    config = ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")
    app = create_app(config)
    return TestClient(app), app


def record_run(app, **overrides):
    record = make_record(**overrides)
    trace = np.zeros((5, 21), dtype=np.float32)
    app.state.store.append(record, encode(trace))
    return record


def test_a_tug_serves_its_course_and_its_bouts(client):
    api, _ = client
    tug = next(e for e in api.get("/api/events").json()["events"] if e["id"] == "tug-of-war")
    assert (tug["course"], tug["category"], tug["metric"]) == ("tug", "versus", "mean_ground_cm")
    assert [tug[k] for k in ("ring_m", "string_m", "pit_m", "pit_depth_m")] == [3.0, 1.0, 0.3, 0.3]
    assert tug["bout"] == {"time_limit_s": 45.0, "bouts_to_win": 2, "max_bouts": 5}
    assert tug["ropes"][0] == {"name": "rope_west_0", "from": [-1.5, -1.5, 0.06], "to": [-1.5, 1.5, 0.06], "radius": 0.006}
    assert len(tug["ropes"]) == 12 and tug["posts"][3]["name"] == "post_se"
    assert not {"length_m", "width_m", "walls", "pit"} & tug.keys()
    assert "string_offset" not in tug   # the page draws the string as recorded
    assert "sweep_lo" not in tug and "size_m" not in tug


def test_a_rated_run_serves_its_bouts_and_a_board_strongest_first_each_row_with_its_seed(client):
    api, app = client
    record_run(app, event_id="tug-of-war", user="bob", score=-15.2, trace_seed=2, per_seed=(SeedResult(2, "lost", 45.0, -15.2),))
    mine = record_run(app, event_id="tug-of-war", user="alice", score=12.5, trace_seed=1, per_seed=(SeedResult(1, "won", 45.0, 12.5),))
    body = api.get(f"/api/runs/{mine.run_id}").json()
    assert body["per_seed"] == [{"seed": 1, "status": "won", "time_s": 45.0, "score_cm": 12.5}]
    assert [(r["user"], r["trace_seed"]) for r in body["board"]] == [("alice", 1), ("bob", 2)]
    assert [r["user"] for r in api.get("/api/events/tug-of-war/leaderboard").json()["rows"]] == ["alice", "bob"]
    assert api.get("/api/players/alice").json()["publications"][0]["metric"] == "mean_ground_cm"


def test_a_race_answer_carries_no_centimetres(client):
    api, app = client
    body = api.get(f"/api/runs/{record_run(app).run_id}").json()
    assert "score_cm" not in body["per_seed"][0]


def test_events_lists_the_whole_programme(client):
    api, _ = client
    assert {e["id"] for e in api.get("/api/events").json()["events"]} == {
        "sprint-2m",
        "roller-sprint-2m",
        "hill-climb-1m5",
        "sock-heist-6m",
        "got-a-talent",
        "tug-of-war",
    }


def test_an_event_carries_what_the_page_needs_to_describe_it(client):
    api, _ = client
    sprint = next(e for e in api.get("/api/events").json()["events"] if e["id"] == "sprint-2m")
    assert sprint["title"] == "2 m Sprint"
    assert sprint["rig"] == "legs"
    assert sprint["length_m"] == 2.0
    # The frontend sizes the drawn course from this, so it has to be served.
    assert sprint["width_m"] == 0.8
    assert sprint["time_limit_s"] == 50.0
    assert sprint["seeds"] == 5
    # The page advertises the sweep, because "commanded 0.25 m/s" stopped being
    # true of the score the moment the harness started searching for the speed.
    assert sprint["sweep_lo"] == 0.20
    assert sprint["sweep_hi"] == 1.20
    assert sprint["sweep_step"] == 0.05
    assert sprint["sweep_count"] == 21
    assert "command_vx" not in sprint, "an event no longer pins one speed"
    assert sprint["slope_deg"] == 0.0


def test_the_hill_reports_its_slope(client):
    api, _ = client
    hill = next(
        e for e in api.get("/api/events").json()["events"] if e["id"] == "hill-climb-1m5"
    )
    assert hill["slope_deg"] == 8.0


def test_an_empty_leaderboard_is_an_empty_list_not_an_error(client):
    api, _ = client
    body = api.get("/api/events/sprint-2m/leaderboard").json()
    assert body["rows"] == []
    assert body["event"]["id"] == "sprint-2m"


def test_the_leaderboard_ranks_recorded_runs(client):
    """The slower run is recorded FIRST, deliberately.

    Runs are read back in run-id order, which is insertion order, so recording
    the winner first would let a route that returned records untouched pass this
    test by accident. Recording bob first means insertion order and rank order
    disagree, and only real ranking satisfies the assertion.
    """
    api, app = client
    record_run(app, user="bob", score=25.0, seeds_finished=4)
    record_run(app, user="alice", score=18.2, seeds_finished=5)

    rows = api.get("/api/events/sprint-2m/leaderboard").json()["rows"]
    assert [r["user"] for r in rows] == ["alice", "bob"]
    assert [r["rank"] for r in rows] == [1, 2]
    assert rows[0]["score"] == 18.2
    assert rows[0]["seeds_finished"] == 5
    assert rows[0]["seeds_total"] == 1  # make_record ships one seed result
    assert rows[0]["run_id"]


def test_only_the_best_run_of_an_entrant_is_returned(client):
    """Same person, same policy name: the better run replaces the worse one."""
    api, app = client
    record_run(app, user="alice", score=30.0)
    record_run(app, user="alice", score=19.0)
    rows = api.get("/api/events/sprint-2m/leaderboard").json()["rows"]
    assert len(rows) == 1
    assert rows[0]["score"] == 19.0


def test_two_policies_from_one_user_both_appear(client):
    """The reported bug: submitting a second policy showed only one row.

    The app runs as a single local user, so ranking per PERSON collapsed every
    submission into one line and the head-to-head replay had nothing to race.
    """
    api, app = client
    record_run(app, user="coralie", policy_name="walker-v1", score=22.0)
    record_run(app, user="coralie", policy_name="walker-v2", score=19.0)

    rows = api.get("/api/events/sprint-2m/leaderboard").json()["rows"]
    assert [r["policy_name"] for r in rows] == ["walker-v2", "walker-v1"]
    assert [r["rank"] for r in rows] == [1, 2]


def test_runs_are_scoped_to_their_event(client):
    api, app = client
    record_run(app, user="alice", event_id="sprint-2m")
    record_run(app, user="bob", event_id="roller-sprint-2m")
    assert [r["user"] for r in api.get("/api/events/sprint-2m/leaderboard").json()["rows"]] == [
        "alice"
    ]
    assert [
        r["user"] for r in api.get("/api/events/roller-sprint-2m/leaderboard").json()["rows"]
    ] == ["bob"]


def test_an_unknown_event_is_a_404_with_a_reason(client):
    api, _ = client
    response = api.get("/api/events/nope/leaderboard")
    assert response.status_code == 404
    assert "no such event" in response.json()["detail"]


def test_a_published_policy_can_be_downloaded(client):
    """The point of the whole feature: race someone else's weights yourself."""
    api, app = client
    record = make_record(user="alice", policy_name="sprinter", model_stored=True)
    app.state.store.append(record, encode(np.zeros((5, 21), "f4")), b"the-onnx-bytes")

    response = api.get(f"/api/runs/{record.run_id}/policy")
    assert response.status_code == 200, response.text
    assert response.content == b"the-onnx-bytes"
    assert response.headers["content-disposition"] == (
        'attachment; filename="alice-sprinter.onnx"'
    )
    # The checksum travels with the file, so a download can be verified against
    # the record without trusting the store.
    assert response.headers["x-model-sha256"] == record.model_sha256


def test_downloading_a_run_recorded_before_policies_were_kept_404s(client):
    api, app = client
    record = record_run(app, user="alice")

    response = api.get(f"/api/runs/{record.run_id}/policy")
    assert response.status_code == 404
    # A real explanation, not FastAPI's bare 404: this run's weights are gone
    # for good and the person asking should know why.
    assert "before policies were kept" in response.json()["detail"]


def test_downloading_an_unknown_run_404s_with_the_run_id(client):
    api, _ = client
    response = api.get("/api/runs/NOPE/policy")
    assert response.status_code == 404
    # Distinguishes "no such run" from "run exists, no weights" — without this,
    # FastAPI's own 404 for an unrouted path would satisfy a status-only check.
    assert "no such run" in response.json()["detail"]


def test_the_leaderboard_says_which_rows_offer_a_download(client):
    api, app = client
    app.state.store.append(
        make_record(user="alice", score=12.0, model_stored=True),
        encode(np.zeros((5, 21), "f4")),
        b"onnx",
    )
    record_run(app, user="bob", score=13.0)

    rows = api.get("/api/events/sprint-2m/leaderboard").json()["rows"]
    assert {r["user"]: r["model_stored"] for r in rows} == {"alice": True, "bob": False}


@pytest.mark.parametrize(
    "policy_name,expected",
    [
        ("sprinter", "alice-sprinter.onnx"),
        # Path traversal, quote injection into the header, and unicode all have
        # to come out as a plain filename. This text is submitter-supplied and
        # lands in a Content-Disposition header and a person's filesystem.
        ("../../etc/passwd", "alice-etc-passwd.onnx"),
        ('a"; filename="evil', "alice-a-filename-evil.onnx"),
        ("run/../..", "alice-run.onnx"),
        # A dot in the stem is dropped rather than kept, which also rules out
        # `policy.onnx.exe` reaching someone's downloads folder.
        ("walker-v1.2", "alice-walker-v1-2.onnx"),
        ("evil.onnx.exe", "alice-evil-onnx-exe.onnx"),
        ("🦆", "alice.onnx"),
        ("", "alice.onnx"),
    ],
)
def test_a_download_filename_is_sanitised_not_trusted(policy_name, expected):
    from arena.web.routes_read import policy_filename

    assert policy_filename(policy_name, "alice") == expected


def test_a_download_filename_is_capped():
    from arena.web.routes_read import policy_filename

    name = policy_filename("x" * 500, "alice")
    assert len(name) <= 65
    assert name.endswith(".onnx")


def test_the_download_route_redirects_to_the_hub_for_a_hub_record(client):
    api, app = client
    record = make_record(
        user="alice",
        source={
            "kind": "hub",
            "repo_id": "alice/microduck-walker",
            "filename": "policy.onnx",
            "revision": "rev123",
            "url": "https://huggingface.co/alice/microduck-walker/resolve/rev123/policy.onnx",
        },
    )
    app.state.store.append(record, encode(np.zeros((5, 21), "f4")))

    response = api.get(f"/api/runs/{record.run_id}/policy", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == record.source["url"]


def test_a_local_upload_record_is_still_served_from_the_store(client):
    """The CLI and every pre-existing run. Both paths keep working."""
    api, app = client
    record = make_record(user="alice", model_stored=True)
    app.state.store.append(record, encode(np.zeros((5, 21), "f4")), b"the-onnx")
    response = api.get(f"/api/runs/{record.run_id}/policy")
    assert response.status_code == 200
    assert response.content == b"the-onnx"


def test_the_programme_is_served_in_its_declared_order(client):
    """Sorted once on the server, so every client reads the same programme."""
    api, _ = client
    events = api.get("/api/events").json()["events"]
    assert [e["id"] for e in events[:6]] == [
        "sprint-2m",
        "got-a-talent",
        "roller-sprint-2m",
        "hill-climb-1m5",
        "tug-of-war",
        "sock-heist-6m",
    ]
    assert [e["order"] for e in events] == sorted(e["order"] for e in events)


def test_an_event_carries_the_walls_the_physics_uses(client):
    """Drawn walls must be the ones the robot can hit, so the page is given the
    geometry rather than the ingredients to recompute it."""
    api, _ = client
    sprint = next(e for e in api.get("/api/events").json()["events"] if e["id"] == "sprint-2m")
    walls = sprint["walls"]
    assert [w["name"] for w in walls] == ["wall_left", "wall_right"]
    assert walls[0]["pos"] == pytest.approx([1.0, 0.425, 0.075])
    assert walls[0]["half"] == pytest.approx([1.5, 0.025, 0.075])
    # Mirrored across the lane, and nothing else differs.
    assert walls[1]["pos"][1] == pytest.approx(-walls[0]["pos"][1])
    assert walls[1]["half"] == walls[0]["half"]


def test_a_stage_event_is_served_without_a_lane_or_a_sweep(client):
    """MicroDuck Got a Talent plays on an open stage: no length, walls, slope or speed sweep to draw."""
    api, _ = client
    talent = next(e for e in api.get("/api/events").json()["events"] if e["id"] == "got-a-talent")
    for key in ("length_m", "width_m", "slope_deg", "walls", "sweep_lo", "sweep_hi", "sweep_step", "sweep_count"):
        assert key not in talent, key
    assert talent["time_limit_s"] == 20.0
    assert talent["seeds"] == 1


def test_a_lane_serves_every_seeds_timetable_so_the_page_draws_the_giant(client):
    api, _ = client
    events = {e["id"]: e for e in api.get("/api/events").json()["events"]}
    assert events["sock-heist-6m"]["lights"] == served(load_event("sock-heist-6m"))
    assert set(events["sock-heist-6m"]["lights"]["timetables"]) == {"1", "2", "3", "4", "5"}
    assert "speed" not in events["sock-heist-6m"]["clip"]
    assert events["sprint-2m"]["lights"] is None
    assert "lights" not in events["got-a-talent"]


def test_a_stage_serves_where_a_duck_may_start(client):
    """The workshop's plan refuses a spot with the loader's own numbers, not copies of them."""
    api, _ = client
    talent = next(e for e in api.get("/api/events").json()["events"] if e["id"] == "got-a-talent")
    assert (talent["edge_margin_m"], talent["min_spacing_m"]) == (EDGE_MARGIN_M, MIN_SPACING_M)


def test_a_stage_serves_its_floor_and_how_many_ducks_it_takes(client):
    """The server's placement rules, the workshop's plan and the drawn stage read these same numbers."""
    api, _ = client
    events = {e["id"]: e for e in api.get("/api/events").json()["events"]}
    assert (events["got-a-talent"]["size_m"], events["got-a-talent"]["max_ducks"]) == ([2.6, 3.8], 8)
    assert "size_m" not in events["sprint-2m"] and "max_ducks" not in events["sprint-2m"]


def test_a_board_row_and_its_run_page_carry_the_cast(client):
    """A lane on a stage is a board row: the event page, the run page and the clip put any row on it,
    every duck in its place, and the run page credits the borrowed ones."""
    api, app = client
    cast = ({"policy": "self", "rig": "legs", "start": {"x": 0.0, "y": 0.0, "yaw": 0.0},
             "sound": {"triggers": [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0]]}},
            {"policy": WALKER, "rig": "rollers", "start": {"x": 0.4, "y": -0.6, "yaw": 90.0}, "sound": None})
    troupe = record_run(app, event_id="got-a-talent", user="ann", cast=cast)
    record_run(app, event_id="got-a-talent", user="bob")
    rows = {row["user"]: row for row in api.get("/api/events/got-a-talent/leaderboard").json()["rows"]}
    assert (rows["ann"]["cast"], rows["bob"]["cast"]) == (list(cast), [ALONE])
    assert "sound" not in rows["ann"]
    detail = api.get(f"/api/runs/{troupe.run_id}").json()
    assert detail["cast"] == list(cast)
    assert next(row for row in detail["board"] if row["you"])["cast"] == list(cast)


def test_standings_rank_every_player_who_published(client):
    api, app = client
    record_run(app, user="ann", score=20.0, submitted_at="2026-09-03T09:00:00Z")
    record_run(app, user="bob", score=22.0, submitted_at="2026-09-03T10:00:00Z")
    rows = api.get("/api/standings").json()["rows"]
    # ann: first_event 100 + run 10 + podium 250; bob: 100 + 10 + 150.
    assert rows == [
        {"rank": 1, "user": "ann", "points": 360},
        {"rank": 2, "user": "bob", "points": 260},
    ]


def test_standings_are_empty_before_anyone_publishes(client):
    api, _ = client
    assert api.get("/api/standings").json() == {"rows": []}


def test_a_player_page_carries_points_rank_and_every_publication_newest_first(client):
    api, app = client
    slow = record_run(app, user="ann", event_id="sprint-2m", score=30.0,
                      policy_name="v1", submitted_at="2026-09-03T09:00:00Z")
    fast = record_run(app, user="ann", event_id="sprint-2m", score=20.0,
                      policy_name="v2", submitted_at="2026-09-03T10:00:00Z")
    hill = record_run(app, user="ann", event_id="hill-climb-1m5", score=40.0,
                      submitted_at="2026-09-03T11:00:00Z")
    record_run(app, user="bob", event_id="hill-climb-1m5", score=35.0,
               submitted_at="2026-09-03T12:00:00Z")

    body = api.get("/api/players/ann").json()
    # sprint: first 100 + runs 10+10 + own_best 25 + podium 250; hill: first 100 + run 10 + podium 150.
    assert (body["user"], body["rank"], body["points"]) == ("ann", 1, 655)
    assert [(p["run_id"], p["rank"], p["on_board"]) for p in body["publications"]] == [
        (hill.run_id, 2, True),
        (fast.run_id, 1, True),
        # Beaten by her own v2, so off the board — and still placed: alone in
        # a field with nobody else on the sprint, first.
        (slow.run_id, 1, False),
    ]
    sprint = body["publications"][1]
    assert (sprint["event_title"], sprint["policy_name"], sprint["seeds_total"]) == (
        "2 m Sprint", "v2", 1,
    )
    assert (sprint["withdrawn"], sprint["seen"]) == (False, False)


def test_a_player_with_no_publication_is_404(client):
    api, _ = client
    response = api.get("/api/players/nobody")
    assert response.status_code == 404
    assert "nobody" in response.json()["detail"]


def test_a_withdrawn_run_leaves_the_ladder_but_stays_on_the_player_page(client):
    api, app = client
    from arena.store import Withdrawal
    run = record_run(app, user="ann")
    app.state.store.withdraw(Withdrawal(run_id=run.run_id, event_id="sprint-2m", user="ann",
                                        withdrawn_at="2026-09-03T12:00:00Z"))
    assert api.get("/api/standings").json() == {"rows": []}
    body = api.get("/api/players/ann").json()
    assert (body["points"], body["rank"]) == (0, None)
    assert [(p["run_id"], p["withdrawn"], p["on_board"]) for p in body["publications"]] == [
        (run.run_id, True, False),
    ]


def test_an_event_says_whether_it_takes_votes_and_how(client):
    api, _ = client
    events = {e["id"]: e for e in api.get("/api/events").json()["events"]}
    assert events["sprint-2m"]["vote"] is None
    assert events["sprint-2m"]["metric"] == "mean_finish_time"
    talent = events["got-a-talent"]
    assert talent["title"] == "MicroDuck Got a Talent"
    assert talent["metric"] == "votes"
    assert talent["vote"] == {
        "ballot_min": 2, "ballot_max": 4, "window_days": 7, "per_day": 20,
    }


def cast(app, choice, candidates, **overrides):
    from datetime import UTC, datetime

    from arena.store import Ballot, new_id

    fields = {
        "ballot_id": new_id(),
        "event_id": "got-a-talent",
        "voter": "coralie",
        "cast_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidates": tuple(candidates),
        "choice": choice,
    }
    fields.update(overrides)
    app.state.ballots.cast(Ballot(**fields))


def test_every_event_says_what_kind_of_course_it_is(client):
    api, _ = client
    courses = {e["id"]: e["course"] for e in api.get("/api/events").json()["events"]}
    assert courses == {"sprint-2m": "lane", "roller-sprint-2m": "lane", "hill-climb-1m5": "lane",
                       "sock-heist-6m": "lane", "got-a-talent": "stage", "tug-of-war": "tug"}


def test_a_voted_events_publication_stands_where_its_votes_put_it(client):
    api, app = client
    ann = record_run(app, user="ann", event_id="got-a-talent", score=20.0, submitted_at="2026-09-03T10:00:00Z")
    bob = record_run(app, user="bob", event_id="got-a-talent", score=20.0, submitted_at="2026-09-04T10:00:00Z")
    cast(app, bob.run_id, [ann.run_id, bob.run_id])
    body = api.get(f"/api/runs/{bob.run_id}").json()
    assert (body["rank"], body["on_board"]) == (1, True)
    assert [(r["user"], r["votes"], r["you"]) for r in body["board"]] == [("bob", 1, True), ("ann", 0, False)]
    assert body["board"][0]["rate"] > body["board"][1]["rate"]


def test_an_older_performance_finds_its_place_off_the_board(client):
    api, app = client
    old = record_run(app, user="ann", event_id="got-a-talent", score=20.0, submitted_at="2026-09-03T10:00:00Z")
    record_run(app, user="ann", event_id="got-a-talent", score=20.0, submitted_at="2026-09-05T10:00:00Z")
    body = api.get(f"/api/runs/{old.run_id}").json()
    assert body["on_board"] is False
    assert [r["you"] for r in body["board"]] == [True]


def test_a_voted_board_ranks_on_its_rate_and_still_reports_the_time(client):
    api, app = client
    ann = record_run(app, user="ann", event_id="got-a-talent", score=12.0)
    bob = record_run(app, user="bob", event_id="got-a-talent", score=40.0)
    cast(app, bob.run_id, [ann.run_id, bob.run_id])

    rows = api.get("/api/events/got-a-talent/leaderboard").json()["rows"]
    assert [(r["rank"], r["user"], r["votes"], r["shown"]) for r in rows] == [
        (1, "bob", 1, 1),
        (2, "ann", 0, 1),
    ]
    assert rows[0]["rate"] > rows[1]["rate"]
    # The time is measured anyway, so it stays on the row — as a fact, not a rank.
    assert rows[0]["score"] == 40.0


def test_a_players_best_row_on_a_voted_event_carries_its_vote_count(client):
    """`player_page` used to return a voted `rank` beside a timed `score` and
    no votes, so the profile rendered `#1 · 18.46s` for the MicroDuck Got a Talent — a
    vote rank next to a finish time, with nothing saying which is which."""
    api, app = client
    ann = record_run(app, user="ann", event_id="got-a-talent", score=12.0)
    bob = record_run(app, user="bob", event_id="got-a-talent", score=40.0)
    cast(app, bob.run_id, [ann.run_id, bob.run_id])

    winner = api.get("/api/players/bob").json()
    [won] = [b for b in winner["publications"] if b["event_id"] == "got-a-talent"]
    assert won["votes"] == 1

    runner_up = api.get("/api/players/ann").json()
    [lost] = [b for b in runner_up["publications"] if b["event_id"] == "got-a-talent"]
    assert lost["votes"] == 0
    assert won["rate"] > lost["rate"]


def test_a_players_best_row_on_a_timed_event_carries_no_vote_count(client):
    api, app = client
    record_run(app, user="ann", event_id="sprint-2m", score=12.0)
    body = api.get("/api/players/ann").json()
    [sprint] = [b for b in body["publications"] if b["event_id"] == "sprint-2m"]
    assert sprint["votes"] is None
    assert sprint["rate"] is None


def test_a_vote_cast_days_ago_but_still_inside_the_window_counts(client):
    """The seam where the two window stages meet: `since()` fetches whole DAY
    shards, `window()` then trims to the exact instant. This ballot is one
    second inside the window's exact edge — the same calendar day the edge
    falls on in the common case, the one day a first_day off-by-one would
    drop from the shard fetch entirely. It has to survive both stages to
    reach the board, not just one.

    Anchored to the edge instant, not a clock face: a fixed 23:59:59 would
    coincide with the server's own edge string exactly once a day (whenever
    `now`'s time-of-day floors to that same second), making this assertion
    fail deterministically rather than prove anything.
    """
    from datetime import UTC, datetime, timedelta

    api, app = client
    ann = record_run(app, user="ann", event_id="got-a-talent")
    bob = record_run(app, user="bob", event_id="got-a-talent")
    edge = (datetime.now(UTC) - timedelta(days=7)).replace(microsecond=0)
    stamp = (edge + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cast(app, bob.run_id, [ann.run_id, bob.run_id], cast_at=stamp)

    rows = api.get("/api/events/got-a-talent/leaderboard").json()["rows"]
    by_user = {r["user"]: r["votes"] for r in rows}
    assert by_user == {"ann": 0, "bob": 1}


def test_a_vote_that_fell_out_of_the_window_no_longer_counts(client):
    """One second before the window's exact edge — usually the same calendar
    day the edge falls on, so `since()` still opens this ballot's day shard,
    and it is genuinely `window()`'s instant trim, not the day-shard fetch,
    that excludes it. (In the rare case this second crosses a UTC midnight,
    the ballot lands in the previous day's shard instead and `since()` is
    what excludes it — the assertion still holds, it just proves a little
    less that one second of the day.)

    Anchored to the edge instant, not a clock face: a fixed 00:00:00 would
    coincide with the server's own edge string exactly once a day, making
    this assertion fail deterministically rather than prove anything.
    """
    from datetime import UTC, datetime, timedelta

    api, app = client
    ann = record_run(app, user="ann", event_id="got-a-talent")
    bob = record_run(app, user="bob", event_id="got-a-talent")
    edge = (datetime.now(UTC) - timedelta(days=7)).replace(microsecond=0)
    stamp = (edge - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cast(app, ann.run_id, [ann.run_id, bob.run_id], cast_at=stamp)

    rows = api.get("/api/events/got-a-talent/leaderboard").json()["rows"]
    assert all(r["votes"] == 0 for r in rows)


def test_the_leaderboard_only_counts_this_events_own_ballots(client):
    """`points.boards_by_user` filters ballots to `b.event_id == event_id`;
    `event_leaderboard` did not. Harmless only because run ids are globally
    unique in practice — contrived here to name the same run id from another
    event's ballot, which is exactly the leak the missing filter allowed."""
    api, app = client
    ann = record_run(app, user="ann", event_id="got-a-talent", score=12.0)
    bob = record_run(app, user="bob", event_id="got-a-talent", score=40.0)
    cast(app, ann.run_id, [ann.run_id, bob.run_id], event_id="some-other-votable-event")

    rows = api.get("/api/events/got-a-talent/leaderboard").json()["rows"]
    assert all(r["votes"] == 0 for r in rows)


def test_a_timed_board_is_untouched_and_carries_no_vote_columns(client):
    api, app = client
    record_run(app, user="ann", event_id="sprint-2m", score=12.0)
    rows = api.get("/api/events/sprint-2m/leaderboard").json()["rows"]
    assert "votes" not in rows[0]


def test_voting_puts_points_on_the_ladder(client):
    api, app = client
    ann = record_run(app, user="ann", event_id="got-a-talent")
    bob = record_run(app, user="bob", event_id="got-a-talent")
    cast(app, ann.run_id, [ann.run_id, bob.run_id], voter="coralie")

    rows = {r["user"]: r["points"] for r in api.get("/api/standings").json()["rows"]}
    assert rows["coralie"] == 2


def test_every_event_tells_the_page_what_kind_it_is(client):
    """The MicroDuck Got a Talent is not a race, and not even timed — so the page has to
    be told, not left to guess from `metric`."""
    api, _ = client
    events = {e["id"]: e.get("category") for e in api.get("/api/events").json()["events"]}
    assert events["sprint-2m"] == "race"
    assert events["got-a-talent"] == "showcase"


def test_a_run_detail_carries_its_place_its_receipts_and_its_event(client):
    api, app = client
    record_run(app, user="bob", score=10.0, submitted_at="2026-09-03T09:00:00Z")
    mine = record_run(app, user="coralie", score=12.0, submitted_at="2026-09-03T10:00:00Z")

    body = api.get(f"/api/runs/{mine.run_id}").json()
    assert body["event"]["title"] == "2 m Sprint"
    assert (body["rank"], body["on_board"], body["withdrawn"], body["seen"]) == (
        2, True, False, False,
    )
    assert [(r["rank"], r["user"], r["you"]) for r in body["board"]] == [
        (1, "bob", False),
        (2, "coralie", True),
    ]
    # The same columns the event's board shows: the page draws the same table.
    assert {"command_vx", "seeds_total", "offers_download", "policy_url", "robot_command", "env_url", "livery"} \
        <= set(body["board"][0])
    # first entry 100 + run 10 + second place 150; no own_best, a lone run beats nothing.
    assert sorted(r["act"] for r in body["receipts"]) == ["first_event", "podium", "run"]
    assert sum(r["points"] for r in body["receipts"]) == 260
    # Dropped: it cost a full trace decode, and the page loads the trace anyway.
    assert "frames" not in body


def test_a_run_page_reads_no_cup(client, monkeypatch):
    """A cup's receipts are paid to its deciding matches, never to a run: the run page has nothing to read there."""
    api, app = client
    monkeypatch.setattr("arena.web.routes_read.all_cups", lambda store: pytest.fail("the run page read the cups"))
    assert api.get(f"/api/runs/{record_run(app).run_id}").status_code == 200


def test_a_player_page_and_the_ladder_count_the_cups(client):
    api, app = client
    store_cup(app.state.store, played_cup(6, starts_at="2026-01-02T17:00:00Z"))
    record_run(app, run_id="R0", event_id="tug-of-war", user="p0")
    assert api.get("/api/players/p0").json()["cups"] == [{"event_id": "tug-of-war", "event_title": load_event("tug-of-war").title,
        "number": 1, "starts_at": "2026-01-02T17:00:00Z", "reached": "champion"}]
    ladder = {row["user"]: row["points"] for row in api.get("/api/standings").json()["rows"]}
    assert (ladder["p1"], ladder["p2"]) == (150, 100)


def test_a_player_page_lists_its_cups_newest_first(client):
    api, app = client
    store_cup(app.state.store, played_cup(6, starts_at="2026-01-02T17:00:00Z"))
    store_cup(app.state.store, played_cup(6, number=2, starts_at="2026-01-09T17:00:00Z"))
    record_run(app, run_id="R0", event_id="tug-of-war", user="p0")
    assert [cup["number"] for cup in api.get("/api/players/p0").json()["cups"]] == [2, 1]


def test_a_cup_that_has_not_aired_tells_nothing_to_the_profiles_the_ladder_or_the_chip(tmp_path):
    """The routes read their own clock: a cup dated 2099 is stored, played and ordered, and none of it is told."""
    app = create_app(ArenaConfig.from_env(store_dir=tmp_path, dev_user="p0"))
    api = TestClient(app)
    store_cup(app.state.store, played_cup(6, starts_at="2026-01-02T17:00:00Z"))
    record_run(app, run_id="R0", event_id="tug-of-war", user="p0")

    def told():
        return [api.get(path).json() for path in ("/api/players/p0", "/api/standings", "/api/me")]

    before = told()
    assert [cup["number"] for cup in before[0]["cups"]] == [1]
    store_cup(app.state.store, played_cup(6, number=2, starts_at="2099-01-02T17:00:00Z"))
    assert told() == before


def test_the_chip_counts_cup_points(tmp_path):
    app = create_app(ArenaConfig.from_env(store_dir=tmp_path, dev_user="p1"))
    store_cup(app.state.store, played_cup(6, starts_at="2026-01-02T17:00:00Z"))
    assert TestClient(app).get("/api/me").json()["points"] == 150
