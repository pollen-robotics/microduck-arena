import json
from dataclasses import replace
from datetime import UTC, date, datetime, time

from arena.cup import (
    Cup,
    Entrant,
    MatchRecord,
    closed_cups,
    cup_times,
    cup_title,
    draw_groups,
    first_knockout,
    group_count,
    group_fixtures,
    group_table,
    is_match_id,
    match_id,
    match_label,
    match_title,
    parse_match_id,
    reached,
    round_name,
)
from arena.manifest import CupRules
from arena.match import BoutResult


def entrant(i, rating=None):
    return Entrant(f"p{i}", f"R{i}", f"duck {i}", "classic", float(10 - i if rating is None else rating), "s" * 64,
                   {"kind": "hub", "repo_id": f"p{i}/tug", "filename": "policy.onnx", "revision": "c" * 40, "url": "u"},
                   f"duck {i}")


Z = lambda *a: datetime(*a, tzinfo=UTC)
PARIS = lambda first: CupRules(first, time(18, 0), "Europe/Paris", 2.0, 4)


def test_a_cup_round_trips_through_its_three_files():
    match = MatchRecord("tug-of-war-0001-000", 0, "final", None, 0, 1, (BoutResult(0, 7, "west", "a", "pit", 4.5),), (1, 0), 0, "bouts")
    cup = Cup("tug-of-war", 1, "2026-10-30T15:00:00Z", "2026-10-30T17:00:00Z", "ab" * 16, (entrant(0), entrant(1)),
              ((0, 1),), matches=(match,), order={"starts_at": "2026-10-30T17:00:00Z", "segments": []})
    assert Cup.from_json(cup.draw_json(), cup.matches_json(), json.dumps(cup.order).encode()) == cup
    assert set(json.loads(cup.draw_json())) == {"event_id", "number", "close_at", "premiere_at", "secret", "entrants", "groups", "skipped"}
    assert Cup.from_json(cup.draw_json()) == replace(cup, matches=(), order=None)
    assert entrant(0).view() == {"user": "p0", "policy_name": "duck 0", "name": "duck 0", "livery": "classic", "rating": 10.0, "run_id": "R0"}


def test_a_match_id_names_its_event_cup_and_place():
    assert match_id("tug-of-war", 3, 12) == "tug-of-war-0003-012"
    assert parse_match_id("tug-of-war-0003-012") == ("tug-of-war", 3, 12)
    assert is_match_id("tug-of-war-0003-012") and not is_match_id("01M4Z4YCJ15T56BAXX1RPD")
    assert parse_match_id("01M4Z4YCJ15T56BAXX1RPD") is None and parse_match_id("tug-of-war-3-12") is None


def test_cup_times_follow_paris_across_the_october_change():
    rules = PARIS(date(2026, 10, 23))
    assert cup_times(rules, 1) == (Z(2026, 10, 23, 14), Z(2026, 10, 23, 16))
    assert cup_times(rules, 2) == (Z(2026, 10, 30, 15), Z(2026, 10, 30, 17))


def test_cup_times_in_summer():
    assert cup_times(PARIS(date(2026, 7, 3)), 2) == (Z(2026, 7, 10, 14), Z(2026, 7, 10, 16))


def test_a_cup_closes_at_its_own_instant_across_the_change():
    rules = PARIS(date(2026, 10, 23))
    moments = [(2026, 10, 23, 13, 59, 59), (2026, 10, 23, 14), (2026, 10, 30, 14, 59, 59), (2026, 10, 30, 15)]
    assert [closed_cups(rules, Z(*m)) for m in moments] == [0, 1, 1, 2]


def won(a, b, wins):
    return MatchRecord(f"m{a}{b}", 0, "group", "A", a, b, (), wins, a if wins[0] > wins[1] else b, "bouts")


def test_the_group_count_leaves_at_least_three_ducks_a_group():
    assert {n: group_count(n) for n in (3, 4, 5, 6, 11, 12, 23, 24, 47, 48)} == \
        {3: 1, 4: 1, 5: 1, 6: 2, 11: 2, 12: 4, 23: 4, 24: 8, 47: 8, 48: 16}


def test_the_draw_puts_one_duck_of_each_pot_in_every_group():
    ducks = [entrant(i, rating=8 - i) for i in range(8)]
    assert draw_groups(ducks, "0" * 32) == [[0, 2, 5, 6], [1, 3, 4, 7]]
    assert draw_groups(ducks, "f" * 32) == [[1, 2, 4, 7], [0, 3, 5, 6]]


def test_pots_rank_by_rating_then_user_and_the_last_pot_may_be_short():
    ducks = [replace(entrant(i, rating=r), user=u) for i, (r, u) in enumerate(zip([5, 5, 3, 2, 1, 9, 4], "bacdefg"))]
    assert draw_groups(ducks, "0" * 32) == [[5, 0, 3, 4], [1, 6, 2]]


