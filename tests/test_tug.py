import dataclasses
import math

import numpy as np
import pytest

from arena import runner, tug
from arena.assets import ASSET_ROOT
from arena.constants import CTRL_DT
from arena.course import compile_tug, string_sites
from arena.evaluate import evaluate
from arena.manifest import BoutRules, load_event
from arena.policy import PolicyError, load_policy
from arena.tug import (
    MIDDLE,
    SIDES,
    STRING_POINTS,
    BoutOutcome,
    _verdict,
    bout_score_cm,
    bout_status,
    entry_side,
    in_pit,
    marker_x,
    reference_duck,
    run_bout,
)
from tests.test_assets import REFERENCE_SHA256
from tests.test_policy import looping_onnx

TUG = load_event("tug-of-war")
SHORT = dataclasses.replace(TUG, bout=BoutRules(4.0, 2, 5))
WALKER = ASSET_ROOT / "policies" / "BEST_alpha_walking.onnx"
WEST, EAST = (1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)
ON_ITS_SIDE = (math.cos(math.pi / 4), math.sin(math.pi / 4), 0.0, 0.0)   # 90° about x: gravity z 0 > -0.5

class _ZeroPolicy:
    def act(self, obs):
        return np.zeros(14, dtype=np.float32)

class _NaN:
    """A duck whose action is not a number on its calls in `bad` (counted from 1, settle included), on
    every call when `bad` is None, and zeros otherwise."""
    def __init__(self, bad=None):
        self.bad, self.calls = bad, 0

    def act(self, obs):
        self.calls += 1
        return np.full(14, np.nan if self.bad is None or self.calls in self.bad else 0.0, dtype=np.float32)

class _Constant:
    """The same action on every joint, every step."""
    def __init__(self, value):
        self.value = value

    def act(self, obs):
        return np.full(14, self.value, dtype=np.float32)

class _Fails:
    """A policy that never gives an action (arena.policy.Policy raises a PolicyError for it)."""
    def act(self, obs):
        raise PolicyError("no action: broken")

def frame(pos, quat):
    f = np.zeros(21)
    f[0:3], f[3:7] = pos, quat
    return f

def straight(trace):
    """A string laid straight between the two trunks of every frame, (frames, 17, 3): its middle is their midpoint."""
    w, e = trace[0, :, None, 0:3], trace[1, :, None, 0:3]
    return w + (e - w) * np.linspace(0.0, 1.0, 17)[None, :, None]

def test_the_marker_is_the_strings_middle_point():
    s = np.zeros((2, 17, 3)); s[:, 8, 0] = [0.07, -0.02]; s[:, 7, 0] = 9.0
    assert list(marker_x(s)) == pytest.approx([0.07, -0.02]) and (STRING_POINTS, MIDDLE) == (17, 8)

def test_a_trunk_below_the_drop_is_in_the_pit():
    assert in_pit(frame((0, 0, -0.051), WEST)) and not in_pit(frame((0, 0, -0.049), WEST))

def test_the_judge_reads_the_pit_then_the_strings_middle():
    base = np.array([[frame((-0.6, 0, 0.1), WEST)], [frame((0.6, 0, 0.1), EAST)]])
    assert _verdict(base, straight(base), final=False) is None
    east_in = base.copy(); east_in[1, 0, 2] = -0.1
    assert _verdict(east_in, straight(east_in), final=False) == (1, "pit")
    both = base.copy(); both[:, 0, 2] = -0.1
    pulled = straight(both); pulled[:, 8, 0] = -0.03                      # the middle west, the ends' midpoint at 0
    assert _verdict(both, pulled, final=False) == (1, "marker")
    assert _verdict(base, straight(base), final=True) == (None, "draw")
    sagging = straight(base); sagging[:, 8, :] = [0.02, 0.0, -0.11]       # dipped into the pit, east of the line
    assert _verdict(base, sagging, final=True) == (0, "marker")

def test_a_duck_on_its_side_stays_in_play():
    base = np.array([[frame((-0.6, 0, 0.1), WEST)], [frame((0.6, 0, 0.1), EAST)]])
    tipped = np.repeat(base, 15, axis=1); tipped[0, :, 3:7] = ON_ITS_SIDE     # 15 frames: 0.3 s on its side
    assert _verdict(tipped, straight(tipped), final=False) is None            # still in play
    tipped[1, -1, 2] = -0.1                                                   # the duck on its feet drops in
    assert _verdict(tipped, straight(tipped), final=False) == (1, "pit")

