import json

from fastapi.testclient import TestClient

from arena.usage import MAX_HELD, UsageLog, to_folder
from arena.web.app import create_app
from arena.web.config import ArenaConfig


class Written:
    """A writer that keeps what it is handed, and can be made to fail a number of times first."""

    def __init__(self, failures=0):
        self.files: dict[str, list[dict]] = {}
        self.failures = failures

    def __call__(self, path, data):
        if self.failures:
            self.failures -= 1
            raise ConnectionError("the Hub is away")
        self.files[path] = [json.loads(line) for line in data.decode().splitlines()]


def hit(at="2026-11-03T10:00:00Z", **fields):
    return {"at": at, "visitor": "v1", "visit": "s1", "kind": "view", "page": "/", **fields}


def test_a_batch_is_one_jsonl_file_under_its_first_hits_day():
    written = Written()
    log = UsageLog(written)
    log.record(hit())
    log.record(hit(at="2026-11-04T00:00:01Z", kind="time", seconds=12))
    log.flush()
    [(path, lines)] = written.files.items()
    assert path.startswith("usage/2026-11-03/") and path.endswith(".jsonl")
    assert [line["kind"] for line in lines] == ["view", "time"]


def test_nothing_in_hand_writes_nothing():
    written = Written()
    UsageLog(written).flush()
    assert written.files == {}


def test_a_failed_write_keeps_the_batch_for_the_next_one():
    written = Written(failures=1)
    log = UsageLog(written)
    log.record(hit(page="/live"))
    log.flush()
    log.record(hit(page="/vote/got-a-talent"))
    log.flush()
    [lines] = written.files.values()
    assert [line["page"] for line in lines] == ["/live", "/vote/got-a-talent"]


def test_a_flood_is_dropped_past_the_cap():
    written = Written()
    log = UsageLog(written)
    for _ in range(MAX_HELD + 5):
        log.record(hit())
    log.flush()
    [lines] = written.files.values()
    assert len(lines) == MAX_HELD


def test_stop_writes_what_is_in_hand(tmp_path):
    log = UsageLog(to_folder(tmp_path))
    log.start()
    log.record(hit())
    log.stop()
    [path] = (tmp_path / "usage").rglob("*.jsonl")
    assert json.loads(path.read_text())["page"] == "/"


def client_for(tmp_path):
    config = ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")
    return TestClient(create_app(config))


def held(client):
    return client.app.state.usage._held


def test_a_view_is_held_with_its_time_and_whether_its_visitor_is_signed_in(tmp_path):
    client = client_for(tmp_path)
    sent = {"visitor": "a1b2c3d4-e5f6", "visit": "f6e5d4c3-b2a1", "kind": "view",
            "page": "/race/sprint-2m", "referrer": "huggingface.co", "embedded": True,
            "mobile": False}
    assert client.post("/api/usage", json=sent).status_code == 204
    [kept] = held(client)
    assert kept["signed_in"] is True  # locally the dev user is always signed in
    assert kept["at"].endswith("Z")
    assert {k: kept[k] for k in sent} == sent


def test_an_unknown_field_is_dropped_and_no_name_is_kept(tmp_path):
    client = client_for(tmp_path)
    client.post("/api/usage", json={"visitor": "a1b2c3d4", "visit": "e5f6a7b8", "kind": "out",
                                    "page": "/", "href": "https://store.pollen-robotics.com/x",
                                    "user": "coralie"})
    [kept] = held(client)
    assert "user" not in kept and "coralie" not in json.dumps(kept)


def test_a_malformed_hit_is_refused(tmp_path):
    client = client_for(tmp_path)
    base = {"visitor": "a1b2c3d4", "visit": "e5f6a7b8", "kind": "view", "page": "/"}
    for bad in ({**base, "kind": "click"}, {**base, "visitor": "<script>"},
                {**base, "page": "/" * 300}, {**base, "kind": "time", "seconds": -1}):
        assert client.post("/api/usage", json=bad).status_code == 422
    assert held(client) == []
