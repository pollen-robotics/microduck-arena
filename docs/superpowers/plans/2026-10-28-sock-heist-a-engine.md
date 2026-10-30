# Sock Heist A — The Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the contributor's red light, green light lane becomes `sock-heist-6m`: 6 m, a giant whose looks each seed draws from three ranges, a caught duck that collapses with its motors off, the five seeds' traces kept in one file and served one seed at a time, a booth and a guide that tell the heist, and the ranges and the time limit measured on x86.

**Architecture:** `arena/lights.py` draws each seed's reds from `[lights]`' ranges on a fourth `seed_rng` stream; the runner lays them over the timed steps (`_LightSteps`) and, on a catch, zeroes the duck's motors and records `COLLAPSE_S` more. `evaluate` keeps every seed of the scored command (`SeedTrace`), `trace_file` writes them as `trace_{s}`/`settle_{s}`/`caught_{s}` in the run's one npz, and the trace routes serve one seed (`?seed=`, `X-Caught-Frame`). An HF Job on the Space's own image, the branch's changed files laid over its package, measures the reference walker on x86 for several candidate range sets.

**Tech Stack:** Python 3.12, MuJoCo 3.10.0, numpy 2.4.1 (PCG64), FastAPI, pytest; HF Jobs (cpu-xl).

**Spec:** `docs/superpowers/specs/2026-10-27-sock-heist-design.md`, on top of #3's `docs/superpowers/specs/2026-10-21-red-light-green-light-design.md` (its "What was measured" is A6's method). **Contract (binding):** `docs/superpowers/plans/2026-10-28-sock-heist-interfaces.md`. **Measurements behind this plan** (Mac, read before A2 and A6): `/private/tmp/claude-501/-Users-nicolasrabault-Projects-HuggingFace-microduck-arena/67e38f06-738a-416e-a1fe-9ac25e562f3b/scratchpad/plan-a/` — `draw.py` (the draw by hand), `collapse.py` and `still.py` (three friction choices), `probe6m.py` (the walker on 6 m), `held.py` (the heading hold), `overlay_size.py`.

## Contract changes this plan assumes

Proposed to the contract's owner; if one is refused, its task reverts to the contract's wording.

1. `Lights.to_dict()` is deleted: once the summary serves `served(manifest)` nothing calls it.
2. The summary's switch to `served(manifest)` and the runner's draw land in A1, with the new `Lights`: A1 cannot end green with the ranges in and the old cycling schedule still read. A2 is the collapse alone.
3. The draw's golden test pins a literal `Lights` (the contract's placeholder ranges), not the event's, so A6's retune leaves it alone and any change to it is a change to the draw.
4. `trace_file(result: Evaluation) -> bytes` in `arena/evaluate.py` is the one writer the three writers call.
5. `DEFAULT_SOUNDS = ("crowd", "horn", "verdict")` is `ClipConfig.sounds`' default: with `"giant"` in `SOUND_SOURCES`, the old default would give every event the giant.
6. `decode_settle(blob, seed)` raises `KeyError` for a seed the file lacks, as `decode` does.
7. A caught duck's collapse runs past the time limit: its trace may be `round(time_limit_s / CTRL_DT) + round(COLLAPSE_S / CTRL_DT)` frames.

## Global Constraints

- The contract's rules apply: English only; unsigned commits in the repository's style (one plain sentence, no prefix, no trailer); `/usr/bin/git`; `uv run --frozen` only; tests in the FOREGROUND with `timeout: 600000`; nothing leaves this Mac without the owner's yes (the only thing that does is A6's HF Job, behind a STOP step).
- Shorthands, written out in full in every call: **PYTEST** `cd /Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist && uv run --frozen --extra dev pytest -q`; **RUFF** `cd /Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist && uv run --frozen ruff check`; **GIT** `/usr/bin/git -C /Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist`; **SCRATCH** the implementing session's own scratchpad (absolute path).
- Scope guard: every new line sits behind `manifest.lights is not None`; `RUNNER_VERSION` stays 5; the golden run and every other event's run are bit for bit as before (A1's `test_a_lane_without_lights_runs_bit_for_bit_as_before`).
- No dead code: #3's list schedule (`green_s`/`red_s` lists, the phase cycle, their checks and tests), `ClipConfig.speed` and its checks and tests, `Lights.to_dict` all go.
- No number that ships comes from the Mac: A1's ranges and 60 s are placeholders, said so in the event file, until A6 writes x86's.
- The booth: lines read for a newcomer (no joke that needs to know Peter and Ray); a bad line is fixed in the bible or the prompt, never filtered by a check.
- Between A1 and Plan C the page's old caller cannot read the served `lights` (no `green_s`): expected on this unpushed branch; no front-end file but `app/src/guides.test.js` (A5) is touched here.
- The contributor's spec, the Sock Heist spec and the contract keep their "red light, green light" wording: they are records.

## Review Focus

1. **A timetable that differs between processes or platforms** (a salted hash, a numpy change): A1's `test_the_draw_is_pinned` and `test_the_draw_is_the_same_in_another_process`; A6's job prints the pinned draw on x86.
2. **A red that starts on the race's last step, or exactly at the limit**: A1's `test_a_red_on_the_last_step_is_kept_whole_and_none_starts_at_the_limit`.
3. **A duck caught on the last step, its collapse cut by the limit**: decided, the collapse runs past it; A2's `test_a_duck_caught_on_the_last_step_collapses_past_the_limit`.
4. **A heist file read without its seed** (an old-format heist file, a seed it never kept): a 404, never a 500; A4's `test_a_seed_a_heist_run_kept_no_trace_of_is_a_404_not_a_500`.
5. **A workshop evaluation of a lights event**: its body says where its traced duck was caught; A3's `test_a_heist_checkpoint_says_where_its_traced_duck_was_caught`.

---

### Task A1: The event, its three ranges, and a timetable per seed

**Files:**
- Rename: `GIT mv arena/events/red-light-green-light-15m.toml arena/events/sock-heist-6m.toml`, then rewrite it
- Create: `arena/lights.py`
- Modify: `arena/manifest.py` (`Lights`, `_lights`, `SOUND_SOURCES`, `ClipConfig`, `_clip`, `load_manifest`), `arena/runner.py` (`_LightSteps.of`, `run_once`'s draw, the comments that name the caller), `arena/web/routes_read.py` (`event_summary`'s `lights`)
- Test: `tests/test_runner.py`, `tests/test_lights.py`, `tests/test_steering.py`, `tests/test_manifest.py`, `tests/test_routes_read.py`, `tests/test_course.py`, `tests/test_commentary_context.py`, `tests/test_commentary_notable.py`

