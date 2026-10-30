"""Sock Heist: how the giant's three ranges are declared, how a seed draws its
timetable from them, how it lies over a run's control steps, and how the giant
judges a duck."""

import dataclasses
import subprocess
import sys
from itertools import pairwise

import numpy as np
import pytest

from arena.actuator import Servos
from arena.constants import CTRL_DT, DECIMATION
from arena.course import compile_course
from arena.evaluate import evaluate, evaluate_at, trace_file
from arena.lights import Red, served, timetable
from arena.manifest import Lights, ManifestError, all_events, load_event, load_manifest
from arena.policy import load_policy
from arena.runner import COLLAPSE_S, _LightSteps, run_once
from arena.trace import as_ducks, decode, decode_caught
from tests.test_manifest import GOOD, STAGE, write_manifest
from tests.test_runner import REFERENCE, STEADY_VX

EVENT = "sock-heist-6m"

# A well-formed [lights] table, field by field. A test overrides one field (None
# leaves it out) to build a specific malformation.
FIELDS = {"first_green_s": "[0.6,1.0]", "green_s": "[1.6,3.0]", "red_s": "[1.4,2.4]",
          "turn_s": "0.4", "tolerance_m": "0.03"}
# The draw, pinned on these ranges: the contract's placeholders, kept here whatever A6 tunes.
PINNED = Lights(first_green_s=(0.6, 1.0), green_s=(1.6, 3.0), red_s=(1.4, 2.4), turn_s=0.4, tolerance_m=0.03)


def lights_table(**overrides) -> str:
    fields = FIELDS | overrides
    return "[lights]\n" + "".join(f"{key}={value}\n" for key, value in fields.items() if value is not None)


def write_lights(tmp_path, **overrides):
    # GOOD's last section is the empty [clip], so the table goes there, after every other one.
    return write_manifest(tmp_path, clip=lights_table(**overrides))


@pytest.fixture(scope="module")
def heist():
    return load_event(EVENT)


@pytest.fixture(scope="module")
def walker():
    return load_policy(REFERENCE)


def test_the_heist_is_played_to_lights_on_a_6_m_lane(heist):
    assert (heist.title, heist.order, heist.course.kind, heist.course.length_m) == ("6 m Sock Heist", 50, "lane", 6.0)
    assert heist.lights == Lights(first_green_s=(0.6, 1.0), green_s=(1.6, 3.0), red_s=(1.4, 2.4),
                                  turn_s=0.4, tolerance_m=0.03)
    assert heist.time_limit_s == 40.0
    assert len({heist, load_event(EVENT)}) == 1


def test_the_heist_is_filmed_whole_at_life_speed_with_its_giant(heist):
    assert heist.clip.tape_max_s == heist.time_limit_s
    assert heist.clip.sounds == ("crowd", "horn", "giant", "verdict")
    assert heist.clip.camera.kind == "chase" and heist.clip.camera.track is True
    assert 0 < heist.clip.camera.hold < heist.course.length_m


def test_no_other_event_has_lights():
    assert [m.id for m in all_events() if m.lights is not None] == [EVENT]


def test_lights_load_as_three_ranges(tmp_path):
    assert load_manifest(write_lights(tmp_path)).lights == PINNED
    assert load_manifest(write_lights(tmp_path, turn_s="0")).lights.turn_s == 0.0
    assert load_manifest(write_lights(tmp_path, green_s="[2.0,2.0]")).lights.green_s == (2.0, 2.0)


def test_the_giants_sound_goes_with_lights(tmp_path):
    giant = '[clip]\nsounds=["crowd","giant"]\n'
    with pytest.raises(ManifestError, match=r"the giant's sound goes with \[lights\]"):
        load_manifest(write_manifest(tmp_path, clip=giant))
    assert load_manifest(write_manifest(tmp_path, clip=giant + lights_table())).clip.sounds == ("crowd", "giant")


def test_a_stage_refuses_lights(tmp_path):
    with pytest.raises(ManifestError, match=r"takes no \[lights\]"):
        load_manifest(write_manifest(tmp_path, **STAGE, clip=lights_table()))


def test_lights_must_be_a_table(tmp_path):
    with pytest.raises(ManifestError, match=r"\[lights\] must be a table"):
        load_manifest(write_manifest(tmp_path, root=GOOD["root"] + "lights=3\n"))


