import json
from datetime import date

from stats import build, load, page_group

TODAY = date(2026, 11, 3)  # a Tuesday


def view(at, visitor, visit, page="/", **fields):
    return {"at": f"{at}T10:00:00Z", "visitor": visitor, "visit": visit, "kind": "view",
            "page": page, "signed_in": False, **fields}


def out(at, visitor, visit, href):
    return {"at": f"{at}T10:01:00Z", "visitor": visitor, "visit": visit, "kind": "out",
            "page": "/", "href": href, "signed_in": False}


def looked(at, visitor, visit, seconds):
    return {"at": f"{at}T10:02:00Z", "visitor": visitor, "visit": visit, "kind": "time",
            "page": "/", "seconds": seconds, "signed_in": False}


def run(at, user, event="sprint-2m"):
    return {"at": f"{at}T09:00:00Z", "user": user, "event": event}


def vote(at, voter):
    return {"at": f"{at}T09:00:00Z", "voter": voter, "event": "got-a-talent"}


STORE = "https://store.pollen-robotics.com/products/microduck?utm_source=microduck-arena"


def day_of(stats, day):
    return next(d for d in stats["days"] if d["day"] == day)


def test_a_visitor_is_new_on_their_first_day_only():
    hits = [view("2026-11-02", "ann", "a1"), view("2026-11-03", "ann", "a2"),
            view("2026-11-03", "bob", "b1")]
    stats = build(hits, [], [], TODAY)
    assert day_of(stats, "2026-11-02").items() >= {"visitors": 1, "new_visitors": 1}.items()
    assert day_of(stats, "2026-11-03").items() >= {"visitors": 2, "new_visitors": 1, "visits": 2}.items()


def test_a_visit_is_measured_in_pages_and_minutes_looked():
    hits = [view("2026-11-03", "ann", "a1"), view("2026-11-03", "ann", "a1", "/live"),
            looked("2026-11-03", "ann", "a1", 150), view("2026-11-03", "bob", "b1"),
            looked("2026-11-03", "bob", "b1", 30)]
    today = day_of(build(hits, [], [], TODAY), "2026-11-03")
    assert today["pages_per_visit"] == 1.5
    assert today["minutes_per_visit"] == 1.5


def test_only_the_store_counts_as_a_buy_click():
    hits = [view("2026-11-03", "ann", "a1"), out("2026-11-03", "ann", "a1", STORE),
            out("2026-11-03", "ann", "a1", STORE), out("2026-11-03", "bob", "b1", "https://discord.com/x")]
    stats = build(hits, [], [], TODAY)
    assert day_of(stats, "2026-11-03")["buy_clicks"] == 2
    week = stats["periods"]["7"]["now"]
    assert week["buy_clicks"] == 2 and week["buyers"] == 1
    assert {row["label"]: row["clicks"] for row in stats["periods"]["7"]["outs"]} == {
        "Store (buy)": 2, "Discord": 1}


def test_players_are_counted_per_week_new_or_returning():
    runs = [run("2026-10-20", "ann"), run("2026-10-27", "ann"), run("2026-10-28", "ann"),
            run("2026-10-29", "bob")]
    weeks = {w["week"]: w for w in build([], runs, [], TODAY)["weeks"]}
    assert weeks["2026-10-19"].items() >= {"players": 1, "new_players": 1}.items()
    assert weeks["2026-10-26"].items() >= {"players": 2, "new_players": 1, "runs": {"sprint-2m": 3}}.items()
    assert weeks["2026-11-02"]["players"] == 0


def test_a_period_is_compared_with_the_one_before_it():
    runs = [run("2026-10-25", "ann"), run("2026-10-30", "ann"), run("2026-11-01", "bob")]
    week = build([], runs, [vote("2026-11-03", "cy")], TODAY)["periods"]["7"]
    assert week["now"].items() >= {"players": 2, "new_players": 1, "runs": 2, "voters": 1}.items()
    assert week["before"].items() >= {"players": 1, "runs": 1, "voters": 0}.items()


def test_members_add_up_players_and_voters_once_each():
    stats = build([], [run("2026-11-01", "ann")], [vote("2026-11-02", "ann"), vote("2026-11-03", "bob")], TODAY)
    assert stats["members"][-1] == {"day": "2026-11-03", "players": 1, "voters": 2, "members": 2}


def test_pages_are_grouped_by_kind():
    assert page_group("/") == "Home"
    assert page_group("/e/sprint-2m") == "Board · sprint-2m"
    assert page_group("/r/01M66D216JMZQ2QRQ7DZA1") == "A run's page"
    assert page_group("/p/jrubiosainz") == "A player's page"
    assert page_group("/guides/start?section=x") == "Guides"


def test_load_reads_the_run_log_and_the_usage_log(tmp_path):
    runs, usage = tmp_path / "runs", tmp_path / "usage"
    (runs / "runs" / "sprint-2m").mkdir(parents=True)
    (runs / "runs" / "sprint-2m" / "R1.json").write_text(json.dumps(
        {"run_id": "R1", "event_id": "sprint-2m", "user": "ann", "submitted_at": "2026-11-01T09:00:00Z"}))
    (runs / "votes" / "2026-11-02").mkdir(parents=True)
    (runs / "votes" / "2026-11-02" / "B1.json").write_text(json.dumps(
        {"voter": "bob", "event_id": "got-a-talent", "cast_at": "2026-11-02T09:00:00Z"}))
    (usage / "usage" / "2026-11-03").mkdir(parents=True)
    (usage / "usage" / "2026-11-03" / "U1.jsonl").write_text(
        json.dumps(view("2026-11-03", "ann", "a1")) + "\n")
    hits, runs_, votes = load(runs, usage)
    assert [h["visitor"] for h in hits] == ["ann"]
    assert runs_ == [run("2026-11-01", "ann")]
    assert votes == [{"at": "2026-11-02T09:00:00Z", "voter": "bob", "event": "got-a-talent"}]
