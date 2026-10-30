import numpy as np
import pytest
from fastapi.testclient import TestClient

from arena.constants import TRACE_WIDTH
from arena.evaluate import SeedResult
from arena.trace import SeedTrace, encode, encode_seeds
from arena.web.app import create_app
from arena.web.config import ArenaConfig
from tests.test_store import make_record


@pytest.fixture
def client(tmp_path):
    config = ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")
    app = create_app(config)
    return TestClient(app), app


def a_trace(frames=7, ducks=None):
    """A trace whose every value is distinct, so a transpose or stride bug shows: one duck's
    (frames, TRACE_WIDTH), or a troupe's (ducks, frames, TRACE_WIDTH)."""
    shape = (frames, TRACE_WIDTH) if ducks is None else (ducks, frames, TRACE_WIDTH)
    return np.arange(np.prod(shape), dtype=np.float32).reshape(shape)


def test_run_detail_reports_the_per_seed_breakdown(client):
    api, app = client
    record = make_record(
        user="alice",
        per_seed=(
            SeedResult(seed=1, status="finish", time_s=18.46),
            SeedResult(seed=2, status="fall", time_s=None),
        ),
    )
    app.state.store.append(record, encode(a_trace(frames=9)))

    body = api.get(f"/api/runs/{record.run_id}").json()
    assert body["user"] == "alice"
    assert [s["status"] for s in body["per_seed"]] == ["finish", "fall"]
    assert body["per_seed"][0]["time_s"] == 18.46
    assert body["per_seed"][1]["time_s"] is None
    # This record's source is a plain "repo" reference with no url and
    # model_stored defaults to False, so it offers no download.
    assert body["offers_download"] is False
    assert body["policy_url"] is None


def test_run_detail_reports_whether_the_policy_can_be_downloaded(client):
    """The board's download link is driven by these two keys. Checked for both
    a run that offers a download (a Hub-hosted policy) and one that does not
    (recorded before policies were kept, or a plain reference with no url)."""
    api, app = client

    hub_record = make_record(
        model_stored=False,
        source={
            "kind": "hub",
            "repo_id": "alice/microduck-walker",
            "filename": "policy.onnx",
            "revision": "rev1",
            "url": "https://huggingface.co/alice/microduck-walker/resolve/rev1/policy.onnx",
        },
    )
    app.state.store.append(hub_record, encode(a_trace()))
    body = api.get(f"/api/runs/{hub_record.run_id}").json()
    assert body["offers_download"] is True
    assert body["policy_url"] == hub_record.source["url"]
    assert body["robot_command"] == hub_record.robot_command

    bare_record = make_record(model_stored=False, source=None)
    app.state.store.append(bare_record, encode(a_trace()))
    body = api.get(f"/api/runs/{bare_record.run_id}").json()
    assert body["offers_download"] is False
    assert body["policy_url"] is None
    assert body["robot_command"] is None


def test_the_trace_round_trips_as_float32(client):
    api, app = client
    record = make_record()
    original = a_trace(frames=11)
    app.state.store.append(record, encode(original))

    response = api.get(f"/api/runs/{record.run_id}/trace")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-frame-count"] == "11"
    assert response.headers["x-duck-count"] == "1"

    restored = np.frombuffer(response.content, dtype="<f4").reshape(-1, TRACE_WIDTH)
    assert restored.shape == (11, TRACE_WIDTH)
    # float16 storage is lossy; these values are small integers so they survive.
    np.testing.assert_allclose(restored, original, rtol=0, atol=1e-2)


def test_a_troupes_trace_and_settle_are_served_duck_after_duck(client):
    api, app = client
    record = make_record(event_id="got-a-talent")
    trace, settle = a_trace(frames=9, ducks=3), a_trace(frames=4, ducks=3)
    app.state.store.append(record, encode(trace, settle))
    for path, original in (("trace", trace), ("settle", settle)):
        response = api.get(f"/api/runs/{record.run_id}/{path}")
        assert response.headers["x-duck-count"] == "3", path
        assert response.headers["x-frame-count"] == str(original.shape[1]), path
        restored = np.frombuffer(response.content, dtype="<f4").reshape(original.shape)
        np.testing.assert_allclose(restored, original, rtol=0, atol=1e-2, err_msg=path)


def test_the_settle_is_served_like_the_trace(client):
    api, app = client
    record = make_record()
    settle = a_trace(frames=4)
    app.state.store.append(record, encode(a_trace(frames=9), settle))

    response = api.get(f"/api/runs/{record.run_id}/settle")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-frame-count"] == "4"
    restored = np.frombuffer(response.content, dtype="<f4").reshape(-1, TRACE_WIDTH)
    np.testing.assert_allclose(restored, settle, rtol=0, atol=1e-2)


def test_a_run_stored_before_settles_were_recorded_serves_an_empty_one(client):
    api, app = client
    record = make_record()
    app.state.store.append(record, encode(a_trace(frames=9)))
    response = api.get(f"/api/runs/{record.run_id}/settle")
    assert response.status_code == 200
    assert response.headers["x-frame-count"] == "0"
    assert response.headers["x-duck-count"] == "1"
    assert response.content == b""