@pytest.mark.parametrize(
    "overrides, complaint",
    [
        ({"green_s": "[]"}, r"green_s must be two positive seconds, lo then hi, got \[\]"),
        ({"green_s": "1.6"}, r"green_s must be two positive seconds, lo then hi, got 1\.6"),
        ({"red_s": "[1.4,2.0,2.4]"}, r"red_s must be two positive seconds"),
        ({"red_s": "[0,2.4]"}, r"red_s must be two positive seconds"),
        ({"first_green_s": "[true,1.0]"}, r"first_green_s must be two positive seconds"),
        ({"green_s": '["1.6",3.0]'}, r"green_s must be two positive seconds"),
        ({"green_s": "[3.0,1.6]"}, r"green_s must not have its lo above its hi, got \[3\.0, 1\.6\]"),
        ({"first_green_s": "[0.61,1.0]"}, r"first_green_s must be whole numbers of 0\.02 s control steps, got \[0\.61, 1\.0\]"),
        ({"red_s": "[1.4,2.41]"}, r"red_s must be whole numbers of 0\.02 s control steps"),
        ({"turn_s": "-0.02"}, r"turn_s must be zero or more, a whole number of 0\.02 s control steps, got -0\.02"),
        ({"turn_s": "0.41"}, r"turn_s must be zero or more, a whole number of 0\.02 s control steps, got 0\.41"),
        ({"turn_s": "true"}, r"turn_s must be zero or more"),
        ({"turn_s": "1.4"}, r"turn_s must be shorter than the shortest red, or the giant never looks"),
        ({"tolerance_m": "0.0"}, r"tolerance_m must be a positive distance, got 0\.0"),
        ({"tolerance_m": "-0.03"}, r"tolerance_m must be a positive distance"),
        ({"tolerance_m": "true"}, r"tolerance_m must be a positive distance, got True"),
        ({"tolerance_m": None}, r"\[lights\]: missing 'tolerance_m'"),
        ({"first_green_s": None}, r"\[lights\]: missing 'first_green_s'"),
        ({"seed": "1"}, r"\[lights\]: unknown keys \['seed'\]"),
    ],
)
def test_malformed_lights_are_refused(tmp_path, overrides, complaint):
    with pytest.raises(ManifestError, match=complaint):
        load_manifest(write_lights(tmp_path, **overrides))


def test_the_draw_is_pinned():
    assert timetable(PINNED, EVENT, 1, 3000)[:5] == (
        Red(35, 97), Red(239, 74), Red(463, 97), Red(653, 95), Red(849, 111))


def test_the_draw_is_the_same_in_another_process():
    code = ("from arena.lights import timetable; from arena.manifest import Lights; "
            "print([(r.onset, r.length) for r in timetable("
            "Lights((0.6, 1.0), (1.6, 3.0), (1.4, 2.4), 0.4, 0.03), 'sock-heist-6m', 4, 3000)])")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == str([(r.onset, r.length) for r in timetable(PINNED, EVENT, 4, 3000)])


def test_every_seed_draws_its_own_timetable_within_the_ranges(heist):
    steps = round(heist.time_limit_s / CTRL_DT)
    tables = {seed: timetable(heist.lights, heist.id, seed, steps) for seed in heist.seeds}
    assert len(set(tables.values())) == len(heist.seeds)
    first, green, red = ((round(lo / CTRL_DT), round(hi / CTRL_DT)) for lo, hi in
                         (heist.lights.first_green_s, heist.lights.green_s, heist.lights.red_s))
    for reds in tables.values():
        assert first[0] <= reds[0].onset <= first[1]
        assert all(red[0] <= r.length <= red[1] for r in reds)
        assert all(green[0] <= b.onset - a.onset - a.length <= green[1] for a, b in pairwise(reds))
        assert reds[-1].onset < steps


def test_a_red_on_the_last_step_is_kept_whole_and_none_starts_at_the_limit():
    # A first green of 50 steps, reds of 70, greens of 50: reds start at steps 50 and 170.
    fixed = Lights(first_green_s=(1.0, 1.0), green_s=(1.0, 1.0), red_s=(1.4, 1.4), turn_s=0.4, tolerance_m=0.03)
    assert timetable(fixed, EVENT, 1, 171) == (Red(50, 70), Red(170, 70))
    assert timetable(fixed, EVENT, 1, 170) == (Red(50, 70),)
    steps = _LightSteps.of(timetable(fixed, EVENT, 1, 171), 20, 171)
    assert steps.red[170] and np.flatnonzero(steps.mark).tolist() == [69] and not steps.watch[120:].any()


def test_a_shorter_race_meets_the_first_reds_of_a_longer_one(heist):
    short, long = (timetable(heist.lights, heist.id, 2, steps) for steps in (150, 3000))
    assert short and long[:len(short)] == short


