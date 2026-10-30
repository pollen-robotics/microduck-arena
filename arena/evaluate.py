"""Score an entry: find the speed it is best at, then prove it over every seed.

Two things are being measured and they pull apart. A single pinned command
measures how faithfully a policy tracks THAT speed — the reference walker is
far slower commanded at the sprint's declared 0.25 m/s than at its own best
speed, and falls over not far past that one (arena/golden.py and
tests/test_evaluate.py hold the current numbers). Which is faster is not a
question a pinned command can answer, and "which is faster" is the entire point
of a race.

So the event declares a wide sweep and the harness runs it, in two stages:

1. **Scan** every commanded speed on one seed. Cheap and broad — it locates the
   policy's own optimum without anyone having to declare it, and it is wide
   enough to hold a policy substantially faster than today's reference.
2. **Score** the best few of those speeds over every seed, and keep the best
   mean. One seed can flatter a speed that is actually flaky, so no speed
   reaches the board on the strength of a single lucky run.

A DNF still counts at the full time limit, which makes flakiness cost
proportionally instead of hiding behind a best-of: a policy that is brilliant
four times and falls once ranks below a steady one.

A stage is not a race and none of this applies to it: it plays the entry's
cast once (every duck of its troupe, arena/cast.py), on one seed, and every
performance that plays to the end goes to the voters. Its score is the
duration played, and only informs: a stage's board ranks on votes.

A tug's rating is neither: the entry plays one bout a seed against the reference duck
(arena/tug.py), west on odd seeds and east on even, on the event's own command. Nothing is
swept: every duck walks backwards at the same command, and what is measured is the centimetres
of ground the entry won, the marker's distance from the centre line towards its own side, plus
the event's pit bonus when only the opponent went into the pit, minus it when only the entry
did. The rating is the mean of those over every seed, and a higher one is better. The replay
is the lower-median seed by score.
"""

import statistics
from dataclasses import dataclass

import numpy as np

from .constants import RUNNER_VERSION
from .course import compile_course, compile_tug
from .manifest import Manifest
from .runner import Performer, run_once, run_stage
from .timeline import Start, constant_timeline
from .trace import SeedTrace, encode, encode_seeds
from .tug import bout_score_cm, bout_status, entry_side, reference_duck, run_bout


@dataclass(frozen=True)
class SeedResult:
    seed: int
    status: str
    time_s: float | None
    # The centimetres a bout won (a pit counts its bonus); only a tug's seeds carry one.
    score_cm: float | None = None


def seed_row(result: SeedResult) -> dict:
    """A seed as the log and the API write it: a race's and a performance's with no centimetres,
    a tug seed's with the centimetres it won."""
    row = {"seed": result.seed, "status": result.status, "time_s": result.time_s}
    if result.score_cm is not None:
        row["score_cm"] = result.score_cm
    return row


@dataclass(frozen=True)
class ScanPoint:
    """One commanded speed, tried once. The stage-1 record."""

    command_vx: float
    status: str
    time_s: float | None
    progress_m: float


@dataclass(frozen=True)
class Evaluation:
    event_id: str
    score: float
    # The speed the score was set at. Part of the result, not a detail: two
    # entries with the same time did not necessarily do the same thing.
    command_vx: float
    seeds_finished: int
    per_seed: tuple[SeedResult, ...]
    scan: tuple[ScanPoint, ...]
    # (frames, TRACE_WIDTH) for a race; (ducks, frames, TRACE_WIDTH) for a stage.
    trace: np.ndarray
    # The trace seed's untimed settle, from the reset pose, shaped as the trace (see RunOutcome).
    settle: np.ndarray
    trace_seed: int
    runner_version: int
    # A tug's traced bout's string, (frames, STRING_POINTS, 3), and its settle's, (settle + 1,
    # STRING_POINTS, 3) (arena/tug.py); None but on a tug.
    string: np.ndarray | None = None
    string_settle: np.ndarray | None = None
    # A lights event: every seed of the scored command, keyed by seed; None on any other.
    seed_traces: dict[int, SeedTrace] | None = None


def trace_file(result: Evaluation) -> bytes:
    """What a run stores: every seed's trace for a lights event, else the one traced run."""
    if result.seed_traces is not None:
        return encode_seeds(result.seed_traces)
    return encode(result.trace, result.settle, result.string, result.string_settle)


def mean_finish_time(per_seed: tuple[SeedResult, ...], time_limit_s: float) -> float:
    return statistics.fmean(
        r.time_s if r.time_s is not None else time_limit_s for r in per_seed
    )


def mean_ground_cm(per_seed: tuple[SeedResult, ...], time_limit_s: float) -> float:
    return statistics.fmean(r.score_cm for r in per_seed)


