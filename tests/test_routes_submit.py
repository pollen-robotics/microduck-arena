import hashlib
import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from arena.assets import ASSET_ROOT
from arena.hub_fetch import FetchedPolicy
from arena.timeline import SELF, Duck, Start, Timeline, Troupe, solo
from arena.trace import decode, decode_string
from arena.web.app import create_app
from arena.web.config import ArenaConfig

REFERENCE = ASSET_ROOT / "policies" / "BEST_alpha_walking.onnx"

# Every entry is a Hub repo now. `submit()` puts the file it is given in this
# fake Hub under a repo id; the autouse fixture below serves it back.
_HUB: dict[str, Path] = {}

# A repo id registered here also carries this timeline.json, as (Troupe, sha256).
_TIMELINES: dict[str, tuple] = {}


def _fetched(path=REFERENCE, repo_id="alice/walker", filename="policy.onnx", revision="rev1", **more):
    return FetchedPolicy(repo_id=repo_id, filename=filename, revision=revision, path=path,
                         url=f"https://huggingface.co/{repo_id}/resolve/{revision}/{filename}", **more)


@pytest.fixture(autouse=True)
def hub(monkeypatch):
    """Stands in for the Hub: a repo id registered in _HUB comes back as that file, at the
    revision asked for. Records every call, so a test can see what reached it."""
    _HUB.clear()
    _TIMELINES.clear()
    calls = []

    def fetch(repo_id, revision, event):
        calls.append((repo_id, revision, event.id))
        if repo_id not in _HUB:
            from arena.hub_fetch import FetchError

            raise FetchError(f"{repo_id} has no .onnx file")
        troupe, digest = _TIMELINES.get(repo_id, (None, None))
        return _fetched(path=_HUB[repo_id], repo_id=repo_id, revision=revision or "rev1",
                        troupe=troupe, timeline_sha256=digest)

    monkeypatch.setattr("arena.web.routes_submit._fetch_from_hub", fetch)
    return calls


@pytest.fixture
def store_dir(tmp_path):
    return tmp_path / "board"


@pytest.fixture
def api(store_dir):
    config = ArenaConfig.from_env(store_dir=store_dir, dev_user="coralie")
    return TestClient(create_app(config), base_url="https://testserver")


