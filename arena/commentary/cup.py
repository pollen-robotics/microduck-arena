"""The cup as it stood before a match: its stage, tables and bracket, and what the booth may say of it.

Everything here reads the matches before `before`, the pair of match `before`, the entrants, the earlier cups and
the manifest, so nothing is told that has not aired.
"""

from collections.abc import Sequence
from zoneinfo import ZoneInfo

from ..cup import (
    GROUP_NAMES,
    Cup,
    Entrant,
    MatchRecord,
    cup_times,
    cup_title,
    duck,
    group_fixtures,
    group_table,
    parse_iso,
)
from ..manifest import Manifest, all_events
from ..points import counting, receipts, standings
from .context import NOTABLE_GAP_CM, Fact
from .notable import season


def group_round(cup: Cup, match: MatchRecord) -> int:
    group = cup.groups[GROUP_NAMES.index(match.group)]
    pairs = group_fixtures(group)
    pair = (match.a, match.b)
    place = pairs.index(pair) if pair in pairs else pairs.index(pair[::-1])
    return place // (len(group) // 2) + 1


def group_rounds(cup: Cup) -> int:
    return max(len(group_fixtures(group)) // (len(group) // 2) for group in cup.groups)


def stage_of(cup: Cup, index: int) -> str:
    match = cup.matches[index]
    if match.group:
        return f"group round {group_round(cup, match)} of {group_rounds(cup)} in Group {match.group}"
    same = [m for m in cup.matches if m.round == match.round]
    return f"the {match.round}" + (f" ({same.index(match) + 1} of {len(same)})" if len(same) > 1 else "")


def _groups_end(cup: Cup) -> int:
    """The index of the first knockout match, or of the end of a cup without one."""
    return next((m.index for m in cup.matches if not m.group), len(cup.matches))


def _ratings(cup: Cup) -> list[float]:
    return [entrant.rating for entrant in cup.entrants]


def _table(cup: Cup, name: str, played: Sequence[MatchRecord]) -> list[int]:
    return group_table(cup.groups[GROUP_NAMES.index(name)], [m for m in played if m.group == name], _ratings(cup))


def screen_view(cup: Cup, before: int, manifest: Manifest) -> dict:
    """The desk screen as it stands before match `before`: the group tables by their players' handles, the
    bracket, the next match and the champion billed with their players."""
    names = [duck(entrant) for entrant in cup.entrants]
    done, count = cup.matches[:before], len(cup.matches)
    groups = [{"name": name,
               "rows": [{"name": f"@{cup.entrants[i].user}", "won": sum(m.winner == i for m in done if m.group == name),
                         "played": sum(i in (m.a, m.b) for m in done if m.group == name)}
                        for i in _table(cup, name, done)]}
              for name, _ in zip(GROUP_NAMES, cup.groups)]
    knockout = []
    for round_ in dict.fromkeys(m.round for m in cup.matches[_groups_end(cup):]):
        matches = [m for m in cup.matches if m.round == round_]
        paired = matches[0].index <= before  # the round before it is all aired
        knockout.append({"round": round_, "matches": [
            {"a": names[m.a] if paired else None, "b": names[m.b] if paired else None,
             "winner": None if m.index >= before else "a" if m.winner == m.a else "b", "next": m.index == before}
            for m in matches]})
    upcoming = cup.matches[before] if before < count else None
    stage = ("Champion" if upcoming is None else f"Groups · round {group_round(cup, upcoming)} of {group_rounds(cup)}"
             if upcoming.group else upcoming.round.capitalize())
    return {"title": cup_title(manifest.title, cup.number), "stage": stage, "groups": groups, "knockout": knockout,
            "next": None if upcoming is None else {"a": names[upcoming.a], "b": names[upcoming.b],
                                                   "group": upcoming.group, "round": upcoming.round},
            "champion": names[cup.matches[-1].winner] if upcoming is None else None}


def _fact(ref: str, text: str) -> Fact:
    return Fact(ref, text, "cup")


def _and(items: Sequence[str]) -> str:
    return f"{', '.join(items[:-1])} and {items[-1]}" if len(items) > 1 else items[0]


def _cm(value: float) -> str:
    return f"{value:.1f} cm"


def score_text(match: MatchRecord) -> str:
    """A match's bouts won, the winner's first."""
    return f"{max(match.wins)}–{min(match.wins)}"


def _loser(match: MatchRecord) -> int:
    return match.b if match.winner == match.a else match.a


def _on_rating(match: MatchRecord, won: bool) -> str:
    """A group loss puts no duck out; a knockout tie does."""
    if match.group:
        return "won" if won else "lost"
    return "went through" if won else "went out"


def _beat(cup: Cup, match: MatchRecord) -> str:
    winner, loser = duck(cup.entrants[match.winner]), duck(cup.entrants[_loser(match)])
    if match.decided_by == "rating":
        return f"{winner} {_on_rating(match, True)} on rating after {score_text(match)} against {loser}"
    return f"{winner} beat {loser} {score_text(match)}"


def _verdict(match: MatchRecord, won: bool) -> str:
    """How a match ended for one of its sides."""
    if match.decided_by == "rating":
        return f"{_on_rating(match, won)} on rating after {score_text(match)}"
    return f"{'won' if won else 'lost'} {score_text(match)}"


def _opening(cup: Cup, manifest: Manifest) -> Fact:
    count = len(cup.groups)
    shape = ("one group where everyone meets everyone, then a final between its top two" if count == 1 else
             f"{count} groups where everyone meets everyone, then a knockout between the top two of each")
    # The course in numbers: told to open on "the course as the event fact describes it", a desk given none
    # made the pit "50 centimetres wide".
    course = (f"Two ducks tied by a {manifest.course.string_m:.1f} m string pull across a pit "
              f"{manifest.course.pit_m * 100:.0f} cm wide in a {manifest.course.ring_m:g} m wrestling ring, "
              "walking backwards. ")
    return _fact("cup#/cup", f"This is the {manifest.title} Cup #{cup.number}, {len(cup.entrants)} players: {shape}. "
                 f"{course}A match is first to {manifest.bout.bouts_to_win} bouts, the ducks swapping sides after "
                 "each; a duck that drops into the pit loses the bout, and at the time limit the duck the marker "
                 f"moved away from loses. Level after {manifest.bout.max_bouts} bouts, the higher rating goes through.")


def _rating_line(cup: Cup) -> Fact:
    ranked = sorted(cup.entrants, key=lambda e: (-e.rating, e.user))

    def line(ducks: Sequence[Entrant]) -> str:
        return ", ".join(f"{duck(e)} {_cm(e.rating)}" for e in ducks)

    if len(ranked) <= 4:
        return _fact("cup#/ratings", f"Ratings against the reference duck: {line(ranked)}.")
    return _fact("cup#/ratings", f"Ratings against the reference duck, at the top: {line(ranked[:3])}; "
                 f"at the bottom: {line(ranked[-1:])}.")


def _group_facts(cup: Cup, done: Sequence[MatchRecord]) -> list[Fact]:
    out = []
    for name, group in zip(GROUP_NAMES, cup.groups):
        played = [m for m in done if m.group == name]
        if not played:
            members = _and([duck(cup.entrants[i]) for i in group])
            out.append(_fact(f"cup#/group/{name}", f"Group {name}: {members}, no match played yet."))
            continue
        rows = ", ".join(
            f"{duck(cup.entrants[i])} {won} win{'s' if won != 1 else ''}"
            for i in _table(cup, name, done) for won in [sum(m.winner == i for m in played)])
        out.append(_fact(f"cup#/group/{name}",
                         f"Group {name} after {len(played)} match{'es' if len(played) > 1 else ''}: {rows}."))
    return out


def _next_facts(cup: Cup, upcoming: MatchRecord) -> list[Fact]:
    a, b = cup.entrants[upcoming.a], cup.entrants[upcoming.b]
    gap = abs(a.rating - b.rating)
    favourite = a if a.rating >= b.rating else b
    ending = (f"only {_cm(gap)} apart, too close to call" if gap < NOTABLE_GAP_CM
              else f"{duck(favourite)} is the favourite by {_cm(gap)}")
    return [
        _fact("cup#/next", f"Next is match {upcoming.index + 1} of {len(cup.matches)}, "
              f"{stage_of(cup, upcoming.index)}: {duck(a)} against {duck(b)}."),
        _fact("cup#/favourite", f"Against the reference duck {duck(a)} rates {_cm(a.rating)} and {duck(b)} "
              f"{_cm(b.rating)}: {ending}."),
    ]


def _last_fact(cup: Cup, last: MatchRecord) -> Fact:
    last_bout = last.bouts[-1]
    how = ("" if last.decided_by == "rating" else ", the last bout ending in the pit" if last_bout.how == "pit"
           else ", the last bout lost on a fault" if last_bout.how == "fault" else ", the last bout decided on the marker")
    return _fact("cup#/last", f"In the last match, {stage_of(cup, last.index)}, {_beat(cup, last)}{how}.")


def _round_fact(cup: Cup, done: Sequence[MatchRecord]) -> list[Fact]:
    """The results of a group round, once its last match has aired."""
    last = done[-1] if done else None
    if last is None or not last.group:
        return []
    r, before = group_round(cup, last), len(done)
    if before < _groups_end(cup) and group_round(cup, cup.matches[before]) == r:
        return []
    results = "; ".join(_beat(cup, m) for m in done if m.group and group_round(cup, m) == r)
    return [_fact("cup#/round", f"Group round {r} results: {results}.")]


def _through_fact(cup: Cup, done: Sequence[MatchRecord]) -> Fact:
    tops = [[duck(cup.entrants[i]) for i in _table(cup, name, done)[:2]] for name, _ in zip(GROUP_NAMES, cup.groups)]
    if len(tops) == 1:
        return _fact("cup#/through", f"Through to the final: {_and(tops[0])}.")
    round_ = cup.matches[len(done)].round
    groups = "; ".join(f"Group {name}: {_and(top)}" for name, top in zip(GROUP_NAMES, tops))
    return _fact("cup#/through", f"Through to the {round_ + 's' if round_.endswith('final') else round_}: {groups}.")


def _defending_fact(cup: Cup, last: Cup) -> Fact:
    champion = last.entrants[last.matches[-1].winner].user
    if champion in {entrant.user for entrant in cup.entrants}:
        return _fact("cup#/defending", f"@{champion} won Cup #{last.number} and defends the title.")
    return _fact("cup#/defending", f"Cup #{last.number} was won by @{champion}, who is not in this cup.")


def _meetings(cup: Cup, done: Sequence[MatchRecord], history: Sequence[Cup]) -> list[tuple[Cup, MatchRecord]]:
    return [(c, m) for c in history for m in c.matches] + [(cup, m) for m in done]


def _rematch_fact(cup: Cup, done: Sequence[MatchRecord], history: Sequence[Cup], upcoming: MatchRecord) -> list[Fact]:
    a, b = cup.entrants[upcoming.a].user, cup.entrants[upcoming.b].user
    met = [(c, m) for c, m in _meetings(cup, done, history)
           if {c.entrants[m.a].user, c.entrants[m.b].user} == {a, b}]
    if not met:
        return []
    last_cup, last = met[-1]
    stage = stage_of(last_cup, last.index).removeprefix("the ")
    where = "this cup's " + stage if last_cup is cup else f"Cup #{last_cup.number}'s {stage}"
    result = f"@{last_cup.entrants[last.winner].user} {_verdict(last, True)}"
    if len(met) == 1:
        return [_fact("cup#/rematch", f"@{a} and @{b} have met before, in {where}: {result}.")]
    return [_fact("cup#/rematch", f"@{a} and @{b} have met {len(met)} times in cups; the last time, in {where}, "
                  f"{result}.")]


def _streak_facts(cup: Cup, done: Sequence[MatchRecord], history: Sequence[Cup], upcoming: MatchRecord) -> list[Fact]:
    out = []
    for user in (cup.entrants[upcoming.a].user, cup.entrants[upcoming.b].user):
        results = [c.entrants[m.winner].user == user for c, m in _meetings(cup, done, history)
                   if user in (c.entrants[m.a].user, c.entrants[m.b].user)]
        streak = 0
        for won in reversed(results):
            if not won:
                break
            streak += 1
        if streak >= 3:
            out.append(_fact(f"cup#/streak/{user}", f"@{user} has won their last {streak} cup matches."))
    return out


def _ending_facts(cup: Cup, manifest: Manifest) -> list[Fact]:
    final = cup.matches[-1]
    champion, runner_up = duck(cup.entrants[final.winner]), duck(cup.entrants[_loser(final)])
    title = f"{manifest.title} Cup #{cup.number}"
    crowned = (f"going through on rating after {score_text(final)} against {runner_up}" if final.decided_by == "rating"
               else f"beating {runner_up} {score_text(final)}")
    path = [m for m in cup.matches if final.winner in (m.a, m.b)]
    steps = [f"{f'Group {m.group}' if m.group else m.round} against "
             f"{duck(cup.entrants[m.b if m.a == final.winner else m.a])}, {_verdict(m, m.winner == final.winner)}"
             for m in path]
    # Counted here: asked to look back on the cup, the desk counts the path itself ("four matches, eight
    # bouts") into numbers no fact prints.
    won = sum(m.winner == final.winner for m in path)
    bouts = [m.wins if m.a == final.winner else m.wins[::-1] for m in path]
    tally = (f"{won} of {len(path)} matches won, {sum(w for w, _ in bouts)} bouts won and "
             f"{sum(lost for _, lost in bouts)} lost")
    premiere = cup_times(manifest.cup, cup.number + 1)[1].astimezone(ZoneInfo(manifest.cup.timezone))
    return [
        _fact("cup#/champion", f"{champion} wins the {title}, {crowned} in the final."),
        _fact("cup#/path", f"{champion}'s cup, {tally}: {'; '.join(steps)}."),
        _fact("cup#/next-cup", f"Cup #{cup.number + 1} premieres on {premiere:%A %-d %B at %H:%M}, "
              f"{manifest.cup.timezone} time."),
    ]


def cup_facts(cup: Cup, before: int, history: Sequence[Cup], manifest: Manifest) -> list[Fact]:
    """What the booth may cite about the cup as it stands before match `before`."""
    done = cup.matches[:before]
    facts = [_opening(cup, manifest), _rating_line(cup)]
    if before <= _groups_end(cup):
        facts += _group_facts(cup, done)
    upcoming = cup.matches[before] if before < len(cup.matches) else None
    if upcoming:
        facts += _next_facts(cup, upcoming)
    if done:
        facts.append(_last_fact(cup, done[-1]))
        facts += _round_fact(cup, done)
    if done and before == _groups_end(cup) and upcoming:
        facts.append(_through_fact(cup, done))
    if history and history[-1].matches:
        facts.append(_defending_fact(cup, history[-1]))
    if upcoming:
        facts += _rematch_fact(cup, done, history, upcoming) + _streak_facts(cup, done, history, upcoming)
    else:
        facts += _ending_facts(cup, manifest)
    return facts


def player_profiles(store, cup: Cup, history: Sequence[Cup]) -> dict[str, Fact]:
    """The season of each entrant as it stood when entries closed."""
    close = parse_iso(cup.close_at)
    withdrawn = frozenset(w.run_id for w in store.withdrawals())
    runs = [r for m in all_events() for r in counting(store.runs(m.id), withdrawn)
            if parse_iso(r.submitted_at) <= close]
    voted = {m.id: m.vote for m in all_events() if m.vote is not None}
    ladder = {card.user: card for card in standings(receipts(runs, frozenset(), voted=voted, cups=history, now=close))}
    return {e.user: Fact(f"profile#/{e.user}", f"@{e.user} has {season(e.user, runs, ladder)}.", "notable",
                         ("profile",))
            for e in cup.entrants if e.user in ladder}
