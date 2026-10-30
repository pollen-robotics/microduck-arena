# Sock Heist — the interfaces contract

The names, signatures, file layouts and wire formats that the Sock Heist plans share. Each plan
implements its part of this contract and relies on the rest of it as written. A change to anything
here is a change to this file first, then to every plan that uses it.

**Spec:** [`../specs/2026-10-27-sock-heist-design.md`](../specs/2026-10-27-sock-heist-design.md),
on top of PR #3's own spec,
[`../specs/2026-10-21-red-light-green-light-design.md`](../specs/2026-10-21-red-light-green-light-design.md).

**Plans:**

| Plan | File | What it builds |
| --- | --- | --- |
| A | `2026-10-28-sock-heist-a-engine.md` | The event, random timetables, the collapse, five traces per run, the API, the booth, the guide, the x86 numbers |
| B | `2026-10-28-sock-heist-b-blender.md` | The nest, the socks, the giant in place: Blender script, GLBs, renders for the owner |
| C | `2026-10-28-sock-heist-c-site.md` | The giant, the head turn, the sounds, the dive, the replay on one seed, the clip to the slowest lane, the names |
| D | `2026-10-28-sock-heist-d-training.md` | The training folder in microduck-challenges, up to 10 trainings, the reference |
| E | `2026-10-28-sock-heist-e-release.md` | Push, PR, merge, version, wheel, relock, publish: each on the owner's yes |
| F | `2026-10-29-sock-heist-f-playground.md` | The playground venue, the pages' camera on the giant, a quack per red; replaces C6b and C8 |

**Order.** A1–A4 first (C reads the API they serve). B runs alongside A; its renders go to the owner,
and C's venue task waits for the owner's yes on them. D starts once A1–A2 have fixed the rules,
and its last evaluation waits for A's x86 numbers. E waits for D's reference.

## Where the work happens

- Worktree `/Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist`,
  branch `red-light-green-light`, which tracks `jrubiosainz/red-light-green-light` (PR #3). Today's
  `main` is merged in (74104f6). Never rebase, never force; merge `origin/main` again if it moves.
- In this worktree the shell's `git` is rewritten by a hook and refused: call `/usr/bin/git`.
- microduck-challenges: `/Users/nicolasrabault/Projects/HuggingFace/microduck-challenges`, on a
  branch `sock-heist` of its own (Plan D), from its `main`.
- Python commands: `uv run --frozen …` (a non-frozen `uv run` rewrites `uv.lock`). Front-end:
  `cd app && npx vitest run <file>`, and `npm run build`.
- Tests run in the foreground, never as a background run waited on.
- Known failures, not regressions: 4 tests of `app/src/brightness.test.js` (jsdom localStorage).

## Rules every plan follows

- English only, in code, comments, docs, commit messages, UI and clips.
- No signature of any assistant in commits; plain commit messages in the repository's style (one
  sentence saying what changed and why, no prefix).
- No dead code: what #3 built and Sock Heist no longer uses is deleted, its tests with it.
- No push, no PR edit, no merge, no publication, no HF Job, without the owner's yes. Plan D's
  trainings are authorised (up to 10), each launch still reported to the owner.
- Scope guard (#3's): every new behaviour sits behind `manifest.lights is not None` (or
  `steering`); the sweep, the golden run and `RUNNER_VERSION` (5) are unchanged for every other
  event.
