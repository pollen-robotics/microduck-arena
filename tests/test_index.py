from arena.constants import RUNNER_VERSION
from arena.evaluate import SeedResult
from arena.index import by_policy, by_user, copies, leaderboard, standing
from tests.test_store import make_record


def test_ranks_ascend_by_score():
    rows = leaderboard([
        make_record(user="slow", score=30.0),
        make_record(user="fast", score=20.0),
        make_record(user="mid", score=25.0),
    ])
    assert [r.record.user for r in rows] == ["fast", "mid", "slow"]
    assert [r.rank for r in rows] == [1, 2, 3]


def test_only_the_best_run_per_user_appears():
    rows = leaderboard([
        make_record(user="alice", score=30.0),
        make_record(user="alice", score=22.0),
        make_record(user="alice", score=27.0),
        make_record(user="bob", score=25.0),
    ])
    assert [(r.record.user, r.record.score) for r in rows] == [("alice", 22.0), ("bob", 25.0)]


def finishes(*times):
    """Seeds finished in these times: two runs that tie on the mean, raced apart."""
    return tuple(SeedResult(seed, "finish", t) for seed, t in enumerate(times, 1))


def test_a_tie_breaks_on_seeds_finished():
    rows = leaderboard([
        make_record(user="flaky", score=20.0, seeds_finished=3, per_seed=finishes(19.0, 21.0)),
        make_record(user="steady", score=20.0, seeds_finished=5),
    ])
    assert [r.record.user for r in rows] == ["steady", "flaky"]


def test_a_full_tie_breaks_on_earliest_submission():
    rows = leaderboard([
        make_record(user="later", score=20.0, seeds_finished=5, per_seed=finishes(19.0, 21.0),
                    submitted_at="2026-09-03T12:00:00Z"),
        make_record(user="earlier", score=20.0, seeds_finished=5,
                    submitted_at="2026-09-03T09:00:00Z"),
    ])
    assert [r.record.user for r in rows] == ["earlier", "later"]


def test_runs_from_another_runner_version_are_excluded():
    rows = leaderboard(
        [
            make_record(user="current", score=30.0, runner_version=RUNNER_VERSION),
            # Offset from the real version rather than a literal, so this can
            # never accidentally BE the current version after a bump — which
            # would leave the test asserting nothing.
            make_record(user="stale", score=10.0, runner_version=RUNNER_VERSION - 1),
        ],
        runner_version=RUNNER_VERSION,
    )
    assert [r.record.user for r in rows] == ["current"]


def test_an_empty_log_is_an_empty_board():
    assert leaderboard([]) == []


def test_a_dnf_entry_still_ranks_last_rather_than_vanishing():
    rows = leaderboard([
        make_record(user="finisher", score=20.0, seeds_finished=5),
        make_record(user="faller", score=45.0, seeds_finished=0),
    ])
    assert [r.record.user for r in rows] == ["finisher", "faller"]
    assert rows[-1].record.seeds_finished == 0


def test_by_user_collapses_a_persons_policies_into_one_row():
    """The public rule: one determined competitor cannot own the top ten."""
    rows = leaderboard(
        [
            make_record(user="alice", policy_name="v1", score=22.0),
            make_record(user="alice", policy_name="v2", score=19.0),
        ],
        entrant=by_user,
    )
    assert [r.record.policy_name for r in rows] == ["v2"]


def test_by_policy_lets_one_persons_policies_race_each_other():
    """The local rule.

    With a single signed-in user, ranking per person leaves one row no matter
    how many policies are tried — which makes the head-to-head replay, the whole
    point of running locally, impossible to use.
    """
    rows = leaderboard(
        [
            make_record(user="alice", policy_name="v1", score=22.0),
            make_record(user="alice", policy_name="v2", score=19.0),
        ],
        entrant=by_policy,
    )
    assert [r.record.policy_name for r in rows] == ["v2", "v1"]
    assert [r.rank for r in rows] == [1, 2]


def test_by_policy_still_keeps_only_the_best_run_of_each_policy():
    """Retrying a policy should improve its row, not add another."""
    rows = leaderboard(
        [
            make_record(user="alice", policy_name="v1", score=25.0),
            make_record(user="alice", policy_name="v1", score=20.0),
            make_record(user="alice", policy_name="v2", score=30.0),
        ],
        entrant=by_policy,
    )
    assert [(r.record.policy_name, r.record.score) for r in rows] == [("v1", 20.0), ("v2", 30.0)]


def test_by_policy_keeps_two_people_apart_even_with_the_same_policy_name():
    """The key is (person, policy) — two people entering "walker" are distinct."""
    rows = leaderboard(
        [
            make_record(user="alice", policy_name="walker", score=19.0),
            make_record(user="bob", policy_name="walker", score=21.0),
        ],
        entrant=by_policy,
    )
    assert [r.record.user for r in rows] == ["alice", "bob"]


def test_the_default_entrant_is_the_public_rule():
    """Unless a caller asks otherwise, the safe multi-user semantics apply."""
    rows = leaderboard(
        [
            make_record(user="alice", policy_name="v1", score=22.0),
            make_record(user="alice", policy_name="v2", score=19.0),
        ]
    )
    assert len(rows) == 1


