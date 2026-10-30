"""Facts are sentences with references; nothing invented, nothing technical."""

import dataclasses

import pytest

from arena.commentary.context import label, nature, result_facts, technical_text
from arena.evaluate import SeedResult
from arena.manifest import load_event
from arena.points import Receipt
from tests.test_store import WALKER, make_record


def seeds(finished, total=5, status="fall"):
    return tuple(
        SeedResult(seed=i + 1, status="finish" if i < finished else status,
                   time_s=12.0 if i < finished else None)
        for i in range(total)
    )


def run(user, score, at, finished=5, event="sprint-2m", run_id=None, **more):
    fields = {"user": user, "score": score, "submitted_at": at, "seeds_finished": finished,
              "per_seed": seeds(finished), "event_id": event, "policy_name": f"{user}-v1"}
    if run_id:
        fields["run_id"] = run_id
    fields.update(more)
    return make_record(**fields)


def test_technical_text_catches_paths_ids_and_filenames_but_not_prose():
    assert technical_text("see clips/01M2/landscape.mp4")
    assert technical_text("run 01a2b3c4d5e6f7a8b9")
    assert technical_text("the sprint_2m event")
    assert not technical_text("a 12.40 s sprint, every seed finished")
    assert label("walker-v3") and not label("<b>walker</b>") and not label("x" * 81)
    # Machine-shaped: a fact quoting it would have every turn that spoke it refused.
    assert not label("walker_v3")


def test_nature_reads_the_manifest():
    assert nature(load_event("sprint-2m")) == ("a 2 m sprint on foot", ("sprint",))
    assert nature(load_event("hill-climb-1m5")) == ("a 1.5 m climb up an 8 degree slope", ("hill",))
    assert nature(load_event("roller-sprint-2m")) == ("a 2 m race on roller skates", ("rollers",))
    assert nature(load_event("got-a-talent")) == (
        "a performance on a stage decided by the public's votes", ("vote",))
    assert nature(load_event("sock-heist-6m")) == (
        ("a 6 m sock heist: little microducks sneak up on a giant microduck's nest to steal its socks, "
         "and must freeze whenever it turns its head"), ("lights",))


def test_a_clean_run_states_event_participant_time_rank_gap_and_points():
    manifest = load_event("sprint-2m")
    leader = run("carol", 11.20, "2026-09-10T10:00:00Z", run_id="R0")
    mine = run("alice", 12.40, "2026-09-11T10:00:00Z", run_id="R1")
    receipts = [Receipt("alice", "first_event", 100, "sprint-2m", "R1", mine.submitted_at),
                Receipt("alice", "run", 10, "sprint-2m", "R1", mine.submitted_at),
                Receipt("carol", "podium", 250, "sprint-2m", "R0", leader.submitted_at)]
    facts = result_facts(mine, manifest, [leader, mine], receipts)
    by_ref = {f.ref: f for f in facts}
    assert by_ref["run#/event"].text == "The event is the 2 m Sprint, a 2 m sprint on foot."
    assert by_ref["run#/event"].tags == ("sprint",)
    participant = by_ref["run#/participant"]
    assert participant.text == "The participant is @alice, racing a policy named alice-v1."
    assert by_ref["run#/result"].text == "The mean finish time is 12.40 s, every one of the 5 seeds finished."
    assert by_ref["run#/result"].tags == ("clean",)
    board = by_ref["run#/board"]
    assert board.text == "On the 2 m Sprint board this run ranks 2 of 2, 1.20 s behind the leader, @carol."
    assert "podium" in board.tags
    points = by_ref["run#/points"]
    assert points.text == "This run earned 110 points: a first run on this event (100), a run of the day (10)."
    assert points.tags == ("first-run",)
    assert all(f.kind == "result" for f in facts)