def test_a_tugs_string_is_served_settle_first_then_timed(client):
    api, app = client
    record = make_record(event_id="tug-of-war")
    string = np.arange(3 * 17 * 3, dtype=np.float32).reshape(3, 17, 3)
    settle = -1 - np.arange(2 * 17 * 3, dtype=np.float32).reshape(2, 17, 3)
    app.state.store.append(record, encode(a_trace(frames=3, ducks=2), a_trace(frames=2, ducks=2), string, settle))
    response = api.get(f"/api/runs/{record.run_id}/string")
    assert response.status_code == 200
    assert [response.headers[h] for h in ("x-frame-count", "x-settle-frame-count", "x-point-count", "cache-control")] == ["3", "2", "17", "no-store"]
    assert len(response.content) == 5 * 51 * 4
    wire = np.frombuffer(response.content, dtype="<f4")
    np.testing.assert_array_equal(wire[:102], settle.ravel())
    np.testing.assert_array_equal(wire[102:], string.ravel())


def test_a_run_without_a_string_has_no_string_route(client):
    api, app = client
    record = make_record()
    app.state.store.append(record, encode(a_trace(frames=3)))
    response = api.get(f"/api/runs/{record.run_id}/string")
    assert response.status_code == 404 and record.run_id in response.json()["detail"]


def test_the_trace_byte_length_matches_the_frame_count(client):
    api, app = client
    record = make_record()
    app.state.store.append(record, encode(a_trace(frames=13)))
    content = api.get(f"/api/runs/{record.run_id}/trace").content
    assert len(content) == 13 * TRACE_WIDTH * 4


def test_an_unknown_run_is_a_404(client):
    """Assert our message, not just the status.

    FastAPI 404s an unmapped path all by itself with `{"detail": "Not Found"}`,
    so a status-only assertion passes whether the route exists or not — it did
    exactly that before these routes were written. Only our own handler says
    "no such run", so checking the detail is what distinguishes a working route
    from a deleted one.
    """
    api, _ = client
    for path in ("/api/runs/01NOPE", "/api/runs/01NOPE/trace", "/api/runs/01NOPE/settle"):
        response = api.get(path)
        assert response.status_code == 404, path
        assert "no such run" in response.json()["detail"], path


def heist_run(app, trace_seed=3, caught=None):
    """A heist run kept on seeds 1 to 5: seed s's trace s + 4 frames long, its settle 2, both offset by 100 s."""
    caught = {4: 6} if caught is None else caught
    record = make_record(event_id="sock-heist-6m", trace_seed=trace_seed)
    seeds = {s: SeedTrace(a_trace(frames=s + 4) + 100 * s, a_trace(frames=2) + 100 * s, caught.get(s)) for s in range(1, 6)}
    app.state.store.append(record, encode_seeds(seeds))
    return record, seeds


def frames(response):
    return np.frombuffer(response.content, dtype="<f4").reshape(-1, TRACE_WIDTH)


def test_a_heist_run_serves_its_trace_seed_unless_asked_another(client):
    api, app = client
    record, seeds = heist_run(app)
    plain = api.get(f"/api/runs/{record.run_id}/trace")
    assert plain.headers["x-frame-count"] == "7" and "x-caught-frame" not in plain.headers
    np.testing.assert_array_equal(frames(plain), seeds[3].trace)
    four = api.get(f"/api/runs/{record.run_id}/trace?seed=4")
    assert (four.headers["x-frame-count"], four.headers["x-caught-frame"]) == ("8", "6")
    np.testing.assert_array_equal(frames(four), seeds[4].trace)
    np.testing.assert_array_equal(frames(api.get(f"/api/runs/{record.run_id}/settle?seed=2")), seeds[2].settle)
    np.testing.assert_array_equal(frames(api.get(f"/api/runs/{record.run_id}/settle")), seeds[3].settle)


def test_a_seed_a_heist_run_kept_no_trace_of_is_a_404_not_a_500(client):
    api, app = client
    record, _ = heist_run(app)
    for path in ("trace?seed=9", "settle?seed=9"):
        response = api.get(f"/api/runs/{record.run_id}/{path}")
        assert response.status_code == 404 and "seed 9" in response.json()["detail"], path
    # Stored as one trace, before every seed was kept: there is no seed to serve, and that is a 404 too.
    old = make_record(event_id="sock-heist-6m", trace_seed=1)
    app.state.store.append(old, encode(a_trace(frames=5), a_trace(frames=2)))
    for path in ("trace", "settle"):
        assert api.get(f"/api/runs/{old.run_id}/{path}").status_code == 404, path


def test_another_event_serves_its_trace_seed_and_no_other(client):
    api, app = client
    record = make_record(trace_seed=2)
    app.state.store.append(record, encode(a_trace(frames=9), a_trace(frames=4)))
    plain, asked = (api.get(f"/api/runs/{record.run_id}/trace{q}") for q in ("", "?seed=2"))
    assert asked.status_code == 200 and asked.content == plain.content and "x-caught-frame" not in asked.headers
    assert api.get(f"/api/runs/{record.run_id}/settle?seed=2").headers["x-frame-count"] == "4"
    for path in ("trace?seed=1", "settle?seed=1"):
        response = api.get(f"/api/runs/{record.run_id}/{path}")
        assert response.status_code == 404 and "seed 1" in response.json()["detail"], path
