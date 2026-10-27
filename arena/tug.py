"""A tug of war: a duck pulls on a string against another duck, the reference duck on a rating
seed (a bout).

The string is a rope (`arena.course.compile_tug`): sixteen capsules tied neck to neck, it sags,
pulls only when taut and never pushes. Its seventeen points, west to east (its two ends and the
joints between its capsules), are recorded beside the ducks at every control step, settle
included.

The judge, after every control step: only the pit decides. A duck is out when its trunk is in
the pit; knocked over, sitting or lying on the platform, it stays in play and can still be
dragged in. The first duck in the pit loses the bout; when both go in on one step, or nobody is
in at the time limit, the marker (the string's middle point) decides: pulled to the west, east
loses; to the east, west loses; exactly on the centre line, a draw. Only its x counts: the
marker sagging into the pit is still on its side of the line.

Before the pit, a fault: a duck whose servos are driven by a command that is not a number loses
the bout on that step (both at once, nobody wins it). MuJoCo drives no motor at all while one
command is not a number, the other duck's included, and the servo model carries a NaN on to the
end of the bout: unjudged, a duck answering NaN froze the reference duck and rated -0.1 cm, above
a duck that never moves (-15.0 cm). Found by @jrubiosainz's duel (pollen-robotics/microduck-arena#2).
A duck that gives no action is answering no number too: its policy failed, or it has thought,
over the bout, settle included, for longer than the bout lasts (the robot asks every 20 ms), so a
policy that hangs or crawls holds no cup.

A step MuJoCo had to reset ends the bout with nobody winning it, its frame left out: a solver
explosion is not a result, and the reset pose stands the west duck over the pit. In a match it is
nobody's; in a rating it is the entry's fault, as any fault is there: the reference duck never
causes one on its own, and a duck that blew the physics up on purpose rated 0.0 cm, above every
duck that pulls and loses.

A blow-up MuJoCo does not flag is judged the same way: a step that puts a trunk or a point of the
string off the course (`off_the_course`: past the ring's edge or below the pit's floor by more than
OFF_COURSE_M) ends the bout for nobody, its frame left out. Unjudged, one such step flung the string
23 m and the west trunk 1.3 m under the canvas, every number still finite, and the pit read a win
with the marker 12.8 m out: a 1378.6 cm bout and a 405.4 cm rating
(pollen-robotics/microduck-arena#6).

A trace frame is a runner frame: trunk position (0:3), trunk quaternion w, x, y, z (3:7), then
the joint angles.
"""

from dataclasses import dataclass
from time import monotonic

import numpy as np

from .assets import ASSET_ROOT
from .constants import CTRL_DT, NUM_JOINTS, TRACE_WIDTH
from .course import STRING_SEGMENTS, compile_tug, string_sites
from .manifest import Manifest
from .policy import PolicyError, load_policy
from .runner import _reset_by_mujoco, _start

PIT_DROP_M = 0.05  # a trunk below z = -PIT_DROP_M is in the pit
OFF_COURSE_M = 0.5  # how far past the ring's edge, or below the pit's floor, no step of a real bout reaches
FAULT_PITS = 2  # a fault scores this many pit bonuses: beyond any bout played out (a pit and 65 cm of marker)
SIDES = ("west", "east")
STRING_POINTS = STRING_SEGMENTS + 1  # a recorded string frame: its points, west to east
MIDDLE = STRING_SEGMENTS // 2  # the point the marker is tied at


def marker_x(string: np.ndarray) -> np.ndarray:
    """The marker's x per frame, (frames, STRING_POINTS, 3) -> (frames,): the string's middle point."""
    return string[:, MIDDLE, 0]


def in_pit(frame: np.ndarray) -> bool:
    return bool(frame[2] < -PIT_DROP_M)


def off_the_course(course, trunks: np.ndarray, string: np.ndarray) -> bool:
    """Is a trunk, (2, 3), or a point of the string, (STRING_POINTS, 3), where no real bout goes:
    more than OFF_COURSE_M past the ring's edge in x or y, above it, or below the pit's floor?"""
    p = np.concatenate([trunks, string])
    reach = course.ring_m / 2 + OFF_COURSE_M
    return bool((np.abs(p[:, 0:2]) > reach).any() or (p[:, 2] < -course.pit_depth_m - OFF_COURSE_M).any()
                or (p[:, 2] > reach).any())


def _verdict(trace: np.ndarray, string: np.ndarray, final: bool) -> tuple[int | None, str] | None:
    """The bout's verdict after the last frame of `trace`, (2, frames, 21), and of its `string`,
    (frames, STRING_POINTS, 3): (loser, how), or None while it goes on."""
    inside = [in_pit(trace[k, -1]) for k in (0, 1)]
    if inside.count(True) == 1:
        return inside.index(True), "pit"
    if all(inside) or final:
        x = marker_x(string[-1:])[0]
        return (1, "marker") if x < 0 else (0, "marker") if x > 0 else (None, "draw")
    return None