def test_a_bout_records_its_string_every_step_and_the_settle_before():
    out = run_bout(SHORT, _ZeroPolicy(), _ZeroPolicy(), 1)
    assert out.string.shape == (out.trace.shape[1], 17, 3) and out.string_settle.shape == (26, 17, 3)
    assert np.linalg.norm(out.string[:, 0] - out.string[:, 16], axis=1).max() <= 1.005
    again = run_bout(SHORT, _ZeroPolicy(), _ZeroPolicy(), 1)
    np.testing.assert_array_equal(again.string, out.string)

def test_two_ducks_that_do_nothing_are_decided_the_same_way_every_time():
    out = run_bout(SHORT, _ZeroPolicy(), _ZeroPolicy(), 1)
    assert out.how in ("pit", "marker", "draw")
    assert out.trace.shape[1] == round(out.time_s / CTRL_DT) and out.settle.shape == (2, 26, 21)
    again = run_bout(SHORT, _ZeroPolicy(), _ZeroPolicy(), 1)
    np.testing.assert_array_equal(again.trace, out.trace)
    assert (again.loser, again.how) == (out.loser, out.how)

def test_a_bout_nobody_goes_out_of_is_decided_by_the_marker_at_the_time_limit():
    out = run_bout(SHORT, _ZeroPolicy(), _ZeroPolicy(), 1)
    assert out.trace.shape == (2, 200, 21) and out.time_s == pytest.approx(4.0)
    x = marker_x(out.string[-1:])[0]
    assert (out.loser, out.how) == ((0, "marker") if x > 0 else (1, "marker") if x < 0 else (None, "draw"))

def test_the_string_never_stretches_past_its_length():
    walker = load_policy(WALKER)
    out = run_bout(TUG, walker, walker, 1)
    length = np.linalg.norm(out.string[:, 0] - out.string[:, 16], axis=1)
    assert TUG.course.string_m - 0.01 <= length.max() <= TUG.course.string_m + 0.01   # taut, never longer

def _string_bout(manifest, west, east, seed):
    """run_bout's timed steps, read off the physics after each: the distance between the two ducks'
    string ends, and the larger of the two ties' errors (a duck's end to the string's own end)."""
    model = compile_tug(manifest)
    command = np.asarray(manifest.command, dtype=np.float64)
    sim, _, _ = runner._start(manifest, model, [west, east], [0.0, 180.0], seed, [command, command])
    ends = [model.site(name).id for name in ("string_end", "duck1/string_end")]
    tips = string_sites(model)[[0, -1]]
    gaps, ties = [], []
    for _ in range(round(manifest.bout.time_limit_s / CTRL_DT)):
        sim.step([command, command])
        assert not runner._reset_by_mujoco(sim.data)
        at = sim.data.site_xpos
        gaps.append(float(np.linalg.norm(at[ends[0]] - at[ends[1]])))
        ties.append(float(np.linalg.norm(at[ends] - at[tips], axis=1).max()))
    return gaps, ties

def test_a_bout_on_the_string_holds_together():
    """The reference against itself, 4 s of timed steps: no reset, ends never past 1.005 m, ties within 1 cm."""
    gaps, ties = _string_bout(SHORT, reference_duck(TUG), reference_duck(TUG), 1)   # _start + sim.step as run_bout, each step read off data
    assert max(gaps) <= 1.005 and max(ties) <= 0.01

def test_a_duck_whose_action_is_not_a_number_loses_by_a_fault_at_once():
    """MuJoCo drives no motor while a servo's command is not a number, the other duck's included: unjudged,
    a NaN duck froze the reference and rated -0.1 cm, above a duck that never moves (-15.0)."""
    for west, east, loser in ((_NaN(), _ZeroPolicy(), 0), (_ZeroPolicy(), _NaN(), 1), (_NaN(), _NaN(), None)):
        out = run_bout(SHORT, west, east, 1)
        assert (out.loser, out.how, out.trace.shape) == (loser, "fault", (2, 1, 21)) and out.time_s == pytest.approx(CTRL_DT)

