from datetime import timedelta

import pytest

from arena.constants import RUNNER_VERSION
from arena.points import (
    RUNS_PER_DAY,
    SCHEDULE,
    Card,
    boards_by_user,
    counting,
    receipts,
    standings,
)
from tests.test_cup_view import REVEAL, START_ISO
from tests.test_cupworker import played_cup
from tests.test_store import make_record


def acts(rs, act):
    return [r for r in rs if r.act == act]


def test_counting_applies_the_boards_filter_and_orders_by_time():
    old = make_record(user="alice", runner_version=RUNNER_VERSION - 1)
    gone = make_record(user="alice", submitted_at="2026-09-03T11:00:00Z")
    late = make_record(user="alice", submitted_at="2026-09-03T12:00:00Z")
    early = make_record(user="alice", submitted_at="2026-09-03T09:00:00Z")
    kept = counting([old, gone, late, early], withdrawn=frozenset({gone.run_id}))
    assert kept == [early, late]


def test_first_publication_on_an_event_pays_once_per_event():
    a1 = make_record(user="alice", event_id="sprint-2m", submitted_at="2026-09-03T09:00:00Z")
    a2 = make_record(user="alice", event_id="sprint-2m", submitted_at="2026-09-03T10:00:00Z")
    a3 = make_record(user="alice", event_id="hill-climb-1m5", submitted_at="2026-09-03T11:00:00Z")
    firsts = acts(receipts([a2, a3, a1], frozenset()), "first_event")
    assert [(r.event_id, r.source_id, r.points) for r in firsts] == [
        ("sprint-2m", a1.run_id, SCHEDULE["first_event"]),
        ("hill-climb-1m5", a3.run_id, SCHEDULE["first_event"]),
    ]


def test_a_run_pays_ten_capped_at_three_per_utc_day_across_events():
    day = [
        make_record(user="alice", event_id="sprint-2m", submitted_at=f"2026-09-03T1{i}:00:00Z")
        for i in range(3)
    ] + [make_record(user="alice", event_id="hill-climb-1m5", submitted_at="2026-09-03T14:00:00Z")]
    tomorrow = make_record(user="alice", submitted_at="2026-09-04T08:00:00Z")
    runs = acts(receipts(day + [tomorrow], frozenset()), "run")
    assert len(runs) == RUNS_PER_DAY + 1
    assert {r.source_id for r in runs} == {d.run_id for d in day[:3]} | {tomorrow.run_id}
    assert all(r.points == SCHEDULE["run"] for r in runs)


def test_beating_your_own_best_pays_once_per_event_on_the_first_improvement():
    worse = make_record(user="alice", score=30.0, submitted_at="2026-09-03T09:00:00Z")
    better = make_record(user="alice", score=25.0, submitted_at="2026-09-03T10:00:00Z")
    same = make_record(user="alice", score=25.0, submitted_at="2026-09-03T11:00:00Z")
    best = make_record(user="alice", score=20.0, submitted_at="2026-09-03T12:00:00Z")
    own = acts(receipts([worse, better, same, best], frozenset()), "own_best")
    assert [(r.source_id, r.points) for r in own] == [(better.run_id, SCHEDULE["own_best"])]


def test_a_voted_event_pays_no_own_best():
    """A voted event's score measures nothing to beat (a stage's is the performance's length),
    so a shorter performance is no personal best; the same pair of runs on a timed event pays one."""
    from arena.manifest import Vote

    rules = {"got-a-talent": Vote(ballot_min=2, ballot_max=4, window_days=7, per_day=20)}
    long = make_record(user="alice", event_id="got-a-talent", score=20.0,
                       submitted_at="2026-09-03T09:00:00Z")
    short = make_record(user="alice", event_id="got-a-talent", score=12.0,
                        submitted_at="2026-09-03T10:00:00Z")
    assert acts(receipts([long, short], frozenset(), voted=rules), "own_best") == []
    timed = [make_record(user="alice", event_id="sprint-2m", score=s, submitted_at=r.submitted_at)
             for s, r in ((20.0, long), (12.0, short))]
    assert len(acts(receipts(timed, frozenset(), voted=rules), "own_best")) == 1


def test_a_single_run_never_pays_own_best():
    only = make_record(user="alice")
    assert acts(receipts([only], frozenset()), "own_best") == []


