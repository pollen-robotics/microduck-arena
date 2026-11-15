from dataclasses import replace

from arena.commentary.cup import (
    cup_facts,
    duck,
    group_rounds,
    player_profiles,
    screen_view,
    stage_of,
)
from arena.store import LocalStore
from tests.show_cups import MANIFEST, played_cup
from tests.test_store import make_record

CUP = played_cup()
CUP2 = played_cup(number=2)


def texts(cup, before, history=()):
    return [fact.text for fact in cup_facts(cup, before, history, MANIFEST)]


def test_a_match_s_stage_reads_like_a_broadcast():
    assert stage_of(CUP, 0) == "group round 1 of 3 in Group A"
    assert stage_of(CUP, 1) == "group round 1 of 3 in Group B"
    assert stage_of(CUP, 6) == "the semi-final (1 of 2)"
    assert stage_of(CUP, 8) == "the final"
    assert group_rounds(CUP) == 3
    assert duck(CUP.entrants[0]) == "puller 0 (@p0)"


def test_the_opening_knows_the_field_and_the_draw():
    opening = texts(CUP, 0)
    assert ("This is the Tug of War Cup #1, 6 players: 2 groups where everyone meets everyone, then a knockout "
            "between the top two of each. Two ducks tied by a 1.0 m string pull across a pit 30 cm wide in a 3 m "
            "wrestling ring, walking backwards. A match is first to 2 bouts, the ducks swapping sides after each; a duck "
            "that drops into the pit loses the bout, and at the time limit the duck the marker moved away from "
            "loses. Level after 5 bouts, the higher rating goes through.") in opening
    assert "Group A: puller 0 (@p0), puller 2 (@p2) and puller 4 (@p4), no match played yet." in opening
    assert ("Ratings against the reference duck, at the top: puller 0 (@p0) 50.0 cm, puller 1 (@p1) 45.0 cm, "
            "puller 2 (@p2) 40.0 cm; at the bottom: puller 5 (@p5) 25.0 cm.") in opening
    assert not any(fact.ref.startswith("cup#/last") for fact in cup_facts(CUP, 0, (), MANIFEST))
    single = texts(played_cup(4, groups=((0, 1, 2, 3),)), 0)
    assert any(t.startswith("This is the Tug of War Cup #1, 4 players: one group where everyone meets everyone, "
                            "then a final between its top two. Two ducks") for t in single)
    assert ("Ratings against the reference duck: puller 0 (@p0) 50.0 cm, puller 1 (@p1) 45.0 cm, "
            "puller 2 (@p2) 40.0 cm, puller 3 (@p3) 35.0 cm.") in single


def test_the_knockout_s_eve_knows_who_went_through():
    eve = texts(CUP, 6)
    assert ("Through to the semi-finals: Group A: puller 0 (@p0) and puller 2 (@p2); "
            "Group B: puller 1 (@p1) and puller 3 (@p3).") in eve
    assert "Next is match 7 of 9, the semi-final (1 of 2): puller 0 (@p0) against puller 3 (@p3)." in eve
    assert ("Against the reference duck puller 0 (@p0) rates 50.0 cm and puller 3 (@p3) 35.0 cm: "
            "puller 0 (@p0) is the favourite by 15.0 cm.") in eve
    view = screen_view(CUP, 6, MANIFEST)
    assert view["stage"] == "Semi-final"
    assert view["knockout"] == [
        {"round": "semi-final", "matches": [{"a": "puller 0 (@p0)", "b": "puller 3 (@p3)", "winner": None, "next": True},
                                            {"a": "puller 1 (@p1)", "b": "puller 2 (@p2)", "winner": None, "next": False}]},
        {"round": "final", "matches": [{"a": None, "b": None, "winner": None, "next": False}]}]


def test_two_close_ducks_are_too_close_to_call():
    close = played_cup(4, groups=((0, 1, 2, 3),))
    close = replace(close, entrants=tuple(replace(e, rating=50.0 - k) for k, e in enumerate(close.entrants)))
    assert ("Against the reference duck puller 0 (@p0) rates 50.0 cm and puller 1 (@p1) 49.0 cm: "
            "only 1.0 cm apart, too close to call.") in texts(close, 6)


def test_after_the_final_the_champion_and_the_next_cup():
    over = texts(CUP, 9)
    assert "puller 0 (@p0) wins the Tug of War Cup #1, beating puller 1 (@p1) 2–0 in the final." in over
    assert "Cup #2 premieres on Friday 6 November at 18:00, Europe/Paris time." in over
    assert ("puller 0 (@p0)'s cup, 4 of 4 matches won, 8 bouts won and 0 lost: Group A against puller 4 (@p4), "
            "won 2–0; Group A against puller 2 (@p2), "
            "won 2–0; semi-final against puller 3 (@p3), won 2–0; final against puller 1 (@p1), won 2–0.") in over
    view = screen_view(CUP, 9, MANIFEST)
    assert (view["champion"], view["stage"], view["next"]) == ("puller 0 (@p0)", "Champion", None)


def test_a_group_table_counts_only_what_has_aired():
    view = screen_view(CUP, 2, MANIFEST)
    assert view["title"] == "Tug of War · Cup #1" and view["stage"] == "Groups · round 2 of 3"
    group_a = view["groups"][0]
    assert sum(row["played"] for row in group_a["rows"]) == 2
    assert sorted(row["name"] for row in group_a["rows"]) == ["puller 0 (@p0)", "puller 2 (@p2)", "puller 4 (@p4)"]
    assert all(side is None for round_ in view["knockout"] for m in round_["matches"] for side in (m["a"], m["b"]))
    assert view["next"]["group"] == "A"
    assert ("Group A after 1 match: puller 2 (@p2) 1 win, puller 0 (@p0) 0 wins, puller 4 (@p4) 0 wins."
            in texts(CUP, 2))