def test_standing_places_a_run_among_everyone_elses_best():
    field = [make_record(run_id=f"R{i}", user=f"u{i}", score=10.0 + i) for i in range(10)]
    mine = make_record(run_id="ME", user="me", score=14.5)  # between R4 and R5
    s = standing([*field, mine], "ME")
    assert (s.rank, s.on_board) == (6, True)
    # The whole field, the run in its place: the page's table scrolls.
    assert [row.rank for row in s.board] == list(range(1, 12))
    assert [row.record.run_id for row in s.board][4:7] == ["R4", "ME", "R5"]


def test_standing_of_a_run_beaten_by_your_own_better_one():
    """Off the board, since the board keeps one row per person — but still placed
    against the others, with the author's own better row taken out of the way."""
    runs = [
        make_record(run_id="BEST", user="me", score=10.0),
        make_record(run_id="WORSE", user="me", score=12.0),
        make_record(run_id="B", user="bob", score=11.0),
    ]
    s = standing(runs, "WORSE")
    assert (s.rank, s.on_board) == (2, False)
    assert [row.record.run_id for row in s.board] == ["B", "WORSE"]


def tug(user, score, **more):
    return make_record(event_id="tug-of-war", user=user, score=score, **more)


def test_a_tug_board_ranks_the_strongest_first_and_keeps_each_ones_strongest():
    rows = leaderboard([tug("weak", 2.0), tug("strong", 4.0), tug("mid", 3.0), tug("strong", 5.0)])
    assert [(r.record.user, r.record.score) for r in rows] == [("strong", 5.0), ("mid", 3.0), ("weak", 2.0)]
    mine = tug("me", 4.0)
    assert standing([tug("a", 5.0), tug("b", 3.0), mine], mine.run_id).rank == 2


def test_a_tie_on_the_tug_goes_to_who_got_there_first():
    rows = leaderboard([tug("later", 7.0, submitted_at="2026-09-03T12:00:00Z", per_seed=finishes(6.0, 8.0)),
                        tug("earlier", 7.0, submitted_at="2026-09-03T09:00:00Z")])
    assert [r.record.user for r in rows] == ["earlier", "later"]


# Five seeds raced the way the Sock Heist's leader raced them on the Space.
HEIST = tuple(SeedResult(seed, "finish", t) for seed, t in enumerate((4.82, 5.24, 4.9, 4.86, 4.865), 1))


def raced(user, at, per_seed=HEIST, event_id="sock-heist-6m", **more):
    return make_record(user=user, submitted_at=f"2026-11-03T{at}:00Z", per_seed=per_seed,
                       score=4.937, event_id=event_id, **more)


def test_a_run_racing_exactly_like_another_players_earlier_run_is_a_copy_of_it():
    """Whatever its bytes: a re-upload with one more metadata field races like the original."""
    original = raced("rumezhak", "09:00", model_sha256="a" * 64)
    copy = raced("jrubiosainz", "09:19", model_sha256="b" * 64)
    assert copies([copy, original]) == {copy.run_id: original}


def test_a_copy_holds_no_place_and_the_original_keeps_its_own():
    original, copy = raced("rumezhak", "09:00"), raced("jrubiosainz", "09:19")
    third = make_record(event_id="sock-heist-6m", user="lphatnguyen", score=4.987)
    assert [r.record.user for r in leaderboard([original, copy, third])] == ["rumezhak", "lphatnguyen"]
    s = standing([original, copy, third], copy.run_id)
    assert (s.rank, s.on_board) == (2, False)


def test_a_copy_of_a_withdrawn_run_is_still_a_copy():
    original, copy = raced("rumezhak", "09:00"), raced("jrubiosainz", "09:19")
    assert leaderboard([original, copy], withdrawn=frozenset({original.run_id})) == []


def test_entering_your_own_policy_again_is_no_copy():
    assert copies([raced("rumezhak", "09:00"), raced("rumezhak", "10:00")]) == {}


def test_a_different_result_on_one_seed_is_another_policy():
    nudged = (*HEIST[:4], SeedResult(5, "finish", 4.86))
    assert copies([raced("rumezhak", "09:00"), raced("jrubiosainz", "09:19", per_seed=nudged)]) == {}


def test_runs_that_finish_no_seed_are_never_copies():
    """A fall carries no time: two different policies that fall on every seed look alike."""
    fell = tuple(SeedResult(seed, "fall", None) for seed in range(1, 6))
    runs = [raced(user, at, per_seed=fell, seeds_finished=0) for user, at in (("a", "09:00"), ("b", "10:00"))]
    assert copies(runs) == {}


def test_the_same_results_on_another_event_or_runner_are_no_copy():
    original = raced("rumezhak", "09:00")
    elsewhere = raced("jrubiosainz", "09:19", event_id="sprint-2m")
    older = raced("dadudu", "09:30", runner_version=original.runner_version - 1)
    assert copies([original, elsewhere, older]) == {}


def test_a_stage_performance_is_never_a_copy():
    """The same weights with another timeline are another performance."""
    runs = [raced(user, at, event_id="got-a-talent") for user, at in (("a", "09:00"), ("b", "10:00"))]
    assert copies(runs) == {}