def test_a_fall_is_said_and_an_open_board_is_said_as_such():
    manifest = load_event("hill-climb-1m5")
    fell = run("bob", 32.0, "2026-09-11T10:00:00Z", finished=3, event="hill-climb-1m5", run_id="R2")
    facts = {f.ref: f for f in result_facts(fell, manifest, [fell], [])}
    assert facts["run#/result"].text == (
        "The mean finish time is 32.00 s, with 3 of 5 seeds finished; an unfinished seed "
        "counts as the 60 s limit, and the duck fell on 2 of them."
    )
    assert facts["run#/result"].tags == ("fall",)
    assert facts["run#/board"].text == "This run opens the 1.5 m Hill Climb board: nobody else has published on it."
    assert "open-board" in facts["run#/board"].tags
    assert "run#/points" not in facts


def test_a_dnf_by_timeout_is_not_a_fall_and_a_voted_event_has_no_board():
    sprint = load_event("sprint-2m")
    timed_out = make_record(user="dan", score=50.0, seeds_finished=0, per_seed=seeds(0, status="timeout"),
                            submitted_at="2026-09-11T10:00:00Z", policy_name="<script>")
    facts = {f.ref: f for f in result_facts(timed_out, sprint, [timed_out], [])}
    assert facts["run#/result"].text == "@dan did not finish: none of the 5 seeds reached the line."
    # A policy name that is not a label is left out, never quoted.
    assert facts["run#/participant"].text == "The participant is @dan."
    talent = load_event("got-a-talent")
    voted = run("eve", 20.0, "2026-09-11T10:00:00Z", event="got-a-talent")
    refs = [f.ref for f in result_facts(voted, talent, [voted], [])]
    assert "run#/board" not in refs


def test_caught_by_the_giant_is_said_and_is_not_a_fall():
    lights = load_event("sock-heist-6m")
    per_seed = (SeedResult(1, "caught", None), SeedResult(2, "caught", None), SeedResult(3, "timeout", None),
                SeedResult(4, "caught", None), SeedResult(5, "timeout", None))
    caught = make_record(user="fay", score=150.0, seeds_finished=0, per_seed=per_seed,
                         event_id="sock-heist-6m", submitted_at="2026-09-11T10:00:00Z")
    facts = {f.ref: f for f in result_facts(caught, lights, [caught], [])}
    assert facts["run#/result"].text == (
        "@fay did not finish: none of the 5 seeds reached the line, the duck was caught moving "
        "while the giant looked on 3 of them."
    )
    assert facts["run#/result"].tags == ("dnf", "caught")
    per_seed = (SeedResult(1, "finish", 63.0), SeedResult(2, "fall", None), SeedResult(3, "caught", None),
                SeedResult(4, "finish", 70.0), SeedResult(5, "finish", 66.5))
    mixed = make_record(user="fay", score=99.9, seeds_finished=3, per_seed=per_seed,
                        event_id="sock-heist-6m", submitted_at="2026-09-11T10:00:00Z")
    facts = {f.ref: f for f in result_facts(mixed, lights, [mixed], [])}
    assert facts["run#/result"].text == (
        "The mean finish time is 99.90 s, with 3 of 5 seeds finished; an unfinished seed counts as "
        f"the {lights.time_limit_s:g} s limit, and the duck fell on 1 and was caught moving while the giant looked on 1 of them."
    )
    assert facts["run#/result"].tags == ("fall", "caught")


def test_the_authors_words_are_a_fact_when_they_read_as_prose():
    manifest = load_event("sprint-2m")
    mine = run("alice", 12.40, "2026-09-11T10:00:00Z", run_id="R1", description="It leans into every step.")
    (note,) = [f for f in result_facts(mine, manifest, [mine], []) if f.ref == "run#/note"]
    assert note.text == '@alice says about the policy: "It leans into every step."'
    assert note.kind == "notable"


