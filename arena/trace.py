"""Replay traces on the wire.

float16 at 50 Hz: a 20 s sprint is ~42 KB, and half a millimetre of precision is
invisible in a replay. The frontend renders these directly through the rig, so
physics never runs client-side.

float16's error grows with the value, though: under a millimetre below 4, but
up to 4 mm between 8 and 16. A frame array with any value of 4 or more, a duck
that walked that far down a long lane, is stored float32 instead. Every array
decodes to float32, whichever it was stored as.

Beside the timed trace, the untimed settle that led into it (see RunOutcome).
Traces stored before settles were recorded have none.

A race keeps one duck's (frames, TRACE_WIDTH); a stage keeps every duck of its
troupe, (ducks, frames, TRACE_WIDTH). Read back, both are (ducks, frames,
TRACE_WIDTH): a race, and a performance stored before troupes, are one duck.

A tug's file carries its string beside its two ducks: the string's points, west
to east, (frames, STRING_POINTS, 3), and its settle's, (settle + 1,
STRING_POINTS, 3), float16 like the ducks (0.24 mm off). The key's presence is
the version: every race and performance stored is as it was, and a tug's file
always carries its string.

A lights event's run keeps every seed in its one file, the store paying per file: `trace_{s}`,
`settle_{s}` and, for a duck the giant caught, `caught_{s}`, the frame it was caught on, an int32
because a frame index past 2048 is not exact in float16. A replay plays every lane on one seed.
"""

import io
from dataclasses import dataclass

import numpy as np

from .constants import TRACE_WIDTH
from .tug import STRING_POINTS

# Below this, float16 places a value to within a millimetre.
FLOAT16_REACH = 4.0


def _on_the_wire(array: np.ndarray) -> np.ndarray:
    # Finite values only: a solver explosion's NaNs say nothing about the lane.
    finite = np.abs(array[np.isfinite(array)])
    return array.astype(np.float32 if finite.size and finite.max() >= FLOAT16_REACH else np.float16)


@dataclass(frozen=True)
class SeedTrace:
    """One seed's run of a lights event: its trace, its settle, the frame the duck was caught on."""

    trace: np.ndarray
    settle: np.ndarray
    caught: int | None = None


def _check_ducks(ducks: dict[str, np.ndarray]) -> None:
    for name, array in ducks.items():
        if array.ndim not in (2, 3) or array.shape[-1] != TRACE_WIDTH:
            raise ValueError(
                f"{name} must be (frames, {TRACE_WIDTH}) or (ducks, frames, {TRACE_WIDTH}), got {array.shape}"
            )


def encode_seeds(seeds: dict[int, SeedTrace]) -> bytes:
    ducks = {f"{key}_{seed}": getattr(kept, key) for seed, kept in seeds.items() for key in ("trace", "settle")}
    _check_ducks(ducks)
    caught = {f"caught_{seed}": np.int32(kept.caught) for seed, kept in seeds.items() if kept.caught is not None}
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **{name: _on_the_wire(array) for name, array in ducks.items()}, **caught)
    return buffer.getvalue()


def encode(
    trace: np.ndarray,
    settle: np.ndarray | None = None,
    string: np.ndarray | None = None,
    string_settle: np.ndarray | None = None,
) -> bytes:
    ducks = {"trace": trace} if settle is None else {"trace": trace, "settle": settle}
    _check_ducks(ducks)
    points = {name: array for name, array in (("string", string), ("string_settle", string_settle))
              if array is not None}
    for name, array in points.items():
        if array.shape[1:] != (STRING_POINTS, 3):
            raise ValueError(f"{name} must be (frames, {STRING_POINTS}, 3), got {array.shape}")
    arrays, buffer = {**ducks, **points}, io.BytesIO()
    np.savez_compressed(buffer, **{name: _on_the_wire(array) for name, array in arrays.items()})
    return buffer.getvalue()


def as_ducks(frames: np.ndarray) -> np.ndarray:
    """A trace or a settle as (ducks, frames, TRACE_WIDTH) float32: one duck's is the first of one."""
    return (frames[np.newaxis] if frames.ndim == 2 else frames).astype(np.float32)


def decode(blob: bytes, seed: int | None = None) -> np.ndarray:
    """A race's trace; a heist's file needs its seed, and a seed it did not keep is a KeyError."""
    with np.load(io.BytesIO(blob)) as loaded:
        return as_ducks(loaded["trace" if seed is None else f"trace_{seed}"])


def decode_settle(blob: bytes, seed: int | None = None) -> np.ndarray:
    key = "settle" if seed is None else f"settle_{seed}"
    with np.load(io.BytesIO(blob)) as loaded:
        if seed is None and key not in loaded:
            return np.zeros((1, 0, TRACE_WIDTH), dtype=np.float32)
        return as_ducks(loaded[key])


def decode_caught(blob: bytes, seed: int) -> int | None:
    """The frame the giant caught this seed's duck on; None for a duck it never caught."""
    with np.load(io.BytesIO(blob)) as loaded:
        return int(loaded[f"caught_{seed}"]) if f"caught_{seed}" in loaded else None


def decode_string(blob: bytes) -> tuple[np.ndarray, np.ndarray]:
    """A tug's string, float32: its settle's points, then the timed ones."""
    with np.load(io.BytesIO(blob)) as loaded:
        if "string" not in loaded:
            raise ValueError("this trace holds no string")
        return loaded["string_settle"].astype(np.float32), loaded["string"].astype(np.float32)