- New binary assets go through Git LFS: add a `.gitattributes` line for each new path or pattern
  (`app/public/venue/*.glb`, the card's webp is already covered).

## Names

| Thing | Name |
| --- | --- |
| Event id | `sock-heist-6m` |
| Title | `6 m Sock Heist` |
| Event file | `arena/events/sock-heist-6m.toml` (`git mv` from `red-light-green-light-15m.toml`) |
| Guide | `docs/guides/challenges/sock-heist-6m.md` (`git mv` from `red-light-green-light-15m.md`) |
| Card | `app/public/cards/sock-heist-6m.webp` (replaces `red-light-green-light-15m.webp`) |
| Programme order | `order = 50` (after the Tug of War, 40) |
| Mechanism names that stay | `lights`, `[lights]`, `caught`, `steering`, `lights.js` |
| Training folder | `microduck-challenges/src/microduck_challenges/sock_heist_6m/` |
| Training task | `Mjlab-SockHeist6m-MicroDuck` |

## The event file

```toml
id           = "sock-heist-6m"
order        = 50
title        = "6 m Sock Heist"
category     = "race"
kind         = "perpetual"
rig          = "legs"
time_limit_s = 60.0          # A6 sets it from x86 (rule below)
metric       = "mean_finish_time"
seeds        = [1, 2, 3, 4, 5]

[course]   # kind "lane", length_m = 6.0, width_m 0.8, wall 0.15, slope 0: as #3 but 6 m
[command]  # as #3: vel = [0.25, 0.0, 0.0]
[start]    # as #3
[termination]  # as #3
[sweep]    # as #3: 0.20 to 1.20 by 0.05, 3 finalists

[lights]
first_green_s = [0.6, 1.0]   # A6 tunes the three ranges on x86
green_s       = [1.6, 3.0]
red_s         = [1.4, 2.4]
turn_s        = 0.4
tolerance_m   = 0.03

[steering]  # as #3

[clip]
tape_max_s = 60.0            # = time_limit_s; no `speed` key any more
sounds     = ["crowd", "horn", "giant", "verdict"]
[clip.camera]  # chase, track = true, hold: C retunes back/height/side/hold
```

**Time limit rule (A6):** on x86, the reference walker's slowest seed at its scored command, plus
50 %, rounded up to the next 5 s. `tape_max_s` equals it.

**Range rule (A6):** on x86, the reference walker finishes all five seeds, and meets 5 to 7 reds
per crossing at its scored command (counted on its trace seed).

## Python

### `arena/manifest.py`

```python
@dataclass(frozen=True)
class Lights:
    first_green_s: tuple[float, float]  # (lo, hi), seconds
    green_s: tuple[float, float]
    red_s: tuple[float, float]
    turn_s: float
    tolerance_m: float
```

`Lights.to_dict()` is deleted: the summary serves `served(manifest)`, and nothing else calls it.

Parsing (`_lights`): exactly the five keys; each range a list of two positive numbers, `lo <= hi`,
each a whole number of `CTRL_DT` steps; `turn_s` zero or more, whole steps, and shorter than
`red_s[0]`; `tolerance_m` positive. #3's `green_s`/`red_s` lists are gone with their checks.

`ClipConfig.speed` and the `[clip] speed` key are deleted (`_clip` refuses `speed` as unknown).
`SOUND_SOURCES` gains `"giant"`: `("crowd", "horn", "verdict", "giant")`. `ClipConfig.sounds`'
default becomes `DEFAULT_SOUNDS = ("crowd", "horn", "verdict")`, so that no other event gets the
giant. A manifest whose `[clip] sounds` lists `"giant"` without `[lights]` is refused.

### `arena/lights.py` (new): the giant's timetable

```python
LIGHTS_STREAM = 4  # the seed_rng family's stream: 1 is the servo delays, 2 and 3 a troupe's

@dataclass(frozen=True)
class Red:
    onset: int   # the control step the light turns red on, from the start of the clock
    length: int  # how many control steps it stays red

def timetable(lights: Lights, event_id: str, seed: int, steps: int) -> tuple[Red, ...]:
    """Every red of one seed's race, `steps` control steps long."""

def served(manifest: Manifest) -> dict:
    """The event summary's `lights`: turn_s, tolerance_m, and every seed's timetable in seconds."""
```

The draw: `rng = np.random.default_rng([zlib.crc32(event_id.encode()), seed, LIGHTS_STREAM])`;
step counts `int(rng.integers(lo, hi + 1))` over each range turned into steps; in the order: first
green, red, green, red, … until an onset reaches `steps`. A red that starts before `steps` is kept
whole. A golden test pins `timetable(Lights((0.6, 1.0), (1.6, 3.0), (1.4, 2.4), 0.4, 0.03),
"sock-heist-6m", 1, 3000)`'s first five reds, a literal rather than the event's lights, so that a
change to the draw cannot pass unseen and A6's retune leaves it as it is. (On the Mac, they start at
steps 35, 239, 463, 653 and 849.)

