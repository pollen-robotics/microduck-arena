import io

import numpy as np
import pytest

from arena import trace as codec
from arena.constants import TRACE_WIDTH


def test_round_trip_preserves_shape_and_dtype():
    original = np.random.default_rng(0).standard_normal((100, TRACE_WIDTH)).astype(np.float32)
    restored = codec.decode(codec.encode(original))
    # A race's trace, or a performance stored before troupes, reads back as one duck.
    assert restored.shape == (1, *original.shape)
    assert restored.dtype == np.float32


def test_round_trip_is_accurate_to_float16():
    original = np.random.default_rng(0).uniform(-3, 3, (50, TRACE_WIDTH)).astype(np.float32)
    restored = codec.decode(codec.encode(original))
    # float16 has ~3 decimal digits; millimetre accuracy is plenty for a replay.
    np.testing.assert_allclose(restored[0], original, atol=3e-3)


def test_a_troupes_trace_and_settle_round_trip_duck_by_duck():
    rng = np.random.default_rng(3)
    trace = rng.uniform(-3, 3, (4, 40, TRACE_WIDTH)).astype(np.float32)
    settle = rng.uniform(-3, 3, (4, 26, TRACE_WIDTH)).astype(np.float32)
    blob = codec.encode(trace, settle)
    np.testing.assert_allclose(codec.decode(blob), trace, atol=3e-3)
    np.testing.assert_allclose(codec.decode_settle(blob), settle, atol=3e-3)


def test_a_trace_stored_before_troupes_reads_as_one_duck():
    """What the store holds today: a plain 2-D float16 trace and settle, written before this codec knew ducks."""
    trace = np.random.default_rng(4).uniform(-3, 3, (30, TRACE_WIDTH)).astype(np.float16)
    buffer = io.BytesIO()
    np.savez_compressed(buffer, trace=trace, settle=trace[:5])
    assert codec.decode(buffer.getvalue()).shape == (1, 30, TRACE_WIDTH)
    assert codec.decode_settle(buffer.getvalue()).shape == (1, 5, TRACE_WIDTH)


@pytest.mark.parametrize("shape", [(TRACE_WIDTH,), (2, 3, 4, TRACE_WIDTH), (5, TRACE_WIDTH + 1), (2, 5, 7)])
def test_a_trace_that_is_neither_one_duck_nor_a_troupe_is_refused(shape):
    with pytest.raises(ValueError, match="must be"):
        codec.encode(np.zeros(shape, dtype=np.float32))


def test_the_wire_format_is_float16():
    """Pin the dtype directly.

    The size assertion below cannot do this job: an all-zero or otherwise
    compressible array is crushed by zip regardless of dtype, so a regression
    that dropped the float16 downcast would sail past a size bound.
    """
    original = np.random.default_rng(0).standard_normal((10, TRACE_WIDTH)).astype(np.float32)
    assert np.abs(original).max() < codec.FLOAT16_REACH
    with np.load(io.BytesIO(codec.encode(original))) as loaded:
        assert loaded["trace"].dtype == np.float16


def test_a_long_lanes_trace_is_stored_float32_and_its_settle_need_not_be():
    """Six metres down a lane, float16 would place the duck to the nearest 4 mm or so."""
    rng = np.random.default_rng(5)
    trace = rng.uniform(-3, 3, (60, TRACE_WIDTH)).astype(np.float32)
    trace[:, 0] = np.linspace(0.0, 6.0, 60, dtype=np.float32)
    settle = rng.uniform(-3, 3, (26, TRACE_WIDTH)).astype(np.float32)
    blob = codec.encode(trace, settle)
    with np.load(io.BytesIO(blob)) as loaded:
        assert (loaded["trace"].dtype, loaded["settle"].dtype) == (np.float32, np.float16)
    np.testing.assert_array_equal(codec.decode(blob)[0], trace)
    np.testing.assert_allclose(codec.decode_settle(blob)[0], settle, atol=3e-3)


def test_a_solver_explosions_nans_leave_a_short_trace_float16():
    trace = np.random.default_rng(6).uniform(-3, 3, (20, TRACE_WIDTH)).astype(np.float32)
    trace[-1] = np.nan
    with np.load(io.BytesIO(codec.encode(trace))) as loaded:
        assert loaded["trace"].dtype == np.float16


def test_a_20_second_sprint_trace_stays_small():
    # Random data, not zeros: incompressible content is what makes the bound
    # mean something. A real 911-frame trace measures about 35 KB.
    frames = int(20.0 / 0.02)  # 1000 frames at 50 Hz
    noisy = np.random.default_rng(1).standard_normal((frames, TRACE_WIDTH)).astype(np.float32)
    blob = codec.encode(noisy)
    assert len(blob) < 100_000, f"{len(blob)} bytes is larger than expected"