def test_withdrawn_and_old_runner_runs_pay_nothing():
    gone = make_record(user="alice")
    old = make_record(user="bob", runner_version=RUNNER_VERSION - 1)
    assert receipts([gone, old], frozenset({gone.run_id})) == []


def test_a_copy_pays_nothing_and_leaves_the_podium_to_the_next_player():
    leader = make_record(user="rumezhak", score=4.937, submitted_at="2026-11-03T09:00:00Z")
    copy = make_record(user="jrubiosainz", score=4.937, submitted_at="2026-11-03T09:19:00Z")
    third = make_record(user="lphatnguyen", score=4.987, submitted_at="2026-11-02T19:00:00Z")
    rs = receipts([leader, copy, third], frozenset())
    assert [r for r in rs if r.source_id == copy.run_id] == []
    assert [(r.user, r.points) for r in acts(rs, "podium")] == [("rumezhak", 250), ("lphatnguyen", 150)]


def test_receipts_carry_the_runs_own_timestamp():
    run = make_record(user="alice", submitted_at="2026-09-03T09:30:00Z")
    assert {r.at for r in receipts([run], frozenset())} == {"2026-09-03T09:30:00Z"}


def test_podium_pays_the_top_three_by_user_and_skips_dnf_rows():
    first = make_record(user="ann", score=20.0, submitted_at="2026-09-03T09:00:00Z")
    first_again = make_record(user="ann", score=21.0, policy_name="v2")
    second = make_record(user="bob", score=22.0)
    third = make_record(user="cid", score=23.0)
    fourth = make_record(user="dee", score=24.0)
    dnf = make_record(user="eve", score=50.0, seeds_finished=0)
    podium = acts(receipts([dnf, fourth, third, first_again, second, first], frozenset()), "podium")
    assert [(r.user, r.points, r.source_id) for r in podium] == [
        ("ann", 250, first.run_id),
        ("bob", 150, second.run_id),
        ("cid", 100, third.run_id),
    ]


def test_a_lone_dnf_is_not_a_podium():
    dnf = make_record(user="eve", score=50.0, seeds_finished=0)
    assert acts(receipts([dnf], frozenset()), "podium") == []


def test_podium_is_per_event():
    sprint = make_record(user="ann", event_id="sprint-2m")
    hill = make_record(user="ann", event_id="hill-climb-1m5")
    podium = acts(receipts([sprint, hill], frozenset()), "podium")
    assert sorted(r.event_id for r in podium) == ["hill-climb-1m5", "sprint-2m"]
    assert all(r.points == 250 for r in podium)


def test_boards_by_user_collapse_a_players_policies_to_one_row():
    v1 = make_record(user="ann", policy_name="v1", score=25.0)
    v2 = make_record(user="ann", policy_name="v2", score=20.0)
    bob = make_record(user="bob", score=22.0)
    rows = boards_by_user([v1, v2, bob], frozenset())["sprint-2m"]
    assert [(r.rank, r.record.user, r.record.run_id) for r in rows] == [
        (1, "ann", v2.run_id),
        (2, "bob", bob.run_id),
    ]


def test_standings_sum_receipts_and_rank_by_total():
    ann = make_record(user="ann", score=20.0, submitted_at="2026-09-03T09:00:00Z")
    bob = make_record(user="bob", score=22.0, submitted_at="2026-09-03T10:00:00Z")
    cards = standings(receipts([ann, bob], frozenset()))
    # ann: first_event 100 + run 10 + podium 250; bob: 100 + 10 + 150.
    assert cards == [Card(1, "ann", 360), Card(2, "bob", 260)]


def test_a_tied_total_goes_to_whoever_published_first_then_by_name():
    later = make_record(user="zed", event_id="sprint-2m", submitted_at="2026-09-03T10:00:00Z")
    earlier = make_record(user="amy", event_id="hill-climb-1m5", submitted_at="2026-09-03T09:00:00Z")
    same_time = make_record(user="bea", event_id="roller-sprint-2m",
                            submitted_at="2026-09-03T09:00:00Z")
    cards = standings(receipts([later, earlier, same_time], frozenset()))
    assert [c.user for c in cards] == ["amy", "bea", "zed"]
    assert [c.rank for c in cards] == [1, 2, 3]


def test_standings_of_nothing_is_empty():
    assert standings([]) == []