`served(manifest)` in the event summary and `_LightSteps.of(reds, turn, steps)` land in A1 with the
new `Lights`; A2 is the collapse alone.

`served(manifest)` returns:

```json
{"turn_s": 0.4, "tolerance_m": 0.03,
 "timetables": {"1": [[0.84, 1.62], [3.9, 2.1], ...], "2": [...], ...}}
```

each pair `[onset_s, length_s]` = `[onset * CTRL_DT, length * CTRL_DT]` rounded to 2 decimals, over
`round(time_limit_s / CTRL_DT)` steps, for every seed of `manifest.seeds`. The page draws the giant
from this: it never draws a random number of its own.

### `arena/runner.py`

- `_LightSteps.of(reds: tuple[Red, ...], turn: int, steps: int)` replaces `of(lights, steps)`;
  `red`, `mark`, `watch` mean what they meant.
- `run_once` draws `timetable(manifest.lights, manifest.id, seed, max_steps)` for its seed.
- **The collapse.** On the step a duck is caught, the run records that frame's index, then switches
  the duck's motors off: no more policy, no more `Servos.drive`, `data.ctrl[adr.act] = 0`, and
  simulates on (`DECIMATION` `mj_step`s then `mj_forward` per control step, a frame recorded per
  step) for `COLLAPSE_S` seconds, then ends `"caught"` with `time_s = None`.
  `COLLAPSE_S = 2.0`, a module constant (C's render may ask to retune it; it changes no score).
- `RunOutcome` gains `caught_frame: int | None = None`: the index in `trace` of the step it was
  caught on.
- A caught duck's trace runs `COLLAPSE_S` past its caught frame, even past the time limit. With no
  servo call after the catch, friction stays as the last drive left it: measured on the Mac, the
  trunk folds from 0.12 m to 0.04–0.07 m and lies still within 1 s.

### `arena/trace.py`

```python
@dataclass(frozen=True)
class SeedTrace:
    trace: np.ndarray          # (frames, TRACE_WIDTH)
    settle: np.ndarray         # (settle steps + 1, TRACE_WIDTH)
    caught: int | None = None  # the frame its duck was caught on

def encode_seeds(seeds: dict[int, SeedTrace]) -> bytes: ...
def decode(blob: bytes, seed: int | None = None) -> np.ndarray: ...
def decode_settle(blob: bytes, seed: int | None = None) -> np.ndarray: ...
def decode_caught(blob: bytes, seed: int) -> int | None: ...
```

A lights run's file holds, for every seed `s`: `trace_{s}`, `settle_{s}`, and `caught_{s}` (an
int32 scalar) for a seed caught. It holds no `trace`/`settle` key. Every array goes through
`_on_the_wire` as today. `decode(blob)` reads `trace` as before; `decode(blob, s)` reads `trace_{s}`;
`decode_settle` reads the settles the same way. A missing key raises `KeyError` in both. One file per
run, as the Space's store requires.

### `arena/evaluate.py`

`Evaluation` gains `seed_traces: dict[int, SeedTrace] | None = None`: on a lights event, every seed
of the scored command, keyed by seed (`trace`/`settle` stay the trace seed's). `evaluate` and
`evaluate_at` fill it. `pick_trace_seed` is unchanged.

`trace_file(result: Evaluation) -> bytes` in `arena/evaluate.py`: `encode_seeds(result.seed_traces)`
when it is set, `encode(...)` as today otherwise. Every writer of a run's trace file calls it
(`routes_submit`, the CLI, the recover path).

The workshop's local evaluation body (`arena/workshop/evaluations.py`) keeps its one trace, the
trace seed's, and gains `caught_frame` (that seed's `caught`, or null) on a lights event, so the
workshop replays it with the giant on `trace_seed`'s timetable.

### The API