def test_empty_trace_round_trips():
    empty = np.zeros((0, TRACE_WIDTH), dtype=np.float32)
    assert codec.decode(codec.encode(empty)).shape == (1, 0, TRACE_WIDTH)


def test_the_settle_round_trips_beside_the_trace():
    rng = np.random.default_rng(2)
    trace = rng.uniform(-3, 3, (40, TRACE_WIDTH)).astype(np.float32)
    settle = rng.uniform(-3, 3, (26, TRACE_WIDTH)).astype(np.float32)
    blob = codec.encode(trace, settle)
    np.testing.assert_allclose(codec.decode(blob)[0], trace, atol=3e-3)
    restored = codec.decode_settle(blob)
    assert restored.dtype == np.float32
    np.testing.assert_allclose(restored[0], settle, atol=3e-3)


def test_a_trace_stored_before_settles_were_recorded_has_none():
    blob = codec.encode(np.zeros((5, TRACE_WIDTH), dtype=np.float32))
    assert codec.decode_settle(blob).shape == (1, 0, TRACE_WIDTH)


def test_a_tugs_string_round_trips_beside_its_ducks():
    rng = np.random.default_rng(5)
    trace = rng.uniform(-3, 3, (2, 5, TRACE_WIDTH)).astype(np.float32)
    settle = rng.uniform(-3, 3, (2, 26, TRACE_WIDTH)).astype(np.float32)
    string = rng.uniform(-3, 3, (5, 17, 3)).astype(np.float32)
    string_settle = rng.uniform(-3, 3, (26, 17, 3)).astype(np.float32)
    blob = codec.encode(trace, settle, string, string_settle)
    np.testing.assert_allclose(codec.decode(blob), trace, atol=3e-3)
    np.testing.assert_allclose(codec.decode_settle(blob), settle, atol=3e-3)
    restored_settle, restored = codec.decode_string(blob)
    assert restored_settle.dtype == restored.dtype == np.float32
    np.testing.assert_allclose(restored_settle, string_settle, atol=3e-3)
    np.testing.assert_allclose(restored, string, atol=3e-3)
    with np.load(io.BytesIO(blob)) as loaded:
        assert loaded["string"].dtype == loaded["string_settle"].dtype == np.float16


def test_a_trace_without_a_string_says_so():
    blob = codec.encode(np.zeros((2, 5, TRACE_WIDTH)), np.zeros((2, 26, TRACE_WIDTH)))
    with pytest.raises(ValueError, match="no string"):
        codec.decode_string(blob)


@pytest.mark.parametrize("shape", [(17, 3), (5, 16, 3), (5, 17, 2), (1, 5, 17, 3)])
def test_a_string_that_is_not_seventeen_points_a_frame_is_refused(shape):
    with pytest.raises(ValueError, match=r"string_settle must be \(frames, 17, 3\)"):
        codec.encode(np.zeros((2, 5, TRACE_WIDTH)), string=np.zeros((5, 17, 3)), string_settle=np.zeros(shape))


def test_a_heists_file_holds_every_seed_its_settle_and_its_catch():
    rng = np.random.default_rng(5)
    one, two = (rng.uniform(-6, 6, (n, TRACE_WIDTH)).astype(np.float32) for n in (40, 2100))
    settle = rng.uniform(-1, 1, (26, TRACE_WIDTH)).astype(np.float32)
    blob = codec.encode_seeds({1: codec.SeedTrace(one, settle), 2: codec.SeedTrace(two, settle, caught=2049)})
    with np.load(io.BytesIO(blob)) as loaded:
        assert sorted(loaded.files) == ["caught_2", "settle_1", "settle_2", "trace_1", "trace_2"]
        # 6 m lanes reach past FLOAT16_REACH; a frame index is exact, which float16 is not past 2048.
        assert (loaded["trace_1"].dtype, loaded["caught_2"].dtype) == (np.float32, np.int32)
    np.testing.assert_array_equal(codec.decode(blob, 1), one[np.newaxis])
    np.testing.assert_array_equal(codec.decode(blob, 2), two[np.newaxis])
    np.testing.assert_allclose(codec.decode_settle(blob, 2), settle[np.newaxis], atol=3e-3)
    assert (codec.decode_caught(blob, 1), codec.decode_caught(blob, 2)) == (None, 2049)


def test_a_heists_file_has_no_seed_it_did_not_keep():
    frames = np.zeros((3, TRACE_WIDTH), np.float32)
    blob = codec.encode_seeds({1: codec.SeedTrace(frames, frames)})
    for read in (lambda: codec.decode(blob), lambda: codec.decode(blob, 3), lambda: codec.decode_settle(blob, 3)):
        with pytest.raises(KeyError):
            read()
