"""Every detector is a function of the log as it stood at the publish."""

from arena.commentary.notable import notable_facts, pick, profiles, situation
from arena.manifest import all_events
from arena.points import counting, receipts
from tests.test_commentary_context import run

EVENTS = {m.id: m for m in all_events()}


def facts_for(record, *others):
    s = situation(record, [record, *others], frozenset(), EVENTS)
    return {f.ref: f for f in notable_facts(s)}


def test_a_first_publication_is_a_first_in_the_arena():
    mine = run("alice", 12.4, "2026-09-11T10:00:00Z")
    facts = facts_for(mine)
    # The only angle a lone first run has: that it also opens the board is the
    # board fact's to say, and it says it.
    assert list(facts) == ["notable#/first-ever"]
    assert facts["notable#/first-ever"].text == "This is @alice's first publication in the arena."


def test_the_log_after_the_publish_is_invisible():
    mine = run("alice", 12.4, "2026-09-11T10:00:00Z")
    later = run("carol", 11.0, "2026-09-12T10:00:00Z")
    s = situation(mine, [mine, later], frozenset(), EVENTS)
    assert [r.run_id for r in s.on_event()] == [mine.run_id]


def test_a_first_time_under_a_threshold_is_a_record_for_the_event_or_a_milestone_for_the_player():
    old = run("alice", 13.1, "2026-09-10T10:00:00Z")
    other = run("carol", 12.6, "2026-09-10T11:00:00Z")
    mine = run("alice", 11.8, "2026-09-11T10:00:00Z")
    record = facts_for(mine, old, other)["notable#/record"]
    assert record.text == "At 11.80 s this is the first run under 12 s ever recorded on the 2 m Sprint."
    assert record.tags == ("record", "milestone")
    faster = run("carol", 11.5, "2026-09-10T12:00:00Z")
    milestone = facts_for(mine, old, other, faster)["notable#/milestone"]
    assert milestone.text == "At 11.80 s this is @alice's first run under 12 s on the 2 m Sprint."


def test_a_personal_best_says_the_margin_and_a_climb_names_who_was_passed():
    old = run("alice", 13.4, "2026-09-10T10:00:00Z")
    bob = run("bob", 12.0, "2026-09-10T11:00:00Z")
    carol = run("carol", 12.9, "2026-09-09T12:00:00Z")
    mine = run("alice", 12.4, "2026-09-11T10:00:00Z")
    facts = facts_for(mine, old, bob, carol)
    pb = facts["notable#/personal-best"]
    assert pb.text == "@alice beats their previous best on the 2 m Sprint, 13.40 s, by 1.00 s."
    assert pb.tags == ("pb",)
    climb = facts["notable#/climb"]
    assert climb.text == "@alice climbs from rank 3 to rank 2 on the 2 m Sprint, passing @carol."
    assert "podium" in climb.tags
    dropped = facts["notable#/opponent/carol"]
    assert dropped.text == ("@carol drops from rank 2 to rank 3 on the 2 m Sprint; their best "
                            "time there, 12.90 s, was published a day ago.")


def test_a_dnf_after_clean_runs_and_a_dnf_streak():
    clean = [run("alice", 12.0 + i, f"2026-09-0{i + 1}T10:00:00Z") for i in range(3)]
    dnf = run("alice", 50.0, "2026-09-11T10:00:00Z", finished=0)
    assert facts_for(dnf, *clean)["notable#/first-dnf"].text == (
        "@alice did not finish after 3 clean runs in a row on the 2 m Sprint.")
    second = run("alice", 50.0, "2026-09-12T10:00:00Z", finished=0)
    assert facts_for(second, *clean, dnf)["notable#/dnf-streak"].text == (
        "This is @alice's DNF number 2 in a row on the 2 m Sprint.")


def test_leading_two_events_publishing_on_every_event_and_a_busy_day():
    hill = run("alice", 30.0, "2026-09-10T09:00:00Z", event="hill-climb-1m5")
    roller = run("alice", 9.0, "2026-09-10T09:30:00Z", event="roller-sprint-2m")
    tug = run("alice", 4.0, "2026-09-10T09:15:00Z", event="tug-of-war")
    # Published, but no lead: a board's top run that finished no seed leads nothing.
    lights = run("alice", 60.0, "2026-09-10T10:00:00Z", finished=0, event="sock-heist-6m")
    first = run("alice", 12.9, "2026-09-11T08:00:00Z")
    second = run("alice", 12.7, "2026-09-11T09:00:00Z")
    mine = run("alice", 12.4, "2026-09-11T10:00:00Z")
    facts = facts_for(mine, hill, roller, tug, lights, first, second)
    # Titles come in `all_events()` order, which is by event id.
    assert facts["notable#/leads-events"].text == (
        "@alice now leads 4 events at once: 1.5 m Hill Climb, 2 m Roller Sprint, 2 m Sprint, Tug of War.")
    assert facts["notable#/regular"].text == "@alice has published on every open event."
    assert facts["notable#/busy-day"].text == "This is @alice's publication number 3 today."