def test_beating_your_best_on_seeds_alone_pays_own_best():
    flaky = make_record(user="alice", score=20.0, seeds_finished=3,
                        submitted_at="2026-09-03T09:00:00Z")
    steady = make_record(user="alice", score=20.0, seeds_finished=5,
                         submitted_at="2026-09-03T10:00:00Z")
    own = acts(receipts([flaky, steady], frozenset()), "own_best")
    assert [r.source_id for r in own] == [steady.run_id]


def test_withdrawing_the_first_run_moves_first_event_to_the_next():
    first = make_record(user="alice", submitted_at="2026-09-03T09:00:00Z")
    second = make_record(user="alice", submitted_at="2026-09-03T10:00:00Z")
    firsts = acts(receipts([first, second], frozenset({first.run_id})), "first_event")
    assert [r.source_id for r in firsts] == [second.run_id]


def test_a_ballot_pays_its_voter_two_capped_at_the_manifests_per_day():
    from datetime import UTC, datetime

    from arena.manifest import Vote
    from tests.test_ballots import make_ballot

    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)
    rules = {"got-a-talent": Vote(ballot_min=2, ballot_max=4, window_days=7, per_day=2)}
    today = [
        make_ballot(voter="ann", cast_at=f"2026-09-15T0{i}:00:00Z") for i in range(3)
    ]
    yesterday = [make_ballot(voter="ann", cast_at="2026-09-14T09:00:00Z")]

    paid = acts(
        receipts([], frozenset(), ballots=today + yesterday, voted=rules, now=now), "ballot"
    )
    assert [r.points for r in paid] == [SCHEDULE["ballot"]] * 3
    assert {r.user for r in paid} == {"ann"}


def test_a_ballot_on_an_event_that_does_not_take_votes_pays_nothing():
    from datetime import UTC, datetime

    from tests.test_ballots import make_ballot

    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)
    stray = make_ballot(event_id="sprint-2m", cast_at="2026-09-15T09:00:00Z")
    assert acts(receipts([], frozenset(), ballots=[stray], voted={}, now=now), "ballot") == []


def test_a_voted_events_podium_is_paid_on_votes_not_on_time():
    from datetime import UTC, datetime

    from arena.manifest import Vote
    from tests.test_ballots import make_ballot

    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)
    rules = {"got-a-talent": Vote(ballot_min=2, ballot_max=4, window_days=7, per_day=20)}
    quick = make_record(
        user="ann", event_id="got-a-talent", score=10.0, submitted_at="2026-09-14T09:00:00Z"
    )
    slow = make_record(
        user="bob", event_id="got-a-talent", score=40.0, submitted_at="2026-09-14T10:00:00Z"
    )
    loved = [
        make_ballot(
            candidates=(quick.run_id, slow.run_id),
            choice=slow.run_id,
            cast_at="2026-09-15T09:00:00Z",
        )
    ]
    rows = boards_by_user([quick, slow], frozenset(), ballots=loved, voted=rules, now=now)
    assert [r.record.user for r in rows["got-a-talent"]] == ["bob", "ann"]

    # bob is slow but voted-for; ann is quick but unvoted. bob takes the
    # podium, ann does not — a zero-vote row is unpaid even where it ranks
    # second only on its head start, which is not a place held.
    podium = acts(
        receipts([quick, slow], frozenset(), ballots=loved, voted=rules, now=now), "podium"
    )
    assert [(r.user, r.points) for r in podium] == [("bob", 250)]


def test_a_zero_vote_row_is_unpaid_even_beside_a_row_that_holds_votes():
    """Pins the distinction a per-BOARD guard would miss: it is not enough for
    the board to have SOME votes cast anywhere on it. Each row's own vote
    count gates its own podium pay, so a voted entry and its unvoted rival on
    the very same ballot do not both take a place."""
    from datetime import UTC, datetime

    from arena.manifest import Vote
    from tests.test_ballots import make_ballot

    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)
    rules = {"got-a-talent": Vote(ballot_min=2, ballot_max=4, window_days=7, per_day=20)}
    voted_for = make_record(
        user="bob", event_id="got-a-talent", submitted_at="2026-09-14T09:00:00Z"
    )
    unvoted = make_record(
        user="ann", event_id="got-a-talent", submitted_at="2026-09-14T10:00:00Z"
    )
    ballots = [
        make_ballot(
            candidates=(voted_for.run_id, unvoted.run_id),
            choice=voted_for.run_id,
            cast_at="2026-09-15T09:00:00Z",
        )
    ]
    podium = acts(
        receipts([voted_for, unvoted], frozenset(), ballots=ballots, voted=rules, now=now),
        "podium",
    )
    assert [(r.user, r.points) for r in podium] == [("bob", 250)]