def test_the_authors_words_on_several_lines_are_quoted_on_one():
    """A textarea's line breaks are layout, not markup: the words still read as prose."""
    manifest = load_event("sprint-2m")
    mine = run("alice", 12.40, "2026-09-11T10:00:00Z", run_id="R1",
               description="It leans into every step.\n\nThen it  sprints,\tlow.  ")
    (note,) = [f for f in result_facts(mine, manifest, [mine], []) if f.ref == "run#/note"]
    assert note.text == '@alice says about the policy: "It leans into every step. Then it sprints, low."'


@pytest.mark.parametrize("description", [
    "It runs at 0.8 m/s.",
    "Near 3 km/h on the flat, e.g. a brisk trot, and it turns at 2 rad/s.",
    "It walks at 0.5m/s².",
    "Tuned track_linear_velocity until the wobble went.",
])
def test_the_authors_words_may_give_a_unit_or_a_snake_case_name(description):
    manifest = load_event("sprint-2m")
    mine = run("alice", 12.40, "2026-09-11T10:00:00Z", run_id="R1", description=description)
    (note,) = [f for f in result_facts(mine, manifest, [mine], []) if f.ref == "run#/note"]
    assert note.text == f'@alice says about the policy: "{description}"'


@pytest.mark.parametrize("description", [
    None, "x" * 281, "<b>fast</b>", "run 01a2b3c4d5e6f7a8b9", "see C:\\ducks",
    "see https://example.com", "see www.duckpond", "see duckpond.com",
    "the reward is in env.py", "set it in challenge.toml", "the rewards live in rewards/gait/env",
    "see configs/walking", "copied from sprint_2m/rewards",
])
def test_no_note_when_the_words_are_missing_or_machine_shaped(description):
    manifest = load_event("sprint-2m")
    mine = run("alice", 12.40, "2026-09-11T10:00:00Z", run_id="R1", description=description)
    assert not [f for f in result_facts(mine, manifest, [mine], []) if f.ref == "run#/note"]


def stage_run(finished=True):
    """A MicroDuck Got a Talent record: one performance, its score its length."""
    return make_record(
        user="eve", event_id="got-a-talent", policy_name="eve-v1", score=20.0,
        seeds_finished=1 if finished else 0, submitted_at="2026-09-11T10:00:00Z",
        per_seed=(SeedResult(seed=1, status="finish" if finished else "fall",
                             time_s=20.0 if finished else None),),
    )


def test_a_performance_is_told_as_one_its_length_the_only_time():
    """No clock, no seeds, no line, no limit: the booth hears a performance and how long it lasts."""
    record = stage_run()
    facts = result_facts(record, load_event("got-a-talent"), [record], [])
    by_ref = {f.ref: f for f in facts}
    assert by_ref["run#/event"].text == (
        "The event is the MicroDuck Got a Talent, a performance on a stage decided by the public's votes.")
    assert by_ref["run#/participant"].text == "The participant is @eve, performing a policy named eve-v1."
    result = by_ref["run#/result"]
    assert result.text == "The performance lasts 20.00 s."
    assert result.tags == ("performance",)
    assert "run#/board" not in by_ref
    spoken = " ".join(f.text for f in facts).lower()
    for word in ("seed", "finish", "limit", "mean", "racing", "line"):
        assert word not in spoken, word


def test_a_performance_cut_short_says_so_without_a_time_or_a_fall():
    """A stage ends early only when the simulation breaks down: that is not a fall."""
    record = stage_run(finished=False)
    result = {f.ref: f for f in result_facts(record, load_event("got-a-talent"), [record], [])}["run#/result"]
    assert result.text == "The performance was cut short."
    assert result.tags == ("performance",)


ON_STAGE = {"rig": "legs", "start": {"x": 0.0, "y": 0.0, "yaw": 0.0}, "sound": None}


def troupe_run(*policies, policy_name="sitter"):
    """xia's performance, one duck per policy in order: "self" or a borrowed duck's credit."""
    return make_record(
        user="xia", event_id="got-a-talent", policy_name=policy_name, score=20.0, seeds_finished=1,
        per_seed=(SeedResult(seed=1, status="finish", time_s=20.0),), submitted_at="2026-09-11T10:00:00Z",
        cast=tuple({**ON_STAGE, "policy": policy} for policy in policies),
    )


