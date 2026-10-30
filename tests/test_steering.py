"""A long lane's heading hold: how it is declared, the yaw rate it asks for,
and the steps it asks for one."""

from types import SimpleNamespace

import numpy as np
import pytest

from arena.constants import CTRL_DT
from arena.manifest import ManifestError, Steering, all_events, load_event, load_manifest
from arena.policy import load_policy
from arena.runner import _steered, run_once
from tests.test_lights import _Listener, _schedule, _short
from tests.test_manifest import GOOD, STAGE, write_manifest
from tests.test_runner import REFERENCE

EVENT = "sock-heist-6m"

FIELDS = {"lookahead_m": "0.5", "gain": "2.0", "max_yaw_rate": "1.0"}


def steering_table(**overrides) -> str:
    fields = FIELDS | overrides
    return "[steering]\n" + "".join(f"{key}={value}\n" for key, value in fields.items() if value is not None)


def write_steering(tmp_path, **overrides):
    # GOOD's last section is the empty [clip], so the table goes there, after every other one.
    return write_manifest(tmp_path, clip=steering_table(**overrides))


@pytest.fixture(scope="module")
def heist():
    return load_event(EVENT)


@pytest.fixture(scope="module")
def walker():
    return load_policy(REFERENCE)


def test_the_long_lane_holds_its_ducks_heading(heist):
    assert heist.steering == Steering(lookahead_m=0.5, gain=2.0, max_yaw_rate=1.0)


def test_no_other_event_holds_a_heading():
    assert [m.id for m in all_events() if m.steering is not None] == [EVENT]


def test_steering_loads_and_serialises(tmp_path):
    m = load_manifest(write_steering(tmp_path, gain="3"))
    assert m.steering == Steering(lookahead_m=0.5, gain=3.0, max_yaw_rate=1.0)
    assert m.steering.to_dict() == {"lookahead_m": 0.5, "gain": 3.0, "max_yaw_rate": 1.0}


def test_a_stage_refuses_steering(tmp_path):
    with pytest.raises(ManifestError, match=r"takes no \[steering\]"):
        load_manifest(write_manifest(tmp_path, **STAGE, clip=steering_table()))


def test_steering_must_be_a_table(tmp_path):
    with pytest.raises(ManifestError, match=r"\[steering\] must be a table"):
        load_manifest(write_manifest(tmp_path, root=GOOD["root"] + "steering=3\n"))


def test_the_hold_owns_the_yaw_rate(tmp_path):
    turning = '[command]\nvel=[0.25,0,0.2]\nhead=[0,0,0,0]\nbody=[0,0,0,0,0,0]\n'
    with pytest.raises(ManifestError, match=r"\[command\] vel's third value must be 0"):
        load_manifest(write_manifest(tmp_path, command=turning, clip=steering_table()))


@pytest.mark.parametrize(
    "overrides, complaint",
    [
        ({"lookahead_m": "0"}, r"lookahead_m must be a positive number, got 0"),
        ({"gain": "-2.0"}, r"gain must be a positive number, got -2\.0"),
        ({"max_yaw_rate": "true"}, r"max_yaw_rate must be a positive number, got True"),
        ({"gain": '"2"'}, r"gain must be a positive number, got '2'"),
        ({"gain": None}, r"\[steering\]: missing 'gain'"),
        ({"target": "0"}, r"\[steering\]: unknown keys \['target'\]"),
    ],
)
def test_malformed_steering_is_refused(tmp_path, overrides, complaint):
    with pytest.raises(ManifestError, match=complaint):
        load_manifest(write_steering(tmp_path, **overrides))


def _standing(y: float, yaw: float):
    """A duck's free joint at `y` across the lane, turned `yaw` from straight down it."""
    qpos = np.array([1.0, y, 0.2, np.cos(yaw / 2), 0.0, 0.0, np.sin(yaw / 2)])
    return SimpleNamespace(qpos=qpos), SimpleNamespace(free=0)


@pytest.mark.parametrize(
    "y, yaw, rate",
    [
        (0.0, 0.0, 0.0),  # on the centre line, facing down the lane
        (0.1, 0.0, 2.0 * np.arctan2(-0.1, 0.5)),  # left of it: turned right, back toward it
        (-0.1, 0.0, -2.0 * np.arctan2(-0.1, 0.5)),  # and the other way from the right
        (0.0, 0.3, -0.6),  # on it, facing left: turned right
        (0.1, -np.arctan2(0.1, 0.5), 0.0),  # already headed for the line half a metre on
        (0.0, 1.0, -1.0),  # no faster than the event allows
        (0.0, np.pi - 0.1, -1.0),  # facing back up the lane: round the short way
    ],
)
def test_the_hold_turns_the_duck_toward_the_centre_line_ahead(heist, y, yaw, rate):
    command = np.asarray(heist.command_at(0.6), dtype=np.float64)
    steered = _steered(heist.steering, *_standing(y, yaw), command)
    assert steered[2] == pytest.approx(rate, abs=1e-12)
    np.testing.assert_array_equal(np.delete(steered, 2), np.delete(command, 2))
    assert command[2] == 0.0, "the command asked for was steered in place"


def test_the_duck_is_steered_on_green_and_on_green_only(heist, walker):
    # The first green, the first red, and the start of the next green; no catch.
    event = _short(heist, 3.0, tolerance_m=100.0)
    listener = _Listener(walker)
    run_once(event, listener, seed=1, command=event.command_at(0.6))

    settle = round(event.start.settle_s / CTRL_DT)
    red = _schedule(event, 1).red
    twists = np.array(listener.twists)
    assert len(twists) == settle + len(red)
    # Standing on the line and under a red light: no yaw rate either.
    np.testing.assert_array_equal(twists[:settle], 0.0)
    np.testing.assert_array_equal(twists[settle:][red], 0.0)
    walking = twists[settle:][~red]
    np.testing.assert_array_equal(walking[:, 0], np.float32(0.6))
    np.testing.assert_array_equal(walking[:, 1], 0.0)
    assert np.abs(walking[:, 2]).max() <= event.steering.max_yaw_rate
    assert np.count_nonzero(walking[:, 2]) == len(walking)


def test_a_held_duck_keeps_to_its_lane(heist, walker):
    """Twenty seconds of the shipped event at a brisk walk, every light obeyed: the
    duck is still near the centre line it started on, and facing down the lane. On
    seeds 1 to 10 it strays 0.19 to 0.26 m from it, in a lane 0.8 m wide."""
    event = _short(heist, 20.0, tolerance_m=100.0)
    outcome = run_once(event, walker, seed=1, command=event.command_at(0.8))
    assert outcome.status == "timeout"
    assert outcome.progress_m > 2.0
    assert np.abs(outcome.trace[:, 1]).max() < 0.25
    w, z = outcome.trace[-1, 3], outcome.trace[-1, 6]
    assert abs(np.degrees(2 * np.arctan2(z, w))) < 20