def test_the_summary_serves_every_seeds_timetable_in_seconds(heist):
    pinned = served(dataclasses.replace(heist, lights=PINNED, time_limit_s=60.0))
    assert set(pinned) == {"turn_s", "tolerance_m", "timetables"}
    assert (pinned["turn_s"], pinned["tolerance_m"]) == (0.4, 0.03)
    assert set(pinned["timetables"]) == {"1", "2", "3", "4", "5"}
    assert pinned["timetables"]["1"][:5] == [[0.7, 1.94], [4.78, 1.48], [9.26, 1.94], [13.06, 1.9], [16.98, 2.22]]


# Reds of 80, 70 and 80 steps from steps 30, 160 and 260: in 0.02 s steps a turn of 20 is 0.4 s.
REDS = (Red(30, 80), Red(160, 70), Red(260, 80))


def _spans(steps: int, *spans: tuple[int, int]) -> np.ndarray:
    mask = np.zeros(steps, dtype=bool)
    for start, stop in spans:
        mask[start:stop] = True
    return mask


def test_the_timetable_lies_over_the_steps():
    steps = _LightSteps.of(REDS, 20, 300)
    # The third red is cut short by the end of the run.
    np.testing.assert_array_equal(steps.red, _spans(300, (30, 110), (160, 230), (260, 300)))
    # Step i ends at (i + 1) * CTRL_DT: the giant has turned round once step
    # onset + 20 - 1 is over, and is watching from the step after it.
    assert np.flatnonzero(steps.mark).tolist() == [49, 179, 279]
    np.testing.assert_array_equal(steps.watch, _spans(300, (50, 110), (180, 230), (280, 300)))


def test_with_no_turn_the_mark_is_the_last_green_step_and_the_whole_red_is_watched():
    steps = _LightSteps.of(REDS, 0, 300)
    assert np.flatnonzero(steps.mark).tolist() == [29, 159, 259]
    np.testing.assert_array_equal(steps.watch, steps.red)


def test_a_red_the_run_ends_inside_its_turn_is_never_watched():
    steps = _LightSteps.of((Red(30, 80),), 20, 40)
    np.testing.assert_array_equal(steps.red, _spans(40, (30, 40)))
    assert not steps.mark.any()
    assert not steps.watch.any()


class _Listener:
    """The reference walker, noting the twist it is asked for at every control step."""

    def __init__(self, policy):
        self.policy = policy
        self.twists = []

    def act(self, obs):
        self.twists.append(obs[48:51].copy())
        return self.policy.act(obs)


def _short(event, seconds: float, tolerance_m: float):
    """The event cut to its first red or two, judged at a tolerance of the test's choosing."""
    return dataclasses.replace(event, time_limit_s=seconds,
                               lights=dataclasses.replace(event.lights, tolerance_m=tolerance_m))


def _schedule(event, seed: int) -> _LightSteps:
    """The giant's timetable for `seed`, laid over the event's timed steps as run_once lays it."""
    steps = round(event.time_limit_s / CTRL_DT)
    return _LightSteps.of(timetable(event.lights, event.id, seed, steps), round(event.lights.turn_s / CTRL_DT), steps)


def _first_look(event, seed: int) -> int:
    """The first step the giant watches on `seed`: its first red's onset plus the turn."""
    steps = round(event.time_limit_s / CTRL_DT)
    return timetable(event.lights, event.id, seed, steps)[0].onset + round(event.lights.turn_s / CTRL_DT)


@pytest.mark.parametrize("seed", [1, 3])
def test_the_duck_settles_standing_walks_on_green_and_is_asked_to_stand_on_red(heist, walker, seed):
    # 3 s: the first green, the first red, and the start of the next green. A
    # tolerance no duck strays from: this test is about what the duck is asked.
    # Without the lane's heading hold, which asks for a yaw rate of its own
    # (tests/test_steering.py).
    event = dataclasses.replace(_short(heist, 3.0, tolerance_m=100.0), steering=None)
    listener = _Listener(walker)
    outcome = run_once(event, listener, seed=seed, command=event.command_at(STEADY_VX))
    assert outcome.status == "timeout"

    settle = round(event.start.settle_s / CTRL_DT)
    red = _schedule(event, seed).red
    walk, stand = np.float32([STEADY_VX, 0.0, 0.0]), np.zeros(3, dtype=np.float32)
    expected = [stand] * settle + [stand if r else walk for r in red]
    assert len(listener.twists) == len(expected) == settle + len(outcome.trace)
    np.testing.assert_array_equal(np.array(listener.twists), np.array(expected))