def test_a_group_plays_a_circle_round_robin():
    assert group_fixtures([10, 11, 12, 13]) == [(10, 13), (11, 12), (10, 12), (13, 11), (10, 11), (12, 13)]
    assert group_fixtures([10, 11, 12]) == [(11, 12), (10, 12), (10, 11)]
    assert len(group_fixtures([1, 2, 3, 4, 5])) == 10


def test_a_table_ranks_wins_then_bout_difference():
    played = [won(0, 1, (1, 2)), won(0, 2, (2, 0)), won(0, 3, (2, 1)), won(1, 2, (2, 1)), won(1, 3, (0, 2)), won(2, 3, (2, 1))]
    assert group_table([0, 1, 2, 3], played, [4, 3, 2, 1]) == [0, 1, 3, 2]


def test_head_to_head_breaks_a_tie_before_the_rating():
    played = [won(0, 1, (1, 2)), won(0, 2, (2, 1)), won(0, 3, (2, 1)), won(1, 2, (2, 1)), won(1, 3, (1, 2)), won(2, 3, (2, 1))]
    assert group_table([0, 1, 2, 3], played, [4, 3, 1, 2]) == [1, 0, 2, 3]


def test_a_three_way_cycle_falls_to_the_rating_then_the_draw():
    cycle = [won(0, 1, (2, 1)), won(1, 2, (2, 1)), won(0, 2, (1, 2))]
    assert group_table([0, 1, 2], cycle, [1.0, 3.0, 2.0]) == [1, 2, 0]
    assert group_table([0, 1, 2], cycle, [2.0, 2.0, 2.0]) == [0, 1, 2]
    assert group_table([2, 0, 1], cycle, [2.0, 2.0, 2.0]) == [2, 0, 1]
    assert group_table([0, 1, 2], [], [1.0, 3.0, 2.0]) == [1, 2, 0]
    assert group_table([0, 1], [won(0, 5, (0, 2))], [1.0, 2.0]) == [1, 0]   # a match outside the group counts for nothing


def test_the_knockout_crosses_the_groups():
    """The bracket's two halves: a group's first and second are in different halves, so meet at the earliest in the final."""
    assert first_knockout([[2, 0, 1, 3]]) == [(2, 0)]                       # one group: 1st v 2nd is the final
    assert first_knockout([[0, 5, 3], [1, 4, 2]]) == [(0, 4), (1, 5)]       # A1–B2, B1–A2 are the semi-finals
    assert first_knockout([[0, 7], [1, 6], [2, 5], [3, 4]]) == [(0, 6), (2, 4), (1, 7), (3, 5)]   # A1–B2, C1–D2, B1–A2, D1–C2
    assert first_knockout([[g, 8 + g] for g in range(8)]) == [
        (0, 9), (2, 11), (4, 13), (6, 15), (1, 8), (3, 10), (5, 12), (7, 14)]   # A1–B2 … G1–H2, then B1–A2 … H1–G2
    assert [round_name(n) for n in (1, 2, 4, 8, 16)] == ["final", "semi-final", "quarter-final", "round of 16", "round of 32"]


def test_a_cup_is_named_on_air_by_its_event_and_number():
    assert cup_title("Tug of War", 12) == "Tug of War · Cup #12"


def test_a_title_says_the_stage_and_both_ducks_with_their_players():
    cup = Cup("tug-of-war", 1, "", "", "", tuple(entrant(i) for i in range(4)), ((0, 1, 2, 3),))
    assert match_title(cup, won(0, 3, (2, 0))) == "Group A · duck 0 (@p0) vs duck 3 (@p3)"
    assert (match_title(cup, replace(won(0, 1, (2, 1)), round="semi-final", group=None))
            == "Semi-final · duck 0 (@p0) vs duck 1 (@p1)")
    clash = replace(cup, entrants=(replace(entrant(0), name="duck 0 (@p0)"),) + cup.entrants[1:])
    assert match_title(clash, won(0, 3, (2, 0))) == "Group A · duck 0 (@p0) vs duck 3 (@p3)"   # the handle once


def test_reached_is_how_far_each_entrant_went():
    ko = lambda a, b, r: replace(won(a, b, (2, 0)), round=r, group=None)
    cup = Cup("tug-of-war", 1, "", "", "", tuple(entrant(i) for i in range(6)), ((0, 2, 4), (1, 3, 5)),
              matches=(won(0, 2, (2, 0)), ko(0, 3, "semi-final"), ko(1, 2, "semi-final"), ko(0, 1, "final")))
    assert reached(cup) == ["champion", "final", "semi-final", "semi-final", "group", "group"]
    assert [match_label(cup, m) for m in cup.matches] == ["Group A", "Semi-final 1", "Semi-final 2", "Final"]