- `GET /api/runs/{id}/trace?seed=N` and `GET /api/runs/{id}/settle?seed=N`. On a lights event, `seed`
  defaults to the run's `trace_seed`; a seed the run has no trace of is a 404. On any other event, a
  `seed` other than the run's `trace_seed` is a 404, and no `seed` is as today.
- A lights seed's trace response carries `X-Caught-Frame: <k>` when that seed was caught.
- The event summary's `lights` (`event_summary`) is `served(manifest)`, or null.

### The booth

`nature()` for lights: `f"a {length} sock heist: little microducks sneak up on a giant microduck's
nest to steal its socks, and must freeze whenever it turns its head"`, tags `("lights",)`.
`_unfinished`'s caught words: `"was caught moving while the giant looked on {caught}"`. The
`lights`/`caught` lore lines are rewritten for the giant (no Reachy caller, no "red light, green
light"), newcomer rules: no joke that needs to know Peter and Ray.

## Front-end

### `app/src/api.js`

`getTrace(runId, seed)` and `getSettle(runId, seed)`: `seed` optional, sent as `?seed=` when given.
The array `frames()` returns carries `caught`: the `X-Caught-Frame` header as a number, or null.

### The replay seed

On a lights event every lane of a replay plays one seed, and every lane's `traceSeed` is that seed:

- the event page (`race.js`): the leader's `trace_seed` (the board's first row);
- the run page (`run.js`) and its clip (`clip/main.js`): the run's own `trace_seed`.

`replayLane(..., { traceSeed, caught })`: the lane entry carries the fetched trace's `caught`. A lane's
`caught` is a frame of its timed trace, as served; the viewer adds the lane's `lead`. The seed a row
replays on comes from `cast.js` `replaySeed(event, row)`.

### `app/src/lights.js` (rewritten)

```js
/** The light `seconds` into the race, from one seed's timetable ([[onset_s, length_s], ...]):
 * { red, facing, watching }, facing 0 (head away) to 1 (head on the lanes), smoothstep over turnS. */
export function lightAt(timetable, turnS, seconds)
/** The frame from which a lane's duck is out, or null if it crossed: `caught` when set, else its
 * last frame when the trace ends short of the line (a fall, or the time limit). */
export function outAt(trace, length, caught)
/** outAt with the lane's caught frame counted after its lead-in. */
export function laneOut(lane, length)
/** That seed's served timetable, [] when the event has none. */
export function timetableOf(event, seed)
/** The first lanes across the line: { frame, lanes } or null when none crossed. */
export function firstAcross(lanes, length)
```

### `app/src/giant.js` (new; `caller.js`, `caller.test.js` deleted)

```js
export const GIANT_SCALE = 4.5;     // C may retune within 4–5
export const GIANT_BEHIND_M = 1.7;  // the giant's and the nest's centre past the line
/** Plan B's nest and socks, loaded once. */
export function loadHeistVenue() // -> Promise<{ nest: Mesh, socks: Mesh[] }>
/** How far past the line the ground runs on this event. */
export function floorBeyond(venue)
/** Where the loose socks lie between the line and the nest. */
export function laySocks(kinds, length, edge) // -> [{ kind, x, z, yaw }]
/** The giant microduck in its nest past the line of a `length` m race, its back to the lanes.
 * `pose(facing)` turns its head only, 0 away, 1 on the lanes; `dive(divers, seconds)` poses the
 * socks `seconds` after the first crossing. */
export function buildGiant(model, venue, length, edge) // -> { group, pose(facing), dive(divers, seconds), dispose() }
```

`model` is the racers' rig assets `{ kinematics, geometries }` (viewer.js `loadAssets("legs")`).
`microduck.glb` is a bank of part meshes, not a duck: the duck is built from `kinematics.json`, and
`pose` turns the rig's `head_yaw` to the joint's own limit (−2.967 rad, 170°). `venue` is
`loadHeistVenue()`'s, loaded only when `createViewer(canvas, { lights })` is asked for a lights event.
The viewer builds the giant instead of the caller when `event.lights` is set, and poses it with
`lightAt(timetable, turn_s, player.time - lead).facing`. `buildCourse(event, lanes, stripes, beyond =
OVERRUN)` runs the ground `floorBeyond(venue)` past the line on this event.