def test_a_rivalry_counts_the_lead_changes_between_two_players():
    a1 = run("alice", 12.0, "2026-09-01T10:00:00Z")
    b1 = run("bob", 11.5, "2026-09-02T10:00:00Z")
    a2 = run("alice", 11.2, "2026-09-03T10:00:00Z")
    b2 = run("bob", 11.0, "2026-09-04T10:00:00Z")
    mine = run("alice", 10.8, "2026-09-05T10:00:00Z")
    rivalry = facts_for(mine, a1, b1, a2, b2)["notable#/rivalry"]
    assert rivalry.text == "@alice and @bob have traded the lead of the 2 m Sprint 4 times."


def test_pick_keeps_the_best_and_varies_the_angle():
    a1 = run("alice", 12.0, "2026-09-01T10:00:00Z")
    b1 = run("bob", 11.5, "2026-09-02T10:00:00Z")
    mine = run("alice", 11.2, "2026-09-03T10:00:00Z")
    s = situation(mine, [mine, a1, b1], frozenset(), EVENTS)
    ranked = notable_facts(s)
    assert [f.score for f in ranked] == sorted((f.score for f in ranked), reverse=True)
    chosen = pick(ranked, limit=2)
    assert len(chosen) == 2
    assert chosen[0].tags[0] != chosen[1].tags[0]


def test_a_withdrawn_run_is_not_in_the_world():
    gone = run("carol", 10.0, "2026-09-10T10:00:00Z", run_id="GONE")
    mine = run("alice", 12.4, "2026-09-11T10:00:00Z")
    s = situation(mine, [mine, gone], frozenset({"GONE"}), EVENTS)
    assert [r.run_id for r in s.on_event()] == [mine.run_id]


def test_profiles_give_the_season_of_the_author_and_of_who_the_board_measures_them_against():
    carol = run("carol", 11.2, "2026-09-10T10:00:00Z", run_id="R0")
    hill = run("alice", 30.0, "2026-09-10T12:00:00Z", event="hill-climb-1m5", run_id="R1")
    mine = run("alice", 12.4, "2026-09-11T10:00:00Z", run_id="R2")

    def profiles_for(record, *others):
        s = situation(record, [record, *others], frozenset(), EVENTS)
        return profiles(s, receipts(counting(list(s.runs), frozenset()), frozenset()))

    author, rival = profiles_for(mine, carol, hill)
    assert author.text == ("@alice has 620 points this season, rank 1 of 2 on the points ladder, "
                           "from 2 publications on 2 events.")
    assert rival.ref == "notable#/profile/carol"
    assert rival.text == ("@carol, who leads this board, has 360 points this season, rank 2 of 2 "
                          "on the points ladder, from 1 publication on 1 event.")
    back = run("carol", 11.0, "2026-09-12T10:00:00Z", run_id="R3")
    _, behind = profiles_for(back, carol, hill, mine)
    assert behind.text.startswith("@alice, next on this board, has 620 points")
    assert [f.ref for f in profiles_for(carol)] == ["notable#/profile"]


def test_a_rated_run_has_no_time_milestone_and_beats_its_best_by_winning_more_ground():
    first = run("alice", 3.0, "2026-09-10T10:00:00Z", event="tug-of-war")
    facts = facts_for(run("alice", 4.2, "2026-09-11T10:00:00Z", event="tug-of-war"), first)
    assert "notable#/milestone" not in facts and "notable#/record" not in facts
    assert facts["notable#/personal-best"].text == "@alice beats their previous best on the Tug of War, 3.00 cm, by 1.20 cm."


def test_a_tug_best_beaten_by_a_little_below_zero_is_no_big_margin():
    first = run("alice", -20.0, "2026-09-10T10:00:00Z", event="tug-of-war")
    facts = facts_for(run("alice", -19.9, "2026-09-11T10:00:00Z", event="tug-of-war"), first)
    assert facts["notable#/personal-best"].text == "@alice beats their previous best on the Tug of War, -20.00 cm, by 0.10 cm."
    assert facts["notable#/personal-best"].tags == ("pb",)


def test_a_tug_best_is_a_big_margin_from_five_centimetres_whatever_its_size():
    small = facts_for(run("alice", 1.7, "2026-09-11T10:00:00Z", event="tug-of-war"),
                      run("alice", 1.5, "2026-09-10T10:00:00Z", event="tug-of-war"))
    assert small["notable#/personal-best"].tags == ("pb",)
    big = facts_for(run("alice", 7.0, "2026-09-11T10:00:00Z", event="tug-of-war"),
                    run("alice", 1.5, "2026-09-10T10:00:00Z", event="tug-of-war"))
    assert big["notable#/personal-best"].tags == ("pb", "big-margin")


def test_a_displaced_rated_rival_is_quoted_in_centimetres():
    bob = run("bob", 3.0, "2026-09-01T10:00:00Z", event="tug-of-war")
    facts = facts_for(run("alice", 4.0, "2026-09-11T10:00:00Z", event="tug-of-war"), bob)
    assert facts["notable#/opponent/bob"].text == ("@bob drops from rank 1 to rank 2 on the Tug of War; their best "
                                                   "rating there, 3.00 cm, was published 10 days ago.")
