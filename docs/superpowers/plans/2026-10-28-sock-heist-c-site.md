# Sock Heist C — The Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the event page, the run page, the workshop's replay and the race clip, every lane of a Sock Heist replay plays one seed under a giant microduck that turns its head on that seed's timetable with a deep quack; a caught duck collapses under its OUT plate with the fall sound; the first duck across dives into the socks; the clip runs at 1× until every lane is decided.

**Architecture:** The page draws only what Plan A serves: each seed's timetable in the event summary and each lane's `X-Caught-Frame`; it never draws a random number. `lights.js` turns a timetable into the head's turn (`lightAt`) and a lane into the frame it is out (`outAt`, `laneOut`) or the first crossing (`firstAcross`). `giant.js` builds the giant from the racers' own rig (`kinematics.json` and the `microduck.glb` meshes, as every racer is built) at 4.5×, seats it in Plan B's nest, lays the instanced socks, and poses the head and the socks as pure functions of the replay clock. `heist-sound.js` lists every cue once (`heistCues`) for the page's live player and the clip's `giant` source. #3's caller, lamps, strip and time-lapse go, with their tests.

**Tech Stack:** vanilla JS ES modules, three.js 0.169, Web Audio, vitest (jsdom and node); headless Chrome through puppeteer for local shots; one HF Job (t4-small) for the clip measure.

**Spec:** `docs/superpowers/specs/2026-10-27-sock-heist-design.md`, on `docs/superpowers/specs/2026-10-21-red-light-green-light-design.md` (§5 the site). **Contract:** `docs/superpowers/plans/2026-10-28-sock-heist-interfaces.md` (Front-end). **Plan B:** `docs/superpowers/plans/2026-10-28-sock-heist-b-blender.md` (the GLBs this plan loads).

## Global Constraints