@pytest.fixture
def spaced_api(store_dir, monkeypatch):
    """A Space-like app: OAuth configured, so nobody is signed in by default."""
    monkeypatch.setenv("OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("SPACE_HOST", "example.hf.space")
    config = ArenaConfig.from_env(store_dir=store_dir, dev_user="coralie")
    return TestClient(create_app(config), base_url="https://testserver")


def sign_in(api, username="alice"):
    """Put a real session in the app's table and hand the client its cookie."""
    from arena.web.session import COOKIE_NAME, sign

    app = api.app
    sid = app.state.sessions.create(username, 3600)
    api.cookies.set(COOKIE_NAME, sign(sid, app.state.config.session_secret))


def submit(api, path=REFERENCE, event="sprint-2m", name="walker", **fields):
    repo_id = f"alice/{Path(path).stem.lower()}"
    _HUB[repo_id] = Path(path)
    data = {"repo_id": repo_id, **fields}
    if name is not None:
        data["name"] = name
    return api.post(f"/api/events/{event}/submit", data=data)


import logging

from arena.web.hub_identity import HubUnreachable, HubUser, TokenRefused

TOKENS = {
    "hf_alice": HubUser("alice", "user", frozenset({"duck-lab"})),
    "hf_org": HubUser("duck-lab", "org", frozenset()),
}


@pytest.fixture
def hub_users(monkeypatch):
    """Stands in for the Hub's whoami-v2. Records the tokens it was asked about."""
    asked = []

    def whoami(token):
        asked.append(token)
        if token == "hf_down":
            raise HubUnreachable("huggingface.co did not answer")
        if token not in TOKENS:
            raise TokenRefused
        return TOKENS[token]

    monkeypatch.setattr("arena.web.routes_submit._whoami", whoami)
    return asked


def enter(api, token="hf_alice", repo_id="alice/walker", path=REFERENCE, event="sprint-2m", **fields):
    """What `publish --enter` sends: a repo, and the token in Authorization."""
    _HUB[repo_id] = Path(path)
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return api.post(f"/api/events/{event}/submit", data={"repo_id": repo_id, **fields}, headers=headers)


def test_an_entry_is_credited_to_the_tokens_owner(spaced_api, hub_users):
    response = enter(spaced_api)
    assert response.status_code == 200, response.text
    assert response.json()["user"] == "alice"
    assert response.json()["course"] == "lane"
    assert hub_users == ["hf_alice"]


def test_without_a_token_it_says_how_to_enter(spaced_api, hub, hub_users):
    response = enter(spaced_api, token=None)
    assert response.status_code == 401
    assert "uv run publish" in response.json()["detail"] and "--enter" in response.json()["detail"]
    assert hub == [], "nothing fetched for an entry nobody can be credited with"


def test_a_session_cookie_does_not_enter(spaced_api, hub_users):
    sign_in(spaced_api, username="alice")
    assert enter(spaced_api, token=None).status_code == 401


def test_a_refused_token_is_401(spaced_api, hub_users):
    response = enter(spaced_api, token="hf_nobody")
    assert response.status_code == 401 and response.json()["detail"] == "Hugging Face refused this token."


def test_an_unreachable_hub_is_503(spaced_api, hub_users):
    assert enter(spaced_api, token="hf_down").status_code == 503


def test_an_organisations_token_is_refused(spaced_api, hub_users):
    response = enter(spaced_api, token="hf_org", repo_id="duck-lab/walker")
    assert response.status_code == 403 and "person" in response.json()["detail"]


def test_a_repo_outside_your_namespace_is_refused(spaced_api, hub, hub_users):
    response = enter(spaced_api, repo_id="bob/walker")
    assert response.status_code == 403 and "bob/walker" in response.json()["detail"]
    assert hub == []


def test_a_repo_of_one_of_your_orgs_is_yours(spaced_api, hub_users):
    assert enter(spaced_api, repo_id="duck-lab/walker").status_code == 200


def test_the_namespace_ignores_case(spaced_api, hub_users):
    assert enter(spaced_api, repo_id="Alice/walker").status_code == 200


def test_one_entry_races_at_a_time(spaced_api, hub, hub_users):
    spaced_api.app.state.racing.add("alice")  # as while an earlier entry of hers is being raced
    response = enter(spaced_api)
    assert response.status_code == 409 and "still racing" in response.json()["detail"]
    assert hub == []


def test_the_racing_mark_goes_whatever_the_outcome(spaced_api, hub_users, tmp_path):
    junk = tmp_path / "junk.onnx"
    junk.write_bytes(b"not a model")
    assert enter(spaced_api, path=junk).status_code == 400
    assert spaced_api.app.state.racing == set()


def test_the_token_is_never_logged_nor_repeated(spaced_api, hub_users, caplog):
    caplog.set_level(logging.DEBUG)
    answers = [enter(spaced_api, token=t, repo_id=r)
               for t, r in [("hf_alice", "alice/walker"), ("hf_nobody", "alice/walker"),
                            ("hf_alice", "bob/walker"), ("hf_org", "duck-lab/walker"), ("hf_down", "alice/walker")]]
    for token in ("hf_alice", "hf_nobody", "hf_org", "hf_down"):
        assert token not in caplog.text
        assert all(token not in a.text for a in answers)


def test_a_local_arena_needs_no_token_and_checks_no_namespace(api, hub_users):
    response = enter(api, token=None, repo_id="bob/walker")
    assert response.status_code == 200 and response.json()["user"] == "coralie"
    assert hub_users == []


def test_the_same_policy_entered_again_answers_the_entry_already_there(api, monkeypatch):
    first = enter(api, token=None).json()
    raced = []
    monkeypatch.setattr("arena.web.routes_submit.evaluate", lambda *a: raced.append(a))
    again = enter(api, token=None, name="another name")
    assert again.status_code == 200
    body = again.json()
    assert body["already_entered"] is True and body["run_id"] == first["run_id"]
    assert body["score"] == first["score"] and body["page_url"] == first["page_url"]
    assert raced == [], "not raced again"
    assert [r["run_id"] for r in api.get("/api/events/sprint-2m/leaderboard").json()["rows"]] == [first["run_id"]]


def test_a_withdrawn_entry_can_be_entered_again(api):
    first = enter(api, token=None).json()
    assert api.post(f"/api/runs/{first['run_id']}/withdraw").status_code == 200
    again = enter(api, token=None).json()
    assert again["already_entered"] is False and again["run_id"] != first["run_id"]


def test_an_entry_from_an_older_runner_is_not_the_same_entry(api, monkeypatch):
    from arena.constants import RUNNER_VERSION

    first = enter(api, token=None).json()
    monkeypatch.setattr("arena.web.routes_submit.RUNNER_VERSION", RUNNER_VERSION + 1)
    again = enter(api, token=None).json()
    assert again["already_entered"] is False and again["run_id"] != first["run_id"]


def test_the_answer_says_where_to_see_the_entry(api):
    body = enter(api, token=None).json()
    assert body["page_url"] == f"https://testserver/#/r/{body['run_id']}"
    assert body["already_entered"] is False


def test_on_hugging_face_the_page_is_the_spaces_own(store_dir, monkeypatch, hub_users):
    monkeypatch.setenv("OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("SPACE_HOST", "pollen-robotics-microduck-arena.hf.space")
    monkeypatch.setenv("SPACE_ID", "pollen-robotics/microduck-arena")
    space = TestClient(create_app(ArenaConfig.from_env(store_dir=store_dir, dev_user="coralie")),
                       base_url="https://testserver")
    body = enter(space).json()
    assert body["page_url"] == f"https://huggingface.co/spaces/pollen-robotics/microduck-arena#/r/{body['run_id']}"


def test_a_file_is_not_an_entry(api):
    response = api.post("/api/events/sprint-2m/submit",
                        files={"file": ("p.onnx", REFERENCE.read_bytes(), "application/octet-stream")})
    assert response.status_code == 400
    assert "--enter" in response.json()["detail"]


def test_there_is_no_trial_route_any_more(api):
    assert api.post("/api/events/sprint-2m/try", data={"repo_id": "alice/walker"}).status_code in (404, 405)


def test_the_reference_policy_scores_and_is_recorded(api):
    response = submit(api)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["user"] == "coralie"
    assert body["policy_name"] == "walker"
    assert body["seeds_finished"] == 5
    assert body["seeds_total"] == 5
    # v3 (MJCF position servos): 11.724 s at 0.40 m/s. v4 (BAM servos): 7.988 s
    # at 0.55 before training's reset and fifth actuator writes joined the runner; re-measured since.
    assert body["score"] == pytest.approx(8.666, rel=0.02)
    # The submitter is told which speed set the time, not just the time.
    assert body["command_vx"] == pytest.approx(0.50)
    assert len(body["per_seed"]) == 5
    assert body["trace_seed"] in {s["seed"] for s in body["per_seed"]}

    # It is on the board immediately — that is the whole point of submitting.
    rows = api.get("/api/events/sprint-2m/leaderboard").json()["rows"]
    assert [r["user"] for r in rows] == ["coralie"]
    assert rows[0]["run_id"] == body["run_id"]
    # The score the submitter was told must be the score that got recorded. Without
    # this, a route that returned one number and stored another would pass.
    assert rows[0]["score"] == body["score"]
    assert rows[0]["seeds_finished"] == body["seeds_finished"]


def test_the_replay_of_a_fresh_submission_is_fetchable(api):
    run_id = submit(api).json()["run_id"]
    trace = api.get(f"/api/runs/{run_id}/trace")
    assert trace.status_code == 200
    assert int(trace.headers["x-frame-count"]) > 100
    # And the settle that led into it: the sprint's 0.5 s from the reset pose.
    settle = api.get(f"/api/runs/{run_id}/settle")
    assert settle.status_code == 200
    assert settle.headers["x-frame-count"] == "26"


def test_a_garbage_file_is_rejected_with_its_reason(api, tmp_path):
    junk = tmp_path / "junk.onnx"
    junk.write_bytes(b"not an onnx file")
    response = submit(api, path=junk)
    assert response.status_code == 400
    assert "not a loadable ONNX model" in response.json()["detail"]


def test_submitting_to_an_unknown_event_is_a_404(api):
    """Assert our message, not just the status.

    An unmapped path 404s on its own, so a status-only assertion passes whether
    this route exists or not — it did exactly that before the route was written.
    Only the event loader says "no such event".
    """
    response = submit(api, event="nope")
    assert response.status_code == 404
    assert "no such event" in response.json()["detail"]


def test_an_absurd_policy_name_is_truncated(api):
    """Submitter-supplied text on a shared board needs a bound."""
    response = submit(api, name="x" * 5000)
    assert len(response.json()["policy_name"]) == 80


def test_a_nameless_entry_is_called_by_its_manifest_then_its_repo(api, monkeypatch):
    monkeypatch.setattr(
        "arena.web.routes_submit._fetch_from_hub",
        lambda repo_id, revision, event: _fetched(repo_id="alice/microduck-walker", manifest={"name": "strider"}),
    )
    named = api.post("/api/events/sprint-2m/submit", data={"repo_id": "alice/microduck-walker"}).json()
    assert named["policy_name"] == "strider"
    # Withdrawn first: otherwise the second call is the same user re-entering the same
    # ONNX (identical bytes both times) and comes back as the first entry, unraced.
    assert api.post(f"/api/runs/{named['run_id']}/withdraw").status_code == 200
    monkeypatch.setattr(
        "arena.web.routes_submit._fetch_from_hub",
        lambda repo_id, revision, event: _fetched(repo_id="alice/microduck-walker"),
    )
    bare = api.post("/api/events/sprint-2m/submit", data={"repo_id": "alice/microduck-walker"}).json()
    assert bare["policy_name"] == "walker"


def test_nothing_is_recorded_when_a_submission_is_rejected(api, tmp_path):
    """The board stays empty — and for the right reason.

    Asserting only that the board is empty passes if the submission failed for
    ANY reason, including the route not existing at all, which is how this test
    passed before the route was written. Pinning the 400 and its message first
    makes the empty board mean "rejected cleanly, recorded nothing" rather than
    "something went wrong somewhere".
    """
    junk = tmp_path / "junk.onnx"
    junk.write_bytes(b"nope")
    rejected = submit(api, path=junk)
    assert rejected.status_code == 400
    assert "not a loadable ONNX model" in rejected.json()["detail"]
    assert api.get("/api/events/sprint-2m/leaderboard").json()["rows"] == []


def test_a_submission_remembers_its_livery(api):
    response = submit(api, name="purple-runner", livery="purple")
    assert response.json()["livery"] == "purple"

    # And the board serves it, so a replay can be drawn in the right colours.
    rows = api.get("/api/events/sprint-2m/leaderboard").json()["rows"]
    assert rows[0]["livery"] == "purple"


def test_a_submission_without_a_livery_races_in_the_default(api):
    assert submit(api).json()["livery"] == "classic"


def test_an_absurd_livery_is_capped_rather_than_stored_whole(api):
    """Submitter-supplied text again. The viewer falls back for a name it does
    not know, so this only has to stay bounded."""
    response = submit(api, livery="z" * 500)
    assert len(response.json()["livery"]) == 32


def _entered_with(api, monkeypatch, manifest):
    monkeypatch.setattr("arena.web.routes_submit._fetch_from_hub",
                        lambda repo_id, revision, event: _fetched(repo_id="alice/walker", manifest=manifest))
    run_id = api.post("/api/events/sprint-2m/submit", data={"repo_id": "alice/walker"}).json()["run_id"]
    return next(r for r in api.app.state.store.runs("sprint-2m") if r.run_id == run_id)


def test_the_manifests_description_is_kept_for_the_commentators(api, monkeypatch):
    record = _entered_with(api, monkeypatch, {"name": "strider", "description": "  It leans into every step. ",
                                              "training": {"task_id": "Mjlab-Sprint2m-MicroDuck"}})
    assert record.description == "It leans into every step."


@pytest.mark.parametrize("description", [None, 42, "", "   ", "strider", "Mjlab-Sprint2m-MicroDuck", "x" * 501])
def test_a_description_that_is_missing_a_default_or_too_long_is_not_kept(api, monkeypatch, description):
    manifest = {"name": "strider", "training": {"task_id": "Mjlab-Sprint2m-MicroDuck"}}
    if description is not None:
        manifest["description"] = description
    assert _entered_with(api, monkeypatch, manifest).description is None


def test_a_manifest_whose_training_is_not_an_object_still_enters_and_keeps_a_description(api, monkeypatch):
    record = _entered_with(api, monkeypatch, {"name": "strider", "training": "Mjlab-Sprint2m-MicroDuck",
                                              "description": "It leans into every step."})
    assert record.description == "It leans into every step."


def test_a_description_that_only_repeats_the_trimmed_name_is_not_kept(api, monkeypatch):
    manifest = {"name": "  strider  ", "description": "strider"}
    assert _entered_with(api, monkeypatch, manifest).description is None


def test_publishing_honours_a_pinned_speed(api):
    """Reversed deliberately. This test previously asserted the opposite — that a
    published time is always the full sweep — on the reasoning that letting
    entrants choose a speed ranks whoever guessed best.

    The arithmetic does not support that fear: the sweep already keeps the BEST
    time across every speed in the range, including the one you would have
    pinned, so pinning can only match or lose to sweeping. It is self-penalising.
    Here, 0.25 m/s scores ~24.9 s (one seed of five falls and counts at the
    time limit) where the sweep finds ~8.7 s at 0.50 — the submitter is
    recorded slower for having pinned, which is the whole point.

    v3 (MJCF position servos): 18.216 s pinned, 11.724 s swept. v4 (BAM
    servos) before training's reset and fifth actuator writes joined the runner: 18.208 s pinned, all five finishing, 7.988 s swept at 0.55.
    """
    response = submit(api, name="pinned", command_vx="0.25")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["command_vx"] == pytest.approx(0.25)
    assert body["score"] == pytest.approx(24.853, rel=0.02)
    assert body["score"] > 8.666, "pinning must not be able to beat the sweep here"


def test_publishing_without_a_speed_still_sweeps(api):
    """The default is unchanged, and it is the comparable measurement."""
    response = submit(api, name="swept")
    assert response.status_code == 200, response.text
    body = response.json()
    # v3 (MJCF position servos): 0.40 m/s, 11.724 s. v4 (BAM servos): 0.55 m/s,
    # 7.988 s before training's reset and fifth actuator writes joined the runner; re-measured since.
    assert body["command_vx"] == pytest.approx(0.50)
    assert body["score"] == pytest.approx(8.666, rel=0.02)


def test_a_signed_out_publish_is_refused_and_records_nothing(spaced_api, hub_users, store_dir):
    """A 401 alone would pass a gate that raced and recorded first and refused after: the store
    must be as empty as before."""
    response = enter(spaced_api, token=None)
    assert response.status_code == 401
    assert list(store_dir.rglob("*.json")) == []
    assert list(store_dir.rglob("*.npz")) == []


def test_the_local_path_still_needs_no_session_at_all(api):
    """With no OAuth configured, ARENA_DEV_USER races. This is the local run."""
    response = submit(api)
    assert response.status_code == 200
    assert response.json()["user"] == "coralie"


def test_a_repo_id_races_without_uploading_anything(api, store_dir, monkeypatch):
    """The whole point: give a reference, upload nothing, and it still scores."""
    fetched = _fetched()
    monkeypatch.setattr(
        "arena.web.routes_submit._fetch_from_hub", lambda repo_id, revision, event: fetched
    )
    response = api.post(
        "/api/events/sprint-2m/submit",
        data={"repo_id": "alice/walker", "name": "someone else's walker"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # v3 (MJCF position servos): 11.724. v4 (BAM servos): 7.988 before training's reset and fifth actuator writes joined the runner;
    # re-measured since.
    assert body["score"] == pytest.approx(8.666, rel=0.02)
    assert body["model_stored"] is False
    assert body["offers_download"] is True
    assert body["policy_url"] == fetched.url

    # Nothing was written to the store's model cache: the weights already
    # live with their author.
    assert not (store_dir / "models").exists()

    rows = api.get("/api/events/sprint-2m/leaderboard").json()["rows"]
    assert rows[0]["offers_download"] is True
    assert rows[0]["policy_url"] == fetched.url


def test_an_unresolvable_repo_id_is_refused_with_its_reason(api, store_dir, monkeypatch):
    from arena.hub_fetch import FetchError

    def boom(repo_id, revision, event):
        raise FetchError(f"{repo_id} has no .onnx file")

    monkeypatch.setattr("arena.web.routes_submit._fetch_from_hub", boom)
    response = api.post(
        "/api/events/sprint-2m/submit",
        data={"repo_id": "alice/empty"},
    )
    assert response.status_code == 400
    assert "has no .onnx file" in response.json()["detail"]
    assert api.get("/api/events/sprint-2m/leaderboard").json()["rows"] == []


def test_a_training_environment_link_is_recorded_and_served(api):
    body = submit(api, name="linked", env_url="https://github.com/me/training-env").json()
    assert body["run_id"]
    rows = api.get("/api/events/sprint-2m/leaderboard").json()["rows"]
    assert rows[0]["env_url"] == "https://github.com/me/training-env"


def test_a_submission_without_a_link_simply_has_none(api):
    submit(api)
    rows = api.get("/api/events/sprint-2m/leaderboard").json()["rows"]
    assert rows[0]["env_url"] is None


def test_a_refused_link_is_a_400_and_costs_no_simulation(api, store_dir, monkeypatch):
    """Checked before racing: a link this server will refuse should not cost
    anyone thirty seconds of physics first — and the refusal says why."""
    import arena.web.routes_submit as routes

    raced = []
    monkeypatch.setattr(routes, "evaluate", lambda *a, **k: raced.append(True))

    response = submit(api, env_url="https://github.com.evil.com/x")
    assert response.status_code == 400
    assert "github.com.evil.com" in response.json()["detail"]
    assert raced == []
    assert list(store_dir.rglob("*.json")) == []


def test_a_revision_is_pinned_and_recorded(api, hub):
    body = submit(api, revision="abc1234").json()
    assert hub[-1] == ("alice/best_alpha_walking", "abc1234", "sprint-2m")
    assert body["policy_url"].endswith("/resolve/abc1234/policy.onnx")
    row = api.get("/api/events/sprint-2m/leaderboard").json()["rows"][0]
    assert row["policy_url"] == body["policy_url"]


def test_a_manifest_that_disagrees_is_a_400_naming_the_field(api, monkeypatch, store_dir):
    from arena.hub_fetch import FetchError

    def refuse(repo_id, revision, event):
        raise FetchError(f"manifest.json: kind is 'episodic'; {event.title} takes {event.kind} policies")

    monkeypatch.setattr("arena.web.routes_submit._fetch_from_hub", refuse)
    response = api.post("/api/events/sprint-2m/submit", data={"repo_id": "alice/walker"})
    assert response.status_code == 400
    assert "kind" in response.json()["detail"]
    assert list(store_dir.rglob("*.json")) == []


def performance(seconds, sit_at=None):
    """A one-duck performance of `seconds` standing, sitting from `sit_at` when given."""
    stand, sit = (0.0,) * 13, (1.0,) + (0.0,) * 12
    if sit_at is None:
        return solo(Timeline(seconds, (0.0,), (stand,)))
    return solo(Timeline(seconds, (0.0, sit_at), (stand, sit)))


def test_a_stage_entry_plays_its_timeline(api):
    _TIMELINES["alice/best_alpha_walking"] = (performance(2.0), "a" * 64)
    response = submit(api, event="got-a-talent")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["course"] == "stage"
    assert (body["score"], body["seeds_finished"], body["seeds_total"]) == (pytest.approx(2.0), 1, 1)
    trace = api.get(f"/api/runs/{body['run_id']}/trace")
    assert int(trace.headers["X-Frame-Count"]) == 100


def test_the_same_weights_with_another_timeline_are_another_performance(api):
    _TIMELINES["alice/best_alpha_walking"] = (performance(2.0), "a" * 64)
    first = submit(api, event="got-a-talent").json()
    again = submit(api, event="got-a-talent").json()
    assert again["already_entered"] and again["run_id"] == first["run_id"]
    _TIMELINES["alice/best_alpha_walking"] = (performance(2.0, sit_at=1.0), "b" * 64)
    other = submit(api, event="got-a-talent").json()
    assert not other["already_entered"] and other["run_id"] != first["run_id"]


def _stored(api, event_id, run_id):
    return next(r for r in api.app.state.store.runs(event_id) if r.run_id == run_id)


def test_a_stage_entry_keeps_the_sound_its_timeline_makes(api):
    stand = (0.0,) * 13
    pulled = solo(Timeline(2.0, (0.0, 0.5, 1.0), (stand,) * 3, ((0.0, 0.0), (1.0, 0.0), (0.0, 0.0))))
    _TIMELINES["alice/best_alpha_walking"] = (pulled, "c" * 64)
    body = submit(api, event="got-a-talent").json()
    assert _stored(api, "got-a-talent", body["run_id"]).cast == ({
        "policy": "self", "rig": "legs", "start": {"x": 0.0, "y": 0.0, "yaw": 0.0},
        "sound": {"triggers": [[0.0, 0.0, 0.0], [0.5, 1.0, 0.0], [1.0, 0.0, 0.0]]},
    },)


def test_a_race_is_one_duck_of_its_events_rig_and_a_still_performance_makes_no_sound(api):
    race = submit(api).json()
    assert _stored(api, "sprint-2m", race["run_id"]).cast == ({"policy": "self", "rig": None, "start": None, "sound": None},)
    _TIMELINES["alice/best_alpha_walking"] = (performance(1.0), "d" * 64)
    still = submit(api, event="got-a-talent").json()
    assert _stored(api, "got-a-talent", still["run_id"]).cast[0]["sound"] is None


def test_a_star_whose_manifest_names_the_rollers_performs_on_them_and_is_kept_on_them(api, monkeypatch):
    from arena.web import routes_submit

    monkeypatch.setattr("arena.web.routes_submit._fetch_from_hub", lambda repo_id, revision, event: _fetched(
        troupe=performance(1.0), timeline_sha256="f" * 64, rig="rollers"))
    played, evaluate = [], routes_submit.evaluate

    def watched(manifest, policy, cast):
        played.extend(performer.rig for performer in cast)
        return evaluate(manifest, policy, cast)

    monkeypatch.setattr(routes_submit, "evaluate", watched)
    response = api.post("/api/events/got-a-talent/submit", data={"repo_id": "alice/walker"})
    assert response.status_code == 200, response.text
    assert played == ["rollers"]
    assert _stored(api, "got-a-talent", response.json()["run_id"]).cast[0]["rig"] == "rollers"


def test_a_speed_sent_to_a_stage_is_ignored_not_a_500(api):
    _TIMELINES["alice/best_alpha_walking"] = (performance(1.0), "a" * 64)
    response = submit(api, event="got-a-talent", command_vx="0.3")
    assert response.status_code == 200, response.text
    assert response.json()["command_vx"] == 0.0


SITTER = "pollen-robotics/microduck-sitter@" + "a" * 40


def _troupe(seconds=1.0):
    """The entry's own duck at the centre, and the sitter borrowed beside it."""
    still = Timeline(seconds, (0.0,), ((0.0,) * 13,))
    return Troupe(seconds, (Duck(SELF, Start(), still), Duck(SITTER, Start(0.0, 0.6, 90.0), still)))


def _with_a_borrowed(monkeypatch, path=REFERENCE):
    lent = _fetched(path=path, repo_id="pollen-robotics/microduck-sitter", revision="a" * 40)
    monkeypatch.setattr("arena.web.routes_submit._fetch_from_hub", lambda repo_id, revision, event: _fetched(
        troupe=_troupe(), timeline_sha256="e" * 64, borrowed={SITTER: lent}))


def test_a_troupe_plays_its_borrowed_ducks_beside_the_entrys_own(api, monkeypatch):
    _with_a_borrowed(monkeypatch)
    response = api.post("/api/events/got-a-talent/submit", data={"repo_id": "alice/walker"})
    assert response.status_code == 200, response.text
    body = response.json()
    trace = api.get(f"/api/runs/{body['run_id']}/trace")
    assert (trace.headers["X-Duck-Count"], trace.headers["X-Frame-Count"]) == ("2", "50")
    assert _stored(api, "got-a-talent", body["run_id"]).cast[1] == {
        "policy": {"repo_id": "pollen-robotics/microduck-sitter", "filename": "policy.onnx", "revision": "a" * 40,
                   "url": "https://huggingface.co/pollen-robotics/microduck-sitter/resolve/" + "a" * 40 + "/policy.onnx",
                   "model_sha256": hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),
                   "user": "pollen-robotics", "policy_name": "sitter"},
        "rig": "legs", "start": {"x": 0.0, "y": 0.6, "yaw": 90.0}, "sound": None,
    }


def test_a_borrowed_policy_that_does_not_load_is_a_400_naming_its_duck(api, monkeypatch, tmp_path, store_dir):
    junk = tmp_path / "junk.onnx"
    junk.write_bytes(b"not a model")
    _with_a_borrowed(monkeypatch, path=junk)
    response = api.post("/api/events/got-a-talent/submit", data={"repo_id": "alice/walker"})
    assert response.status_code == 400
    assert response.json()["detail"].startswith("ducks[1]: pollen-robotics/microduck-sitter: not a loadable ONNX model")
    assert list(store_dir.rglob("*.json")) == []


def test_a_tug_entry_is_rated_in_bouts_against_the_reference(api):
    body = submit(api, event="tug-of-war").json()
    assert body["course"] == "tug" and body["seeds_total"] == 5 and all("score_cm" in s for s in body["per_seed"])
    assert body["metric"] == "mean_ground_cm"
    assert api.get(f"/api/runs/{body['run_id']}/trace").headers["X-Duck-Count"] == "2"
    blob = api.app.state.store.trace(body["run_id"])
    assert decode_string(blob)[1].shape == (decode(blob).shape[1], 17, 3)   # the string, frame by frame with the ducks
    assert submit(api, event="sprint-2m").json()["metric"] == "mean_finish_time"


def test_a_heist_entry_is_stored_with_every_seeds_trace(api):
    # Pinned fast: at 1.2 m/s the walker meets its end within seconds, whatever it is.
    response = submit(api, event="sock-heist-6m", name="heist", command_vx="1.2")
    assert response.status_code == 200, response.text
    with np.load(io.BytesIO(api.app.state.store.trace(response.json()["run_id"]))) as loaded:
        assert {f"{key}_{s}" for key in ("trace", "settle") for s in range(1, 6)} <= set(loaded.files)
        assert "trace" not in loaded.files