**Interfaces:**
- Produces in `arena/manifest.py`: `Lights(first_green_s: tuple[float, float], green_s: tuple[float, float], red_s: tuple[float, float], turn_s: float, tolerance_m: float)`, frozen, no `to_dict`; `SOUND_SOURCES = ("crowd", "horn", "verdict", "giant")`; `DEFAULT_SOUNDS = ("crowd", "horn", "verdict")`; `ClipConfig(tape_max_s, sounds, camera)`, `to_dict() -> {"tape_max_s", "sounds", "camera"}`; `_clip(raw, where)` (no `stage`).
- Produces in `arena/lights.py`: `LIGHTS_STREAM = 4`; `Red(onset: int, length: int)`, frozen; `timetable(lights: Lights, event_id: str, seed: int, steps: int) -> tuple[Red, ...]`; `served(manifest: Manifest) -> dict`.
- Produces in `arena/runner.py`: `_LightSteps.of(reds: tuple[Red, ...], turn: int, steps: int) -> _LightSteps` (`red`, `mark`, `watch` as before).
- Produces in the API: an event summary's `lights` is `served(manifest)` on a lights event, `None` on another lane, absent on a stage or a tug; `clip` has no `speed`.

- [ ] **Step 1: The scope guard, written first, on the code as it is.** In `tests/test_runner.py` (imports: `from hashlib import sha256`, `from arena.golden import PLATFORM`):

```python
# The sprint's seed-1 run at STEADY_VX, hashed on this platform at 74104f6, before Sock Heist:
# a lane without lights must stay that run bit for bit (scratchpad plan-a/collapse.py measured it).
UNLIT = {"Darwin-arm64": ("614878b4b905b518e98d8c1eb0198651c504cd501708d76bbf9d74f18b4643a7",
                          "a0c4efe15af6c16d00934d439f57c77e936a9114ba3da742e39c8b9abbb1b07e")}


@pytest.mark.skipif(PLATFORM not in UNLIT, reason=f"no unlit run measured on {PLATFORM}")
def test_a_lane_without_lights_runs_bit_for_bit_as_before(sprint, walker):
    outcome = run_once(sprint, walker, seed=1, command=sprint.command_at(STEADY_VX))
    assert outcome.status == "finish" and outcome.time_s == pytest.approx(14.45, abs=1e-9)
    assert (sha256(outcome.trace.tobytes()).hexdigest(), sha256(outcome.settle.tobytes()).hexdigest()) == UNLIT[PLATFORM]
```

- [ ] **Step 2:** `PYTEST tests/test_runner.py::test_a_lane_without_lights_runs_bit_for_bit_as_before` — PASS on the code as it is (it guards what follows).

- [ ] **Step 3: The failing tests.** `tests/test_lights.py` keeps its structure (`lights_table`, `write_lights`, `_spans`, `_Listener`, `_short`); its module docstring and every comment speak of the giant; `EVENT = "sock-heist-6m"`, the `rlgl` fixture becomes `heist`; imports gain `subprocess`, `sys`, `from arena.lights import Red, served, timetable`. Replace the declaration and schedule tests with:

```python
FIELDS = {"first_green_s": "[0.6,1.0]", "green_s": "[1.6,3.0]", "red_s": "[1.4,2.4]",
          "turn_s": "0.4", "tolerance_m": "0.03"}
# The draw, pinned on these ranges: the contract's placeholders, kept here whatever A6 tunes.
PINNED = Lights(first_green_s=(0.6, 1.0), green_s=(1.6, 3.0), red_s=(1.4, 2.4), turn_s=0.4, tolerance_m=0.03)


def test_the_heist_is_played_to_lights_on_a_6_m_lane(heist):
    assert (heist.title, heist.order, heist.course.kind, heist.course.length_m) == ("6 m Sock Heist", 50, "lane", 6.0)
    # Task A6 replaces these with the ranges measured on x86.
    assert heist.lights == Lights(first_green_s=(0.6, 1.0), green_s=(1.6, 3.0), red_s=(1.4, 2.4),
                                  turn_s=0.4, tolerance_m=0.03)
    assert len({heist, load_event(EVENT)}) == 1


def test_the_heist_is_filmed_whole_at_life_speed_with_its_giant(heist):
    assert heist.clip.tape_max_s == heist.time_limit_s
    assert heist.clip.sounds == ("crowd", "horn", "giant", "verdict")
    assert heist.clip.camera.kind == "chase" and heist.clip.camera.track is True
    assert 0 < heist.clip.camera.hold < heist.course.length_m


def test_lights_load_as_three_ranges(tmp_path):
    assert load_manifest(write_lights(tmp_path)).lights == PINNED
    assert load_manifest(write_lights(tmp_path, turn_s="0")).lights.turn_s == 0.0
    assert load_manifest(write_lights(tmp_path, green_s="[2.0,2.0]")).lights.green_s == (2.0, 2.0)


def test_the_giants_sound_goes_with_lights(tmp_path):
    giant = '[clip]\nsounds=["crowd","giant"]\n'
    with pytest.raises(ManifestError, match=r"the giant's sound goes with \[lights\]"):
        load_manifest(write_manifest(tmp_path, clip=giant))
    assert load_manifest(write_manifest(tmp_path, clip=giant + lights_table())).clip.sounds == ("crowd", "giant")
```

`test_no_other_event_has_lights`, `test_a_stage_refuses_lights`, `test_lights_must_be_a_table` stay. `test_malformed_lights_are_refused`'s cases become exactly:

```python
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
```