@dataclass(frozen=True)
class BoutOutcome:
    seed: int
    loser: int | None  # 0 west, 1 east, None undecided by the physics
    how: str  # "fault" (a command not a number; both at once, nobody's bout),
    # "pit" (the first duck in the pit),
    # "marker" (both in on one control step, or the time limit),
    # "draw" (the marker exactly on the centre line),
    # "reset" (a step MuJoCo had to reset, nobody's bout)
    time_s: float  # when it was decided
    trace: np.ndarray  # (2, frames, 21), west first; stops at the deciding step
    settle: np.ndarray  # (2, settle + 1, 21)
    string: np.ndarray  # (frames, STRING_POINTS, 3), west to east, frame for frame with the trace
    string_settle: np.ndarray  # (settle + 1, STRING_POINTS, 3)


class _OnTheClock:
    """A duck's policy on its bout's clock, `seconds` of thinking in all: an answer it fails to give,
    or gives once they are spent, is no number, and so a fault. It answers none after that."""

    def __init__(self, policy, seconds: float):
        self.policy, self.left = policy, seconds

    def act(self, obs: np.ndarray) -> np.ndarray:
        started = monotonic()
        try:
            action = self.policy.act(obs) if self.left > 0 else None
        except PolicyError:
            action = None
        self.left = self.left - (monotonic() - started) if action is not None else 0.0
        return action if self.left > 0 else np.full(NUM_JOINTS, np.nan, dtype=np.float32)


def _faults(sim) -> list[bool]:
    """Per duck, west first: are its servos driven by a command that is not a number?"""
    return [not np.isfinite(sim.data.ctrl[duck.servos.act_ids]).all() for duck in sim.ducks]


def run_bout(manifest: Manifest, west, east, seed: int, model=None) -> BoutOutcome:
    """Two ducks tied neck to neck, west facing east and east facing west, both on the event's
    command, until the judge's first verdict: at the latest the bout's time limit, where the
    marker always gives one. Each duck thinks on its own clock, the bout's time limit (module
    docstring)."""
    model = model if model is not None else compile_tug(manifest)
    command = np.asarray(manifest.command, dtype=np.float64)
    limit = manifest.bout.time_limit_s
    sim, settle, string_settle = _start(
        manifest, model, [_OnTheClock(west, limit), _OnTheClock(east, limit)], [0.0, 180.0], seed,
        [command, command], string_sites(model),
    )
    steps = round(limit / CTRL_DT)
    frames = np.empty((2, steps, TRACE_WIDTH), dtype=np.float32)
    string = np.empty((steps, STRING_POINTS, 3), dtype=np.float32)
    for step in range(steps):
        sim.step([command, command])
        if _reset_by_mujoco(sim.data):
            return BoutOutcome(
                seed, None, "reset", (step + 1) * CTRL_DT, frames[:, :step].copy(), settle,
                string[:step].copy(), string_settle,
            )
        sim.record(frames[:, step])
        sim.points(string[step])
        if off_the_course(manifest.course, frames[:, step, 0:3], string[step]):  # a blow-up MuJoCo did not flag
            return BoutOutcome(
                seed, None, "reset", (step + 1) * CTRL_DT, frames[:, :step].copy(), settle,
                string[:step].copy(), string_settle,
            )
        faults = _faults(sim)
        verdict = ((faults.index(True) if faults.count(True) == 1 else None), "fault") if any(faults) else \
            _verdict(frames[:, : step + 1], string[: step + 1], final=step == steps - 1)
        if verdict is not None:
            loser, how = verdict
            return BoutOutcome(
                seed, loser, how, (step + 1) * CTRL_DT, frames[:, : step + 1].copy(), settle,
                string[: step + 1].copy(), string_settle,
            )


def reference_duck(manifest: Manifest):
    """The frozen duck every tug rating is bouts against."""
    return load_policy(ASSET_ROOT / "policies" / manifest.rating.reference)


def entry_side(seed: int) -> int:
    """The entry's side in a seed's bout: west (0) on odd seeds, east (1) on even."""
    return (seed - 1) % 2


def bout_status(outcome: BoutOutcome, entry: int) -> str:
    """A rating bout as the entry saw it: won, lost or draw, with a pit_ prefix when the pit decided;
    a fault, whoever's, or a reset is the entry's fault (module docstring)."""
    if outcome.how in ("fault", "reset"):
        return "fault"
    if outcome.loser is None:
        return "draw"
    status = "lost" if outcome.loser == entry else "won"
    return f"pit_{status}" if outcome.how == "pit" else status


def bout_score_cm(outcome: BoutOutcome, entry: int, pit_bonus_cm: float) -> float:
    """The entry's score for a rating bout: the centimetres of ground it won, the marker's distance
    from the centre line towards the entry's own side, plus the pit bonus when only the opponent is
    in the pit, minus it when only the entry is (nothing when both are); for its fault (bout_status),
    minus FAULT_PITS pit bonuses."""
    if outcome.how in ("fault", "reset"):
        return -FAULT_PITS * pit_bonus_cm
    if outcome.how == "draw":  # the centre line exactly: nobody's ground
        return 0.0
    x = float(marker_x(outcome.string[-1:])[0])
    last = outcome.trace[:, -1]
    pits = int(in_pit(last[1 - entry])) - int(in_pit(last[entry]))
    return 100.0 * (-x if entry == 0 else x) + pit_bonus_cm * pits