- The contract's rules: English only; unsigned commits in the repository's style (plain sentences, no prefix, no assistant signature); `/usr/bin/git`; no dead code; nothing pushed, published, uploaded or launched as an HF Job without the owner's yes.
- **Scope guard.** Every new line runs behind `event.lights`. An event without lights fetches the same URLs (no `?seed=`), loads no venue, builds no giant, plays no heist sound and plans its clip on the author's frames, exactly as today.
- **Shorthands**, written out in full in every call: **WT** `/Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist`; **VITEST** `cd WT/app && npx vitest run`; **BUILD** `cd WT/app && npm run build`; **GIT** `/usr/bin/git -C WT`; **ARENA** `WT/.venv/bin/arena`; **SCRATCH** the executing session's scratchpad (absolute path). The hook refuses globs, shell variables and heredocs in commands: put scripts in SCRATCH files and run them.
- Tests in the foreground. Known failures, not regressions: 4 in `app/src/brightness.test.js`.
- **Clips are deterministic.** The head and the socks are pure functions of the replay clock; every spread (sock layout, flight) is drawn from a fixed integer hash of the sock's index, never `Math.random` or the wall clock.
- **Clip cost is vertices.** The giant is drawn as its skin (`attachMeshes(..., { skin: true })`: 106 537 triangles, half a racer's 198 412); the nest ≤ 6 000 triangles; one `InstancedMesh` per sock model (≤ 400 each).
- **The rig, not a GLB node.** `microduck.glb` is a flat bank of 38 untransformed meshes with no hierarchy: there is no head node in it. The site assembles a duck from `kinematics.json` (`buildRigTree` + `attachMeshes`), and its head turns at the rig's `head_yaw` joint (body `yaw_roll_motion`, range ±2.967 rad). Measured on the assembled rig at STAND: a positive `head_yaw` turns the face to −z; at −2.967 the lens points down −x and 9 mm to +z.
- **Pinned values** (`app/src/giant.js` unless said): `GIANT_SCALE = 4.5`; `GIANT_BEHIND_M = 1.7` (the giant's and the nest's centre past the finish line, on the lanes' centre line; C4 may raise it so the approved nest clears the sock field); the head turns to `head_yaw`'s own lower limit, read from the kinematics (−2.967 rad, 170°, round by +z, the chase camera's side); livery `classic`. `SOCK_FIELD = [0.15, 0.95]` (metres past the line); `SOCKS_PER_M = 7` (per metre across the lanes); `DIVE_REACH_M = 0.8`; a flying sock: lift 2.8–4.2 m/s, spread 0.4–1.2 m/s, 1 or 2 turns, yaw spin −3 to 3 rad/s, gravity 9.81; `FLOOR_MARGIN_M = 0.3`. `app/src/heist-sound.js`: `GIANT_RATE`, `GIANT_CALL` (provisional 0.45 and 0 until the owner picks, C5). Gains: the clip's `GAINS.quack = 1`, `GAINS.fall` 0.45 as today; the page's output 0.6 (the stage voice's), the quack at 1 and the fall at 0.45 under it.
- **Order.** C1 needs Plan A's API (`?seed=`, `X-Caught-Frame`, `served` timetables, the workshop's `caught_frame`). C2 → C3 → C4 → C5 → C6 → C7 → C8. C4 Step 1 waits for the owner's yes on Plan B's renders; C5 and C6 each wait once on the owner; C8's job waits for the owner's yes. Plan A's `git mv` of the guide turns `guides.test.js` red until C7 Step 5 (see the report).

## Review Focus

1. **A lane fetched on another seed than the replay's**: the event page's leader changes on a repaint (withdrawn, a filter's re-read), and a trace cached for the old seed is reused. C1's `race.lights.test.js`.
2. **A clip lane's caught frame counted from the top of its lead-in**: its OUT plate and its fall land a settle (~0.5 s) early. C2's `laneOut` test.
3. **A caught duck whose collapse carries it over the line** taken for a finisher: no OUT plate, and a false dive. C2's `outAt` test and C4's `firstAcross` test.
4. **A clip whose tape runs on past the author's lane** (the author crossed first, a rival is slower): the crowd reads past the author's trace (NaN). C6's `clipScore` test.
5. **The page muted, hushed, or its audio context suspended**: the giant must not quack over a muted Arena or the run page's own clip, and must start on the first gesture. C5's `createHeistSound` tests.

(Also tested in their tasks: two ducks crossing on one frame both dive, C4; every lane out of time gives a tape at the limit, no fall, no dive, C4–C6; a lane caught on its first watched step, C5.)

## Shared recipes

- **R1, a scratch store** (once, after Plan A; C4, C6 and C8 reuse it). Score into `SCRATCH/store` with ARENA, `ARENA score <onnx> --event sock-heist-6m --store SCRATCH/store --user <name>`: `arena/assets/policies/BEST_alpha_walking.onnx` as `walker`; a zero-action policy as `statue` (an ONNX built by a SCRATCH script with `onnx.helper`, the walker's input and output names, 14 zeros for any input: it stands on its line until the limit); `arena/assets/policies/tug-reference-t20-500.onnx` as `puller`; the public sprint-2m board leader's policy (fetched read-only from the Space's `/api/events/sprint-2m/leaderboard`) as `sprinter`; Plan D's reference as `trained` once it exists. The walker's run must have a lane out of time and, on its trace seed, one caught lane among the three ranked under it; if no lane is caught, score more public sprint or hill board policies until one is.
- **R2, a local Arena.** BUILD, then in the background `env ARENA_FRONTEND=WT/app/dist ARENA_COMMENTARY=0 ARENA_CLIPS=0 ARENA serve --store SCRATCH/store --port 8001` (absolute paths; confirm with `ps -o command -p` on the port's listener that it is this worktree's code).
- **R3, clip shots.** A puppeteer script in SCRATCH (`require("/opt/homebrew/lib/node_modules/@modelcontextprotocol/server-puppeteer/node_modules/puppeteer")`, `args: ["--no-sandbox"]`) opens `http://127.0.0.1:8001/clip.html?run=<id>&layout=landscape` (then `vertical`), sets the viewport with CDP `Emulation.setDeviceMetricsOverride` at 1920×1080 (vertical 1080×1920), `deviceScaleFactor: 1`, waits for `window.clip.ready`, calls `window.clip.draw(i)` for the frames asked, and screenshots each to `SCRATCH/shots/<layout>-<i>.png`. Frame indices come from `window.clip.plan` (`intro`, `settle`, `stride`, `tapeEnd`). Close the browser in a `finally`.

---

### Task C1: The replay on one seed

**Files:**
- Modify: `app/src/api.js`, `app/src/cast.js`, `app/src/race.js`, `app/src/run.js`, `app/src/clip/main.js`, `app/src/workshop/job.js`
- Test: `app/src/api.test.js`, `app/src/cast.test.js`, `app/src/workshop/job.test.js`; Create: `app/src/race.lights.test.js`

**Interfaces:**
- Consumes (Plan A): `GET /api/runs/{id}/trace?seed=N`, `/settle?seed=N`, `X-Caught-Frame`; a board row's and a run's `trace_seed`; the workshop body's `trace_seed` and `caught_frame`.
- Produces: `getTrace(runId, seed?)`, `getSettle(runId, seed?)`; the array `frames()` returns carries `caught: number | null`. `cast.js` `replaySeed(event, row) -> number | undefined`: `row.trace_seed` on a lights event, `undefined` otherwise or without a row. `replayLane` on a lights event returns `{ ...lane, trace: traces[0], caught: traces.caught }`. Every lights lane handed to `setLanes` carries `traceSeed` (the replay's seed) and `caught` (a frame of its timed trace, as served).

- [ ] **Step 1: Write the failing tests.**

```js
// api.test.js
describe("a lights run's seeds", () => {
  it("asks for one seed's trace and settle when given one, and for the stored ones as today when not", async () => {
    respondWith({ bytes: new Float32Array(2).buffer });
    await getTrace("R1", 3);
    expect(globalThis.fetch).toHaveBeenLastCalledWith("/api/runs/R1/trace?seed=3");
    await getSettle("R1", 3);
    expect(globalThis.fetch).toHaveBeenLastCalledWith("/api/runs/R1/settle?seed=3");
    await getTrace("R1");
    expect(globalThis.fetch).toHaveBeenLastCalledWith("/api/runs/R1/trace");
  });
  it("carries the frame a seed's duck was caught on, and null when it was not", async () => {
    respondWith({ bytes: new Float32Array(2).buffer, headers: { "X-Caught-Frame": "412" } });
    expect((await getTrace("R1", 3)).caught).toBe(412);
    respondWith({ bytes: new Float32Array(2).buffer });
    expect((await getTrace("R1", 3)).caught).toBeNull();
  });
});

// cast.test.js
const HEIST = { id: "sock-heist-6m", course: "lane", rig: "legs", lights: { turn_s: 0.4, tolerance_m: 0.03, timetables: {} } };
describe("replaySeed", () => {
  it("plays every lane of a lights replay on its row's trace seed, and on no seed elsewhere", () => {
    expect(replaySeed(HEIST, { trace_seed: 3 })).toBe(3);
    expect(replaySeed(HEIST, undefined)).toBeUndefined(); // an empty board
    expect(replaySeed(SPRINT, { trace_seed: 3 })).toBeUndefined();
  });
});
it("carries a lights lane's caught frame beside its trace", () => { // in describe("replayLane")
  const trace = frames(2, 0);
  expect(replayLane(HEIST, [{ policy: "self" }], Object.assign([trace], { caught: 41 }), { ...lane, traceSeed: 3 }))
    .toEqual({ ...lane, traceSeed: 3, trace, caught: 41 });
});
```

  - `race.lights.test.js` mocks `./api.js` (`getLeaderboard`, `getTrace` resolving `Object.assign([new Float32Array(21)], { caught: null })`, `getMe` → null, `getEvents` → [], `getCups`, `getString`, `withdrawRun`) and `./viewer.js` (`createViewer` → a stub with `setLanes: vi.fn()`, `setBrightness`, `follow`, `sweep`), as `workshop/job.test.js` does; its event is race.test.js's sprint fixture with `id: "sock-heist-6m"`, `length_m: 6` and `lights`; rows carry `run_id`, `rank`, `trace_seed`, `user`, `score`, `seeds_finished: 5` and what `buildRows` needs.

```js
it("plays every lane on the leader's trace seed, and on the new leader's once the board is read again", async () => {
  api.getLeaderboard
    .mockResolvedValueOnce({ rows: [row("A", 1, 2), row("B", 2, 4), row("C", 3, 1)] })
    .mockResolvedValue({ rows: [row("B", 1, 4), row("C", 2, 1), row("D", 3, 5)] }); // A withdrawn
  await renderRace(root, { event: HEIST, state: {} });
  expect(api.getTrace.mock.calls).toEqual([["A", 2], ["B", 2], ["C", 2]]);
  expect(viewer.setLanes.mock.lastCall[0].map((lane) => lane.traceSeed)).toEqual([2, 2, 2]);
  root.querySelector('.modes button[data-mode="all"]').click(); // a repaint re-reads the board
  await vi.waitFor(() => expect(api.getTrace).toHaveBeenCalledWith("C", 4));
  expect(api.getTrace.mock.calls.slice(3)).toEqual([["B", 4], ["C", 4]]);
});
it("fetches a sprint's lanes as it always has, each its own stored trace", async () => {
  // the same rows on SPRINT: every call is [id, undefined]
});

// workshop/job.test.js
it("replays a sock heist checkpoint on its trace seed, caught where it was caught", async () => {
  api.getCheckpoint.mockResolvedValueOnce({ checkpoint: 500, score: 30, ducks: 1, traces: [new Float32Array(21)],
    trace_seed: 4, caught_frame: 120, cast: [{ policy: "self", rig: null, start: null, sound: null }] });
  // mounted as the sprint's test is, on HEIST
  expect(viewer.setLanes).toHaveBeenLastCalledWith([expect.objectContaining({ traceSeed: 4, caught: 120 })], HEIST);
});
// and in "opens a race on its best checkpoint and replays it":
expect(viewer.setLanes.mock.lastCall[0][0]).not.toHaveProperty("caught");
```

- [ ] **Step 2:** `cd WT/app && npx vitest run src/api.test.js src/cast.test.js src/race.lights.test.js src/workshop/job.test.js` → FAIL (`replaySeed` not exported, no `?seed=`, no `caught`).
- [ ] **Step 3: Implement.**
  - `api.js`: `frames(path)` sets `caught` on the array it returns (`Number(header)`, or null); `getTrace`/`getSettle` append `?seed=${seed}` only when `seed != null`.
  - `cast.js`: `replaySeed` per Interfaces; `replayLane`'s lane branch adds `caught` on a lights event only.
  - `race.js`: `rows()` keeps `replayed = replaySeed(event, rows[0])` (the server's first row is the leader); `traceFor(runId, seed)` caches per run and seed and calls `getTrace(runId, seed)`; each lane's `traceSeed` is `replayed ?? seeds.get(runId)`.
  - `run.js`: `traceFor(id)` calls `getTrace(id, replaySeed(run.event, run))`; a lane's `traceSeed` is `replaySeed(run.event, run) ?? byId.get(id).trace_seed`.
  - `clip/main.js`: `seed = replaySeed(run.event, run)` for every lane's `getTrace` and `getSettle`; a race lane gains `traceSeed: run.trace_seed, caught: traces[i].caught` on a lights event.
  - `workshop/job.js` `play`: the race lane gains `traceSeed: body.trace_seed, caught: body.caught_frame` on a lights event.
- [ ] **Step 4:** Step 2's command → PASS; VITEST (only the 4 brightness failures); BUILD.
- [ ] **Step 5: Commit.** `GIT add app/src/api.js app/src/api.test.js app/src/cast.js app/src/cast.test.js app/src/race.js app/src/race.lights.test.js app/src/run.js app/src/clip/main.js app/src/workshop/job.js app/src/workshop/job.test.js`, then `GIT commit -m "A sock heist replay plays every lane on one seed, the leader's on the event page and the run's own on its page, its clip and the workshop, and each lane knows the frame its duck was caught on; every other event fetches its stored trace as before"`.

---

### Task C2: The light from the served timetable, the OUT plate from the catch; #3's caller goes

The caller reads #3's single schedule, which Plan A no longer serves: it goes here, with its test, so that this commit is green. The giant takes its place in C3.

**Files:**
- Rewrite: `app/src/lights.js`, `app/src/lights.test.js`
- Delete: `app/src/caller.js`, `app/src/caller.test.js`
- Modify: `app/src/viewer.js` (imports; `caller`, `callerLead`, `buildCaller`; the OUT plate; comments that name the caller)

**Interfaces:**
- Consumes: a lane `{ trace, caught, lead }` (C1; `lead` is a clip's settle frames); `event.lights.timetables` (Plan A).
- Produces in `lights.js`: `lightAt(timetable, turnS, seconds) -> { red, facing, watching }`; `outAt(trace, length, caught) -> number | null`; `laneOut(lane, length) -> number | null`: `outAt(lane.trace, length, lane.caught == null ? null : lane.caught + (lane.lead ?? 0))`; `timetableOf(event, seed) -> [[onset_s, length_s], ...]`: that seed's served timetable, `[]` when it serves none.

- [ ] **Step 1: Write the failing test** (`lights.test.js`, `// @vitest-environment node`; `walk` and `expectLight` as today's file, `expectLight` taking the timetable and `turnS`).

```js
const T = [[0.6, 1.6], [4.2, 2.0], [7.8, 1.4]];
const TURN = 0.4;

describe("lightAt", () => {
  it("is green with the head away before the start and through the first green", () => {
    for (const s of [-1, NaN, 0, 0.3, 0.58]) expectLight(T, TURN, s, { red: false, facing: 0, watching: false });
  });
  it("is red on exactly the timetable's steps", () => {
    const red = (s) => lightAt(T, TURN, s).red;
    expect([0.58, 0.6, 2.18, 2.2, 4.18, 4.2, 6.18, 6.2, 7.8, 9.18, 9.2].map(red))
      .toEqual([false, true, true, false, false, true, true, false, true, true, false]);
  });
  it("turns the head round over turn_s, and only then watches", () => {
    expectLight(T, TURN, 0.6, { red: true, facing: 0, watching: false });
    expectLight(T, TURN, 0.8, { red: true, facing: 0.5, watching: false });
    expect(lightAt(T, TURN, 0.98).facing).toBeGreaterThan(0.95);
    expect(lightAt(T, TURN, 0.98).watching).toBe(false);
    expectLight(T, TURN, 1.0, { red: true, facing: 1, watching: true });
    expectLight(T, TURN, 2.18, { red: true, facing: 1, watching: true });
  });
  it("turns the head back away as the red ends, never watching", () => {
    expectLight(T, TURN, 2.2, { red: false, facing: 1, watching: false });
    expectLight(T, TURN, 2.4, { red: false, facing: 0.5, watching: false });
    expectLight(T, TURN, 2.6, { red: false, facing: 0, watching: false });
  });
  it("keeps the head away after the last red, and on a timetable with none", () => {
    expectLight(T, TURN, 20, { red: false, facing: 0, watching: false });
    expectLight([], TURN, 3, { red: false, facing: 0, watching: false });
  });
  it("reads the served seconds on the runner's whole steps", () => {
    const served = [[0.84, 1.62]]; // steps 42 to 122
    expect([0.82, 0.84, 2.44, 2.46].map((s) => lightAt(served, TURN, s).red)).toEqual([false, true, true, false]);
    expect([1.22, 1.24].map((s) => lightAt(served, TURN, s).watching)).toEqual([false, true]);
  });
  it("faces the lanes at once when the head takes no time to turn", () => {
    expectLight(T, 0, 0.6, { red: true, facing: 1, watching: true });
    expectLight(T, 0, 2.2, { red: false, facing: 0, watching: false });
  });
});

describe("outAt", () => {
  it("leaves a duck that reached the line in, wherever it set off", () => {
    expect(outAt(walk(0.01, 3, 6.02), 6, null)).toBeNull();
    expect(outAt(walk(-0.02, 3, 5.99), 6, null)).toBeNull();
  });
  it("puts a duck that fell or ran out of time out from its last frame", () => {
    expect(outAt(walk(0, 2, 3.9), 6, null)).toBe(2);
  });
  it("puts a caught duck out from the frame it was caught on, not where its collapse ends", () => {
    expect(outAt(walk(0, 1, 2, 2.1, 2.15), 6, 2)).toBe(2);
  });
  it("keeps a caught duck out when its collapse carries it over the line", () => {
    expect(outAt(walk(0, 5.9, 5.97, 6.1), 6, 1)).toBe(1);
  });
  it("has nothing to say about an empty trace", () => {
    expect(outAt(new Float32Array(0), 6, null)).toBeNull();
  });
});

describe("laneOut", () => {
  it("counts a lane's caught frame after the settle it leads in with", () => {
    const trace = walk(0, 0, 0, 1, 2, 2.1); // two frames of settle, then the race
    expect(laneOut({ trace, caught: 2, lead: 2 }, 6)).toBe(4);
    expect(laneOut({ trace, caught: 2 }, 6)).toBe(2);
    expect(laneOut({ trace, caught: null, lead: 2 }, 6)).toBe(5);
  });
});

describe("timetableOf", () => {
  it("is the served timetable of the replay's seed, and none for a seed it does not serve", () => {
    const event = { lights: { turn_s: 0.4, tolerance_m: 0.03, timetables: { 3: T } } };
    expect(timetableOf(event, 3)).toBe(T);
    expect(timetableOf(event, undefined)).toEqual([]);
  });
});
```

- [ ] **Step 2:** `cd WT/app && npx vitest run src/lights.test.js` → FAIL.
- [ ] **Step 3: Implement** `lights.js` per Interfaces. Steps as the runner counts them: `onset = Math.round(onset_s / CTRL_DT)`, `length = Math.round(length_s / CTRL_DT)`, `turn = Math.round(turnS / CTRL_DT)`; the step shown at `seconds` is `Math.floor(seconds / CTRL_DT + 1e-6)`; facing is `smooth((clock − onset) / turn)` through a red and `1 − smooth((clock − (onset + length)) / turn)` after it, clamped to [0, 1]; watching from `onset + turn` to the red's end. `outAt` keeps today's `REACHED_M` (5 cm) rule for an uncaught trace. The header comment says: the timetable is one seed's, served by the Arena (`arena/lights.py served`); the page never draws one.
  - `viewer.js`: drop `buildCaller`, `caller`, `callerLead` and their lines in `setLanes`, `clearScene`, `draw`; `out = event?.lights && entry.trace ? laneOut(entry, courseLength) : null`; reword the comments that name the caller or red light, green light ("a duck that is out says so": a caught duck lies collapsed, out from the frame it was caught).
  - `GIT rm app/src/caller.js app/src/caller.test.js`.
- [ ] **Step 4:** Step 2's command → PASS; VITEST; BUILD; `/usr/bin/grep -rn "caller" WT/app/src/viewer.js WT/app/src/lights.js` prints nothing.
- [ ] **Step 5: Commit.** `GIT add app/src/lights.js app/src/lights.test.js app/src/viewer.js`, then `GIT commit -m "The light is read from one seed's served timetable on the runner's whole steps, and a caught duck is out from the frame it was caught on, after its lane's lead-in, even when its collapse carries it over the line; the Reachy Mini caller, its lamps and its strip go, since they read the one schedule the event no longer has"`.

---

### Task C3: The giant

Until Plan B's nest is approved (C4), the giant stands alone past the line; C4 seats it in the nest and gives `buildGiant` the venue.

**Files:**
- Create: `app/src/giant.js`, `app/src/giant.test.js`
- Modify: `app/src/viewer.js` (`setLanes`, `clearScene`, `draw`)

**Interfaces:**
- Consumes: `lightAt`, `timetableOf` (C2); the racers' rig assets `{ kinematics, geometries }` (`viewer.js` `loadAssets("legs")`, `rigs.legs`); `rig.js` `buildRigTree`, `attachMeshes`, `setJoint`, `STAND`, `TRUNK_HEIGHT`, `JOINT_NAMES`.
- Produces: `GIANT_SCALE = 4.5`, `GIANT_BEHIND_M = 1.7`; `buildGiant(model, length) -> { group, pose(facing), dispose() }` (C4 widens it to the contract's `buildGiant(model, venue, length, edge)`). `group.name = "giant"`; its rig's placer at `(length + GIANT_BEHIND_M, 0, 0)`, unrotated (facing +x, away from the lanes), scaled `GIANT_SCALE`; STAND pose, trunk at `TRUNK_HEIGHT`; `pose(facing)` sets `head_yaw` to `facing × range[0]` of that joint and nothing else.

- [ ] **Step 1: Write the failing test** (`giant.test.js`, `// @vitest-environment node`; the GLB parsed as `caller.test.js` parsed Reachy's, `model = { kinematics, geometries: creasedGeometries(scene) }`; `lensFromPivot(giant)` = the world centre of mesh `lens.stl` minus the world position of group `yaw_roll_motion`).

```js
const LENGTH = 6;
const duck = (giant) => giant.group.getObjectByName("duck_placer"); // the rig, not what C4 lays round it
it("sits centred behind the line, its feet on the floor, 4.5 times a racer's height", () => {
  const giant = buildGiant(model, LENGTH);
  const box = new Box3().setFromObject(duck(giant));
  expect(box.min.x).toBeGreaterThan(LENGTH + 1);
  expect((box.min.z + box.max.z) / 2).toBeCloseTo(0, 1);
  expect(box.min.y).toBeCloseTo(0, 2);
  expect(box.max.y - box.min.y).toBeCloseTo(4.5 * 0.274, 2); // a racer's skin at STAND is 0.274 m tall
});
it("has its back to the lanes on green, and on red turns its head only, about half a turn over its shoulder by the camera's side", () => {
  const giant = buildGiant(model, LENGTH);
  const trunk = () => giant.group.getObjectByName("trunk_base").matrixWorld.clone();
  giant.pose(0);
  const away = lensFromPivot(giant);
  const body = trunk();
  giant.pose(1);
  const round = lensFromPivot(giant);
  expect(away.x).toBeGreaterThan(0);
  expect(round.x).toBeLessThan(0);
  expect(round.z).toBeGreaterThan(0);
  const angle = Math.acos(away.setY(0).normalize().dot(round.setY(0).normalize()));
  expect(angle).toBeGreaterThan(2.8); // head_yaw's own limit, 170°
  expect(trunk().equals(body)).toBe(true);
});
it("draws only the duck's skin, casting and catching shadows", () => {
  const giant = buildGiant(model, LENGTH);
  expect(duck(giant).getObjectByName("speaker.stl")).toBeUndefined();
  giant.group.traverse((node) => { if (node.isMesh) expect([node.castShadow, node.receiveShadow]).toEqual([true, true]); });
});
it("frees its own materials and leaves the racers' shared geometries whole", () => {
  // spies on each mesh under duck(giant): geometry.dispose not called, material.dispose called
});
```

- [ ] **Step 2:** `cd WT/app && npx vitest run src/giant.test.js` → FAIL.
- [ ] **Step 3: Implement** `giant.js` per Interfaces (`attachMeshes(rig, kinematics, geometries, { livery: "classic", skin: true })`); `dispose` removes the group and disposes the materials it made, never a geometry. In `viewer.js`, on a race whose event has `lights`: `giant = buildGiant(rigs.legs, courseLength)`, added to the scene; `heistLead` (the former `callerLead`: the lanes' largest `lead` in seconds); `timetable = timetableOf(event, entries[0]?.traceSeed)`; `draw` poses `giant?.pose(lightAt(timetable, event.lights.turn_s, player.time - heistLead).facing)`; `clearScene` disposes it.
- [ ] **Step 4:** Step 2's command → PASS; VITEST; BUILD. With R1 and R2, open `http://127.0.0.1:8001/#/e/sock-heist-6m` in puppeteer at 1280×800, wait past the leader's first red (`timetables[seed][0][0] + 0.6` s of replay), screenshot to `SCRATCH/shots/c3-red.png` and look at it: the giant past the line, its head round at the lanes.
- [ ] **Step 5: Commit.** `GIT add app/src/giant.js app/src/giant.test.js app/src/viewer.js`, then `GIT commit -m "The giant: the racers' own microduck at four and a half times their size, past the line with its back to the lanes, turns its head over its shoulder towards them on red, to its neck's own limit, and back on green; nothing else of it moves"`.

---

### Task C4: The nest, the socks and the dive

**Files:**
- Modify: `app/src/giant.js`, `app/src/giant.test.js`, `app/src/lights.js`, `app/src/lights.test.js`, `app/src/course.js`, `app/src/course.test.js`, `app/src/viewer.js`, `app/src/race.js`, `app/src/run.js`, `app/src/clip/main.js`, `app/src/workshop/job.js`

**Interfaces:**
- Consumes: `app/public/venue/sock-nest.glb` (node and mesh `nest`, glTF Y up, origin at its floor centre, +X away from the lanes) and `socks.glb` (`sock_0` … `sock_{n-1}`, origin at the floor contact), Plan B; `laneOut` (C2).
- Produces in `giant.js`: `loadHeistVenue() -> Promise<{ nest: Mesh, socks: Mesh[] }>` (memoised; GLTFLoader on `/venue/sock-nest.glb` and `/venue/socks.glb`, socks in name order); `floorBeyond(venue) -> number`: how far past the finish line the ground runs, `GIANT_BEHIND_M + nest's max.x + FLOOR_MARGIN_M`; `laySocks(kinds, length, edge) -> [{ kind, x, z, yaw }]`; `diveAt(socks, divers, seconds) -> [{ x, y, z, yaw, pitch }]`, `divers` the point `[x, z]` in the scene where each lane that crossed first crossed the line, `seconds` since it crossed; `buildGiant(model, venue, length, edge) -> { group, pose(facing), dive(divers, seconds), dispose() }`.
- Produces in `lights.js`: `firstAcross(lanes, length) -> { frame, lanes: number[] } | null`: among lanes whose `laneOut` is null and whose trace is not empty, the fewest frames (`frame` = that last frame's index) and every lane that crossed on it.
- Produces in `course.js`: `buildCourse(event, lanes, stripes, beyond = OVERRUN)`: the ground runs from `-OVERRUN` to `length + beyond`; lines and stripes stay where they are. `viewer.js` `attachCourse` passes it through.
- Produces in `viewer.js`: `createViewer(canvas, { ..., lights = false })` loads the venue alongside the rigs when `lights`; `race.js`, `run.js`, `clip/main.js` (run) and `workshop/job.js` pass `lights: Boolean(event.lights)`.

- [ ] **Step 1: STOP until the owner has approved Plan B's renders.** `GIT log --oneline -- app/public/venue` shows Plan B Task 3's commit ("approved by the owner on <date>"), and both GLBs are there. If not, report and wait.
- [ ] **Step 2: Write the failing tests** (`giant.test.js` loads both venue GLBs from `public/venue/` as it loads the racer, into `venue = { nest, socks }` as `loadHeistVenue` returns it; `EDGE = 1.9`, four lanes at 0.95; C3's tests now call `buildGiant(model, venue, LENGTH, EDGE)`; one more spies on the venue's geometries and materials and finds none disposed by `dispose()`).

```js
it("seats the giant in its nest, its feet in the weave, the sock field clear and the ground past it", () => {
  const giant = buildGiant(model, venue, LENGTH, EDGE);
  const nest = new Box3().setFromObject(giant.group.getObjectByName("nest"));
  for (const ankle of ["ankle_left", "ankle_right"]) {
    expect(nest.containsPoint(giant.group.getObjectByName(ankle).getWorldPosition(new Vector3()))).toBe(true);
  }
  expect(nest.min.x).toBeGreaterThan(LENGTH + SOCK_FIELD[1]);
  expect(LENGTH + floorBeyond(venue) - nest.max.x).toBeCloseTo(FLOOR_MARGIN_M);
});
it("lays the socks between the line and the nest across every lane, the same every time", () => {
  const socks = laySocks(3, LENGTH, EDGE);
  expect(socks).toEqual(laySocks(3, LENGTH, EDGE));
  expect(socks).toHaveLength(Math.round(SOCKS_PER_M * 2 * EDGE));
  for (const { x, z } of socks) {
    expect(x).toBeGreaterThanOrEqual(LENGTH + SOCK_FIELD[0]);
    expect(x).toBeLessThanOrEqual(LENGTH + SOCK_FIELD[1]);
    expect(Math.abs(z)).toBeLessThanOrEqual(EDGE);
  }
  expect(new Set(socks.map((s) => s.kind))).toEqual(new Set([0, 1, 2]));
  for (const lane of [-1.425, -0.475, 0.475, 1.425]) {
    expect(socks.some((s) => Math.hypot(s.x - LENGTH, s.z - lane) <= DIVE_REACH_M)).toBe(true);
  }
});
it("draws each sock model once, instanced, as many as are laid", () => {
  const giant = buildGiant(model, venue, LENGTH, EDGE);
  const instanced = [];
  giant.group.traverse((node) => { if (node.isInstancedMesh) instanced.push(node.count); });
  expect(instanced).toHaveLength(venue.socks.length);
  expect(instanced.reduce((a, b) => a + b)).toBe(laySocks(venue.socks.length, LENGTH, EDGE).length);
});
describe("diveAt", () => {
  const socks = laySocks(3, 6, 1.9);
  const near = (s, z) => Math.hypot(s.x - 6, s.z - z) <= DIVE_REACH_M;
  const rest = socks.map(({ x, z, yaw }) => ({ x, y: 0, z, yaw, pitch: 0 }));
  it("leaves every sock where it was laid before the first duck crosses, and when none crossed", () => {
    expect(diveAt(socks, [[6, 0.475]], -0.1)).toEqual(rest);
    expect(diveAt(socks, [], 0.3)).toEqual(rest);
  });
  it("throws up the socks near the diver's lane, and only those", () => {
    const flown = diveAt(socks, [[6, 0.475]], 0.2);
    socks.forEach((s, k) => expect(flown[k].y > 0).toBe(near(s, 0.475)));
  });
  it("throws up the socks near both lanes when two ducks cross on the same frame", () => {
    const flown = diveAt(socks, [[6, -0.475], [6, 1.425]], 0.2);
    socks.forEach((s, k) => expect(flown[k].y > 0).toBe(near(s, -0.475) || near(s, 1.425)));
  });
  it("drops every sock back flat on the floor, where it stays", () => {
    const landed = diveAt(socks, [[6, 0.475]], 2);
    expect(landed.every((p) => p.y === 0 && p.pitch === 0)).toBe(true);
    expect(diveAt(socks, [[6, 0.475]], 5)).toEqual(landed);
  });
  it("is the same at the same moment, frame after frame", () => {
    expect(diveAt(socks, [[6, 0.475]], 0.31)).toEqual(diveAt(socks, [[6, 0.475]], 0.31));
  });
});

// lights.test.js
describe("firstAcross", () => {
  const lane = (trace, caught = null) => ({ trace, caught });
  it("is the frame the first duck crossed on, and its lane", () => {
    expect(firstAcross([lane(walk(0, 3, 6.1)), lane(walk(0, 6.05)), lane(walk(0, 1))], 6)).toEqual({ frame: 1, lanes: [1] });
  });
  it("names every lane that crossed on that frame", () => {
    expect(firstAcross([lane(walk(0, 6.1)), lane(walk(0, 3, 6.1)), lane(walk(0, 6.02))], 6)).toEqual({ frame: 1, lanes: [0, 2] });
  });
  it("is none when no duck crossed, a caught duck collapsing over the line included", () => {
    expect(firstAcross([lane(walk(0, 2, 3)), lane(walk(0, 5.9, 6.1), 1)], 6)).toBeNull();
  });
});

// course.test.js
it("runs the ground further past the finish line when asked, the lines and stripes where they were", () => {
  const course = buildCourse({ length_m: 6, width_m: 0.8 }, 4, [], 2.5);
  const ground = course.getObjectByName("ground");
  expect(ground.geometry.parameters.width).toBeCloseTo(0.4 + 6 + 2.5);
  expect(ground.position.x).toBeCloseTo((6 + 2.5 - 0.4) / 2);
  expect(course.getObjectByName("finish").position.x).toBe(6);
  expect(course.getObjectByName("lane-stripe-0").geometry.parameters.width).toBeCloseTo(6 + 0.8);
});
```

- [ ] **Step 3:** `cd WT/app && npx vitest run src/giant.test.js src/lights.test.js src/course.test.js` → FAIL.
- [ ] **Step 4: Implement.**
  - `laySocks`: `count = Math.round(SOCKS_PER_M * 2 * edge)`; sock k's z stratified across `[-edge, edge]` (its k-th slice, jittered inside it), its x anywhere in `SOCK_FIELD` past `length`, its yaw any, its kind `k % kinds`, every draw from the fixed hash of k.
  - `diveAt`: a sock within `DIVE_REACH_M` of any diver's point flies from its nearest one; the rest lie as laid. Its lift, spread, turns and yaw spin are drawn from the hash of k within the pinned ranges; `flight = 2 · lift / 9.81`; at `t = min(seconds, flight)` it stands at its rest x, z moved `spread · t` along the floor away from the diver's point (+x if it lies on it), `y = lift·t − 9.81·t²/2`, `pitch = 2π · turns · t / flight` while `t < flight` and 0 once landed, `yaw = rest + spin · t`.
  - `buildGiant(model, venue, length, edge)`: C3's giant, a clone of `venue.nest` at the giant's floor point (shared geometry and material), one `InstancedMesh` per sock model holding its laid socks, every mesh casting and catching shadows; `dive(divers, seconds)` writes `diveAt`'s poses into the instance matrices (`Euler(pitch, yaw, 0)`) and flags them; `dispose` frees what it made, never the venue's geometries or materials.
  - `viewer.js` on a lights race: `beyond = floorBeyond(heistVenue)` into `attachCourse`; `buildGym(courseLength + beyond - OVERRUN, …)` so the hall's end wall stands past the nest (the stadium already sizes itself from the ground); `buildGiant(rigs.legs, heistVenue, courseLength, Math.max(1, laneCount) * spacing / 2)`; once the lanes are built, `crossed = firstAcross(lanes, courseLength)` gives `divers = crossed.lanes.map((i) => [courseLength, lanes[i].rig.placer.position.z])` and `divedAt = crossed.frame * CTRL_DT` on the player's clock; `draw` calls `giant?.dive(divers, player.time - divedAt)` (none crossed: `[]`).
  - The four `createViewer` callers pass `lights`.
- [ ] **Step 5:** Step 3's command → PASS; VITEST; BUILD. With R1–R3, shoot the walker's clip at its first tape frame and 0.25 s after its first crossing (the finished lane with the fewest frames, read off the traces the clip fetches), and look: the nest whole and reading as socks, the socks across every lane, the stands and the hall's end wall beyond the nest, socks in the air at the winner's lane.
- [ ] **Step 6: Commit.** `GIT add app/src/giant.js app/src/giant.test.js app/src/lights.js app/src/lights.test.js app/src/course.js app/src/course.test.js app/src/viewer.js app/src/race.js app/src/run.js app/src/clip/main.js app/src/workshop/job.js`, then `GIT commit -m "The giant sits in its nest of socks with loose socks over the floor before it, the ground and the hall running on past the nest, and when the first duck crosses the line the socks near its lane fly up and fall back, the same on every frame of a clip; only a sock heist loads the venue"`.

---

### Task C5: The sounds

**Files:**
- Create: `app/src/heist-sound.js`, `app/src/heist-sound.test.js`
- Modify: `app/src/clip/score.js`, `app/src/clip/score.test.js`, `app/src/clip/soundtrack.js`, `app/src/clip/soundtrack.test.js`, `app/src/clip/main.js`, `app/src/viewer.js`

**Interfaces:**
- Consumes: `outAt`, `laneOut`, `timetableOf` (C2); `loadCalls` (`live/voice.js`), `DUCK_SEED` (`duck-voice.js`); `/sound/microduck-fall.wav`.
- Produces in `heist-sound.js`: `GIANT_RATE`, `GIANT_CALL`; `giantQuack(calls) -> Float32Array` (`calls.chirp(DUCK_SEED, GIANT_CALL, {})`); `heistCues(timetable, lanes, length, limitS) -> [{ at, kind: "quack" | "fall", lane }]` in race-clock order (a quack at each onset, `lane: null`; a fall at `caught × CTRL_DT`, or at a fallen lane's last race frame; none for a lane that crossed, nor one whose race frames reach `Math.round(limitS / CTRL_DT)`; `lanes` as `{ trace, caught, lead }`, race frames after `lead`); `createHeistSound(loadCalls, { makeContext, muted, load }) -> { set(cues), follow(seconds), dispose() }`, `load(file)` resolving an ArrayBuffer (default: `fetch("/sound/" + file)`).
- Produces in `clip/score.js`: `clipScore({ run, plan, trace, ducks, lanes })`, `lanes` every lane's timed trace and `caught` on the replay's seed; source `giant` → cues `{ at, quack: true, rate: GIANT_RATE, gain: GAINS.quack }` and `{ at, file: "microduck-fall.wav", gain: GAINS.fall }`, each at `start + plan.settle × CTRL_DT + cue.at`.
- Produces in `soundtrack.js`: a `quack` cue renders `giantQuack(synth)` with `playbackRate.value = cue.rate`; the synth loads when any cue is a call, a song or a quack.

- [ ] **Step 1: Write the failing tests.** `heist-sound.test.js` copies `stage-voice.test.js`'s fake context, adds `decodeAudioData` (resolving `{ length: 57600 }`) and a `playbackRate: { value: 1 }` on each source, whose `start` logs `["start", buffer.length, offset, playbackRate.value]`; `calls.chirp` returns 4 800 samples; `soundWith(cues, { muted, state })` builds the sound with that context, `load: async (file) => { loaded.push(file); return new ArrayBuffer(8); }`, calls `set(cues)` and awaits a tick; `walk(frames, to)` is a trace of that many frames from x 0 to `to` (`score.test.js` gets the same helper).

```js
const T = [[0.6, 1.6], [4.2, 2.0]];
const at2 = (cues) => cues.map(({ at, kind, lane }) => [Number(at.toFixed(2)), kind, lane]);
describe("heistCues", () => {
  it("quacks where each red begins and falls where a duck goes out, in race order", () => {
    const lanes = [
      { trace: walk(300, 6.05), caught: null }, // crossed
      { trace: walk(150, 2.0), caught: 50 },    // caught on the first red's first watched step, then collapsed
      { trace: walk(120, 1.5), caught: null },  // fell
    ];
    expect(at2(heistCues(T, lanes, 6, 60))).toEqual([[0.6, "quack", null], [1, "fall", 1], [2.38, "fall", 2], [4.2, "quack", null]]);
  });
  it("never falls for a duck out of time, every lane out of time included", () => {
    expect(heistCues([], [{ trace: walk(3000, 2), caught: null }, { trace: walk(3000, 0.01), caught: null }], 6, 60)).toEqual([]);
  });
  it("counts a clip lane's frames after its lead-in", () => {
    expect(at2(heistCues([], [{ trace: walk(145, 1.5), caught: null, lead: 25 }], 6, 60))).toEqual([[2.38, "fall", 0]]);
  });
});
describe("createHeistSound", () => {
  it("quacks as the clock crosses a red's onset, once, slowed to the giant's rate", async () => {
    const { sound, log } = await soundWith([{ at: 0.6, kind: "quack", lane: null }]);
    [0.58, 0.6, 0.62].forEach((s) => sound.follow(s));
    expect(log.filter(([what]) => what === "start")).toEqual([["start", 4800, 0, GIANT_RATE]]);
  });
  it("plays the fall's recording where a duck goes out", async () => {
    const { sound, log, loaded } = await soundWith([{ at: 1, kind: "fall", lane: 1 }]);
    expect(loaded).toEqual(["microduck-fall.wav"]);
    [0.98, 1].forEach((s) => sound.follow(s));
    expect(log[0]).toEqual(["start", 57600, 0, 1]);
  });
  it("is silent while the Arena is muted or the page hushed", async () => {
    const { sound, log } = await soundWith([{ at: 0.6, kind: "quack", lane: null }], { muted: () => true });
    [0.6, 0.62].forEach((s) => sound.follow(s));
    expect(log).toEqual([]);
  });
  it("waits for a gesture while the browser keeps its context suspended, then plays from where the clock is", async () => {
    const { sound, log, context } = await soundWith([{ at: 0.6, kind: "quack", lane: null }], { state: "suspended" });
    sound.follow(0.6);
    expect(log).toEqual([]);
    window.dispatchEvent(new Event("pointerdown"));
    expect(log).toEqual([["resume"]]);
    context.changeState("running");
    sound.follow(0.64);
    expect(log.at(-1)).toEqual(["start", 4800, expect.closeTo(0.04 * GIANT_RATE, 5), GIANT_RATE]);
  });
  it("starts again from where the clock lands when the replay jumps back", async () => {
    const { sound, log } = await soundWith([{ at: 0.6, kind: "quack", lane: null }]);
    [0.6, 3, 0.65].forEach((s) => sound.follow(s));
    expect(log.filter(([what]) => what === "start").map(([, , offset]) => offset)).toEqual([0, expect.closeTo(0.05 * GIANT_RATE, 5)]);
  });
  it("makes no context and loads nothing for a replay without cues", async () => {
    // set([]): makeContext, loadCalls and load are never called
  });
});

// clip/score.test.js
it("quacks at each red and falls where each duck goes out, on the race's clock after the settle", () => {
  const HEIST = { id: "sock-heist-6m", length_m: 6, time_limit_s: 60,
    lights: { turn_s: 0.4, tolerance_m: 0.03, timetables: { 3: [[0.6, 1.6]] } }, clip: { sounds: ["giant"], tape_max_s: 60 } };
  const plan = clipPlan(300, 60, 26); // the race clock starts at 3 + 26 × 0.02 = 3.52 s of tape
  const lanes = [{ trace: walk(300, 6.05), caught: null }, { trace: walk(150, 2), caught: 50 }];
  const { cues } = clipScore({ run: { run_id: "R5", event: HEIST, seeds_finished: 5, trace_seed: 3 }, plan, trace: walk(326, 6.05), ducks: [], lanes });
  expect(cues.map((c) => [Number(c.at.toFixed(2)), c.quack ?? c.file, c.rate])).toEqual([[4.12, true, GIANT_RATE], [4.52, "microduck-fall.wav", undefined]]);
});

// clip/soundtrack.test.js (the fake source gains playbackRate and logs it as `rate`)
it("renders the giant's quack from the synth's chirp, slowed to its rate", async () => {
  const log = [];
  const calls = { chirp: (seed, variant) => new Float32Array(480).fill(variant + 1), wheee: () => new Float32Array(1) };
  await renderSoundtrack({ crowd: null, cues: [{ at: 2, quack: true, rate: GIANT_RATE, gain: 1 }] }, 3, {
    Context: fakeContext(log), load: () => { throw new Error("a quack fetched a file"); }, calls: async () => calls });
  expect([log[0].at, log[0].rate]).toEqual([2, GIANT_RATE]);
  expect(log[0].buffer.data).toEqual(new Float32Array(480).fill(GIANT_CALL + 1));
});
```

- [ ] **Step 2:** `cd WT/app && npx vitest run src/heist-sound.test.js src/clip/score.test.js src/clip/soundtrack.test.js` → FAIL.
- [ ] **Step 3: Implement.** `createHeistSound` follows `stage-voice.js`: the context made and the fall decoded on the first `set` with cues, a gesture listener while suspended, a jump (`JUMP_S` 0.25) stops and restarts what the new time is inside; each cue its own part, playing while `at ≤ seconds < at + buffer duration / rate`, its offset into the buffer `(seconds − at) × rate`; output gain 0.6 through `limiter` and `ceiling`. `viewer.js`: `heist = manual ? null : createHeistSound(loadCalls, { muted: () => isMuted() || hushed() })`; `setLanes` sets `heistCues(timetable, lanes, courseLength, event.time_limit_s)` on a lights race and `[]` otherwise; `tick` calls `heist?.follow(player.playing ? player.time : null)` (a page's lanes never lead in); `dispose` disposes it. `clip/main.js` passes `lanes: traces.map((t) => ({ trace: t[0], caught: t.caught }))`. `score.js` `GAINS.quack = 1`; `SOURCES.giant` reads `timetableOf(run.event, run.trace_seed)`, `run.event.length_m`, `run.event.time_limit_s`.
- [ ] **Step 4:** Step 2's command → PASS; VITEST; BUILD.
- [ ] **Step 5: Tune the quack with the owner.** A Node script in SCRATCH loads `WT/app/public/sound/microduck-voice.wasm` through `loadCalls(fetcher)` (a fetcher answering `{ ok: true, arrayBuffer }` from the file) and writes `SCRATCH/giant-quacks.wav` (48 kHz, mono, 16-bit): the duck's own chirp at rate 1 first, then for each rate in 0.30, 0.40, 0.50, 0.60 and each variant in 0, 3, 6, 9 the chirp resampled linearly at that rate, 0.8 s apart. Send the owner its path and the order of the candidates; ask which rate and variant, and, on the local event page (R2), whether the quack sits right against the fall. **STOP until they answer.** Set `GIANT_RATE`, `GIANT_CALL` (and the quack's gain if they ask), re-run Step 2's command.
- [ ] **Step 6: Commit.** `GIT add app/src/heist-sound.js app/src/heist-sound.test.js app/src/clip/score.js app/src/clip/score.test.js app/src/clip/soundtrack.js app/src/clip/soundtrack.test.js app/src/clip/main.js app/src/viewer.js`, then `GIT commit -m "The giant quacks, the duck's own chirp played far lower as the owner chose by ear, each time its head starts to turn, and a duck caught or fallen goes out with the microduck fall, on the page as in the clip; a muted Arena, the run page's playing clip and a context the browser holds suspended keep it quiet"`.

---

### Task C6: The clip to the slowest lane, at life speed

**Files:**
- Modify: `app/src/clip/plan.js`, `app/src/clip/plan.test.js`, `app/src/clip/score.js`, `app/src/clip/score.test.js`, `app/src/clip/main.js`, `arena/events/sock-heist-6m.toml` (`[clip.camera]` only: `back`, `height`, `side`, `target_height`, `hold`), and the Python test that pins those values if Plan A wrote one (`tests/test_lights.py`)

**Interfaces:**
- Produces: `clipPlan(frames, tapeMaxS, settle)`, `frames` the frames the tape must show (the author's, or on a lights event the longest lane's); the plan has no `speed`; `stride` is `STRIDE`.

- [ ] **Step 1: Write the failing tests** (delete `plays a time-lapse's tape…` from `plan.test.js` and `hears a time-lapse's progress…` from `score.test.js`).

```js
// plan.test.js
it("runs a lights clip's tape at life speed to its slowest lane, cut at the ceiling", () => {
  expect(clipPlan(3000, 60, 26)).toMatchObject({ stride: 2, steps: 3026, tape: 1513 }); // every lane out of time: the limit
  expect(clipPlan(3100, 60, 26)).toMatchObject({ steps: 3026 }); // a collapse past the limit is cut there
  expect(clipPlan(200, 12, 26)).not.toHaveProperty("speed");
});
// score.test.js
it("follows the author's progress through a tape that runs on past its lane, holding its last frame", () => {
  const plan = clipPlan(400, 60, 0); // a rival's 400 frames; the author's trace has 200
  const { crowd } = clipScore({ run: { run_id: "R6", event, seeds_finished: 5 }, plan, trace, ducks: [] });
  expect(crowd.progress.every((sample) => Number.isFinite(sample.value))).toBe(true);
  expect(crowd.progress.at(-1).second).toBeCloseTo(3 + 8);
  expect(crowd.progress.at(-1).value).toBeCloseTo(0.995);
});
```

- [ ] **Step 2:** `cd WT/app && npx vitest run src/clip/plan.test.js src/clip/score.test.js` → FAIL.
- [ ] **Step 3: Implement.** `plan.js` without `speed` (header comment: the tape at life speed); `score.js` `progress` samples every `PROGRESS_EVERY_S` of tape and reads the author's frame `Math.min(step, frameCount(trace) − 1)`; `main.js` passes `run.event.lights ? Math.max(...traces.map(([t]) => frameCount(t))) : frameCount(traces[0][0])`, and its clock loses the `×N`.
- [ ] **Step 4:** Step 2's command → PASS; VITEST; BUILD; `/usr/bin/grep -rn "speed\|lapse" WT/app/src/clip WT/app/src/viewer.js WT/app/src/viewer.test.js` prints only `app/src/clip/match.js:1` (a match's bouts "at speed").
- [ ] **Step 5: Retune `[clip.camera]` by shots.** R2 restarted on the new build; R3 on the walker's run, both layouts, at: the first tape frame (`plan.intro`); the leader's first red + 0.6 s; the caught lane's caught frame + 0.5 s and + 2.5 s; the first crossing + 0.25 s; the last tape frame; the outro's middle. Change only `back`, `height`, `side`, `target_height`, `hold` until: the first shot holds every lane and the giant whole, head to nest, in landscape, and the author's duck and the giant in vertical; the head is round on the red; the caught duck lies still under "name · OUT" by its catch + 2.5 s (if it still moves, report it for Plan A's `COLLAPSE_S`: it is not this plan's); the dive's socks are in the picture; the stamp lands on the author's lane. Update the pinned values in `tests/test_lights.py` if it pins them; `cd WT && uv run --frozen --extra dev pytest -q tests/test_lights.py` → PASS.
- [ ] **Step 6: Show the owner** the shots (paths under `SCRATCH/shots/`, one line each) and the camera values. **STOP until they say yes**; apply their notes by Step 5 again.
- [ ] **Step 7: Commit.** `GIT add app/src/clip/plan.js app/src/clip/plan.test.js app/src/clip/score.js app/src/clip/score.test.js app/src/clip/main.js arena/events/sock-heist-6m.toml` (and `tests/test_lights.py` if changed), then `GIT commit -m "A sock heist clip films the match at life speed until every lane is decided, from a first shot that holds every lane and the giant whole to a last one on the dive into the socks; the time-lapse goes, and the crowd holds the author's last frame once the tape runs on past it"`.

---

### Task C7: The names and the card

**Files:**
- Modify: `app/src/share.js`, `app/src/share.test.js`, `app/src/roundcard.js`, `app/src/roundcard.test.js`, `app/src/guides.test.js`
- Create: `app/public/cards/sock-heist-6m.webp`; Delete: `app/public/cards/red-light-green-light-15m.webp`

- [ ] **Step 1: Write the failing tests.**

```js
// share.test.js (replaces the caught line)
expect(postText(caught, { origin, network: "x" })).toContain("it got caught moving while the giant looked.");
// roundcard.test.js (the LIGHTS fixture becomes HEIST)
const HEIST = { ...SPRINT, id: "sock-heist-6m", title: "6 m Sock Heist", length_m: 6 };
it("names the heist in a word that holds one line, and its button sneaks in", () => {
  const card = roundCard(HEIST, [], { number: 6 });
  expect(card.querySelector(".round-card__title").textContent).toBe("Sock Heist");
  expect(card.querySelector(".round-card__cta").textContent).toBe("Sneak in!");
  expect(card.style.getPropertyValue("--c")).toBe("var(--magenta)");
  expect(cells(card)).toEqual(["6 m", "Flat", "Legs"]);
  expect(card.querySelector(".round-card__art img").getAttribute("src")).toBe("/cards/sock-heist-6m.webp");
});
// guides.test.js: "red-light-green-light-15m" becomes "sock-heist-6m" in the ids.
```

- [ ] **Step 2:** `cd WT/app && npx vitest run src/share.test.js src/roundcard.test.js src/guides.test.js` → FAIL.
- [ ] **Step 3: Implement.** `share.js`: `"it got caught moving while the giant looked"`, its comment for the giant. `roundcard.js` `CARDS`: `"sock-heist-6m": { accent: "var(--magenta)", cta: "Sneak in!", title: "Sock Heist" }`, the old key gone.
- [ ] **Step 4: The card.** Follow `event-card-illustration-recipe.md` (the owner's notes): from her sprint card, a little microduck tiptoeing with a striped sock in its beak, the giant microduck's head looking back over its shoulder from its nest of socks behind it; short prompts, Kontext to clean, the characters composited in PIL, her frame re-applied last; RGBA 720×667, WebP q93; scripts in SCRATCH, never in the repository. **Show the owner the card. STOP until they say yes** (they may hand their own illustration instead). Then `GIT rm app/public/cards/red-light-green-light-15m.webp`.
- [ ] **Step 5:** Step 2's command → PASS; VITEST; BUILD; `/usr/bin/grep -rniI "red light\|red-light\|green light" WT/app/src WT/app/index.html WT/app/clip.html WT/app/workshop.html WT/app/plan.html WT/app/public/ASSETS.md WT/app/public/sound/PROVENANCE.md` prints nothing, and `/usr/bin/grep -rn "caller" WT/app/src/viewer.js WT/app/src/lights.js WT/app/src/giant.js WT/app/src/heist-sound.js WT/app/src/clip/main.js WT/app/src/clip/score.js` prints nothing.
- [ ] **Step 6: Commit.** `GIT add app/src/share.js app/src/share.test.js app/src/roundcard.js app/src/roundcard.test.js app/src/guides.test.js app/public/cards/sock-heist-6m.webp`, then `GIT commit -m "Sock Heist by name on the site: its card, magenta, sneaks in under a little microduck carrying off a sock past the giant's turned head, a run caught moving says the giant saw it, and no red light, green light is left"`; `GIT lfs ls-files` lists `app/public/cards/sock-heist-6m.webp`.

---

### Task C8: The clip's cost, measured

**Files:** none in the repository; everything in SCRATCH.

- [ ] **Step 1: Local bench.** Two builds of the site: `after` = BUILD at HEAD; `before` = C3's commit's `app/` (`GIT archive --output SCRATCH/before.tar <C3 sha> app`, `tar -xf SCRATCH/before.tar -C SCRATCH/before`, `WT/app/node_modules` symlinked into `SCRATCH/before/app`, `npx vite build` there): the giant without its nest, its socks or the longer floor. The clip is R1's longest case: the walker's run, whose `statue` lane runs out of time (tape = the limit). By the memory's recipe (`clip-frame-cost-under-swiftshader.md`: one browser per build, SwiftShader, frames interleaved, CPU seconds of the browser's processes per frame), measure 40 frames of each, landscape. Write down CPU s/frame before and after, and the clip's frame count.
- [ ] **Step 2: Ask the owner** with Step 1's numbers: upload a bench tarball (the branch's `arena/` as `src/arena`, both dists, the scratch store) to a private dataset `Nico-robot/sock-heist-clip-bench`, and launch one HF Job on it. **STOP until they say yes.**
- [ ] **Step 3: The job.** `run_job` (or `hf jobs run`) on `hf.co/spaces/pollen-robotics/microduck-arena`, flavor `t4-small`, namespace `pollen-robotics`, timeout `60m` (to see past the clip jobs' 30), secret `HF_TOKEN` (the owner's token), env `ARENA_COMMENTARY=0`, `ARENA_CLIP_GPU=1`. Its command downloads and unpacks the bench to `/tmp/bench`, then for `after` then `before`: `env PYTHONPATH=/tmp/bench/src ARENA_FRONTEND=/tmp/bench/<build> arena clip <walker run id> --store /tmp/bench/store`, and prints each render's `clip.json` `timing` (draw and capture ms per frame, total wall) for both layouts. Follow it with `hf jobs logs` (it streams until the end).
- [ ] **Step 4: Report to the owner**: ms/frame before and after per layout, the longest clip's total wall against the clip jobs' `JOB_TIMEOUT` (`arena/clips.py`, 30 min). Passed when HEAD's job, both layouts and the soundtrack, takes at most 20 min and the venue costs at most 10 % more per frame. Otherwise give the numbers and the options (the time limit Plan A sets, a job timeout sized on a clip's frames as a match's is, a lighter nest or fewer socks), and change nothing. On the owner's yes, delete the bench dataset.