def test_a_duck_caught_moving_collapses_where_it_stood(heist, walker, monkeypatch):
    # Judged to 1 µm: the first step the giant watches catches the duck, and not one before it.
    drives, drive = [], Servos.drive
    monkeypatch.setattr(Servos, "drive", lambda self, data, target: (drives.append(1), drive(self, data, target)))
    event, listener = _short(heist, 3.0, tolerance_m=1e-6), _Listener(walker)
    outcome = run_once(event, listener, seed=1, command=event.command_at(STEADY_VX))
    caught, settle = _first_look(event, 1), round(event.start.settle_s / CTRL_DT)
    assert (outcome.status, outcome.time_s, outcome.caught_frame) == ("caught", None, caught)
    assert len(outcome.trace) == caught + 1 + round(COLLAPSE_S / CTRL_DT)
    # Its motors go off on the catch: no policy, no servo drive (one at reset, five a step up to it).
    assert len(listener.twists) == settle + caught + 1
    assert len(drives) == 1 + (DECIMATION + 1) * (settle + caught + 1)
    # It folds up and lies there: measured 6-9 cm lower and under 0.5 mm of motion (plan-a/still.py).
    assert outcome.trace[-1, 2] < outcome.trace[caught, 2] - 0.04
    assert np.ptp(outcome.trace[-25:, 0:3], axis=0).max() < 0.002


def test_a_duck_caught_on_the_last_step_collapses_past_the_limit(heist, walker):
    event = _short(heist, 3.0, tolerance_m=1e-6)
    caught = _first_look(event, 1)
    last = dataclasses.replace(event, time_limit_s=round((caught + 1) * CTRL_DT, 2))
    assert round(last.time_limit_s / CTRL_DT) == caught + 1
    outcome = run_once(last, walker, seed=1, command=last.command_at(STEADY_VX))
    assert (outcome.status, outcome.caught_frame) == ("caught", caught)
    assert len(outcome.trace) == caught + 1 + round(COLLAPSE_S / CTRL_DT)


def test_the_event_runs_end_to_end(heist, walker):
    """The shipped event, start to whatever end the walker meets. Not which end:
    two platforms' runs part ways within seconds (arena.golden), and this one
    runs for a minute."""
    model = compile_course(heist)
    assert model.nu == 14
    outcome = run_once(heist, walker, seed=1, model=model, command=heist.command_at(STEADY_VX))
    assert outcome.status in {"finish", "fall", "timeout", "caught"}
    collapse = round(COLLAPSE_S / CTRL_DT) if outcome.status == "caught" else 0
    assert 0 < len(outcome.trace) <= round(heist.time_limit_s / CTRL_DT) + collapse
    assert (outcome.caught_frame is not None) == (outcome.status == "caught")
    assert (outcome.time_s is not None) == (outcome.status == "finish")


@pytest.fixture(scope="module")
def caught_everywhere(heist, walker):
    """Every seed of the heist cut to 3 s and judged to 1 µm: caught at the giant's first look."""
    return evaluate_at(_short(heist, 3.0, tolerance_m=1e-6), walker, STEADY_VX)


def test_a_heist_evaluation_keeps_every_seed_of_its_command(heist, caught_everywhere):
    result, event = caught_everywhere, _short(heist, 3.0, tolerance_m=1e-6)
    assert set(result.seed_traces) == set(heist.seeds)
    np.testing.assert_array_equal(result.seed_traces[result.trace_seed].trace, result.trace)
    np.testing.assert_array_equal(result.seed_traces[result.trace_seed].settle, result.settle)
    assert {s: kept.caught for s, kept in result.seed_traces.items()} == {s: _first_look(event, s) for s in heist.seeds}


def test_the_full_sweep_keeps_every_seed_of_the_scored_command(heist, walker):
    result = evaluate(_short(heist, 3.0, tolerance_m=1e-6), walker)
    assert set(result.seed_traces) == set(heist.seeds)
    np.testing.assert_array_equal(result.seed_traces[result.trace_seed].trace, result.trace)


def test_a_heist_run_is_stored_with_every_seed_and_its_catch(caught_everywhere):
    blob = trace_file(caught_everywhere)
    for seed, kept in caught_everywhere.seed_traces.items():
        np.testing.assert_allclose(decode(blob, seed), as_ducks(kept.trace), atol=3e-3)
        assert decode_caught(blob, seed) == kept.caught


def test_a_race_without_lights_keeps_its_one_trace(walker):
    result = evaluate_at(dataclasses.replace(load_event("sprint-2m"), time_limit_s=1.0), walker, STEADY_VX)
    assert result.seed_traces is None
    np.testing.assert_allclose(decode(trace_file(result)), as_ducks(result.trace), atol=3e-3)
