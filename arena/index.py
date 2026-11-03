"""The leaderboard is derived, never stored.

Scanned from the append-only log, so a restart costs a re-scan and nothing else.

**One run per entrant** — but who counts as an entrant depends on who is
looking. On a public board the entrant is the PERSON, or one determined
competitor with forty retrains owns the whole top ten. On a local board there is
exactly one person, and collapsing to one row per person leaves a single line no
matter how many policies you try — so locally the entrant is the POLICY, and
`walker-v1` races `walker-v2`. Same ranking arithmetic either way; only the key
differs. `by_user` is the default so the public semantics are what you get
unless a caller deliberately asks otherwise.

**A copy holds no place.** A run that races exactly like an earlier run of
someone else is that run entered again, and is off the board as if withdrawn.
"""

from dataclasses import dataclass

from .constants import RUNNER_VERSION
from .manifest import higher_wins, staged
from .store import RunRecord


@dataclass(frozen=True)
class Row:
    rank: int
    record: RunRecord


def sort_key(record: RunRecord) -> tuple:
    """Lower is better: the better score (the higher where the event's metric says a higher
    score wins, the lower elsewhere), then more seeds finished, then who got there first."""
    score = -record.score if higher_wins(record.event_id) else record.score
    return (score, -record.seeds_finished, record.submitted_at)


def by_user(record: RunRecord) -> str:
    """One row per person. The public board's rule."""
    return record.user


def by_policy(record: RunRecord) -> tuple[str, str]:
    """One row per policy a person entered. The local board's rule."""
    return (record.user, record.policy_name)


ENTRANTS = {"user": by_user, "policy": by_policy}


def copies(records) -> dict[str, RunRecord]:
    """Every run that races exactly like an earlier run of another person, with that run.

    The physics is deterministic, so a policy races the same every time it is entered: the same
    results seed by seed, to the millisecond, are the same policy whatever its bytes are. A file
    entered again with one more metadata field, or a branch of its graph that never fires, races
    like the one it was taken from. The first run to race that way is the original.

    Races only: on a stage the same weights with another timeline are another performance. And a
    run has to finish a seed: a fall carries no time, so two policies that both fall on every
    seed would look alike.
    """
    first: dict = {}
    out = {}
    for record in sorted(records, key=lambda r: (r.submitted_at, r.run_id)):
        if record.seeds_finished == 0 or staged(record.event_id):
            continue
        original = first.setdefault((record.event_id, record.runner_version, record.per_seed), record)
        if original.user != record.user:
            out[record.run_id] = original
    return out


def leaderboard(
    records,
    runner_version: int = RUNNER_VERSION,
    entrant=by_user,
    withdrawn: frozenset[str] = frozenset(),
) -> list[Row]:
    """`withdrawn` is the set of run ids their authors have taken off the board.

    Filtered here rather than deleted from the log, because the log is
    append-only: a withdrawal is one more immutable write, and the run it
    withdraws stays on disk. A withdrawn run also loses to nothing — it is not
    merely outranked, it is absent — so it cannot keep a better run of the same
    entrant off the board. Nor does a copy, which is withdrawn by the rule.
    """
    copied = copies(records)
    best: dict = {}
    for record in records:
        if record.runner_version != runner_version:
            continue  # a different physics; never comparable
        if record.run_id in withdrawn or record.run_id in copied:
            continue
        key = entrant(record)
        current = best.get(key)
        if current is None or sort_key(record) < sort_key(current):
            best[key] = record

    ranked = sorted(best.values(), key=sort_key)
    return [Row(rank=i + 1, record=r) for i, r in enumerate(ranked)]


@dataclass(frozen=True)
class Standing:
    rank: int
    on_board: bool
    board: list[Row]


def standing(
    records,
    run_id: str,
    withdrawn: frozenset[str] = frozenset(),
    runner_version: int = RUNNER_VERSION,
) -> Standing:
    """Where ONE run stands against everyone else's best, on the board or not.

    The board keeps one row per person, so a run beaten by its author's own
    better run, a withdrawn run, or one from an older runner has no row — and
    still deserves an answer to "where would this have placed". The author's
    own row is taken out and the run put in at its sorted place; `rank` is that
    place, and `board` is the whole field ranked that way, this run included:
    the page's table scrolls, so it shows all of it.
    """
    record = next(r for r in records if r.run_id == run_id)
    rows = leaderboard(records, runner_version, entrant=by_user, withdrawn=withdrawn)
    others = [row.record for row in rows if row.record.user != record.user]
    field = sorted([*others, record], key=sort_key)
    at = field.index(record)
    ranked = [Row(rank=i + 1, record=r) for i, r in enumerate(field)]
    return Standing(
        rank=at + 1,
        on_board=any(row.record.run_id == run_id for row in rows),
        board=ranked,
    )