def test_a_voted_events_podium_pays_nothing_when_nobody_has_voted():
    from datetime import UTC, datetime

    from arena.manifest import Vote

    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)
    rules = {"got-a-talent": Vote(ballot_min=2, ballot_max=4, window_days=7, per_day=20)}
    ann = make_record(user="ann", event_id="got-a-talent", score=10.0)
    bob = make_record(user="bob", event_id="got-a-talent", score=20.0)
    cid = make_record(user="cid", event_id="got-a-talent", score=30.0)

    podium = acts(
        receipts([ann, bob, cid], frozenset(), ballots=[], voted=rules, now=now), "podium"
    )
    assert podium == []


def test_a_ballot_outside_its_events_own_window_pays_nothing():
    from datetime import UTC, datetime

    from arena.manifest import Vote
    from tests.test_ballots import make_ballot

    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)
    rules = {"got-a-talent": Vote(ballot_min=2, ballot_max=4, window_days=1, per_day=20)}
    stale = make_ballot(cast_at="2026-09-13T09:00:00Z")  # two days old; the window is one day

    paid = acts(receipts([], frozenset(), ballots=[stale], voted=rules, now=now), "ballot")
    assert paid == []


def test_two_votable_events_each_pay_on_their_own_window_not_the_widest():
    from datetime import UTC, datetime

    from arena.manifest import Vote
    from tests.test_ballots import make_ballot

    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=UTC)
    rules = {
        "got-a-talent": Vote(ballot_min=2, ballot_max=4, window_days=1, per_day=20),
        "sprint-2m": Vote(ballot_min=2, ballot_max=4, window_days=30, per_day=20),
    }
    # Five days old: outside the one-day got-a-talent window, inside sprint-2m's
    # thirty-day one. A payment loop windowed against the WIDEST window any
    # event declares would pay both; each event's own window pays only one.
    old_on_the_short_event = make_ballot(
        event_id="got-a-talent", voter="ann", cast_at="2026-09-10T09:00:00Z"
    )
    old_on_the_long_event = make_ballot(
        event_id="sprint-2m", voter="bob", cast_at="2026-09-10T09:00:00Z"
    )

    paid = acts(
        receipts(
            [],
            frozenset(),
            ballots=[old_on_the_short_event, old_on_the_long_event],
            voted=rules,
            now=now,
        ),
        "ballot",
    )
    assert {r.user for r in paid} == {"bob"}


def test_a_stronger_tug_rating_is_a_personal_best_and_the_podium_pays_the_strongest():
    first, better, weaker = (make_record(user="alice", event_id="tug-of-war", score=s, submitted_at=f"2026-09-03T{h}:00:00Z")
                             for s, h in ((3.0, "09"), (4.0, "10"), (2.0, "11")))
    assert [r.source_id for r in acts(receipts([first, better, weaker], frozenset()), "own_best")] == [better.run_id]
    runs = [make_record(user=u, event_id="tug-of-war", score=s) for u, s in (("a", 2.0), ("b", 5.0), ("c", 3.0))]
    assert [(r.user, r.points) for r in acts(receipts(runs, frozenset()), "podium")] == [("b", 250), ("c", 150), ("a", 100)]


def test_a_cup_pays_its_podium_from_the_finals_reveal():
    cup = played_cup(6, starts_at=START_ISO)
    assert receipts([], frozenset(), cups=[cup], now=REVEAL(8) - timedelta(milliseconds=1)) == []
    paid = receipts([], frozenset(), cups=[cup], now=REVEAL(8))
    final, (semi_a, semi_b) = cup.matches[8].match_id, (cup.matches[6].match_id, cup.matches[7].match_id)
    assert sorted((r.user, r.act, r.points, r.source_id) for r in paid) == sorted([
        ("p0", "cup_champion", 250, final), ("p1", "cup_final", 150, final),
        ("p2", "cup_semi", 100, semi_a), ("p3", "cup_semi", 100, semi_b)])
    assert {r.at for r in paid} == {"2026-10-30T17:01:44Z"}   # the final's clip ends 9 x 11.6 s into the show
    with pytest.raises(ValueError):
        receipts([], frozenset(), cups=[cup])