def test_a_nan_in_the_settle_is_called_on_the_first_timed_step_and_a_later_one_when_it_comes():
    once = run_bout(SHORT, _NaN(bad={1}), _ZeroPolicy(), 1)        # the settle's first step: the servos carry it on
    assert (once.loser, once.how) == (0, "fault") and once.time_s == pytest.approx(CTRL_DT)
    later = run_bout(SHORT, _ZeroPolicy(), _NaN(bad={40}), 1)      # 25 settle steps, then the 15th timed step
    assert (later.loser, later.how) == (1, "fault") and later.time_s == pytest.approx(15 * CTRL_DT)

def test_a_duck_that_faults_rates_below_any_bout_played_out():
    rating = evaluate(TUG, _NaN())
    assert rating.score == pytest.approx(-200.0) and {r.status for r in rating.per_seed} == {"fault"}

def test_a_duck_whose_policy_gives_no_action_faults():
    out = run_bout(SHORT, _Fails(), _ZeroPolicy(), 1)       # from the settle's first step: none at all
    assert (out.loser, out.how) == (0, "fault") and out.time_s == pytest.approx(CTRL_DT)

def test_a_duck_that_thinks_longer_than_the_bout_lasts_faults(monkeypatch):
    """SHORT's bouts last 4 s: a duck answering in 1/8 s has spent them on its 32nd answer, the settle's
    25 and then the 7th timed step's; the duck that answers at once is never short of time."""
    now = [0.0]
    monkeypatch.setattr(tug, "monotonic", lambda: now[0])
    class _Slow:
        def act(self, obs):
            now[0] += 0.125
            return np.zeros(14, dtype=np.float32)
    out = run_bout(SHORT, _ZeroPolicy(), _Slow(), 1)
    assert (out.loser, out.how) == (1, "fault") and out.time_s == pytest.approx(7 * CTRL_DT)

def test_a_model_that_loops_for_ever_rates_as_a_fault_a_second_a_bout(tmp_path):
    """Its first answer, in the settle, is given up after arena.policy.ANSWER_S; it is asked no more."""
    rating = evaluate(TUG, load_policy(looping_onnx(tmp_path / "loop.onnx")))
    assert rating.score == pytest.approx(-200.0) and {r.status for r in rating.per_seed} == {"fault"}

def test_a_duck_that_blows_the_physics_up_rates_as_a_fault():
    """Every joint at -inf: the servos' torque, as large as it goes, makes MuJoCo reset on the first timed
    step, a bout for nobody, with no frame. It rated 0.0 cm, above every duck that pulls and loses."""
    out = run_bout(TUG, _Constant(-np.inf), reference_duck(TUG), 1)
    assert (out.loser, out.how, out.trace.shape, out.string.shape) == (None, "reset", (2, 0, 21), (0, 17, 3))
    rating = evaluate(TUG, _Constant(-np.inf))
    assert rating.score == pytest.approx(-200.0) and {r.status for r in rating.per_seed} == {"fault"}

def _explode_at(monkeypatch, bad_step):
    """MuJoCo resets the simulation on timed step `bad_step`, as the runner's own check would say."""
    calls = iter(range(1_000_000))
    monkeypatch.setattr(tug, "_reset_by_mujoco", lambda data: next(calls) == bad_step)

def test_a_solver_explosion_ends_a_bout_for_nobody_and_its_frame_is_left_out(monkeypatch):
    assert tug._reset_by_mujoco is runner._reset_by_mujoco   # the runner's own check, reused
    whole = run_bout(SHORT, _ZeroPolicy(), _ZeroPolicy(), 1)
    _explode_at(monkeypatch, 10)
    out = run_bout(SHORT, _ZeroPolicy(), _ZeroPolicy(), 1)
    assert (out.loser, out.how, out.trace.shape) == (None, "reset", (2, 10, 21)) and out.time_s == pytest.approx(11 * CTRL_DT)
    assert out.string.shape == (10, 17, 3)
    np.testing.assert_array_equal(out.trace, whole.trace[:, :10])