def test_a_second_cup_knows_the_first():
    facts = cup_facts(CUP2, 6, [CUP], MANIFEST)
    said = [fact.text for fact in facts]
    assert "@p0 won Cup #1 and defends the title." in said
    assert "@p0 and @p3 have met before, in Cup #1's semi-final (1 of 2): @p0 won 2–0." in said
    assert "@p0 has won their last 6 cup matches." in said
    assert not any(fact.ref == "cup#/streak/p3" for fact in facts)


def test_a_match_decided_by_rating_is_never_a_bare_score():
    tied = replace(CUP, matches=tuple(
        replace(m, wins=(1, 1), decided_by="rating", bouts=m.bouts[:2]) if m.index == 0 else m for m in CUP.matches))
    assert "In the last match, group round 1 of 3 in Group A, puller 2 (@p2) won on rating after 1–1 " \
           "against puller 4 (@p4)." in texts(tied, 1)
    assert ("Group round 1 results: puller 2 (@p2) won on rating after 1–1 against puller 4 (@p4); "
            "puller 3 (@p3) beat puller 5 (@p5) 2–1.") in texts(tied, 2)


def test_a_knockout_tie_sends_one_duck_through():
    tied = replace(CUP, matches=tuple(
        replace(m, wins=(1, 1), decided_by="rating", bouts=m.bouts[:2]) if m.index == 6 else m for m in CUP.matches))
    assert ("In the last match, the semi-final (1 of 2), puller 0 (@p0) went through on rating after 1–1 "
            "against puller 3 (@p3).") in texts(tied, 7)
    assert "semi-final against puller 3 (@p3), went through on rating after 1–1;" in texts(tied, 9)[-2]


def test_a_champion_who_lost_a_group_match_says_so():
    upset = played_cup(upsets=frozenset({2}))
    assert upset.matches[2].winner == 4 and upset.matches[-1].winner == 0
    assert "Group A against puller 4 (@p4), lost 2–0" in " ".join(texts(upset, 9))
    assert "puller 0 (@p0)'s cup, 3 of 4 matches won, 6 bouts won and 2 lost: " in " ".join(texts(upset, 9))


def test_a_cup_whose_last_champion_left_says_who_won():
    newcomers = replace(CUP2, entrants=tuple(replace(e, user=f"q{k}") for k, e in enumerate(CUP2.entrants)))
    assert "Cup #1 was won by @p0, who is not in this cup." in texts(newcomers, 0, [CUP])


def test_a_streak_ends_with_a_loss():
    upset = played_cup(number=2, upsets=frozenset({2}))
    facts = cup_facts(upset, 6, [CUP], MANIFEST)
    assert not any(fact.ref == "cup#/streak/p0" for fact in facts)


def test_the_last_match_names_how_its_last_bout_ended():
    marker = replace(CUP, matches=tuple(
        replace(m, bouts=(*m.bouts[:-1], replace(m.bouts[-1], how="marker"))) if m.index == 0 else m
        for m in CUP.matches))
    assert ("In the last match, group round 1 of 3 in Group A, puller 2 (@p2) beat puller 4 (@p4) 2–0, "
            "the last bout decided on the marker.") in texts(marker, 1)
    assert ("In the last match, group round 1 of 3 in Group A, puller 2 (@p2) beat puller 4 (@p4) 2–0, "
            "the last bout ending in the pit.") in texts(CUP, 1)
    fault = replace(CUP, matches=tuple(
        replace(m, bouts=(*m.bouts[:-1], replace(m.bouts[-1], how="fault"))) if m.index == 0 else m
        for m in CUP.matches))
    assert ("In the last match, group round 1 of 3 in Group A, puller 2 (@p2) beat puller 4 (@p4) 2–0, "
            "the last bout lost on a fault.") in texts(fault, 1)


def rewritten(cup, k):
    def flip(side):
        return None if side is None else "b" if side == "a" else "a"

    def reverse(m):
        loser = m.b if m.winner == m.a else m.a
        return replace(m, winner=loser, wins=m.wins[::-1],
                       bouts=tuple(replace(bout, winner=flip(bout.winner)) for bout in m.bouts))

    def swapped(m):
        # The pair of a knockout match follows the winners of the round before it.
        return min(x.index for x in cup.matches if x.round == m.round) - 1 >= k

    out = []
    for m in cup.matches:
        if m.index >= k:
            m = reverse(m)
        if m.group is None and m.index > k and swapped(m):
            m = replace(m, a=m.b, b=m.a)
        out.append(m)
    return replace(cup, matches=tuple(out))


def test_nothing_after_the_match_is_known():
    for k in range(10):
        other = rewritten(CUP2, k)
        assert cup_facts(CUP2, k, [CUP], MANIFEST) == cup_facts(other, k, [CUP], MANIFEST)
        assert screen_view(CUP2, k, MANIFEST) == screen_view(other, k, MANIFEST)


def test_a_profile_is_the_season_as_it_stood_at_close(tmp_path):
    store = LocalStore(tmp_path)
    for at in ("2026-10-20T09:00:00Z", "2026-10-21T09:00:00Z", "2026-10-30T15:00:01Z"):
        store.append(make_record(user="p0", submitted_at=at), b"trace")
    profile = player_profiles(store, CUP, ())["p0"]
    assert profile.ref == "profile#/p0" and profile.text.startswith("@p0 has ")
    assert "from 2 publications on 1 event" in profile.text
    assert set(player_profiles(store, CUP, ())) == {"p0"}