The draw (`Red(35, 97)` … are `plan-a/draw.py`'s output on this Mac):

```python
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
        assert all(green[0] <= b.onset - a.onset - a.length <= green[1] for a, b in zip(reds, reds[1:]))
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
```

`_LightSteps`' three tests keep their expected arrays, built from reds: `REDS = (Red(30, 80), Red(160, 70), Red(260, 80))`, `_LightSteps.of(REDS, 20, 300)` (marks `[49, 179, 279]`), `_LightSteps.of(REDS, 0, 300)` (marks `[29, 159, 259]`, watch == red), `_LightSteps.of((Red(30, 80),), 20, 40)` (red `(30, 40)`, no mark, no watch). Add the helper both runner tests and `tests/test_steering.py` use:

```python
def _schedule(event, seed: int) -> _LightSteps:
    """The giant's timetable for `seed`, laid over the event's timed steps as run_once lays it."""
    steps = round(event.time_limit_s / CTRL_DT)
    return _LightSteps.of(timetable(event.lights, event.id, seed, steps), round(event.lights.turn_s / CTRL_DT), steps)


def _first_look(event, seed: int) -> int:
    """The first step the giant watches on `seed`: its first red's onset plus the turn."""
    steps = round(event.time_limit_s / CTRL_DT)
    return timetable(event.lights, event.id, seed, steps)[0].onset + round(event.lights.turn_s / CTRL_DT)
```

`test_the_duck_settles_standing_walks_on_green_and_is_asked_to_stand_on_red` gains `@pytest.mark.parametrize("seed", [1, 3])` (their first reds differ: 35 and 48 steps in), runs on `seed` and takes `red = _schedule(event, seed).red`. The caught test becomes `test_a_duck_that_moves_while_the_giant_looks_is_caught` with `assert len(outcome.trace) == _first_look(event, 1) + 1` (A2 replaces it). `test_the_event_runs_end_to_end` only renames.

Elsewhere: `tests/test_steering.py` — `EVENT = "sock-heist-6m"`, fixture `heist`, import `_schedule` from `tests.test_lights`, `red = _schedule(event, 1).red` in `test_the_duck_is_steered_on_green_and_on_green_only`, and `test_a_held_duck_keeps_to_its_lane`'s docstring: "On seeds 1 to 10 it strays 0.19 to 0.26 m from it, in a lane 0.8 m wide" (`plan-a/held.py`; seed 1: 0.186 m, 2.8°). `tests/test_manifest.py` — the id in `EXPECTED_CATEGORIES` and the programme order; `test_an_event_without_a_clip_section_gets_the_defaults` loses `clip.speed == 1` and `"speed": 1`; delete `test_a_long_race_is_filmed_as_a_time_lapse`, `test_a_performance_is_filmed_at_the_speed_it_is_sung` and the three `speed=` rows of `test_a_malformed_clip_section_is_refused`, which gains `('[clip]\nspeed=4\n', r"unknown keys \['speed'\]")` and `('[clip]\nsounds=["giant"]\n', r"the giant's sound goes with \[lights\]")`. `tests/test_routes_read.py` — the id in its three lists, and:

```python
def test_a_lane_serves_every_seeds_timetable_so_the_page_draws_the_giant(client):
    api, _ = client
    events = {e["id"]: e for e in api.get("/api/events").json()["events"]}
    assert events["sock-heist-6m"]["lights"] == served(load_event("sock-heist-6m"))
    assert set(events["sock-heist-6m"]["lights"]["timetables"]) == {"1", "2", "3", "4", "5"}
    assert "speed" not in events["sock-heist-6m"]["clip"]
    assert events["sprint-2m"]["lights"] is None
    assert "lights" not in events["got-a-talent"]
```

`tests/test_course.py`, `tests/test_commentary_notable.py`: the id. `tests/test_commentary_context.py`: the id; `nature`'s expected text becomes `"a 6 m game of red light, green light: walk on green, stand still on red"` (A5 rewrites it); the mixed result's `"the 150 s limit"` becomes `f"the {lights.time_limit_s:g} s limit"`, so A6's limit needs no edit there.

- [ ] **Step 4:** `PYTEST tests/test_lights.py tests/test_steering.py tests/test_manifest.py tests/test_routes_read.py tests/test_course.py tests/test_commentary_context.py tests/test_commentary_notable.py` — FAIL: `ModuleNotFoundError: No module named 'arena.lights'`.

- [ ] **Step 5: The event file.** After the `git mv`, the file holds #3's `[command]`, `[start]`, `[start.perturbation]`, `[termination]`, `[sweep]`, `[steering]` and `[clip.camera]` as they are, and:

```toml
id           = "sock-heist-6m"
order        = 50
title        = "6 m Sock Heist"
time_limit_s = 60.0
[course]   # kind "lane", length_m = 6.0, width_m 0.8, wall_height_m 0.15, slope_deg 0.0
[lights]
first_green_s = [0.6, 1.0]
green_s       = [1.6, 3.0]
red_s         = [1.4, 2.4]
turn_s        = 0.4
tolerance_m   = 0.03
[clip]
tape_max_s = 60.0
sounds     = ["crowd", "horn", "giant", "verdict"]
```

Every comment is rewritten for the giant microduck in its nest past the line and for 6 m (none names the caller, fifteen metres or a time-lapse). Above `time_limit_s` and `[lights]`: these are placeholders until Task A6 measures them on Linux-x86_64; above `[lights]`: each seed draws its own timetable from the ranges, the same for every entrant (`arena.lights`).

- [ ] **Step 6: `arena/manifest.py`.** `Lights` as in Interfaces, its docstring the giant's (it looks at moments each seed draws from the ranges, `arena.lights.timetable`; on red the twist drops to zero; nothing counts while it turns its head; past `tolerance_m` from the mark, caught). `_lights` parses exactly the five keys with the messages Step 3 pins (each range a two-item list of positive numbers, lo ≤ hi, each a whole number of `CTRL_DT` steps; `turn_s` as before but shorter than `red_s[0]`). `ClipConfig` loses `speed` (field, docstring paragraph, `to_dict` key); `_clip(raw, where)` refuses `speed` as unknown and defaults `sounds` to `DEFAULT_SOUNDS`; `SOUND_SOURCES` and `DEFAULT_SOUNDS` as in Interfaces. `load_manifest`: `_clip(raw.get("clip"), "[clip]")`, and after parsing, `"giant"` in `clip.sounds` with no `"lights"` in `raw` raises `ManifestError(f"{path}: the giant's sound goes with [lights], and this event has none")`. The `Manifest.lights` comment names the giant.

- [ ] **Step 7: `arena/lights.py`.** Module docstring: the giant's timetable, drawn per seed so every entrant faces the same five, never drawn in JavaScript (the page reads `served`). `timetable` is the contract's draw, in this order (it is what the golden pins):

```python
rng = np.random.default_rng([zlib.crc32(event_id.encode()), seed, LIGHTS_STREAM])
def draw(span): return int(rng.integers(round(span[0] / CTRL_DT), round(span[1] / CTRL_DT) + 1))
reds, onset = [], draw(lights.first_green_s)
while onset < steps:
    length = draw(lights.red_s)
    reds.append(Red(onset, length))
    onset += length + draw(lights.green_s)
```

`served(manifest)`: `{"turn_s": lights.turn_s, "tolerance_m": lights.tolerance_m, "timetables": {str(seed): [[round(r.onset * CTRL_DT, 2), round(r.length * CTRL_DT, 2)] for r in timetable(lights, manifest.id, seed, round(manifest.time_limit_s / CTRL_DT))] for seed in manifest.seeds}}`.

- [ ] **Step 8: `arena/runner.py`.** `_LightSteps.of(reds, turn, steps)`: for each red, `mark[onset + turn - 1]` when that is `< steps`, `red[onset:onset + length]`, `watch[onset + turn:onset + length]` (a first green is at least one step, so `onset + turn - 1 >= 0`). `run_once`: `schedule = _LightSteps.of(timetable(lights, manifest.id, seed, max_steps), round(lights.turn_s / CTRL_DT), max_steps)`. Docstrings and comments say giant, not caller. Nothing else in the loop changes.

- [ ] **Step 9: `arena/web/routes_read.py`.** `"lights": served(manifest) if manifest.lights else None`, its comment: every seed's timetable, so the page draws the giant in step with any replay and never draws a random number itself.

- [ ] **Step 10:** Step 4's command, plus `tests/test_runner.py tests/test_evaluate.py` — PASS (the unlit guard and the golden included). `RUFF arena tests` — clean.

- [ ] **Step 11: Commit.**

```bash
GIT add arena/events/sock-heist-6m.toml arena/lights.py arena/manifest.py arena/runner.py arena/web/routes_read.py tests/test_runner.py tests/test_lights.py tests/test_steering.py tests/test_manifest.py tests/test_routes_read.py tests/test_course.py tests/test_commentary_context.py tests/test_commentary_notable.py
GIT commit -m "Sock Heist: the contributor's lane is now a 6 m heist whose giant looks at moments each seed draws from three ranges, the same for every entrant, and the page is served each seed's timetable; the clip plays at life speed and may sound the giant"
```

(The `git mv` already staged the old path's removal.)

---

### Task A2: A caught duck collapses

**Files:**
- Modify: `arena/runner.py` (`COLLAPSE_S`, `RunOutcome.caught_frame`, `run_once`)
- Test: `tests/test_lights.py`, `tests/test_runner.py`

**Interfaces:**
- Consumes: A1's `timetable`, `_LightSteps.of`, and the test helpers `_short`, `_Listener`, `_first_look`.
- Produces: `arena.runner.COLLAPSE_S = 2.0`; `RunOutcome.caught_frame: int | None = None`, the index in `trace` of the step the duck was caught on. A caught run's trace is `caught_frame + 1 + round(COLLAPSE_S / CTRL_DT)` frames, even past the time limit; its `time_s` is `None` and its `progress_m` is where it stood when caught.

- [ ] **Step 1: The failing tests.** In `tests/test_lights.py`, replace A1's caught test with (imports: `from arena.actuator import Servos`, `from arena.constants import DECIMATION`, `from arena.runner import COLLAPSE_S`):

```python
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
```

`test_the_event_runs_end_to_end` ends:

```python
    collapse = round(COLLAPSE_S / CTRL_DT) if outcome.status == "caught" else 0
    assert 0 < len(outcome.trace) <= round(heist.time_limit_s / CTRL_DT) + collapse
    assert (outcome.caught_frame is not None) == (outcome.status == "caught")
```

`test_a_lane_without_lights_runs_bit_for_bit_as_before` gains `assert outcome.caught_frame is None`.

- [ ] **Step 2:** `PYTEST tests/test_lights.py tests/test_runner.py::test_a_lane_without_lights_runs_bit_for_bit_as_before` — FAIL: `ImportError: cannot import name 'COLLAPSE_S'`.

- [ ] **Step 3: Implement in `arena/runner.py`.** `COLLAPSE_S = 2.0` beside the module's constants, its comment: how long a caught duck is simulated on with its motors off, so its replay shows it fall and lie still; it changes no score (Plan C may retune it). `RunOutcome` gains `caught_frame` (comment as in Interfaces). In `run_once`: on a lights event `frames` holds `max_steps + round(COLLAPSE_S / CTRL_DT)` frames, on any other exactly `max_steps` as before; the catch records `caught_frame = written - 1` before its `break`; after the loop, when caught: `data.ctrl[adr.act] = 0.0`, then for each of `round(COLLAPSE_S / CTRL_DT)` control steps, `DECIMATION` `mujoco.mj_step` then one `mujoco.mj_forward`, and `sim.record(frames[:, written]); written += 1`. No policy, no `Servos` call: `model.dof_frictionloss` keeps what the catch step's last drive wrote, a gearbox left as it stood — measured on this Mac (`plan-a/still.py`), the trunk folds from 0.12 m to 0.04–0.07 m and lies still within 1 s, where the unpowered budget (motor torque 0) or no friction leave it rocking 2 s on. The next run's `Servos` resets the shared model's friction, as it always has. `progress` is not updated during the collapse. Pass `caught_frame` to `RunOutcome`.

- [ ] **Step 4:** `PYTEST tests/test_lights.py tests/test_steering.py tests/test_runner.py tests/test_run_stage.py tests/test_evaluate.py` — PASS. `RUFF arena/runner.py tests/test_lights.py tests/test_runner.py` — clean.

- [ ] **Step 5: Commit.**

```bash
GIT add arena/runner.py tests/test_lights.py tests/test_runner.py
GIT commit -m "A duck the giant catches moving has its motors switched off and collapses: the run simulates two more seconds of it falling and lying still, and says which frame it was caught on"
```

---

### Task A3: Five traces in one file

**Files:**
- Modify: `arena/trace.py` (`SeedTrace`, `encode_seeds`, `decode`, `decode_settle`, `decode_caught`, docstring), `arena/evaluate.py` (`Evaluation.seed_traces`, `evaluate`, `evaluate_at`, `trace_file`), `arena/web/routes_submit.py`, `arena/cli.py`, `arena/recover.py` (each writes `trace_file(result)`), `arena/workshop/evaluations.py` (`caught_frame`)
- Test: `tests/test_trace.py`, `tests/test_lights.py`, `tests/test_routes_submit.py`, `tests/workshop/test_evaluations.py`

**Interfaces:**
- Consumes: A2's `RunOutcome.caught_frame`.
- Produces in `arena/trace.py`: `SeedTrace(trace: np.ndarray, settle: np.ndarray, caught: int | None = None)`, frozen; `encode_seeds(seeds: dict[int, SeedTrace]) -> bytes` (keys `trace_{s}`, `settle_{s}` through `_on_the_wire`, and `caught_{s}` as an `np.int32` scalar for a seed caught; no `trace`/`settle` key; shapes checked as `encode` checks them); `decode(blob, seed: int | None = None) -> np.ndarray`; `decode_settle(blob, seed: int | None = None) -> np.ndarray`; `decode_caught(blob, seed: int) -> int | None`. With a seed, a key the file lacks raises `KeyError`; without one, both read as today.
- Produces in `arena/evaluate.py`: `Evaluation.seed_traces: dict[int, SeedTrace] | None = None` (a lights event: every seed of the scored command, keyed by seed; `None` on any other); `trace_file(result: Evaluation) -> bytes` — `encode_seeds(result.seed_traces)` when set, else `encode(result.trace, result.settle, result.string, result.string_settle)`.
- Produces in a workshop evaluation body on a lights event: `caught_frame`, the trace seed's `caught` (an int or null); absent on any other event. `FORMAT` stays 3: no stored evaluation of a lights event can exist (`sock-heist-6m` is new, and #3's event never had a training folder).

- [ ] **Step 1: The failing tests.** `tests/test_trace.py` (and `test_a_long_lanes_trace_is_stored_float32_and_its_settle_need_not_be` says six metres, `np.linspace(0.0, 6.0, 60, …)`):

```python
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
```

`tests/test_lights.py` (imports: `from arena.evaluate import evaluate, evaluate_at, trace_file`, `from arena.trace import as_ducks, decode, decode_caught`):

```python
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
```

`tests/test_routes_submit.py` (imports `io`, `numpy as np`):

```python
def test_a_heist_entry_is_stored_with_every_seeds_trace(api):
    # Pinned fast: at 1.2 m/s the walker meets its end within seconds, whatever it is.
    response = submit(api, event="sock-heist-6m", name="heist", command_vx="1.2")
    assert response.status_code == 200, response.text
    with np.load(io.BytesIO(api.app.state.store.trace(response.json()["run_id"]))) as loaded:
        assert {f"{key}_{s}" for key in ("trace", "settle") for s in range(1, 6)} <= set(loaded.files)
        assert "trace" not in loaded.files
```

`tests/workshop/test_evaluations.py` (imports: `from arena.evaluate import evaluate_at`, `from arena.workshop import evaluations`, `from tests.test_lights import _short`, and `SPRINT`, `git` from `tests.workshop.conftest`, `TASK` from `tests.workshop.test_tickets`); the sprint test gains `assert "caught_frame" not in body`:

```python
def add_heist(checkout):
    folder = checkout / "src" / "microduck_challenges" / "sock_heist_6m"
    folder.mkdir()
    (folder / "challenge.toml").write_text(
        SPRINT.replace('"sprint-2m"', '"sock-heist-6m"').replace(TASK, "Mjlab-SockHeist6m-MicroDuck"))
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "Sock Heist")


def test_a_heist_checkpoint_says_where_its_traced_duck_was_caught(checkout, fakes, hub, monkeypatch):
    add_heist(checkout)
    client = reopen(checkout, hub)
    measured = []

    def caught_at_the_first_look(event, policy):
        measured.append(evaluate_at(_short(event, 3.0, tolerance_m=1e-6), policy, 0.3))
        return measured[-1]

    monkeypatch.setattr(evaluations, "evaluate", caught_at_the_first_look)
    run = make_run(checkout, "first", checkpoints=(1,), task="Mjlab-SockHeist6m-MicroDuck")
    assert evaluate_next(state(client)) is True
    body = client.get(f"/api/workshop/challenges/sock-heist-6m/jobs/{run.name}/checkpoints/1").json()
    (result,) = measured
    assert body["trace_seed"] == result.trace_seed
    assert body["caught_frame"] is not None
    assert body["caught_frame"] == result.seed_traces[result.trace_seed].caught
```

- [ ] **Step 2:** `PYTEST tests/test_trace.py tests/test_lights.py tests/test_routes_submit.py::test_a_heist_entry_is_stored_with_every_seeds_trace tests/workshop/test_evaluations.py` — FAIL: `AttributeError: module 'arena.trace' has no attribute 'encode_seeds'` (and the imports of `trace_file`).

- [ ] **Step 3: `arena/trace.py`** as in Interfaces; the module docstring gains a paragraph: a lights event's run keeps every seed (`trace_{s}`, `settle_{s}`, `caught_{s}`) in its one file, the store paying per file; a replay plays every lane on one seed. The shape check `encode` makes is shared, not copied.

- [ ] **Step 4: `arena/evaluate.py`.** `Evaluation.seed_traces` (comment as in Interfaces). `evaluate` and `evaluate_at` fill it when `manifest.lights is not None`: `{s: SeedTrace(o.trace, o.settle, o.caught_frame) for each seed's outcome at the scored command}`. `trace_file(result)` as in Interfaces; the module imports `SeedTrace`, `encode`, `encode_seeds` from `.trace`.

- [ ] **Step 5: The writers.** `routes_submit.py`'s `store.append(record, trace_file(result))`, `cli.py`'s and `recover.py`'s `trace_codec.encode(result.trace, …)` become `trace_file(result)`; drop each `trace as trace_codec` import left unused. `GIT grep -n "encode(" -- arena scripts` then shows only `trace.py`'s own and `cupworker.py`'s (a tug's bout files, not a lane run's).

- [ ] **Step 6: `arena/workshop/evaluations.py`.** In `_measure`, when `result.seed_traces is not None`: `body["caught_frame"] = result.seed_traces[result.trace_seed].caught`.

- [ ] **Step 7:** `PYTEST tests/test_trace.py tests/test_lights.py tests/test_evaluate.py tests/test_routes_submit.py tests/test_cli.py tests/test_recover.py tests/workshop/test_evaluations.py` — PASS. `RUFF arena tests` — clean.

- [ ] **Step 8: Commit.**

```bash
GIT add arena/trace.py arena/evaluate.py arena/web/routes_submit.py arena/cli.py arena/recover.py arena/workshop/evaluations.py tests/test_trace.py tests/test_lights.py tests/test_routes_submit.py tests/workshop/test_evaluations.py
GIT commit -m "A Sock Heist run keeps all five seeds' traces in its one file, each with the frame its duck was caught on, so a replay can play every lane on the same seed; a workshop checkpoint says where its traced duck was caught"
```

---

### Task A4: The API serves one seed

**Files:**
- Modify: `arena/web/routes_read.py` (`run_trace`, `run_settle`)
- Test: `tests/test_routes_trace.py`

**Interfaces:**
- Consumes: A3's `decode(blob, seed)`, `decode_settle(blob, seed)`, `decode_caught(blob, seed)`, `SeedTrace`, `encode_seeds`.
- Produces: `GET /api/runs/{id}/trace?seed=N` and `GET /api/runs/{id}/settle?seed=N` (`seed: int | None = None`). On a lights event, `seed` defaults to the run's `trace_seed`, a seed its file lacks is a 404 `"run {id} keeps no trace of seed {N}"`, and a trace response carries `X-Caught-Frame: <k>` when that seed was caught. On any other event, a `seed` other than the run's `trace_seed` is the same 404, and its `trace_seed` or no seed is today's answer.

- [ ] **Step 1: The failing tests,** in `tests/test_routes_trace.py` (imports `SeedTrace`, `encode_seeds` from `arena.trace`):

```python
def heist_run(app, trace_seed=3, caught=None):
    """A heist run kept on seeds 1 to 5: seed s's trace s + 4 frames long, its settle 2, both offset by 100 s."""
    caught = {4: 6} if caught is None else caught
    record = make_record(event_id="sock-heist-6m", trace_seed=trace_seed)
    seeds = {s: SeedTrace(a_trace(frames=s + 4) + 100 * s, a_trace(frames=2) + 100 * s, caught.get(s)) for s in range(1, 6)}
    app.state.store.append(record, encode_seeds(seeds))
    return record, seeds


def frames(response):
    return np.frombuffer(response.content, dtype="<f4").reshape(-1, TRACE_WIDTH)


def test_a_heist_run_serves_its_trace_seed_unless_asked_another(client):
    api, app = client
    record, seeds = heist_run(app)
    plain = api.get(f"/api/runs/{record.run_id}/trace")
    assert plain.headers["x-frame-count"] == "7" and "x-caught-frame" not in plain.headers
    np.testing.assert_array_equal(frames(plain), seeds[3].trace)
    four = api.get(f"/api/runs/{record.run_id}/trace?seed=4")
    assert (four.headers["x-frame-count"], four.headers["x-caught-frame"]) == ("8", "6")
    np.testing.assert_array_equal(frames(four), seeds[4].trace)
    np.testing.assert_array_equal(frames(api.get(f"/api/runs/{record.run_id}/settle?seed=2")), seeds[2].settle)
    np.testing.assert_array_equal(frames(api.get(f"/api/runs/{record.run_id}/settle")), seeds[3].settle)


def test_a_seed_a_heist_run_kept_no_trace_of_is_a_404_not_a_500(client):
    api, app = client
    record, _ = heist_run(app)
    for path in ("trace?seed=9", "settle?seed=9"):
        response = api.get(f"/api/runs/{record.run_id}/{path}")
        assert response.status_code == 404 and "seed 9" in response.json()["detail"], path
    # Stored as one trace, before every seed was kept: there is no seed to serve, and that is a 404 too.
    old = make_record(event_id="sock-heist-6m", trace_seed=1)
    app.state.store.append(old, encode(a_trace(frames=5), a_trace(frames=2)))
    for path in ("trace", "settle"):
        assert api.get(f"/api/runs/{old.run_id}/{path}").status_code == 404, path


def test_another_event_serves_its_trace_seed_and_no_other(client):
    api, app = client
    record = make_record(trace_seed=2)
    app.state.store.append(record, encode(a_trace(frames=9), a_trace(frames=4)))
    plain, asked = (api.get(f"/api/runs/{record.run_id}/trace{q}") for q in ("", "?seed=2"))
    assert asked.status_code == 200 and asked.content == plain.content and "x-caught-frame" not in asked.headers
    assert api.get(f"/api/runs/{record.run_id}/settle?seed=2").headers["x-frame-count"] == "4"
    for path in ("trace?seed=1", "settle?seed=1"):
        response = api.get(f"/api/runs/{record.run_id}/{path}")
        assert response.status_code == 404 and "seed 1" in response.json()["detail"], path
```

- [ ] **Step 2:** `PYTEST tests/test_routes_trace.py` — FAIL: the heist runs raise `KeyError` (their file has no `trace` key), and the sprint's `?seed=1` answers 200.

- [ ] **Step 3: Implement in `arena/web/routes_read.py`.** One helper, `_seed_key(record: RunRecord, seed: int | None) -> int | None`: on a lights event (`load_event(record.event_id).lights is not None`), `seed` or the run's `trace_seed`; on any other, `None` when `seed` is `None` or the `trace_seed`, else `HTTPException(404, f"run {record.run_id} keeps no trace of seed {seed}")`. Both routes take `seed: int | None = None`, use `record = _find_run(...)`, read with the key, and answer a `KeyError` with that 404. `run_trace` sets `X-Caught-Frame` on the response when the key is not `None` and `decode_caught` gives a frame. Both docstrings say what `seed` means.

- [ ] **Step 4:** `PYTEST tests/test_routes_trace.py tests/test_routes_read.py tests/test_routes_submit.py::test_the_replay_of_a_fresh_submission_is_fetchable tests/test_routes_vote.py` — PASS. `RUFF arena/web/routes_read.py tests/test_routes_trace.py` — clean.

- [ ] **Step 5: Commit.**

```bash
GIT add arena/web/routes_read.py tests/test_routes_trace.py
GIT commit -m "The trace and settle routes serve one seed of a Sock Heist run, its trace seed unless asked, with the frame its duck was caught on; any other run serves its trace seed and no other"
```

---

### Task A5: The booth, the guide and the names

**Files:**
- Modify: `arena/commentary/context.py` (`nature`, `_unfinished`), `arena/commentary/lore.json` (three memories), `arena/manifest.py` (`Steering`'s docstring), `app/src/guides.test.js` (the guide's id)
- Rename: `GIT mv docs/guides/challenges/red-light-green-light-15m.md docs/guides/challenges/sock-heist-6m.md`, then rewrite it
- Test: `tests/test_commentary_context.py`, `tests/test_commentary_lore.py`

**Interfaces:**
- Produces: `nature(heist) == ("a 6 m sock heist: little microducks sneak up on a giant microduck's nest to steal its socks, and must freeze whenever it turns its head", ("lights",))`; a caught seed is told `"was caught moving while the giant looked on {n}"`; the guide at `docs/guides/challenges/sock-heist-6m.md` (A6 fills its numbers).

- [ ] **Step 1: The failing tests.** `tests/test_commentary_context.py`: `nature`'s expected value as in Interfaces; `test_caught_under_a_red_light_is_said_and_is_not_a_fall` becomes `test_caught_by_the_giant_is_said_and_is_not_a_fall`, its two texts ending `"the duck was caught moving while the giant looked on 3 of them."` and `"…and the duck fell on 1 and was caught moving while the giant looked on 1 of them."`. `tests/test_commentary_lore.py` (import `re`):

```python
def test_the_heists_memories_tell_of_the_giant():
    heist = [m for m in load().memories if {"lights", "caught"} & set(m.tags)]
    assert {"lights", "caught"} <= {tag for m in heist for tag in m.tags}
    for memory in heist:
        assert not re.search(r"caller|red light|reachy", memory.memory, re.IGNORECASE), memory.id
```

- [ ] **Step 2:** `PYTEST tests/test_commentary_context.py tests/test_commentary_lore.py` — FAIL on the old words.

- [ ] **Step 3: The booth.** `context.py`: `nature`'s lights line and `_unfinished`'s words as in Interfaces; `_unfinished`'s docstring says "caught moving while the giant looked". `lore.json`: the three lights/caught memories become exactly (on-screen observations; a newcomer needs nothing else):

```json
{"id": "statues", "tags": ["lights"], "memory": "A sock heist asks a duck for the one thing a walker is never trained for: to freeze mid-stride the moment the giant microduck turns its head, and stand there while it stares."},
{"id": "the-giant", "tags": ["lights"], "memory": "The giant microduck never leaves its nest of socks: all it does is turn its head round over its shoulder with a very deep quack, and every little duck on the lane has to stop dead."},
{"id": "motors-off", "tags": ["caught"], "memory": "A duck caught moving is not sent back to the start: its motors switch off and it folds up where it stands, a few steps short of the socks it came for."}
```

- [ ] **Step 4: The guide.** After the `git mv`, `docs/guides/challenges/sock-heist-6m.md` reads as below; the bold numbers are A1's placeholders, which A6 replaces. Its only link inside the site stays `../train-a-policy.md` (`app/src/guides.test.js` checks it). In `app/src/guides.test.js`, `"red-light-green-light-15m"` becomes `"sock-heist-6m"`.

````markdown
# 6 m Sock Heist

Sneak 6 metres up to a giant microduck's nest and steal its socks without being seen. The lowest
average time wins.

## The giant

A giant microduck sits in its nest of socks past the finish line, its back to the lanes. Every few
seconds it turns its head round over its shoulder to look at the lanes, with a very deep quack, and
the turn takes **0.4 seconds**. From the moment it faces the lanes until it looks away, a duck whose
trunk moves more than **3 cm** across the floor from where it stood is caught: its motors switch off,
it collapses where it stands, and that attempt ends there.

## When it looks

The giant looks at random moments, different on each of the five starts and the same for every entry.
It first starts to turn **0.6 to 1.0 s** after the start, so a duck that bolts off the line has to stop
as hard as it started. Then it looks for **1.4 to 2.4 s** at a time, and away for **1.6 to 3.0 s**.

## What the policy sees

Only its command, as on every race. From the moment the giant starts to turn its head until it looks
away, the Arena asks the policy to stand still: the forward, sideways and turn rates drop to zero, so
the turn is its time to stop. The policy never sees the giant, the clock or the lane. A walk that stops
dead on a zero command, holds still while watched, and starts again cleanly does well.

## The lane

Nobody walks six metres straight unaided. While the giant looks away, the Arena steers the duck
through its command: the turn rate aims it at the middle of the lane half a metre ahead, at no more
than **1 rad/s**. A walk that follows a turn command holds its lane; one that ignores it drifts into a
wall.

## Train

Open **Train my own robot** on the challenge page, or run this in a terminal:

```bash
uv run https://pollen-robotics-microduck-arena.hf.space/workshop.py sock-heist-6m
```

Its training stops the duck at random moments, as the giant does. Get a walk that stops dead on a zero
command and starts again cleanly first, then make it faster.

## Scoring

The Arena scans forward commands from **0.20 to 1.20 m/s** in 0.05 steps. It tests three shortlisted
speeds over five starts and keeps the best average. Each fall, catch or timeout counts as
**60 seconds**.

For example, four 25-second finishes and one catch score **32 seconds**.

[How the workshop works, and the shell path →](../train-a-policy.md)
````

- [ ] **Step 5: The last names.** `Steering`'s docstring in `arena/manifest.py` says six metres. Then `/usr/bin/grep -rn -i -e "red.light.green.light" -e "rlgl" -e "fifteen metres" arena tests docs/guides app/src/guides.test.js` prints nothing, and `/usr/bin/grep -n -i "caller" arena/runner.py arena/manifest.py arena/lights.py arena/web/routes_read.py arena/commentary/context.py arena/commentary/lore.json arena/events/sock-heist-6m.toml tests/test_lights.py tests/test_steering.py tests/test_routes_read.py` prints only `runner.py`'s "a caller only gets to say how fast" (a function's caller). Fix whatever else either prints.

- [ ] **Step 6:** `PYTEST tests/test_commentary_context.py tests/test_commentary_lore.py tests/test_commentary.py tests/test_commentary_generator.py tests/test_manifest.py`; `cd /Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist/app && npx vitest run src/guides.test.js` — PASS. `RUFF arena tests` — clean.

- [ ] **Step 7: Commit.**

```bash
GIT add arena/commentary/context.py arena/commentary/lore.json arena/manifest.py app/src/guides.test.js docs/guides/challenges/sock-heist-6m.md tests/test_commentary_context.py tests/test_commentary_lore.py
GIT commit -m "The booth and the guide tell the heist: little microducks sneaking up on a giant microduck's nest for its socks, freezing when it turns its head and collapsing when caught; the last red light, green light names go"
```

---

### Task A6: The numbers, measured on x86

**Files:**
- Create (scratch, never committed): `SCRATCH/heist_numbers.py`, `SCRATCH/launch_numbers.py`
- Modify: `arena/events/sock-heist-6m.toml` (ranges, `time_limit_s`, `tape_max_s`, comments), `docs/guides/challenges/sock-heist-6m.md` (its numbers), `tests/test_lights.py` (the event's pinned values)

**Interfaces:**
- Consumes: everything above; `arena.golden.check`, `PLATFORM`.
- Produces: the shipped `[lights]` ranges, `time_limit_s` and `tape_max_s`, and the reference walker's x86 score, command and per-seed times (Plan D's bar and env read them).
- Rules (the contract's): the range rule — on x86 the walker finishes all five seeds and meets 5 to 7 reds on its trace seed at its scored command, a red being met when `red.onset < len(seed_traces[trace_seed].trace)`; the time limit rule — on x86, the walker's slowest seed at its scored command, plus 50 %, rounded up to the next 5 s (`math.ceil(slowest * 1.5 / 5) * 5`); `tape_max_s` equals it.

- [ ] **Step 1: `SCRATCH/heist_numbers.py`.** Candidates (first green, green, red; turn and tolerance as shipped):

| Name | `first_green_s` | `green_s` | `red_s` | Why |
| --- | --- | --- | --- | --- |
| A | (0.6, 1.0) | (1.6, 3.0) | (1.4, 2.4) | the contract's; Mac: 5/5, 6–7 reds at 0.95–1.00 m/s (`plan-a/probe6m.py`) |
| B | (0.6, 1.0) | (1.4, 2.6) | (1.4, 2.4) | more reds |
| C | (0.6, 1.0) | (1.8, 3.4) | (1.4, 2.4) | fewer reds |
| D | (0.6, 1.0) | (1.6, 3.0) | (1.6, 2.6) | longer reds |

The script: if env `ARENA_FILES` is set, lay it over the installed package first (`base64` → `zlib` → JSON `{path inside arena/: text}`, written under `Path(importlib.util.find_spec("arena").origin).parent`, as the runner v5 re-measure's `overlay()` did); print `golden: <arena.golden.check()>` and `draw: <[(r.onset, r.length) for r in timetable(PINNED ranges, "sock-heist-6m", 1, 3000)[:5]]>`; then, for each candidate named in `argv` (default all), in a `ProcessPoolExecutor(max_workers=len(names))`: `limit = 60.0`, and up to three passes of `evaluate(replace(load_event("sock-heist-6m"), lights=replace(lights, ranges), time_limit_s=limit), walker)`, stopping when the walker does not finish all five or when the rule's limit equals `limit`, else `limit = rule`. One line per candidate: `numbers: {json}` with `candidate`, `platform` (`PLATFORM`), `limit`, `score`, `command_vx`, `per_seed` (`seed`, `status`, `time_s`), `trace_seed`, `reds` (every seed's, by the rule's count), `meets` (5/5 and 5 ≤ trace seed's reds ≤ 7).

- [ ] **Step 2: The Mac first.** `cd /Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist && uv run --frozen python SCRATCH/heist_numbers.py A B` then `… C D` (two foreground calls, `timeout: 600000`). If no candidate meets the rule on the Mac, move the green range by 0.2 s (shorter for more reds, longer for fewer) and run again, at most three rounds; if still none, STOP and report the table. The x86 job runs every candidate that met the rule on the Mac, and A.

- [ ] **Step 3: `SCRATCH/launch_numbers.py`.** The base: the GitHub sha the Space runs, from its newest commit's title (`HfApi().list_repo_commits("pollen-robotics/microduck-arena", repo_type="space")[0].title`, `"Deploy <sha>"`), checked against `HfApi().get_space_runtime("pollen-robotics/microduck-arena").raw["sha"]` (that commit's id); `GIT fetch origin main` if the sha is not in the repository. The overlay: every file of `GIT diff --name-only --diff-filter=d <sha> HEAD -- arena`, packed as Step 1 reads it; the launcher refuses to go on above 100 000 bytes (the whole package packs to 287 KB, over Linux's 128 KiB per environment value; the branch's diff to some 40 KB). Then `HfApi().run_job(image="hf.co/spaces/pollen-robotics/microduck-arena", command=["bash", "-c", 'echo "$SCRIPT" | base64 -d > /tmp/heist_numbers.py && python /tmp/heist_numbers.py <names>'], env={"ARENA_FILES": …, "SCRIPT": base64 of heist_numbers.py}, flavor="cpu-xl", timeout="1h", labels={"arena": "sock-heist-numbers"}, namespace="pollen-robotics")`, no secret (the job reads nothing private and writes nothing), printing the job's id and url. Why this way: the Space's own image carries the x86 wheels it times entries with; laying the branch's changed files over its package needs no upload, no repo and nothing to clean up, and it is the recipe the runner v5 re-measure proved (`V5_FILES`). Run it first as `launch_numbers.py --dry-run`, which prints the base, the files and the packed size, and launches nothing.

- [ ] **Step 4: STOP for the owner's yes.** Report: the Mac table, with each candidate's slowest seed and the limit the rule gives it (indicative: `plan-a/probe6m.py` had the walker's slowest seed at 27.1 s at 0.95 m/s, a 45 s limit), the candidates going to x86, the base sha and the overlay's files, flavor cpu-xl, timeout 1 h, paid by pollen-robotics. Launch nothing without the yes.

- [ ] **Step 5: Launch and wait.** With the yes: run `SCRATCH/launch_numbers.py` with the call in. Wait with a Monitor until-loop on `HfApi().inspect_job(job_id=…, namespace="pollen-robotics").status.stage` leaving `RUNNING`, never a background run waited on; then save `HfApi().fetch_job_logs(job_id=…, namespace="pollen-robotics")` to `SCRATCH/x86-numbers.log`. The log must show `golden:` within 2 % of 9.392 (Linux-x86_64's baseline) and `draw:` equal to `test_the_draw_is_pinned`'s five reds; if either does not, STOP and report.

- [ ] **Step 6: Decide, then STOP for the limit.** Among the candidates whose x86 line `meets`, pick the one whose trace seed meets the reds nearest 6, ties in the order A, B, C, D. If none meets, STOP and report the x86 table to the owner. Otherwise report the pick with its walker's slowest seed time beside the limit the rule gives: the limit is the main lever on a clip's cost (Plan C measured a 60 s limit at about 1 640 frames a layout at 1×, some 54 min of render against the clip job's 30 min timeout), so the owner weighs the two. The rule's limit ships unless the owner names another; another limit means one more x86 job on it for the pick (Steps 3–5, the owner's yes again), since it can change which finalist the sweep keeps.

- [ ] **Step 7: Write the numbers.** The event file: the chosen ranges, `time_limit_s` and `tape_max_s` the chosen line's `limit`, and the placeholder comments replaced by what was measured, e.g. above `time_limit_s`: "Measured on Linux-x86_64, the Space's platform (HF Job <id>, <date>): the reference walker (BEST_alpha_walking.onnx) finishes every seed at <v> m/s in <a>–<b> s, a score of <s> s, and its slowest seed plus half, rounded up to 5 s, is this limit", and above `[lights]`: "…it meets <n> reds on its trace seed <t> (<min>–<max> over the five)". `tests/test_lights.py`'s `test_the_heist_is_played_to_lights_on_a_6_m_lane` pins the chosen `Lights` and gains `assert heist.time_limit_s == <limit>`. The guide: the three ranges, the limit in Scoring, and its example recomputed as four finishes of the walker's rounded mean time and one catch, `(4 × t + limit) / 5`.

- [ ] **Step 8:** `PYTEST tests/test_lights.py tests/test_steering.py tests/test_commentary_context.py tests/test_routes_read.py tests/test_manifest.py`; `cd /Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist/app && npx vitest run src/guides.test.js` — PASS. (If `test_a_held_duck_keeps_to_its_lane` fails on the new ranges, re-measure seeds 1 to 10 on the Mac as `plan-a/held.py` did and restate its docstring and bound from that, never loosening it past what seeds 1 to 10 show.)

- [ ] **Step 9: Commit.**

```bash
GIT add arena/events/sock-heist-6m.toml docs/guides/challenges/sock-heist-6m.md tests/test_lights.py
GIT commit -m "Sock Heist's ranges and time limit, measured on x86: the reference walker finishes every seed at <v> m/s, <s> s, meeting <n> reds, and the limit is its slowest seed plus half"
```

(Add `tests/test_steering.py` if Step 8 touched it.)

- [ ] **Step 10: The whole suite.** `PYTEST` over the files `ls tests/test_*.py` lists, in three foreground batches split before `test_constants.py` and before `test_recover.py`, then `PYTEST tests/workshop` — every one PASS; `cd /Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist/app && npx vitest run` — only the 4 known `brightness.test.js` failures (Plan C's front-end tests of the old caller are untouched here and still pass on their fixtures); `RUFF arena tests` — clean.

- [ ] **Step 11: Report** to the owner and to Plans C and D: the chosen ranges, the limit and the walker's slowest seed beside it, the walker's x86 score, command and per-seed times, the job's id; and that a duck caught in the last `COLLAPSE_S` before the limit collapses past it in its trace (A2's decision), which the clip, cut at the limit, does not show whole.