def test_a_step_off_the_course_ends_a_bout_for_nobody_and_its_frame_is_left_out(monkeypatch):
    """A blow-up MuJoCo does not flag (pollen-robotics/microduck-arena#6): a trunk or a string point
    off the course is judged as a reset, never read by the pit or the marker."""
    course, trunks = TUG.course, np.array([[-0.6, 0.0, 0.1], [0.6, 0.0, 0.1]])
    string = np.linspace(trunks[0], trunks[1], STRING_POINTS)
    assert not tug.off_the_course(course, trunks, string)
    in_the_pit = trunks.copy()
    in_the_pit[0] = (-0.05, 0.0, -course.pit_depth_m)                        # down on the pit's floor: in play
    assert not tug.off_the_course(course, in_the_pit, string)
    flung = string.copy()
    flung[MIDDLE] = (12.79, 0.0, 0.5)                                       # the string of issue #6's last step
    assert tug.off_the_course(course, trunks, flung)
    sunk = trunks.copy()
    sunk[0] = (-1.07, 0.32, -1.34)                                          # its west trunk, under the canvas
    assert tug.off_the_course(course, sunk, string)
    whole = run_bout(SHORT, _ZeroPolicy(), _ZeroPolicy(), 1)
    assert not any(tug.off_the_course(course, whole.trace[:, k, 0:3], whole.string[k]) for k in range(whole.trace.shape[1]))
    calls = iter(range(1_000_000))
    monkeypatch.setattr(tug, "off_the_course", lambda *a: next(calls) == 10)
    out = run_bout(SHORT, _ZeroPolicy(), _ZeroPolicy(), 1)
    assert (out.loser, out.how, out.trace.shape, out.string.shape) == (None, "reset", (2, 10, 21), (10, 17, 3))
    np.testing.assert_array_equal(out.trace, whole.trace[:, :10])
    assert bout_status(out, 1) == "fault" and bout_score_cm(out, 1, 100.0) == pytest.approx(-200.0)


def bout_trace(x, pit=()):
    """One frame of a bout whose marker stands x m east of the centre line; the ducks in `pit` below the floor."""
    trace = np.array([[frame((-0.6 + x, 0, 0.1), WEST)], [frame((0.6 + x, 0, 0.1), EAST)]])
    for k in pit:
        trace[k, 0, 2] = -0.1
    return trace


def test_a_bout_scores_the_ground_the_entry_won_and_the_pit_either_way():
    def outcome(loser, how, time_s, trace):
        return BoutOutcome(1, loser, how, time_s, trace, np.zeros((2, 26, 21)), straight(trace), np.zeros((26, 17, 3)))
    out = lambda loser, how, x, pit=(): outcome(loser, how, 45.0, bout_trace(x, pit))
    assert [bout_score_cm(out(1, "marker", -0.1), e, 100.0) for e in (0, 1)] == pytest.approx([10.0, -10.0])
    assert [bout_score_cm(out(1, "pit", -0.1, (1,)), e, 100.0) for e in (0, 1)] == pytest.approx([110.0, -110.0])
    assert bout_score_cm(out(1, "marker", -0.1, (0, 1)), 0, 100.0) == pytest.approx(10.0)   # both in: no bonus
    drawn = out(None, "draw", 0.0)                                                           # dead centre
    assert [bout_score_cm(drawn, e, 100.0) for e in (0, 1)] == [0.0, 0.0] and bout_status(drawn, 1) == "draw"
    assert [bout_status(out(1, "pit", 0.0, (1,)), e) for e in (0, 1)] == ["pit_won", "pit_lost"]
    assert [bout_status(out(0, "marker", 0.1), e) for e in (0, 1)] == ["lost", "won"]
    # a fault, whoever's, and a reset are the entry's: twice the pit bonus, beyond any bout played out
    for faulted in (out(0, "fault", 0.0), out(None, "fault", 0.0), outcome(None, "reset", 0.02, np.zeros((2, 0, 21)))):
        assert [bout_score_cm(faulted, e, 100.0) for e in (0, 1)] == pytest.approx([-200.0, -200.0])
        assert [bout_status(faulted, e) for e in (0, 1)] == ["fault", "fault"]
    assert [entry_side(s) for s in (1, 2, 3, 4, 5)] == [0, 1, 0, 1, 0] and SIDES == ("west", "east")
    assert reference_duck(TUG).sha256 == REFERENCE_SHA256
