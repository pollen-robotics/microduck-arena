"""The giant's timetable: every red of one seed's race.

Drawn per seed from the event's three ranges, so every entrant faces the same
five timetables. It is drawn here and never in JavaScript: the page reads
`served`, and draws the giant in step with any replay."""

import zlib
from dataclasses import dataclass

import numpy as np

from .constants import CTRL_DT
from .manifest import Lights, Manifest

LIGHTS_STREAM = 4  # the seed_rng family's stream: 1 is the servo delays, 2 and 3 a troupe's


@dataclass(frozen=True)
class Red:
    onset: int   # the control step the light turns red on, from the start of the clock
    length: int  # how many control steps it stays red


def timetable(lights: Lights, event_id: str, seed: int, steps: int) -> tuple[Red, ...]:
    """Every red of one seed's race, `steps` control steps long. A red that starts
    before `steps` is kept whole."""
    rng = np.random.default_rng([zlib.crc32(event_id.encode()), seed, LIGHTS_STREAM])

    def draw(span: tuple[float, float]) -> int:
        return int(rng.integers(round(span[0] / CTRL_DT), round(span[1] / CTRL_DT) + 1))

    reds, onset = [], draw(lights.first_green_s)
    while onset < steps:
        length = draw(lights.red_s)
        reds.append(Red(onset, length))
        onset += length + draw(lights.green_s)
    return tuple(reds)


def served(manifest: Manifest) -> dict:
    """The event summary's `lights`: turn_s, tolerance_m, and every seed's timetable in seconds."""
    lights, steps = manifest.lights, round(manifest.time_limit_s / CTRL_DT)
    return {
        "turn_s": lights.turn_s,
        "tolerance_m": lights.tolerance_m,
        "timetables": {
            str(seed): [[round(r.onset * CTRL_DT, 2), round(r.length * CTRL_DT, 2)]
                        for r in timetable(lights, manifest.id, seed, steps)]
            for seed in manifest.seeds
        },
    }