def facts_of(record):
    return {f.ref: f for f in result_facts(record, load_event("got-a-talent"), [record], [])}


def test_a_troupe_is_named_in_order_each_borrowed_duck_by_its_author_and_policy():
    facts = facts_of(troupe_run("self", WALKER, "self"))
    assert facts["run#/troupe"].text == (
        "The performance has 3 ducks: @xia's sitter (the star), @yan's walker and @xia's sitter again.")
    assert facts["run#/troupe"].kind == "result"
    # The participant is still the entrant alone: votes and points are theirs.
    assert facts["run#/participant"].text == "The participant is @xia, performing a policy named sitter."


def test_a_pair_and_a_borrowed_policy_played_twice():
    assert facts_of(troupe_run("self", "self"))["run#/troupe"].text == (
        "The performance has 2 ducks: @xia's sitter (the star) and @xia's sitter again.")
    assert facts_of(troupe_run("self", WALKER, WALKER))["run#/troupe"].text == (
        "The performance has 3 ducks: @xia's sitter (the star), @yan's walker and @yan's walker again.")


def test_a_name_that_is_not_a_label_is_left_out_of_the_troupe():
    record = troupe_run("self", {**WALKER, "policy_name": "<b>walker</b>"}, policy_name="sitter_v2")
    assert facts_of(record)["run#/troupe"].text == (
        "The performance has 2 ducks: @xia's policy (the star) and @yan's policy.")


def test_one_duck_is_told_as_it_always_was():
    assert "run#/troupe" not in facts_of(stage_run())


RATED = (SeedResult(1, "won", 45.0, 12.0), SeedResult(2, "won", 45.0, 8.0), SeedResult(3, "lost", 45.0, -4.0),
         SeedResult(4, "pit_won", 30.0, 130.0), SeedResult(5, "pit_lost", 4.5, -140.0))


def test_a_rated_run_states_its_ground_its_wins_and_its_gap_in_centimetres():
    manifest = load_event("tug-of-war")
    leader = run("carol", 5.0, "2026-09-10T10:00:00Z", event="tug-of-war", run_id="R0", per_seed=RATED)
    mine = run("alice", 1.2, "2026-09-11T10:00:00Z", event="tug-of-war", run_id="R1", per_seed=RATED)
    facts = {f.ref: f for f in result_facts(mine, manifest, [leader, mine], [])}
    assert facts["run#/event"].text == ("The event is the Tug of War, a pulling contest against the Arena's reference duck: "
                                        "the two are tied by a string across a pit in a wrestling ring and each pulls by walking backwards.")
    assert facts["run#/participant"].text == "The participant is @alice, pulling with a policy named alice-v1."
    assert facts["run#/result"].text == (
        "The rating is 1.2 cm: the ground the duck won from the reference duck in 5 bouts, on average, 100 cm more "
        "for dragging it into the pit and 100 cm less for being dragged in; it won 3 of them.")
    assert facts["run#/result"].tags == ("won",)   # the traced seed, 1
    dragged = dataclasses.replace(mine, trace_seed=5)
    assert {f.ref: f for f in result_facts(dragged, manifest, [leader, dragged], [])}["run#/result"].tags == ("pit_lost",)
    assert facts["run#/board"].text == "On the Tug of War board this run ranks 2 of 2, 3.80 cm behind the leader, @carol."
    broken = dataclasses.replace(mine, score=-200.0, per_seed=tuple(SeedResult(s, "fault", 0.02, -200.0) for s in range(1, 6)))
    assert {f.ref: f for f in result_facts(broken, manifest, [leader, broken], [])}["run#/result"].text.endswith(
        "it won 0 of them. It faulted in 5, 200 cm less each: the bout stopped because the duck gave no valid action, "
        "or broke the simulation.")
    assert "close" in facts["run#/board"].tags
    assert nature(manifest)[1] == ("tug",)