METRICS = {
    "mean_finish_time": mean_finish_time,
    # A voted event is still SCORED on its finish time — `metric` says how the
    # board RANKS, not how a run is measured. Without this entry, every
    # submission to a voted event died on `KeyError: 'votes'` the moment
    # evaluate() ran, because manifest.py accepted "votes" as a metric NAME
    # while this registry had no function behind it.
    "votes": mean_finish_time,
    "mean_ground_cm": mean_ground_cm,
}


def pick_trace_seed(per_seed: tuple[SeedResult, ...]) -> int:
    """The lower-median finishing seed.

    Median rather than best, so a replay lane shows typical behaviour and every
    entry's replay is chosen the same way. With no finishers at all we keep the
    first seed's trace: a failed entry should still be watchable.
    """
    finishers = sorted(
        (r for r in per_seed if r.time_s is not None), key=lambda r: (r.time_s, r.seed)
    )
    if not finishers:
        return per_seed[0].seed
    return finishers[(len(finishers) - 1) // 2].seed


def finalists(scan: tuple[ScanPoint, ...], count: int) -> list[float]:
    """The speeds worth paying a full seed set for.

    Fastest scan finishers first. Then — and this is not a nicety — the seed set
    is topped up with the speeds that got FURTHEST without finishing.

    The scan is one seed, so it is one coin toss per speed. Measured on the hill
    climb, the reference walker finished exactly one of eighteen scanned speeds,
    and that one turned out to be a fluke it could not repeat (1/5 seeds). A
    shortlist of finishers alone would have scored the entry on that fluke and
    never tried the speeds that got nearly as far and might well finish four
    seeds out of five. Topping up costs nothing extra: the finalist budget is
    already paid for, and leaving those slots empty buys no speed at all.

    With nothing finishing anywhere the top-up is the whole shortlist, which is
    also what decides the replay — a failed entry should still show its best
    attempt.
    """
    finishers = sorted(
        (p for p in scan if p.time_s is not None), key=lambda p: (p.time_s, p.command_vx)
    )
    shortlist = [p.command_vx for p in finishers[:count]]

    # Ties on progress go to the LOWER command, matching how a tie on score is
    # broken in evaluate(): same result for less asking is the steadier one.
    nearly = sorted(scan, key=lambda p: (-p.progress_m, p.command_vx))
    for point in nearly:
        if len(shortlist) >= count:
            break
        if point.command_vx not in shortlist:
            shortlist.append(point.command_vx)
    return shortlist


def _seed_traces(manifest: Manifest, outcomes) -> dict[int, SeedTrace] | None:
    if manifest.lights is None:
        return None
    return {o.seed: SeedTrace(o.trace, o.settle, o.caught_frame) for o in outcomes}


def evaluate_at(manifest: Manifest, policy, command_vx: float) -> Evaluation:
    """Score a policy at ONE commanded speed, skipping the scan.

    For trying a policy, not for the board. A submitter who wants to know how
    their walker behaves at 0.6 m/s should not have to wait for 21 speeds to be
    swept and then read it off a list — and five runs is under a second where
    the full sweep is three. `scan` carries the single point so callers do not
    have to special-case an empty tuple.

    The board never uses this: a leaderboard where entrants chose their own
    speed is a leaderboard of who guessed best, which is the failure mode the
    sweep exists to remove.
    """
    model = compile_course(manifest)
    command = manifest.command_at(command_vx)
    outcomes = [
        run_once(manifest, policy, seed, model=model, command=command)
        for seed in manifest.seeds
    ]
    per_seed = tuple(
        SeedResult(seed=o.seed, status=o.status, time_s=o.time_s) for o in outcomes
    )
    trace_seed = pick_trace_seed(per_seed)
    first = outcomes[0]

    return Evaluation(
        event_id=manifest.id,
        score=METRICS[manifest.metric](per_seed, manifest.time_limit_s),
        command_vx=float(command_vx),
        seeds_finished=sum(1 for r in per_seed if r.status == "finish"),
        per_seed=per_seed,
        scan=(
            ScanPoint(
                command_vx=float(command_vx),
                status=first.status,
                time_s=first.time_s,
                progress_m=first.progress_m,
            ),
        ),
        trace=next(o.trace for o in outcomes if o.seed == trace_seed),
        settle=next(o.settle for o in outcomes if o.seed == trace_seed),
        trace_seed=trace_seed,
        runner_version=RUNNER_VERSION,
        seed_traces=_seed_traces(manifest, outcomes),
    )


def evaluate(manifest: Manifest, policy, cast: tuple[Performer, ...] | None = None) -> Evaluation:
    if manifest.course.kind == "stage":
        return _evaluate_stage(manifest, policy, cast)
    if manifest.course.kind == "tug":
        if cast is not None:
            raise ValueError(f"{manifest.id} rates the entry alone, against its reference duck")
        return _evaluate_rating(manifest, policy)
    if cast is not None:
        raise ValueError(f"{manifest.id} is a race: it races the entry alone, on the event's command")
    model = compile_course(manifest)  # compiled once, reused for every run
    sweep = manifest.sweep

    # Stage 1: one seed, every speed. The first seed and not a random one, so a
    # re-run of the same entry picks the same finalists.
    scan_seed = manifest.seeds[0]
    outcomes: dict[tuple[float, int], object] = {}
    scan = []
    for vx in sweep.speeds():
        outcome = run_once(
            manifest, policy, scan_seed, model=model, command=manifest.command_at(vx)
        )
        outcomes[(vx, scan_seed)] = outcome
        scan.append(
            ScanPoint(
                command_vx=vx,
                status=outcome.status,
                time_s=outcome.time_s,
                progress_m=outcome.progress_m,
            )
        )
    scan = tuple(scan)

    # Stage 2: the shortlist, over every seed. The scan's own run is reused, so
    # a finalist costs four more runs and not five.
    metric = METRICS[manifest.metric]
    best = None
    for vx in finalists(scan, sweep.finalists):
        for seed in manifest.seeds:
            if (vx, seed) not in outcomes:
                outcomes[(vx, seed)] = run_once(
                    manifest, policy, seed, model=model, command=manifest.command_at(vx)
                )
        per_seed = tuple(
            SeedResult(seed=s, status=outcomes[(vx, s)].status, time_s=outcomes[(vx, s)].time_s)
            for s in manifest.seeds
        )
        score = metric(per_seed, manifest.time_limit_s)
        # Ties go to the lower command: same mean for less asking is the
        # steadier of the two, and it keeps the winner reproducible.
        if best is None or (score, vx) < (best[0], best[1]):
            best = (score, vx, per_seed)

    score, command_vx, per_seed = best
    trace_seed = pick_trace_seed(per_seed)

    return Evaluation(
        event_id=manifest.id,
        score=score,
        command_vx=command_vx,
        seeds_finished=sum(1 for r in per_seed if r.status == "finish"),
        per_seed=per_seed,
        scan=scan,
        trace=outcomes[(command_vx, trace_seed)].trace,
        settle=outcomes[(command_vx, trace_seed)].settle,
        trace_seed=trace_seed,
        runner_version=RUNNER_VERSION,
        seed_traces=_seed_traces(manifest, [outcomes[(command_vx, s)] for s in manifest.seeds]),
    )


def _evaluate_rating(manifest: Manifest, policy) -> Evaluation:
    """The entry in one bout a seed against the reference duck, west on odd seeds. A bout always
    ends with a score, so every seed counts as finished."""
    model, reference = compile_tug(manifest), reference_duck(manifest)
    outcomes, per_seed = {}, []
    for seed in manifest.seeds:
        entry = entry_side(seed)
        west, east = (policy, reference) if entry == 0 else (reference, policy)
        out = outcomes[seed] = run_bout(manifest, west, east, seed, model)
        per_seed.append(SeedResult(seed, bout_status(out, entry), out.time_s,
                                   bout_score_cm(out, entry, manifest.rating.pit_bonus_cm)))
    per_seed = tuple(per_seed)
    ranked = sorted(per_seed, key=lambda r: (r.score_cm, r.seed))
    traced = outcomes[ranked[(len(ranked) - 1) // 2].seed]
    return Evaluation(
        event_id=manifest.id,
        score=METRICS[manifest.metric](per_seed, manifest.time_limit_s),
        command_vx=manifest.command[0],
        seeds_finished=len(per_seed),
        per_seed=per_seed,
        scan=(),
        trace=traced.trace,
        settle=traced.settle,
        trace_seed=traced.seed,
        runner_version=RUNNER_VERSION,
        string=traced.string,
        string_settle=traced.string_settle,
    )


def _evaluate_stage(manifest: Manifest, policy, cast: tuple[Performer, ...] | None) -> Evaluation:
    """One performance: the cast, or the entry alone at the centre on the event's command for the
    whole time limit."""
    if cast is None:
        cast = (Performer(policy, manifest.rig, Start(), constant_timeline(manifest.command, manifest.time_limit_s)),)
    seed = manifest.seeds[0]
    outcome = run_stage(manifest, cast, seed)
    per_seed = (SeedResult(seed=seed, status=outcome.status, time_s=outcome.time_s),)
    return Evaluation(
        event_id=manifest.id,
        score=METRICS[manifest.metric](per_seed, manifest.time_limit_s),
        command_vx=0.0,
        seeds_finished=1 if outcome.status == "finish" else 0,
        per_seed=per_seed,
        scan=(),
        trace=outcome.trace,
        settle=outcome.settle,
        trace_seed=seed,
        runner_version=RUNNER_VERSION,
    )