### Venue assets (Plan B produces, Plan C loads)

| File | Holds |
| --- | --- |
| `app/public/venue/sock-nest.glb` | One mesh `nest`: a nest woven from socks, glTF axes (Y up), origin at its floor centre, +X pointing away from the lanes, metres, sized for the giant at `GIANT_SCALE` |
| `app/public/venue/socks.glb` | Meshes `sock_0` … `sock_{n-1}` (n 3 to 5): loose socks, origin at the floor contact, for instancing |
| `scripts/sock_heist_venue.py` | The Blender script that builds both, run `blender -b -P scripts/sock_heist_venue.py -- <out dir>` |

Budget: the nest at most 6 000 triangles, each sock at most 400; the socks on the floor are one
`InstancedMesh` per sock model. Materials: vertex colours, no texture, no PBR maps. The node carrying
each mesh bears the mesh's name (three.js names an object after its node).

### The dive

```js
/** Where each sock is `seconds` after the first crossing: a pure function, the same every frame
 * of a clip. Before 0 every sock lies where it was laid. divers = [[x, z], ...], where each first
 * lane crossed. */
export function diveAt(socks, divers, seconds) // in app/src/giant.js -> [{ x, y, z, yaw, pitch }]
```

Only the first lane to cross makes the socks fly: the finished lane with the fewest frames, and every
lane that crossed on that same frame.

### Sounds

```js
/** Every sound of a Sock Heist replay, in seconds of the race clock: a quack where each red
 * begins (the head starts turning), and a fall where a lane's duck goes out, caught or fallen
 * (not out of time). */
export function heistCues(timetable, lanes, length, limitS) // -> [{ at, kind: "quack" | "fall", lane }]
```

In `app/src/heist-sound.js`. The page plays them live (`createHeistSound`, on the stage voice's
pattern: muted Arena, suspended context, a jump restarts), the clip through a `giant` source in
`clip/score.js`. The quack is the duck voice's chirp (`loadCalls().chirp`), played far lower
(`GIANT_RATE`, a playback rate under 1, tuned by ear with the owner); the fall is
`microduck-fall.wav`. `heist-sound.js` also exports `GIANT_CALL` (the chirp variant) and
`giantQuack(calls)`. A clip quack cue is `{ at, quack: true, rate, gain }`, and
`clipScore({ run, plan, trace, ducks, lanes })` takes the lanes.

### The clip

- `clipPlan(authorFrames, tapeMaxS, settle)`: no `speed` any more. On a lights event `clip/main.js`
  passes the longest lane's frame count, so the tape runs until every lane is decided.
- The time-lapse goes everywhere: `plan.speed`, `stride * speed`, the `×N` on the clock, the score's
  `plan.speed`.
- The stamp still lands on the author's lane.
- **Its cost.** At 1× a 60 s limit makes a clip of about 1 640 frames per layout, some 54 min of
  render against the clip job's 30 min timeout. The time limit is the main lever: A6 reports the
  walker's slowest seed beside the limit its rule gives, and C8 measures the render on the longest
  case before the owner settles the limit.

## Training (Plan D)

- Folder `src/microduck_challenges/sock_heist_6m/` with `AGENTS.md`, `challenge.toml`
  (`event = "sock-heist-6m"`, `task = "Mjlab-SockHeist6m-MicroDuck"`, `kind = "perpetual"`), `env.py`,
  `tasks.py`, listed in the repository's `AGENTS.md`.
- The env mirrors the event's numbers, each copied with a comment naming
  `arena/events/sock-heist-6m.toml`: the ranges, `turn_s`, `tolerance_m`, the lane, the steering
  hold. The policy sees only its command, as on the Arena: on red the twist is zero.
- A checkpoint is judged with `publish --dry-run` then `arena score` on this worktree's code (Mac,
  for triage), and the candidate on x86.
- The bar: all five seeds finished on x86, and a lower score than the reference walker's
  (`arena/assets/policies/BEST_alpha_walking.onnx`) on x86.
