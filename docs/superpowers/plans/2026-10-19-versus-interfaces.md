# Versus — shared interfaces and constraints for the four plans

**Spec:** `docs/superpowers/specs/2026-10-19-versus-tug-of-war-design.md` (approved by the owner
2026-10-19, amended 2026-10-20 night). Eight plans implement it and all build against the names below:

| Plan | File | What it builds | Repo / branch |
|---|---|---|---|
| A | `2026-10-19-versus-a-tug-and-bench.md` | the tug course, string, bout and match physics, ranking direction, the tug's pages and clips (Plan E replaced its winch bench by the rating against the reference duck) | arena, branch `versus` |
| B | `2026-10-19-versus-b-tug-recipe.md` | the `tug_of_war` training recipe, the trainings, the first candidate, the publish CLI's line for a tug entry | microduck-challenges, branch `tug-of-war`; microduck_rl, branch `tug-publish-line` |
| C | `2026-10-19-versus-c-weekly-cup.md` | calendar, entrants, secret, draw, groups, knockout, cup records, secrecy, match clips, cup and match pages, points, premiere on the live | arena, branch `versus` |
| D | `2026-10-19-versus-d-cup-show.md` | the show: running order with the desk, play-by-play, tournament-aware writer, desk screen | arena, branch `versus` |
| E | `2026-10-20-versus-e-reference-bouts.md` | the rating by five bouts against the reference duck, 45 s bouts, the winch removed | arena, branch `versus` |
| F | `2026-10-20-versus-f-opponent-training.md` | training against a frozen opponent duck, the reference first; the publish line in cm | microduck-challenges, branch `tug-of-war`; microduck_rl, branch `tug-publish-line` |
| G | `2026-10-21-versus-g-ring-and-rope.md` | the 3 m wrestling ring whose ropes are the field's edges, the physical string, the judge on its middle, the string recorded, served and drawn, the venue bound to the ring | arena, branch `versus` |
| H | `2026-10-21-versus-h-upright-on-the-ring.md` | the recipe on the ring and the string, the "stay upright" knob, the upright reference | microduck-challenges, branch `tug-of-war` |

A section's names are owned by the plan that introduces them; a later plan uses them as written
here. If a plan must change a name, it changes this file in the same commit.

## Global constraints (every task of every plan)

- **Commits, PRs, GitHub:** English only, never signed: no `Co-Authored-By`, no "Generated with
  Claude Code". Commit subjects read like the repo's (a sentence saying what changes for a person).
- **English only** in code, comments, UI, docs, clips and commentary. A stage run is a
  "performance"; the cup's broadcast is the "show".
- **Nothing leaves this Mac without the owner's yes**: no push, no wheel upload, no Space dataset
  write, no Hub publish. Exception granted by the owner on 2026-10-19: **HF Jobs trainings for
  Plans B and F under the owner's account (Nico-robot) have no budget limit.** Everything is pushed
  together at the end (Plan D's last task lists the release steps; each needs the owner's yes).
- **Order of execution:** A, then C, then D on one branch `versus` in one worktree. B starts once
  Plan A's Task 3 is committed (it names the commit B needs) and runs alongside, in the challenges
  repo; B's steps that run `arena score` on a tug wait for A's Task 5. B's Task 13 changes the
  publish CLI in microduck_rl (worktree branch `tug-publish-line` from `challenge-recipe-publishing`);
  D's release pushes it before the challenges relock. Stages 2–3 never wait for a good policy: tests
  use the vendored walker and fakes, the local rehearsals use B's intermediate checkpoints.
  **From 2026-10-20 night:** Plan F Task 1 (the winch out of the recipe) → Plan E Tasks 1–8 → Plan F
  Tasks 2–8 (Task 7: trainings t8/t9 on HF Jobs, in the background) → while they train, Plan C
  Tasks 8–14 → Plan D → Plan F Task 9 at release. E's Tasks 2 and 4 bring the challenges' pins along
  in the same sitting (`BOUT_S = 45.0`; `compile_tug(EVENT)`, `tug_layout(EVENT.course)`), so F's
  Tasks 2–9 call the one-argument forms. **From 2026-10-21:** Plan G Task 1 any time first; G2 → G3 → G4
  back to back (from G2's commit the challenges' parity tests are red, until Plan H Task 2; nothing
  trains in between); Plan H Tasks 1–5 after G4, G5–G8 beside them; G9 with Plan H Task 6, in one
  sitting; Plan H Task 7 after G9.
- **Settled by the owner (2026-10-20), no question to ask:** only the pit decides
  (a fall no longer loses: the earlier "a fall loses" ruling of the same day was reversed that
  evening, a downed duck stays in play and can be dragged in); HF Jobs trainings stay on l4x1; the first candidate's repo is
  `Nico-robot/microduck-tug-of-war` unless the owner names another at publish time; cup #1's Friday
  is set at release (D's release step asks); about 150 LLM router calls per cup are acceptable; on
  air a duck is named by its on-air `name` (Plan C's `Entrant.name`: the policy's name, plus
  ` (@<user>)` when another entrant of the cup has the same policy name) on the score bug, the match
  page's stamp, the bout plates and in the call lines, and billed `"<policy name> (@<user>)"`
  (`cup.duck`) in match titles (so the clip cards), under a replayed match's UP NEXT title, on the
  cup screen's bracket and footer and at the desk, the cup screen's group tables by handle alone, a
  match clip's stamp putting the handle on an ink tag under the policy's name and its REC line naming
  the players (amended 2026-11-14, issue #8); the cup page shows the policy's name and the player's handle; the run
  page's stamp `RATED`, the lime round card with `Pull!`; 45 s bouts, a rating of five bouts against
  a frozen reference duck in cm with a pit bonus, no winch (2026-10-20 night).
- **Worktree (arena):** `~/Projects/HuggingFace/microduck-arena/.claude/worktrees/versus`, branch
  `versus` from local `main` at `abcbb9e` or later. From the main checkout:
  - `/usr/bin/git worktree add .claude/worktrees/versus -b versus main`
  - `cd .claude/worktrees/versus && uv sync --no-config --frozen --extra dev && (cd app && npm ci)`
- **Local main carries someone else's uncommitted edits** (`app/public/race.css`,
  `app/src/{main,router,router.test,share,share.test}.js`). Never stash, reset, commit or overwrite
  them; the worktree starts from the committed `main` and does not see them. The one exception is
  Plan D's release step 1, on the owner's yes: it holds them aside for the fast-forward and puts
  them back, checked hunk by hunk.
- **git:** always `/usr/bin/git` (the RTK hook's `git` rewrite is refused inside a worktree).
- **uv:** always `uv run --no-config --frozen …`. If `uv.lock` changes by accident:
  `/usr/bin/git checkout -- uv.lock`.
- **Shell inside the worktree:** no globs and no shell variables inside git, uv and npm commands;
  write paths out in full.
- **Tests run in the FOREGROUND**, one Bash call with `timeout: 600000`; never in the background,
  never "waiting for" a run. Python suite, two calls:
  1. `uv run --no-config --frozen --extra dev pytest -q -m "not network" -p no:cacheprovider tests/workshop`
  2. `uv run --no-config --frozen --extra dev pytest -q -m "not network" -p no:cacheprovider tests --ignore=tests/workshop`
  Front end: `cd app && npm test`; the only accepted failures are the 4 known ones in
  `src/brightness.test.js`. One file: `cd app && npx vitest run src/<file>.test.js`. The rtk filter
  hides vitest's unhandled-rejection report: use `rtk proxy npx vitest run` when counting.
- **Untouched:** the golden run (`arena/golden.py`), `RUNNER_VERSION` (stays 4), the 61-D
  observation and 13-number command, every existing event's physics and stored runs. A lone duck,
  a lane and a stage compile and run bit-identically (the existing tests in `test_course.py`,
  `test_run_stage.py`, `test_evaluate.py` stay green unchanged).
- **No dead code, no just-in-case generality** (owner's standing rule). Versus machinery that the
  tug of war does not use is not written.
- **x86 is the truth:** official ratings and cups are computed on the Space. Never compare a Mac
  run to a Space run; tests pin behaviour, not Space numbers.
- **Booth text** is never filtered by a script; fix bad lines in the prompt. Jokes must land for
  newcomers (no private running gags).
- **New pages** look like the Arena's own pages: few buttons, only what is needed when it is needed.

## Codebase facts the plans rely on

- Physics: `TIMESTEP=0.005`, `DECIMATION=4`, `CTRL_DT=0.02` (50 Hz), `TRACE_WIDTH=21`
  (`frame[0:3]` trunk position, `[3:7]` quaternion w,x,y,z, `[7:21]` the 14 joints in
  `JOINT_NAMES`). `arena/course.py`: `_inject_course` (one static `course` body: an infinite
  `floor` plane, plus `wall_boxes` for a lane), `_robot(rig)`, `build_course_xml`, `_motorized`,
  `_compiled`, `compile_course`, `duck_prefix(k)` (`""` / `"duck{k}/"`), `compile_stage(manifest,
  layout)` (duck 0 from `build_course_xml`, others attached on a frame, keyframe patched after
  compile). `arena/runner.py`: `_Addresses.of`, `_streams(event_id, seed, k)`, `_start(manifest,
  model, policies, yaws_deg, seed, commands, sites=()) -> (sim, settle, settle_points)` (`settle_points`:
  (settle steps + 1, len(sites), 3); `run_once` and `run_stage` take `sim, settle, _`), `_Sim(model, data,
  ducks, sites=())`, `_Sim.step/record/points(out)`, `run_once`, `run_stage`; `run_once` stops on the fall rule (trunk gravity z above `fall_gravity_z` for
  `fall_hold_s`), and `arena/stage.py fell_at(trace, termination)` reads the same rule off a
  `(frames, 21)` trace. The legs robot's `neck` body sits in `trunk_base` at `pos="0.026 0.0145 0.0324215"`
  (`arena/assets/robot/legs/robot_allcollisions.xml:181`); there is no site there today.
- Evaluation and records: `arena/evaluate.py` (`SeedResult`, `Evaluation`, `METRICS`,
  `evaluate`, `pick_trace_seed`); `arena/store.py` (`RunRecord`, `Store` protocol, `LocalStore`,
  `HubStore` with one `create_commit` per write and a tree-diff snapshot that excludes `*.mp4`,
  `*.png`, `votes/`); `arena/trace.py` (`encode(trace, settle)` float16 npz, `decode` →
  `(ducks, frames, 21)`).
- Ranking: `arena/index.py` `sort_key` (lower is better), `leaderboard`, `standing`;
  `arena/points.py` (`SCHEDULE`, `Receipt`, `receipts(…, now)` folds acts; podium points are held,
  recomputed per request); `routes_read.py:183` keeps votes on a separate path.
- Server: `arena/web/app.py create_app` (routers read, submit, auth, vote, unfurl, live, launcher;
  daemon threads `arena-clips`, `arena-commentary`, `arena-recover`, `arena-votes`);
  `ArenaConfig.from_env`. No wall-clock scheduler exists; clocks are injected (`now`) in pure
  modules, patched in route tests.
- Clips: `arena/clips.py` (`ClipRenderer.render_one(id)`, `ClipJobs` with `JOB_TRIES=3`, pending
  markers under `clips/<id>/`), `arena/recorder.py record_run(origin, run_id, …)` opens
  `clip.html?run=<id>&layout=<l>&frame=0`; front `app/src/clip/{main,plan,score,direction}.js`.
- Live: `arena/live.py` (`pool`, `cycle`, `slots_for`, `Programme(source, now_ms, book)` with
  slot kinds `shutter`, `replay`, `booth`; every slot length a multiple of 40 ms);
  `arena/broadcasts.py BroadcastBook`; `arena/commentary/` (`Fact`, `result_facts`, `notable`,
  `lore`, `generator.write(facts, drawn, …)` → 3–6 alternating turns, `stock.CommentaryStock`,
  `tab.PlanTab.prepare(dialogue)` → `window.plan` in `plan.html` → `live/score.js prepare`).
  Front `app/src/live/` (`channel.js` conductor, `replay.js`, `interlude.js` = booth segment,
  `booth.js`, `set.js` with the "pegboard" meshes, `captions.js`, `voice.js`, `score.js`).
  Nothing is said during a replay today.
- Front: hash router `app/src/router.js` (`parseRoute`, `*Href`, `themeFor`, `dress`),
  `main.js show()`, `api.js` (fetch wrappers; traces are float32 with `X-Duck-Count`),
  `format.js` (`formatScore(seconds, {finished})`, `isStage`), `course.js` (`buildCourse`; a lane's
  served `walls` are not drawn today; a tug's served `ropes` and `posts` are drawn by `tug-venue.js`), `viewer.js createViewer(...).setLanes(entries, event, opts)`,
  `replay.js applyFrame`, `rig.js`, `run.js`, `race.js`, `home.js` + `roundcard.js
  roundCard(event, rows, {number, corner})`, `player.js`. vitest + jsdom, no WebGL in tests.
- Tests: `tests/test_store.py make_record(**overrides)`; `test_routes_read.py client(tmp_path)` →
  `(TestClient, app)` from `ArenaConfig.from_env(store_dir=tmp_path, dev_user="coralie")`;
  `test_hub_store.py FakeHub`; the walker `arena/assets/policies/BEST_alpha_walking.onnx` via
  `load_policy`; `_ZeroPolicy` style fakes (`act(obs) -> np.zeros(14, float32)`).

## Plan A — names (as Plan G leaves them)

```python
# arena/manifest.py
CATEGORIES = {"race", "showcase", "versus"}
METRICS = ("mean_finish_time", "votes", "mean_ground_cm")
COURSE_KINDS = ("lane", "stage", "tug")
HIGHER_WINS = frozenset({"mean_ground_cm"})     # every other metric: lower is better

@dataclass(frozen=True)
class Tug:
    ring_m: float         # rope to rope: the field is the square inside the ring's ropes, centred on the pit
    pit_m: float          # the pit's width along x, centred on x = 0, across the whole ring
    pit_depth_m: float
    string_m: float       # neck base to neck base, straight at the start
    kind: str = "tug"

@dataclass(frozen=True)
class Rating:
    reference: str        # the reference duck: a file name in arena/assets/policies/
    pit_bonus_cm: float   # added when the reference ends in the pit, taken off when the entry does

@dataclass(frozen=True)
class BoutRules:
    time_limit_s: float
    bouts_to_win: int
    max_bouts: int

# Manifest gains rating: Rating | None = None, bout: BoutRules | None = None. A tug: versus and mean_ground_cm, needs
# [rating] and [bout], its time_limit_s equal to [bout]'s; others refuse both.
def higher_wins(event_id: str) -> bool   # cached; True iff the event's TOML exists and its metric is in HIGHER_WINS
```

Validation: `course.kind == "tug"` ⇔ `category == "versus"` ⇔ `metric == "mean_ground_cm"`; a tug
requires `[rating]` and `[bout]` (its `time_limit_s` equal to `[bout]`'s), refuses `[sweep]` and
`[vote]`, requires `rig = "legs"`, refuses unknown keys in its `[course]`, `[rating]`, `[bout]`; its
`[course]` values are all positive and `pit_m < string_m < ring_m`;
any other event refuses `[rating]` and `[bout]`.

`arena/events/tug-of-war.toml` (Plan A creates it; Plan C adds `[cup]`; Plan B may retune
`[command]`, `[bout]` and `[rating]`, the parity test keeps both repos equal):

```toml
id           = "tug-of-war"
order        = 40
title        = "Tug of War"
category     = "versus"
kind         = "perpetual"
rig          = "legs"
time_limit_s = 45.0
metric       = "mean_ground_cm"
seeds        = [1, 2, 3, 4, 5]

[course]
kind          = "tug"
ring_m        = 3.00          # rope to rope: the field is the square inside the ring's ropes
pit_m         = 0.30
pit_depth_m   = 0.30
string_m      = 1.00          # neck base to neck base, straight at the start

[command]                     # every duck, every bout: walk backwards
vel  = [-0.30, 0.0, 0.0]
head = [0.0, 0.0, 0.0, 0.0]
body = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

[start]
keyframe = "STAND"
settle_s = 0.5

[start.perturbation]
joint_rad = 0.01
yaw_deg   = 2.0

[termination]                 # summaries only: a fall never ends a bout
fall_gravity_z = -0.5
fall_hold_s    = 0.3

[rating]
reference    = "tug-reference-t20-500.onnx"
pit_bonus_cm = 100.0

[bout]
time_limit_s = 45.0
bouts_to_win = 2
max_bouts    = 5

[clip]
tape_max_s = 45.0
sounds     = ["crowd", "verdict"]
```

```python
# arena/course.py
STRING_SITE = "string_end"   # on each duck's trunk_base (prefixed for duck 1), at the neck's base
PLATFORM_OVERRUN_M = 20.0    # the platforms run this far past the ring: nobody walks off the world
WALL_THICKNESS_M = 0.05      # a backstop is that thick
RING_ROPES_M = (0.06, 0.12, 0.18)   # the ropes' axes over the canvas, bottom to top
RING_ROPE_RADIUS_M = 0.006
RING_POST_RADIUS_M = 0.022
RING_POST_TOP_M = 0.23
STRING = "string/"           # the prefix of the string's bodies `string/seg{k}`, joints `string/root`,
                             # `string/j{k}y`, `string/j{k}z`, geoms `string/cap{k}`, sites `string/p{k}`
STRING_SEGMENTS = 16         # 17 points; STRING_RADIUS_M = 0.004, STRING_MASS_KG = 0.080, STRING_END_MASS_KG = 0.015,
                             # STRING_DAMPING = 0.003, STRING_ARMATURE = 1e-6, STRING_TIE_SOLREF = (0.01, 1.0),
                             # STRING_TIE_SOLIMP = (0.9, 0.95, 0.001, 0.5, 2.0) (MuJoCo's default, as the rope study ran the ties),
                             # STRING_FRICTION = (1.0, 0.005, 0.0001): the measured ones, never lowered

def string_offset(rig: str = "legs") -> tuple[float, float, float]   # the `neck` body's pos in `trunk_base`, read from the rig's MJCF
def ring_ropes(course: Tug) -> list[tuple[str, tuple, tuple]]        # (`rope_<side>_<k>`, from, to): west, east, north, south, each bottom to top, a side post to post
def ring_posts(course: Tug) -> list[tuple[str, tuple, tuple]]        # `post_nw`, `post_ne`, `post_sw`, `post_se`: z 0 to RING_POST_TOP_M at (±ring_m/2, ±ring_m/2)
def backstops(course: Tug) -> list[tuple[str, tuple, tuple]]         # (`backstop_<side>`, pos, half): flush behind the side's ropes, up to the top rope
def pit_boxes(course: Tug) -> list[tuple[str, tuple, tuple]]         # "platform_west", "platform_east" (top face z = 0), "pit_floor" (top face z = -pit_depth_m), sized on ring_m
def tug_layout(course: Tug, rig: str = "legs") -> list[Start]  # [west yaw 0, east yaw 180]; both string ends on y = 0, string_m apart, centred on x = 0
def string_sites(model) -> np.ndarray                          # the string's 17 site ids, west to east
def compile_tug(manifest: Manifest) -> mujoco.MjModel
# two ducks tied by the string: 16 capsule segments, a free root on `string/seg8`, each joint two hinges (y then z),
# a `connect` tie from `string_end` to `string/p0` and from `duck1/string_end` to `string/p16`; no tendon.
# _inject_course gets a "tug" branch: no infinite plane, pit_boxes + backstops, then the rope and post capsules.
# compile_stage is split into helpers it shares with compile_tug; compile_stage stays bit-identical.
# Gone: tug_walls, the geoms wall_left and wall_right (a tug has none), the tendon STRING.
```

```python
# arena/tug.py — new
PIT_DROP_M = 0.05      # a trunk below z = -PIT_DROP_M is in the pit

STRING_POINTS = 17     # the string's recorded points, west to east
MIDDLE = 8             # the marker: the string's middle point
def marker_x(string: np.ndarray) -> np.ndarray             # (frames, 17, 3) -> (frames,), the middle point's x
def in_pit(frame: np.ndarray) -> bool                       # frame (21,): trunk z < -PIT_DROP_M
SIDES = ("west", "east")
def reference_duck(manifest: Manifest) -> Policy            # load_policy(ASSET_ROOT / "policies" / manifest.rating.reference)
def entry_side(seed: int) -> int                            # 0 (west) on an odd seed, 1 (east) on an even one
def bout_status(outcome: BoutOutcome, entry: int) -> str    # "won" | "lost" | "pit_won" | "pit_lost" | "draw"
def bout_score_cm(outcome: BoutOutcome, entry: int, pit_bonus_cm: float) -> float

# Only the pit decides (owner, 2026-10-20 evening): a duck is OUT when, after a control step, its
# trunk is in the pit (in_pit of its last frame, z < -PIT_DROP_M). A duck knocked over, sitting or
# lying on the platform stays in play and can be dragged. A MuJoCo solver reset in a bout stays a draw.

@dataclass(frozen=True)
class BoutOutcome:
    seed: int
    loser: int | None      # 0 west, 1 east, None undecided by the physics
    how: str               # "pit" (the first duck in), "marker" (both in on one control step, or the time
                           # limit), "draw" (marker exactly 0)
    time_s: float          # when it was decided
    trace: np.ndarray      # (2, frames, 21), west first; stops at the deciding step
    settle: np.ndarray     # (2, settle + 1, 21)
    string: np.ndarray     # (frames, 17, 3), float32: the string's points, one frame per trace frame
    string_settle: np.ndarray   # (settle + 1, 17, 3)

def run_bout(manifest: Manifest, west, east, seed: int, model=None) -> BoutOutcome
# the first duck in the pit loses; marker rule (the string's middle point): marker_x < 0 (pulled to the west) -> east loses; > 0 -> west loses; == 0 -> draw
```

```python
# arena/match.py — new
def bout_seed(secret: str, match_id: str, k: int) -> int
#   int.from_bytes(hashlib.sha256(f"{secret}:{match_id}:{k}".encode()).digest()[:4], "big")

@dataclass(frozen=True)
class BoutResult:
    k: int
    seed: int
    a_side: str            # "west" in bouts 0, 2, 4; "east" in 1, 3
    winner: str | None     # "a" | "b" | None (a draw counts for nobody)
    how: str               # BoutOutcome.how: "pit" | "marker" | "draw"
    time_s: float
    def to_dict(self) -> dict; @classmethod def from_dict(cls, raw) -> "BoutResult"

@dataclass(frozen=True)
class MatchOutcome:
    bouts: tuple[BoutResult, ...]
    traces: tuple[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray], ...]   # (trace, settle, string, string_settle) per bout, west first
    wins: tuple[int, int]                               # (a, b)
    winner: str                                         # "a" | "b"
    decided_by: str                                     # "bouts" | "rating"

def play_match(manifest: Manifest, a, b, seeds: Sequence[int], ratings: tuple[float, float], model=None) -> MatchOutcome
# len(seeds) == bout.max_bouts; stops when one side reaches bouts_to_win; after max_bouts without
# a winner: more wins, then higher rating, then "a". It calls run_bout through the module global
# (tests swap arena.match.run_bout).
```

```python
# arena/evaluate.py
SeedResult(seed, status, time_s, score_cm: float | None = None)
def mean_ground_cm(per_seed, time_limit_s) -> float       # METRICS["mean_ground_cm"]
def seed_row(result: SeedResult) -> dict                  # seed, status, time_s, plus score_cm only when set; every writer of a seed uses it
# a tug: one run_bout per seed, the entry on entry_side(seed), reference_duck opposite; trace seed = lower median by
# (score_cm, seed), its (2, frames, 21) trace and settle; no record field (a page places the entry by trace_seed)

# arena/trace.py: encode(trace, settle=None, string=None, string_settle=None); the npz of a tug also holds
# `string` (frames, 17, 3) and `string_settle` (settle + 1, 17, 3), float16; decode_string(blob) -> (string_settle, string),
# float32, ValueError("this trace holds no string") without one. Evaluation.string / .string_settle: None but on a tug.
# arena/moments.py: moments(trace, string, course).
# Wire: GET /api/runs/{id}/string and GET /api/matches/{id}/bouts/{k}/string: little-endian float32, the settle's
# frames then the timed frames, 51 floats a frame; headers X-Frame-Count (timed), X-Settle-Frame-Count,
# X-Point-Count: 17, Cache-Control: no-store; 404 "run {id} has no string" without one.

# arena/store.py: a seed's `score_cm` is written only when set, so every stored race and
# performance serialises as today.

# arena/index.py
def sort_key(record) -> tuple   # (-score if higher_wins(record.event_id) else score, -seeds_finished, submitted_at)

# arena/recover.py: a Hub manifest that names no event is never recovered onto the tug (entering a
# versus enters its cup: it takes a policy entered on purpose).
```

The reference duck's bytes ship with the Arena (`arena/assets/policies/tug-reference-t20-500.onnx`,
pinned by sha256 in `tests/test_assets.py`, recorded in `arena/assets/PROVENANCE.md`).

`arena score` on a tug (Plan F reads it): per seed
`f"seed {s}: {SIDES[entry_side(s)]:<4} {status:<8} {score_cm:+7.1f} cm at {time_s:.2f} s"`, then
`f"rating: {score:.1f} cm · replay from seed {n}"` (a minus sign when negative).

API: `event_summary` of a tug adds `course: "tug"`, `ring_m`, `string_m`, `pit_m`, `pit_depth_m`,
`ropes: [{name, from, to, radius}]` (12), `posts: [{name, from, to, radius}]` (4),
and `bout: {time_limit_s, bouts_to_win, max_bouts}`;
never `length_m`, `width_m`, `walls` or `pit`. `per_seed` items
carry `score_cm`; every board row carries `trace_seed`; a player's publications carry `metric`. `POST /api/events/{id}/submit` answers with the event's `metric` (every
event; the publish CLI reads it, Plan B's Task 13).

```js
// app/src/format.js
export const isTug = (event) => event?.course === "tug";
export function formatScore(value, { finished, metric } = {})   // "12.3 cm" for "mean_ground_cm"; seconds otherwise, as today
// app/src/tug.js — new (mirrors arena/tug.py; MJCF coordinates in, three.js out)
export function toThree([x, y, z])                  // [x, z, -y]
export const STRING_WIDTH = 51, MIDDLE = 8          // floats a frame (17 points × 3), the marker's point
export function stringAt(string, f)                 // frame f's 51 floats
export function tugString(entry, lead)              // a lane's string from where its ducks stand: its settle's last `lead` frames, then its trace
export const SIDES, BOUT_WORDS; export function entrySide(seed)   // mirror tug.py's SIDES, entry_side; REFERENCE (module-private) = {livery: "charcoal", name: "Reference"}
export function ratingLane(traces, settles, string, {traceSeed, livery, name})   // the entry's bout lane, its `string: {trace, settle?}`; the Reference wears "classic" when the entry wears "charcoal"
export function tugDucks(entry)                     // a tug lane -> [{trace, lead, livery, name}], a settle led in
export function tugSpan(frames)
export function buildTugVenue(event, spectators, reachy, branding, clearance)   // app/src/tug-venue.js: the ring drawn from the served ropes and posts
export function buildString()                       // { group, update(points), dispose() }: a Catmull-Rom tube of radius 0.004 m through the 17 points, the red ribbon at point 8
export function getString(runId), getBoutString(matchId, k)   // app/src/api.js: Promise<{settle: Float32Array, trace: Float32Array}>
// app/src/workshop/api.js: getCheckpoint returns `string` (Float32Array) when the body holds `string_b64`
// a tug checkpoint's body (arena/workshop/evaluations.py, FORMAT = 3) gains `string_b64`: the timed string, little-endian float32
// app/src/clip/score.js
export function clipVerdict(run)                    // {stamp, pass}: stamps a tug's traced status; `clip/plan.js stampLane(run, laneCount)`
```

A tug lane handed to `viewer.setLanes` (one per call) is only
`{tug: "bout", ducks: [{trace, settle?, livery, name}, {…}], string: {trace, settle?}}` (west first; a
duck's trace is in world coordinates, so it needs no start; an optional `settle` plays before `trace`;
the string is the recorded one).

## Plan B — cross-repo names (as Plan G leaves them)

Plan B copies these Arena names into `microduck-challenges` (its job cannot import the Arena) and
pins each one with a parity test; the Arena must not change them without Plan B's copy. Plan H
makes the copies the ring and the string need: the lane's names (`wall_left`, `wall_right`,
`WALL_HEIGHT_M`, `LENGTH_M`, `WIDTH_M`) and the tendon's (`STRING` as the tendon, the tendon's range)
go out; in come the geoms `platform_west`, `platform_east`, `pit_floor`, `backstop_<side>`,
`rope_<side>_<k>`, `post_nw`, `post_ne`, `post_sw`, `post_se`; the ring's constants `RING_M`,
`RING_ROPES_M`, `RING_ROPE_RADIUS_M`, `RING_POST_RADIUS_M`, `RING_POST_TOP_M`; the string's
`STRING` (the prefix `"string/"`), `STRING_SEGMENTS`, `STRING_RADIUS_M`, `STRING_MASS_KG`,
`STRING_END_MASS_KG`, `STRING_DAMPING`, `STRING_ARMATURE`, `STRING_TIE_SOLREF`, `STRING_TIE_SOLIMP`, `STRING_FRICTION`,
`MIDDLE`, and the names the string is built from (`string_sites` and `marker_x(string)`: the string's
middle point's x); and still `STRING_SITE`, `SPAWN_HEIGHT_M`, `WALL_THICKNESS_M`,
`PLATFORM_OVERRUN_M`, `string_offset("legs")`, `PIT_DROP_M`, `tug_layout`'s two starts,
`manifest.termination` (summaries only), the tug's `[course]`, `[command]`, `[start]`, `[bout]`,
`[rating]` and the reference duck's bytes. From Plan G Task 2's commit until Plan H Task 2 the
challenges' parity tests are red, by design.

A retune of `[command]`, `[bout]` or `[rating]` by Plan B is, in one sitting: a commit on the arena `versus`
branch (`arena/events/tug-of-war.toml`, its two Python suite calls green), the challenges'
constants, and both repos' parity tests green; C and D read the toml.

microduck_rl (Plan B's Task 13): `publish --enter` says a tug entry as
`[publish] entered on tug-of-war: a 12.3 cm rating → <page url>` (it reads the submit answer's
`score` and `metric`; metric `mean_ground_cm`).

## Plan C — names

```python
# arena/manifest.py
@dataclass(frozen=True)
class CupRules:
    first: date            # cup #1's premiere day (local date in `timezone`)
    premiere: time         # local wall-clock time of every premiere
    timezone: str          # IANA, "Europe/Paris"
    close_before_h: float
    min_entrants: int
# Manifest gains cup: CupRules | None = None; [cup] required on a versus event, refused elsewhere.
# tug-of-war.toml: [cup] first = "2026-10-30"  premiere = "18:00"  timezone = "Europe/Paris"
#                  close_before_h = 2.0  min_entrants = 4     (the owner sets `first` at release)
```

```python
# arena/cup.py — new, pure (no I/O, no clock)
@dataclass(frozen=True)
class Entrant:
    user: str
    run_id: str
    policy_name: str
    livery: str
    rating: float          # in cm (the tug's mean_ground_cm)
    model_sha256: str
    source: dict          # RunRecord.source: where the policy is fetched from
    name: str             # the duck's on-air name in this cup, set once by entrants_at: policy_name, or
                          # f"{policy_name} (@{user})" when another entrant of the cup has the same
                          # policy_name (exact match). view() and to_dict() carry it; draw.json stores it

@dataclass(frozen=True)
class MatchRecord:
    match_id: str
    index: int            # position in playing order
    round: str            # "group" | "round of 16" | "quarter-final" | "semi-final" | "final" | "round of 2n"
    group: str | None     # "A", "B", … on a group match
    a: int
    b: int                # entrant indices
    bouts: tuple[BoutResult, ...]
    wins: tuple[int, int]
    winner: int           # entrant index
    decided_by: str

@dataclass(frozen=True)
class Cup:
    event_id: str
    number: int
    close_at: str         # ISO "…Z"
    premiere_at: str      # the scheduled premiere, ISO "…Z"
    secret: str           # 32 hex chars, drawn at close
    entrants: tuple[Entrant, ...]
    groups: tuple[tuple[int, ...], ...]     # () when skipped
    skipped: bool = False                   # fewer than min_entrants
    matches: tuple[MatchRecord, ...] = ()   # group rounds, then the knockout, in playing order
    order: dict | None = None               # {"starts_at": ISO, "segments": [...]}, once fixed

def match_id(event_id: str, number: int, index: int) -> str   # f"{event_id}-{number:04d}-{index:03d}"
def is_match_id(clip_id: str) -> bool                         # a run id never contains "-"
def cup_times(rules: CupRules, number: int) -> tuple[datetime, datetime]   # (close_at, premiere_at), aware UTC
def closed_cups(rules: CupRules, now: datetime) -> int        # cups whose close_at <= now
def group_count(entrants: int) -> int                         # largest power of two G >= 1 with entrants // G >= 3
def draw_groups(entrants: Sequence[Entrant], secret: str) -> list[list[int]]
#   pots of G by rating (desc, ties by user); each pot shuffled by random.Random(secret + pot index);
#   pot p's i-th entrant goes to group i
def group_fixtures(group: Sequence[int]) -> list[tuple[int, int]]   # circle-method round robin, rounds in order
def group_table(group: Sequence[int], matches: Sequence[MatchRecord], ratings: Sequence[float]) -> list[int]
#   matches won, then bouts won minus lost, then head-to-head, then rating, then draw order
def first_knockout(tables: Sequence[Sequence[int]]) -> list[tuple[int, int]]
#   G = 1: (1st, 2nd) is the final; G = 2: A1–B2, B1–A2 are the semi-finals; else, groups paired
#   (A,B), (C,D)…, the bracket's two halves: A1–B2, C1–D2, E1–F2, G1–H2, then B1–A2, D1–C2, F1–E2,
#   H1–G2 (winners paired in order each round): group-mates cannot meet before the final
def round_name(matches_in_round: int) -> str
def cup_view(cup: Cup, now: datetime) -> dict    # what is public at `now` (see Secrecy)
def airs_at(cup: Cup, match_id: str) -> datetime | None      # starts_at + its match segment's at_ms
def revealed_at(cup: Cup, match_id: str) -> datetime | None  # airs_at + its duration_ms: its clip has finished airing
PREFETCH = timedelta(seconds=30)   # a match's clip and its call are served from airs_at - PREFETCH;
                                   # a desk segment from revealed_at(its `after` match) - PREFETCH
# Plan C's other names: iso, parse_iso, parse_match_id, duck(entrant) ("<policy name> (@<user>)"),
# match_billing (A billed vs B billed), match_title (stage · its billing),
# match_label (the stage alone, no duck: "Group C", "Quarter-final 2", "Final"), reached, ends_at,
# cup_state(cup, now) -> str, GROUP_NAMES; Entrant.view/to_dict/from_dict; Cup.draw_json,
# Cup.matches_json, Cup.from_json
```

Secrecy (`cup_view`): before `order.starts_at` (or with no order): number, times, state, entrants
ranked by rating — no groups, no matches, no secret. From `starts_at`: groups and fixtures; each
match's result, bouts and its effect on the tables and the bracket only from its reveal
(`revealed_at`: the moment its clip has finished airing); the champion and the `secret` only from
the final's reveal. Its clip media and its call come `PREFETCH` before it airs, and a desk segment
`PREFETCH` before the reveal it may mention (Plan D), so the live can buffer them; nothing else is
early. Tests pin cup #1 to 2026-10-30 themselves (the owner sets the shipped `first` at release).
States: `"open"` (before close), `"drawn"` (closed, not ready),
`"ready"` (order fixed, before the start), `"airing"`, `"aired"`, `"skipped"`.

Store (Plan C), dataset layout `cups/{event_id}/{number:04d}/`: `draw.json` (everything but
`matches` and `order`; written first, so a restart recomputes the same cup from its secret),
`matches.json`, `bouts/{match_id}-{k}.npz` (`trace.encode`; `HubStore` leaves them out of its snapshot
and `cup_file` fetches one when it is read), `order.json`, and Plan D's `show.json`.

```python
# Store protocol, LocalStore, HubStore
def put_cup_files(self, event_id: str, number: int, files: dict[str, bytes]) -> None  # one commit; refuses a name that exists
def cup_file(self, event_id: str, number: int, name: str) -> bytes | None
def cup_numbers(self, event_id: str) -> list[int]
```

```python
# arena/cupworker.py — new
def entrants_at(records, withdrawn: frozenset[str], close_at: datetime, runner_version: int = RUNNER_VERSION) -> list[Entrant]
#   each user's latest run submitted at or before close_at, not withdrawn, on runner_version;
#   sets each entrant's on-air `name` (two entrants with one policy_name air under their handles)
def compute_matches(manifest: Manifest, cup: Cup, load: Callable[[Entrant], object]) -> tuple[Cup, dict[str, bytes]]
#   plays every match (groups, then each knockout round from the last), returns the cup with
#   `matches` and the bout trace files
def running_order(cup: Cup, clips: Mapping[str, float], starts_at: datetime, show: dict | None = None) -> dict
#   clips: match_id -> its landscape clip's seconds; Plan C ignores `show`, Plan D fills it
def load_cup(store, event_id: str, number: int) -> Cup | None
def all_cups(store) -> list[Cup]                       # every event with a [cup], each cup in number order
def load_entrant(store, entrant: Entrant) -> Policy    # from the Hub at its revision, or the store's copy
class CupWorker:
    def __init__(self, store, clips, *, events, load, now=lambda: datetime.now(UTC), log=print,
                 show: Callable[[Cup, dict], dict] | None = None): ...
    # show(cup, partial) writes the show (Plan D), filling `partial` as it goes, resumed next tick
    def tick(self) -> None    # close → draw.json → matches → owe clips → (D: write the show) → fix the order
    # the draw waits DRAW_GRACE (60 s) past the close, entries still those stamped at or before it
    def start(self) -> None   # daemon thread "arena-cups", tick every 30 s
    def stop(self) -> None
```

The worker fixes the order only when every match clip is ready (and, from Plan D, the show is
written: it is written once every match clip is ready), with `starts_at = max(premiere_at, now + 10
min)`; a cup never gets an order while the previous cup of the event has not finished airing.

Running order segments (times relative to `starts_at`, every length a multiple of 40 ms). The
grid is served 5 minutes ahead, so a shutter's `next` names the stage, never a duck; a match
segment carries no clip version (the live adds `clip` from `clip_state` when it lays the slot):

```json
{"kind": "shutter", "at_ms": 0, "duration_ms": 1600, "next": {"match_id": "…", "title": "Group C"}}
{"kind": "match", "at_ms": 1600, "duration_ms": 41240, "match_id": "…"}
```

Clips of matches: the clip id is the match id. `mark_clip_pending(match_id, "arena", event_id,
queued_at)`. `record_run(origin, clip_id, …)` opens `clip.html?match=<id>` when
`is_match_id(clip_id)`, and films it in the landscape layout only. `ClipJobs` never gives up on a match id (`JOB_TRIES` is for runs): a match job
that ends with nothing written fails its clip at once, and the cup worker launches a failed match clip
again every `CLIP_RETRY`.
`ArenaConfig.reveal_all` (set by `arena clip`, never on the Space) lets the job's loopback app read
unrevealed matches. A match clip's `clip.json` layout `timing` carries
`bouts: [{"k", "tape_start_s", "tape_end_s", "hold_end_s"}]` (where each bout's timed trace sits in the
mp4, and where the 6 s hold on its last pose, `BOUT_HOLD_S` in `app/src/clip/match.js`, ends).

API (Plan C, `arena/web/routes_cups.py`, `now()` read per request, patched by tests):
- `GET /api/events/{id}/cups` → `{"next": {"number", "close_at", "premiere_at", "entrants": [...]}, "cups": [{"number", "premiere_at", "starts_at", "state", "champion"}]}`
- `GET /api/events/{id}/cups/{number}` → `{"event", "open", "min_entrants", **cup_view(cup, now)}`
- `GET /api/matches/{match_id}` → the match once revealed (404 before): `{match_id, event, cup, round, group, title, a, b, bouts, wins, winner, decided_by, clip}` (`a`/`b` are `Entrant.view()`, `winner` `"a"`/`"b"`)
- `GET /api/matches/{match_id}/bouts/{k}/trace`, `…/settle` (float32, `X-Duck-Count: 2`) — 404 before the reveal.
- `GET /api/matches/{match_id}/bouts/{k}/string` (the string's wire, see Plan A; Plan G Task 5) — 404 before the reveal.
- `GET /api/matches/{match_id}/clip/{name}` (a clip file) — 404 before `airs_at − PREFETCH`. No route says where a
  match's clip stands: the match page reads `clip` off the match, the live off its slot.

Live (Plan C): `pool(store, now)` (`now` required: the programme and the commentary stock pass it)
adds the matches of every cup that has finished airing, until the event's next cup starts; a match
entry (`Entry.title` set: the cup's title and `match_label`, `Entry.billing` its `match_billing`) is
announced by `{"match_id", "title", "billing"}`, plays its match clip and gets no
booth broadcast, and `CommentaryStock` skips every `is_match_id` entry. `shows(store, now) ->
list[Show]` gives every cup not skipped that has not finished airing (`Show(premiere_ms, starts_ms,
ends_ms, slots, standby)`; `starts_ms` and `ends_ms` are None while it has no order).
`Programme(source, now_ms, book, cups=...)` lays a cup's segments at their absolute times; the cycle
before it ends with a `standby` slot that fills to `starts_at`, from the premiere at the latest:
`{"kind": "standby", "at_ms", "duration_ms", "cup": {"title"}}`. Past its premiere a cup with no
order yet is "starting soon": standby slots of `LATE_STANDBY_MS` (60 s) carrying `"late": true`,
whose card gives no time, until the order lands (at least `ORDER_LEAD` ahead, beyond the grid).
A match segment is served as `{"kind": "replay", …, "run_id": <match id>, "clip", "media": "match"}`;
`clip` is None while its clip is not ready (deleted to be rendered again): the screens hold the
shutter's panel over it.

Points: `receipts(…, cups: Sequence[Cup] = (), now)`; acts `cup_champion` 250, `cup_final` 150,
`cup_semi` 100, counted from the final's reveal; `source_id` = the deciding match id.
`GET /api/players/{user}` adds `cups: [{event_id, event_title, number, starts_at, reached}]`
(`reached`: `"champion"`, `"final"`, a round name, or `"group"`), each cup from its final's reveal, newest first.

```js
// app/src/router.js: #/c/<event>/<number> -> {view: "cup", eventId, number}; #/m/<matchId> -> {view: "match", matchId}
export function cupHref(eventId, number); export function matchHref(matchId)
// app/src/api.js
export function getCups(eventId); export function getCup(eventId, number); export function getMatch(matchId)
export function getBoutTrace(matchId, k); export function getBoutSettle(matchId, k); export function getBoutString(matchId, k)   // the last: Promise<{settle: Float32Array, trace: Float32Array}>
export function matchClipUrl(matchId, name, version)
// app/src/bouts.js
export function boutLane(match, k, traces, settles, string)   // {tug: "bout", ducks: [west, east], string: {trace, settle?}}, each duck {trace, settle, livery, name} (the entrant's on-air name), a/b placed by bouts[k].a_side
// app/src/replay.js (Plan G Task 6): leadIn gains a `width` parameter (TRACE_WIDTH for the ducks, STRING_WIDTH for the string)
// app/src/cast.js: replayLane(event, cast, traces, lane, string)
// app/src/clip/match.js: matchPlan(bouts), boutAt(plan, i), scoreAt(plan, match, i), matchWords(match)
//   ({title, line, players, outro, by}: the REC line's players by handle, the winner by its policy's name over `by`);
//   BOUT_HOLD_S = 6: each bout's last pose holds this long, its result on the bug, before the next bout or the outro
// app/src/format.js: countdown(ms); app/src/cup.js: cupPage, renderCup, cupCorner(eventId, cups, nowMs)
// app/src/live/standby.js: createStandby(stage)
// app/src/live/channel.js
export const PREFETCH_MS = 25_000   // a match slot (and, from Plan D, any slot) is prepared from 25 s
                                    // before it starts: inside the server's 30 s PREFETCH, 5 s for a screen's clock
```

## Plan D — names

```python
# arena/moments.py — new
LEAD_M = 0.02      # the marker must be this far past the centre line to change the lead
EDGE_M = 0.08      # a trunk this close to its pit edge is "at the edge"
GROUND_M = 0.10    # the marker this far on one side of the centre line is ground won by that side
SLIP_DEG = 35.0    # a trunk tilting past this has slipped

@dataclass(frozen=True)
class Moment:
    at_s: float          # seconds into the bout's timed trace
    kind: str            # "start" | "lead" | "ground" | "edge" | "slip" | "pit" | "time"
    side: str | None     # "west" | "east"

def moments(trace: np.ndarray, string: np.ndarray, course: Tug) -> list[Moment]   # the marker is the string's middle point
#   "time" only when nobody went into the pit
```

```python
# arena/commentary/cup.py — new
def cup_facts(cup: Cup, before: int, history: Sequence[Cup], manifest: Manifest) -> list[Fact]
#   what is true before match index `before` airs; never anything later (no spoilers); a duck of
#   this cup is named "<policy name> (@<user>)" (for a duck whose policy name another entrant has,
#   that is its on-air `name`: the handle never shows twice), a player across cups "@<user>"
def screen_view(cup: Cup, before: int, manifest: Manifest) -> dict    # the desk screen's view, stored as a desk segment's `screen`
#   {"title", "stage", "groups": [{"name", "rows": [{"name", "won", "played"}]}],
#    "knockout": [{"round", "matches": [{"a": name | None, "b": name | None, "winner": "a" | "b" | None, "next": bool}]}],
#    "next": {"a", "b", "group", "round"} | None, "champion": name | None}      (a group's rows "@<user>",
#    every other duck billed: `duck(entrant)`)
# arena/commentary/show.py — new
def show_outline(cup: Cup) -> list[dict]
#   [{"id": "opening", "kind": "opening", "after": -1},
#    {"id": "intro-<match_id>", "kind": "intro", "match_id", "after": i - 1},
#    {"id": "recap-<group round>", "kind": "recap", "after": i}, {"id": "ceremony", …}, {"id": "close", …}]
def write_show(cup: Cup, *, manifest, history, lore, provider, model, tab, rng,
               profiles: Mapping[str, Fact], footage: Mapping[str, dict], done: dict | None = None) -> dict
#   footage[match_id] = {"duration_ms", "bouts": [{"k", "tape_start_s", "tape_end_s", "hold_end_s", "seconds", "moments": [Moment]}]}
#   returns, filling `done` in place as it goes (a run cut off resumes from it):
#   {"desk": {id: {"kind", "after", "dialogue": {"turns", "brief"}, "plan", "screen"}},
#    "calls": {match_id: {"lines": [{"at_ms", "speaker", "text"}], "plan"}}}
#   a bout's last line also has "by_ms": its bout's hold_end_s (the clip holds the bout's end until then)
#   one LLM call per desk segment and one per bout (the play-by-play); call lines name ducks by their on-air `name`
# PlanTab gains prepare_call(call: dict) -> dict  (window.planCall in plan.html)
```

Running order with the show (`running_order(…, show=…)`): an `opening` desk segment first; per
match: its `intro` desk segment, Plan C's `shutter` (naming the stage only), the `match` segment
with `"call": true`; after the last match of each group round a `shutter` with `"next": null` and
its `recap`; after the final a `shutter` with `"next": null`, the `ceremony`, the `close`. Desk
segment: `{"kind": "desk", "at_ms", "duration_ms", "segment": "<id>", "after": i}`.

Live API (Plan D): `GET /api/live/show/{event_id}/{number}/{segment_id}` → `{dialogue, plan,
screen}`, served from `revealed_at(matches[after]) − PREFETCH` (the opening: from `starts_at −
PREFETCH`); `GET /api/live/call/{match_id}` → `{lines, plan}`, served from `airs_at(match) −
PREFETCH`; 404 before, and for anything the show does not hold; both of a cup's event only, and
served whole under `reveal_all`. Slots:
`{"kind": "desk", …, "show": {"event", "number", "segment"}}`; a match replay slot carries
`"call": true`.

```js
// app/src/live/score.js
export function prepareCall({ id, lines, duration_ms })   // a plan whose captions start at each line's at_ms;
                                                          // a line with by_ms starts early enough to end by it
export function singCaption(plan, caption, sing, out)     // replaces synthesize: one caption's notes, mono 48 kHz, into `out`
// app/src/live/voice.js: start(plan, offsetMs) sings one mono AudioBuffer per caption still to come, each
//   SING_AHEAD_MS (2 s) before it plays, all started on the context's clock from one instant (memory held = the
//   speech, not the plan's length); stop() stops them all and sings none still to come
// app/src/api.js
export function getShow(eventId, number, segment)   // {dialogue, plan, screen}, null on a 404; never cached
export function getCall(matchId)                    // {lines, plan}, null on a 404; never cached
// No desk.js (Ruling F): app/src/live/interlude.js plays `booth` and `desk` slots on the one booth; a desk
//   slot's file is getShow(show.event, show.number, show.segment), handed to booth.prepare(file, null)
// app/src/live/call.js — new: createCall(stage, { replay, audio }), the replay segment, plus for a slot with
//   `call` its getCall voiced and captioned from the offset the screen joins at
export const DUCKED = 10 ** (-10 / 20)        // the clip's own sound while a call line is voiced (−10 dB)
export function clipGain(plan, offsetMs)      // DUCKED inside a caption of the call's plan, else 1
// app/src/live/replay.js: volume(gain) sets every clip's volume
// app/src/live.js: segments { replay: call, booth: interlude, desk: interlude, standby }
// app/src/live/screen.js — new
export function drawCupScreen(canvas, view)   // groups by handle, then the bracket, next match highlighted, ducks billed, a cut keeping the handle
// app/src/live/set.js: booth({ screen }) stands the cup screen (the canvas as a texture) ready, hidden, at the
//   pegboard's place; standScreen(set, shown) stands it in place of the pegboard, or the pegboard back
// app/src/live/booth.js: one booth on the live page (Ruling F): createBooth(canvas) owns a SCREEN_PX canvas;
//   prepare(commentary, posterUrl | null) draws commentary.screen (a desk segment's view) and stands it, a
//   commentary without one stands the pegboard back; a poster is loaded only when given one
```