- The env also copies `[start]`'s `settle_s` (an episode's first `round(settle_s / CTRL_DT)` steps
  stand, unwatched, as `run_once`'s settle) and `yaw_deg`. It has no lane geometry, no walls and no
  finish line: the lane is the spawn line along +x.
- Plan D's parity tests import `arena.runner._LightSteps`, `arena.runner._steered`, `arena.lights.Red`
  and `arena.lights.timetable`, and its `check.py` reads `RunOutcome.caught_frame`: their names and
  signatures are part of this contract.
- A6's x86 job scores every ONNX file it is given (the walker's and Plan D's candidates) with this
  worktree's `arena`, and prints `arena score`'s output for each. Plan D reuses it, on the owner's
  yes each time.
- The trainings run under `--namespace Nico-robot` on l4x1, as the Tug of War's did (the owner's
  grant). A job that fails before its first checkpoint does not count toward the 10.
- The guide's Train section (`docs/guides/challenges/sock-heist-6m.md`) runs `workshop.py sock-heist-6m`,
  in place of #3's pointer to the sprint's template.

## Amendment, 2026-10-29 (Plan F)

The owner's three changes of 2026-10-29 (spec, "Amendment, 2026-10-29"). Where this section and the
rest of the contract disagree, this section holds.

### Venue assets

`app/public/venue/playground.glb`, built by `scripts/sock_heist_venue.py` with the nest and the socks,
in glTF axes, metres, origin on the start line at the lanes' centre line. Its top-level nodes are
`yard` (the ground, its top at y = −0.003), `left` (the school building), `right` (the wooden fence)
and `park` (the trees). The sides are built from z = 0, the lanes' edge, outwards (−z for `left`, +z for
`right`), each carrying crowd spots, empties `spot_<k>` at y = 0, turned about +y towards the track.
Repeated models use `EXT_mesh_gpu_instancing`. Nothing in it stands over the seated giant (0.93 m).
`sock-nest.glb` and `socks.glb` are unchanged, byte for byte.

### `app/src/giant.js`

`loadHeistVenue() -> Promise<{ nest, socks, playground: { yard, left, right, park } }>`.
`floorBeyond` and `FLOOR_MARGIN_M` are deleted. `draw(k, n)` is exported (heist-sound.js draws the
quacks with it).

### `app/src/playground.js` (new)

`buildPlayground(model, spectators, edge) -> { group, crowd, pose(seconds, mood), floorMaterial(), dispose() }`:
clones of the model's nodes, `left` at z = −edge and `right` at +edge, stadium.js `crowd` seated on
their spots. The viewer holds it where it holds the gym on any other race: no stadium, no judges.

### `app/src/course.js`, `app/src/viewer.js`

`buildCourse(event, lanes, stripes)` and `attachCourse(scene, event, lanes, stripes)`: no `beyond`.
`packChase(xs, zs, aspect, fov)`; its one `PACK_REACH = 0.6`, the field's reach on a tracking race (only a lights race tracks).

### `app/src/cast.js`

`pageCamera(event)`: `event.clip.camera` on a lights event, else `null`. The event, run and workshop
pages pass it to `createViewer` as `camera`.

### Sounds

`GIANT_CALL` is deleted. `GIANT_RATE = 0.3` is the centre of a quack's rate, and `GIANT_SPREAD = 0.1`.
`quackOf(seed, red) -> { variant, rate }` is drawn with giant.js's `draw`: the variant among the synth's
`VARIANTS.chirp` (duck-voice.js, now exported), the rate within `GIANT_SPREAD` of `GIANT_RATE`.
`giantQuack(calls, variant)`. `heistCues(timetable, lanes, length, limitS, seed)`, whose quack cues
carry `variant` and `rate`. A clip quack cue is `{ at, quack: true, variant, rate, gain }`, its seed
`run.trace_seed`.

### The clip's cost

Plan F Task 6 replaces C8: the local bench against the gym's version, then one t4-small HF Job on the
owner's yes. Passed when a frame costs no more than the gym version's and the longest clip renders in
at most 20 min.
