# Sock Heist F — the playground, the camera on the giant, a quack per red — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sock Heist races in a school playground of its own at the microducks' scale, modelled in Blender. Its pages and its clip film it from behind the ducks with the giant in the picture, and every red quacks its own quack, drawn from the replayed seed.

**Architecture:** `scripts/sock_heist_venue.py` grows a playground: one more GLB, `playground.glb`, made of four nodes. `yard` is the ground. `left` (the building) and `right` (the fence) are the two sides, each built from the track's edge outwards and carrying the crowd's spots. `park` holds the trees. The site's new `playground.js` stands each side at the edge of the lanes it draws and seats stadium.js's animated `crowd` on the spots. The viewer puts the playground in the gym's place on a lights race, with no judges. The pages hand the viewer the event's `[clip.camera]`, so a page films the heist as its clip does. The field's camera leaves a trailing duck behind sooner on a heist (`HEIST_REACH`), so it reaches the dive. `heist-sound.js` draws each red's chirp variant and rate from the seed and the red's index with giant.js's integer hash.

**Tech Stack:** Blender 5.2.2 (`/opt/homebrew/bin/blender`, bpy, glTF exporter with `EXT_mesh_gpu_instancing`), three.js 0.169 (GLTFLoader, InstancedMesh), vanilla JS ES modules, Web Audio, vitest, pytest, puppeteer for shots, one HF Job (t4-small) for the cost.

**Spec:** `docs/superpowers/specs/2026-10-27-sock-heist-design.md`, section "Amendment, 2026-10-29: the playground, the page's camera, the giant's quacks" (f3507ed). **Contract:** `docs/superpowers/plans/2026-10-28-sock-heist-interfaces.md`, its "Amendment, 2026-10-29 (Plan F)" section. This plan replaces Plan C's C6b (camera) and C8 (clip cost).

## Global Constraints

- **Sock Heist alone.** Every new line runs behind `event.lights` (or `manifest.lights`). The sprint, the hill, the roller sprint, the stage and the tug look, sound and are filmed exactly as before. A sprint clip frame stays pixel-identical (Task 4 checks it).
- **WT** `/Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist`, branch `red-light-green-light`. **GIT** `/usr/bin/git -C WT` (the hook refuses plain `git` here). Python: `uv run --frozen …` from WT. Front-end: `cd WT/app && npx vitest run <files>`, `npm run build`. **SCRATCH**: the executing session's scratchpad (absolute path). The hook refuses globs, shell variables and heredocs in commands. Put scripts in SCRATCH files and run them.
- Tests in the foreground, never a background run waited on. Known failures, not regressions: 4 in `app/src/brightness.test.js`.
- English only in code, comments, docs, commit messages. Commits unsigned, one plain sentence in the repository's style, no prefix, no assistant signature.
- No dead code: what the heist no longer uses goes, its tests with it.
- Nothing pushed, no PR touched, no publication, no HF Job without the owner's yes. Never close PR #3.
- **Gates (STOP until the owner says yes):** the Blender renders (Task 3), the camera captures (Task 5), the HF Job (Task 6).
- **Determinism.** Everything random is drawn from a fixed seed. In Blender, a `random.Random` of its own. On the site, giant.js's `draw(k, n)` hash, never `Math.random` or the wall clock. The approved `sock-nest.glb` and `socks.glb` must rebuild byte-identical.
- **Scale.** A racer stands 0.27 m and the seated giant 0.930 m. No piece of the playground stands taller than 0.93 m.
- **Lanes.** The site draws lanes 0.85 m apart (`width_m` 0.8 plus the 0.05 m wall), and the lanes' edge is the course ground's half span: 1.7 m on four lanes, 0.425 m on one. The giant's centre is `GIANT_BEHIND_M` = 1.95 m past the 6 m finish line.
- **Axes.** glTF and three.js: +x down the track, +y up, +z the chase camera's side, which is the viewer's right. Blender is Z up, and the exporter's Y-up turn maps Blender +y to three.js −z. The left side (the building) is therefore built at Blender y > 0, and the right side (the fence) at Blender y < 0.
- **Recipes R1–R3** are at the top of Plan C (`2026-10-28-sock-heist-c-site.md`). The demo store (R1) already exists, so do not rebuild it: `/private/tmp/claude-501/-Users-nicolasrabault-Projects-HuggingFace-microduck-arena/67e38f06-738a-416e-a1fe-9ac25e562f3b/scratchpad/store`. Its reference run is `01M639ZYYS3QCZRCN9A9Q5`. The scratchpad next to it holds C6b's shot scripts (`c6b/`) and the quack WAV script (`giant-quacks.mjs`). Rendering a clip on this Mac: `ARENA_FRONTEND=WT/app/dist` and a `CHROME` wrapper with `--use-mock-keychain --password-store=basic` (the owner's notes, "Headless Chrome available locally").

## Review Focus

1. **Many lanes on the event page** (its board sheet puts any number on the stage): no spectator, building or fence may stand on a lane. Task 4's `playground.test.js` covers ten lanes.
2. **Another race changed by accident** (a shared function given a new default, the course's ground, the crowd's code): Task 4's pixel check of a sprint frame before and after.
3. **The approved nest and socks moved by the script's rebuild** (a shared `Random(0)` drawn once more, a render constant leaking into an export): Task 1 Step 5 checks `sock-nest.glb` and `socks.glb` byte-identical.
4. **A re-race or a page left and reopened** frees the playground it made and never the shared models (the playground GLB, the crowd's model). The next build would otherwise draw empty geometry. Task 4's dispose test.
5. **The same seed must quack the same on the page and in the clip, and two seeds must differ**: both go through `heistCues(…, seed)`. Task 2's tests.

---

### Task 1: The playground in Blender

**Files:**
- Modify: `scripts/sock_heist_venue.py`, `tests/test_venue_assets.py`
- Create (generated): `app/public/venue/playground.glb` (`app/public/venue/*.glb` is already an LFS rule)

**Interfaces:**
- Produces `app/public/venue/playground.glb`, in glTF axes and metres. Its origin is on the start line at the lanes' centre line. Its top-level nodes, each named:
  - `yard`: the ground, one vertex-coloured mesh with its top at y = −0.003, just under the site's course ground. It holds the concrete yard round the track and, past the nest, the park's grass, and covers at least x −4…14 m and z −10…10 m.
  - `left`: a node at the origin. It carries the school building and its crowd spots, built from z = 0 (the lanes' edge) towards −z.
  - `right`: the same towards +z, with the wooden fence and its crowd spots.
  - `park`: the trees on the grass behind the giant, and nothing within 0.3 m of the nest's footprint.
- Crowd spots are empties named `spot_<k>`, children of `left` or `right`. Each has a `translation` with y = 0 and a `rotation` about +y (the yaw of a duck that faces +x at yaw 0) that turns it towards the track.
- A model drawn many times (a tree, a fence panel) is one mesh instanced through `EXT_mesh_gpu_instancing`: linked duplicates, children of one empty, exported with `export_gpu_instances=True`.
- Materials and colour: vertex colours on the script's one plain material (`venue_material`), as the nest has.

- [ ] **Step 1: Write the failing tests** in `tests/test_venue_assets.py` (helpers `node(doc, name)`, `children(doc, name)`, `yaw(spot)` from its rotation quaternion, `drawn(doc)` counting every instance's triangles):

```python
PLAYGROUND = VENUE / "playground.glb"
GIANT_SEATED_M = 0.93  # the seated giant's height (scripts/sock_heist_venue.py prints it)

def test_the_playground_is_a_yard_two_sides_and_a_park():
    names = [n["name"] for n in gltf(PLAYGROUND)["nodes"] if n.get("name") in {"yard", "left", "right", "park"}]
    assert sorted(names) == ["left", "park", "right", "yard"]

def test_each_side_carries_a_crowd_beyond_the_track_edge_facing_it():
    doc = gltf(PLAYGROUND)
    for side, sign in (("left", -1), ("right", 1)):
        assert "translation" not in node(doc, side)  # the site stands it at the lanes' edge
        spots = [n for n in children(doc, side) if n["name"].startswith("spot_")]
        assert 90 <= len(spots) <= 130
        for spot in spots:
            x, y, z = spot["translation"]
            assert sign * z >= 0.08 and y == 0 and -0.3 <= x <= 7.2
            assert sign * -sin(yaw(spot)) < 0  # its +x turned towards the track
        xz = [(s["translation"][0], s["translation"][2]) for s in spots]
        assert min(dist(a, b) for a, b in combinations(xz, 2)) >= 0.16

def test_nothing_in_the_playground_stands_taller_than_the_seated_giant():
    doc = gltf(PLAYGROUND)
    assert max(bounds(doc, m["name"])[1][1] for m in doc["meshes"]) <= GIANT_SEATED_M

def test_the_playground_instances_its_trees_and_keeps_its_budget():
    doc = gltf(PLAYGROUND)
    assert "EXT_mesh_gpu_instancing" in doc["extensionsUsed"]
    assert sum(triangles(doc, m["name"]) for m in doc["meshes"]) <= 20000  # each model once
    assert drawn(doc) <= 40000  # every instance counted

# test_every_venue_model_is_vertex_coloured: add "playground.glb" to its list.
```

- [ ] **Step 2: Run them to see them fail.**
  `cd WT && uv run --frozen --extra dev pytest -q tests/test_venue_assets.py` → the new tests FAIL (no `playground.glb`), the old five PASS.

- [ ] **Step 3: Build the playground in the script.** Add `playground(material) -> dict[str, bpy.types.Object]`, which returns the four nodes. It draws from its own `random.Random(1)` and runs after the nest and the socks are exported, so their draws from `Random(0)` stay as they were. It exports to `<out>/playground.glb`, and prints each model's triangle count, the drawn total and the spot count per side. Pinned:
  - Copy each constant from the site with a comment naming its source: `LENGTH_M` 6.0 (the event file), `GIANT_BEHIND_M` 1.95 (giant.js). The render constants become the site's: `LANE_SPACING_M` 0.85, `LANES` at ±0.425 and ±1.275, `EDGE_M` 1.7. The nest and the socks do not depend on them.
  - **The crowd:** 100–120 spots a side in ragged rows with gaps, as along a street race. They sit from 0.1 to about 0.9 m out from the edge, along x from −0.2 m to the end of the sock field (6.95 m), at least 0.17 m apart. Each faces the track, turned at random by up to ±0.35 rad.
  - **The left side:** a one-storey school building at the microducks' scale, about 0.7 m tall. It stands behind the crowd, about 1.1 m out from the edge, and runs from about −1 m to 8 m along x. Its door fits a microduck (about 0.35 m tall), and it has windows and a roof. At most 4 000 triangles.
  - **The right side:** a wooden fence of upright planks, about 0.4 m tall, which is over a standing duck's head. It stands about 1.1 m out from the edge over the same x span. Panels are instanced, each at most 100 triangles.
  - **The park:** grass from about 1.2 m past the nest's far edge, about 30 trees of 2 or 3 low-poly models (each at most 300 triangles), 0.6 to 0.9 m tall, spread across z −8…8 m and x up to 14 m. A few may stand nearer the centre line behind the giant so that it sits against them, without any rising over its head.
  - **The colours:** concrete greys for the yard, a greener grass, brick or painted render for the building, warm wood for the fence. The palette is otherwise the builder's.
  - **Instances** may be turned and scaled down, never up, so a model's own height bounds every instance of it (the height test reads the models).
- [ ] **Step 4: The renders**, added to `render()`. The script lays the playground as the site will: `left` at Blender y = +`EDGE_M`, `right` at −`EDGE_M`, `yard` and `park` as exported, the four racers on `LANES`, and the giant at `GIANT_BEHIND_M`. On each spot sits a crowd duck. It is `racer()` built from `app/public/robot/microduck-crowd.glb` (the site's crowd model: pass the model's path to `part_meshes`) in the stadium's SIT pose (`app/src/stadium.js`: STAND with joints 2, 3, 4 = −1.3, 1.5, −0.2 and 11, 12, 13 = 1.3, −1.5, 0.2 in `JOINT_NAMES` order, the trunk 0.055 m over the floor), painted the crowd's shell colours in turn (`app/src/palette.js` `SHELLS`). The views are Eevee at 1600 × 900:
  - `page.png`: the race camera at the start, behind the lanes, as the viewer's chase stands with `[clip.camera]` (back 2.1, height 0.86, side 0.1, target 0.4, fov 42, backed off to fit four lanes);
  - `three-quarter.png`: the whole playground from above, behind and to the left of the start;
  - `crowd.png`: low and close on the right edge's crowd, with the fence behind it;
  - `park.png`: from past the nest, looking back down the track over the giant, with the building and the fence in view.

  The existing four views (`chase`, `three-quarter` renamed `nest-three-quarter`, `close`, `turned`) stay.
- [ ] **Step 5: Build, and check that the approved models did not move.**
  `cd WT && /opt/homebrew/bin/blender -b -P scripts/sock_heist_venue.py -- app/public/venue --render SCRATCH/playground-renders`
  then `GIT diff --exit-code -- app/public/venue/sock-nest.glb app/public/venue/socks.glb` → exit 0. If the two differ, the playground drew from `Random(0)` or changed a shared constant. Fix that, never the nest.
- [ ] **Step 6:** Step 2's command → every test passes. `cd WT && uv run --frozen ruff check scripts/sock_heist_venue.py tests/test_venue_assets.py` → no new error (an unresolved `bpy` is expected).
- [ ] **Step 7: No commit.** Report the render paths, the printed counts and the drawn total. The owner sees them in Task 3.

---

### Task 2: Each red its own quack

**Files:**
- Modify: `app/src/heist-sound.js`, `app/src/heist-sound.test.js`, `app/src/clip/score.js`, `app/src/clip/score.test.js`, `app/src/clip/soundtrack.js`, `app/src/clip/soundtrack.test.js`, `app/src/viewer.js` (the one `heistCues` call), `app/src/giant.js` (export `draw`), `app/src/duck-voice.js` (export `VARIANTS`)

**Interfaces:**
- Produces in `heist-sound.js`: `GIANT_RATE = 0.3` (the centre, unchanged); `GIANT_SPREAD = 0.1`; `quackOf(seed: number, red: number) -> { variant: number, rate: number }`, where `variant = Math.floor(draw(seed, 2 * red) * VARIANTS.chirp)` and `rate = GIANT_RATE * (1 + GIANT_SPREAD * (2 * draw(seed, 2 * red + 1) - 1))`; `giantQuack(calls, variant) -> Float32Array` (`calls.chirp(DUCK_SEED, variant, {})`); `heistCues(timetable, lanes, length, limitS, seed)`, whose quack cues become `{ at, kind: "quack", lane: null, variant, rate }` with `quackOf(seed, index of the red)`. `GIANT_CALL` is deleted.
- Produces in `clip/score.js`: a quack cue `{ at, quack: true, variant, rate, gain }`, the seed `run.trace_seed`. In `soundtrack.js`, `giantQuack(synth, cue.variant)`.
- `createHeistSound`: one buffer per variant heard, made once; each part plays at its cue's `rate`.

- [ ] **Step 1: Write the failing tests.**

```js
// heist-sound.test.js
const TWELVE = Array.from({ length: 12 }, (_, k) => [1 + 3 * k, 1.6]);
describe("quackOf", () => {
  it("gives every red a chirp of the synth's and a rate within a tenth of the owner's", () => {
    for (let red = 0; red < 50; red += 1) {
      const { variant, rate } = quackOf(3, red);
      expect(Number.isInteger(variant) && variant >= 0 && variant < 12).toBe(true);
      expect(rate).toBeGreaterThanOrEqual(0.27);
      expect(rate).toBeLessThanOrEqual(0.33);
    }
  });
  it("is the same for the same seed and red, and varies from red to red and seed to seed", () => {
    expect(quackOf(3, 4)).toEqual(quackOf(3, 4));
    expect(new Set(TWELVE.map((_, red) => quackOf(3, red).variant)).size).toBeGreaterThanOrEqual(4);
    expect(TWELVE.map((_, red) => quackOf(3, red))).not.toEqual(TWELVE.map((_, red) => quackOf(4, red)));
  });
});
it("hands each quack its red's variant and rate, on the replay's seed", () => { // in describe("heistCues")
  const quacks = heistCues(TWELVE, [], 6, 60, 3);
  expect(quacks.map(({ variant, rate }) => ({ variant, rate }))).toEqual(TWELVE.map((_, red) => quackOf(3, red)));
});
// createHeistSound: the fake chirp returns 4800 + variant samples, so the log tells the variants
// apart. Two quacks of reds 0 and 1 of a seed whose two variants differ (a = quackOf(s, 0),
// b = quackOf(s, 1)) each start at their own rate:
expect(log.filter(([what]) => what === "start")).toEqual([["start", 4800 + a.variant, 0, a.rate], ["start", 4800 + b.variant, 0, b.rate]]);
// The existing tests that expect GIANT_RATE now expect their cue's rate.
```

```js
// score.test.js (replaces the GIANT_RATE expectation)
expect(cues.map((c) => [Number(c.at.toFixed(2)), c.quack ?? c.file, c.variant, c.rate]))
  .toEqual([[4.12, true, quackOf(run.trace_seed, 0).variant, quackOf(run.trace_seed, 0).rate], [4.52, "microduck-fall.wav", undefined, undefined]]);
// soundtrack.test.js: a cue { at: 2, quack: true, variant: 5, rate: 0.31, gain: 1 } renders calls.chirp(DUCK_SEED, 5, {}) at rate 0.31.
```

- [ ] **Step 2:** `cd WT/app && npx vitest run src/heist-sound.test.js src/clip/score.test.js src/clip/soundtrack.test.js` → FAIL (`quackOf` not exported).
- [ ] **Step 3: Implement** per Interfaces. The viewer passes `entries[0]?.traceSeed` as `heistCues`'s seed; it is the same seed `timetableOf` reads there. Update `heist-sound.js`'s header and `GIANT_RATE`'s comment: the owner's 0.30 is now the centre of each quack's rate.
- [ ] **Step 4:** Step 2's command → PASS. Then the full VITEST (only the 4 known failures) and BUILD.
- [ ] **Step 5: A WAV for the owner (not a gate).** Adapt `giant-quacks.mjs` (the old scratchpad, Global Constraints) into `SCRATCH/giant-quacks-seed.mjs`. It plays the reference's trace seed's timetable (from the store's event summary) through `quackOf`, each quack at its onset, into `SCRATCH/giant-quacks-seed.wav`. Report its path.
- [ ] **Step 6: Commit.** `GIT add` the eight files, then `GIT commit -m "Every red the giant quacks its own quack, a chirp of the duck's and a pitch a little either side of the owner's three tenths, drawn from the replayed seed and the red's index so that a page and a clip of one seed quack alike"`.

---

### Task 3: The owner sees the playground (gate), then it is committed

**Files:** `scripts/sock_heist_venue.py`, `tests/test_venue_assets.py`, `app/public/venue/playground.glb`

- [ ] **Step 1:** Send the owner the four new renders (SendUserFile, or their absolute paths), one line each: what it shows. Add the triangle counts, the drawn total and the spot counts. Ask what to change: the building, the fence, the park, the crowd's density, the colours. **STOP until they say yes.**
- [ ] **Step 2:** Apply each round of notes in the script, never by hand in Blender. Rebuild with Task 1 Step 5, which includes the byte check of the nest and the socks, and rerun Task 1 Step 6. Send the new renders. Repeat until yes.
- [ ] **Step 3:** `GIT add scripts/sock_heist_venue.py tests/test_venue_assets.py app/public/venue/playground.glb`. `GIT lfs ls-files` must list `app/public/venue/playground.glb`. Update the script's docstring (it builds the playground too, and the render views). Commit: `"Sock Heist's own venue, a school playground at the microducks' scale built by the Blender script and approved by the owner on <date>: a concrete yard, a building and a wooden fence behind a crowd's spots either side, and a park of trees behind the giant"`.

---

### Task 4: The playground on the site, and the gym off the heist's path

**Files:**
- Create: `app/src/playground.js`, `app/src/playground.test.js`
- Modify: `app/src/giant.js`, `app/src/giant.test.js`, `app/src/viewer.js`, `app/src/course.js`, `app/src/course.test.js`

**Interfaces:**
- Consumes: Task 3's `playground.glb`; stadium.js `crowd(kinematics, geometries, placed)` with `placed = [{ x, y, z, yaw }]`; the viewer's `spectators` (`loadAssets("legs", CROWD_MODEL)`).
- Produces in `giant.js`: `loadHeistVenue() -> Promise<{ nest, socks, playground }>`, where `playground` is `{ yard, left, right, park }`, the GLB's four nodes. `floorBeyond` and `FLOOR_MARGIN_M` are deleted.
- Produces in `playground.js`:
  - `buildPlayground(model, spectators, edge) -> { group, crowd, pose(seconds, mood), floorMaterial(), dispose() }`. It takes a clone of each of `model`'s nodes, so the model's geometry and materials are shared. It sets `left.position.z = -edge` and `right.position.z = edge`, and seats `crowd(...)` on every `spot_*` of the two sides. `placed` is read in the group's frame, the yaw from the spot's quaternion. Every mesh but the yard casts a shadow, and every mesh receives one.
  - `floorMaterial()`: the track's concrete for the course ground, a plain `MeshStandardMaterial` (roughness 0.95, metalness 0) a shade apart from the yard's concrete, so the track reads.
  - `dispose()` frees the crowd and what the playground made. It never frees the model's geometries or materials, nor the spectators'.
- Produces in `course.js`: `buildCourse(event, lanes, stripes)`, whose `beyond` is gone (the ground runs `OVERRUN` past the line, as before Plan C). `viewer.js` `attachCourse(scene, event, lanes, stripes)` follows.
- `viewer.js` on a lights race: `gym = buildPlayground(heistVenue.playground, spectators, height / 2)`, where `height` is the course ground's span. There is no stadium (`audience` stays null) and no `buildJudges`. The giant is built as today. The shadow frame takes the course ground and the giant's group, in place of the jury's. Every other race takes its branch unchanged.

- [ ] **Step 1: Write the failing tests.** `playground.test.js` loads `public/venue/playground.glb` and the crowd model as `giant.test.js` loads its GLBs (`parse`, `creasedGeometries`), into `model` and `spectators`.

```js
describe("buildPlayground", () => {
  it.each([[0.425], [1.7], [4.25]])("stands each side at the lanes' edge %f m out, its crowd beyond it", (edge) => {
    const playground = buildPlayground(model, spectators, edge);
    const seats = spotsOf(playground); // every crowd seat's z, read off its instanced meshes
    expect(seats.length).toBe(spotCount(model));
    expect(seats.every((z) => Math.abs(z) > edge)).toBe(true);
    expect(seats.some((z) => z < 0) && seats.some((z) => z > 0)).toBe(true);
    const box = (name) => new Box3().setFromObject(playground.group.getObjectByName(name));
    expect(box("left").max.z).toBeLessThan(-edge);
    expect(box("right").min.z).toBeGreaterThan(edge);
  });
  it("frees what it made and never the playground's model nor the crowd's", () => {
    const spies = [...geometriesOf(model), ...materialsOf(model), ...spectators.geometries.values()]
      .map((resource) => vi.spyOn(resource, "dispose"));
    buildPlayground(model, spectators, 1.7).dispose();
    spies.forEach((spy) => expect(spy).not.toHaveBeenCalled());
  });
});
// giant.test.js: drop floorBeyond, FLOOR_MARGIN_M and the "ground past it" expectation; loadHeistVenue's test also
//   expects venue.playground's four nodes by name.
// course.test.js: delete "runs the ground further past the finish line when asked, …".
```

- [ ] **Step 2:** `cd WT/app && npx vitest run src/playground.test.js src/giant.test.js src/course.test.js` → FAIL.
- [ ] **Step 3: Implement** per Interfaces. In `viewer.js`, delete every line that only the heist used in the gym: `floorBeyond`, the `beyond` passed to `attachCourse`, the hall stretched past the nest (`buildGym(courseLength + beyond - OVERRUN, …)` returns to `buildGym(courseLength, …)`), and the comments about them. The viewer's `createViewer` comment says a heist loads its playground too.
- [ ] **Step 4:** Step 2's command → PASS; VITEST (4 known); BUILD; `/usr/bin/grep -rn "floorBeyond\|FLOOR_MARGIN\|beyond" WT/app/src/viewer.js WT/app/src/course.js WT/app/src/giant.js` → nothing but prose unrelated to the ground.
- [ ] **Step 5: Look, and check the other races.** With R2 on the new build and R3, shoot the reference's landscape clip at `plan.intro` and at the first crossing + 0.25 s. The yard, the crowd on both sides, the building on the left, the fence on the right and the park behind the giant must all be there, and nothing on a lane. Then score `arena/assets/policies/BEST_alpha_walking.onnx` on `sprint-2m` into a SCRATCH store of its own. Shoot its landscape clip frame `plan.intro + 40` with HEAD's build and with the build of the commit before this task (`GIT archive` into SCRATCH, as Plan C's C8 Step 1 builds `before`). `ffmpeg -i a.png -i b.png -lavfi psnr -f null -` must say `inf`.
- [ ] **Step 6: Commit.** `GIT add` the seven files, then `GIT commit -m "A sock heist races in its playground: each side, its crowd of microducks and the building or the fence behind it, stands at the edge of the lanes drawn, the park and the yard round them, on a concrete track; no gym, no stands, no judges, and the ground no longer runs on past the nest"`.

---

### Task 5: Behind the ducks, on the giant: the pages' view and the clip's shots

**Files:**
- Modify: `app/src/cast.js`, `app/src/cast.test.js`, `app/src/race.js`, `app/src/race.lights.test.js`, `app/src/run.js`, `app/src/workshop/job.js`, `app/src/workshop/job.test.js`, `app/src/viewer.js`, `app/src/viewer.test.js`, `arena/events/sock-heist-6m.toml` (`[clip.camera]` and its comment), `tests/test_lights.py` if its pins move

**Interfaces:**
- Produces in `cast.js`: `pageCamera(event) -> object | null`: `event.clip.camera` on a lights event, `null` otherwise. The event, run and workshop pages pass `camera: pageCamera(event)` to `createViewer`, so a page films a heist with its clip's chase and every other event with the close chase as before.
- Produces in `viewer.js`: `packChase(xs, zs, aspect, fov, back = -Infinity, reach = PACK_REACH)`, where `reach` takes PACK_REACH's place in `rear`. `HEIST_REACH` is the field's reach on a lights race: start at 1.2 m and tune it from the shots. A viewer-level `packReach`, set by every `setLanes` (`event?.lights ? HEIST_REACH : PACK_REACH`), is what `draw` passes.

- [ ] **Step 1: Write the failing tests.**

```js
// cast.test.js (HEIST gains clip: { camera: { kind: "chase", back: 2.1, track: true, hold: 0.8 } })
it("films a sock heist on its pages with its clip's camera, and any other race with the page's own chase", () => {
  expect(pageCamera(HEIST)).toBe(HEIST.clip.camera);
  expect(pageCamera(SPRINT)).toBeNull();
});
// race.lights.test.js and workshop/job.test.js
expect(createViewer).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ camera: HEIST.clip.camera }));
// viewer.test.js, describe("packChase")
it("leaves a duck behind sooner when told a shorter reach", () => {
  expect(packChase([2, 3.5, 4.2, 2.6], LANES, 16 / 9, 42, -Infinity, 1.2).rear).toBeCloseTo(3, 9);
  expect(packChase([2, 3.5, 4.2, 2.6], LANES, 16 / 9, 42).rear).toBe(2); // PACK_REACH as before
});
```

- [ ] **Step 2:** `cd WT/app && npx vitest run src/cast.test.js src/race.lights.test.js src/workshop/job.test.js src/viewer.test.js` → FAIL.
- [ ] **Step 3: Implement** per Interfaces.
- [ ] **Step 4:** Step 2's command → PASS; VITEST (4 known); BUILD.
- [ ] **Step 5: Tune by shots.** Restart R2 on the new build. Change only `[clip.camera]`'s `back`, `height`, `side`, `target_height`, `hold` and `HEIST_REACH` until every shot below holds what it must.
  - **The clip** (R3, the reference's run, both layouts):
    - `plan.intro`: in landscape, every lane and the giant whole, from head to nest; in vertical, the author's duck and the giant whole.
    - The leader's first red + 0.6 s: the head turned round.
    - A caught lane's catch + 2.5 s: the duck lying still under "name · OUT". If no lane of this run is caught, use another run of the store's that has one.
    - The first crossing + 0.25 s: the socks in the air, filling a good part of the picture.
    - The last tape frame: the stamp on the author's lane.
  - **The pages** (puppeteer at 1440 × 900 on R2's event page for `sock-heist-6m`, the reference's run page and a workshop replay of it if the store has one): the default view at the replay's start, mid-race on a red, and once the first duck has crossed. Read the replay's clock off the viewer the page holds. The ducks and the whole giant must be in every one.

  Update the event file's comment over `[clip.camera]`: it frames the playground, and the pages use it too. Update `tests/test_lights.py`'s pins if they moved, then `cd WT && uv run --frozen --extra dev pytest -q tests/test_lights.py` → PASS.
- [ ] **Step 6: Show the owner** the shots (paths under `SCRATCH/shots/`, one line each), the camera values and `HEIST_REACH`. **STOP until they say yes.** Apply their notes through Step 5 again.
- [ ] **Step 7: Commit.** `GIT add` the files touched, then `GIT commit -m "A sock heist is filmed from behind its ducks on the giant, on its pages as in its clip: the pages take the event's clip camera, which opens on every lane and the giant whole and reaches the dive into the socks, the field's camera leaving a trailing duck behind sooner on a heist"`.

---

### Task 6: The clip's cost, measured

**Files:** none in the repository; everything in SCRATCH.

- [ ] **Step 1: Local bench.** Build two versions of the site. `after` is BUILD at HEAD. `before` is the gym version, the commit before Task 4: `GIT archive --output SCRATCH/before.tar <sha> app`, untar it into `SCRATCH/before`, symlink `WT/app/node_modules` into it, and run `npx vite build` there. The clip is the store's longest case, the run whose tape runs to the 40 s limit (a lane out of time; the `statue` lane gives one). Use the owner's notes' recipe ("Clip frame cost under SwiftShader"): one browser per build, SwiftShader, frames interleaved, CPU seconds of the browser's processes per frame. Measure 40 frames of each, landscape. Write down CPU s/frame before and after, and the clip's frame count.
- [ ] **Step 2: Ask the owner** with Step 1's numbers. The proposal: upload a bench tarball (the branch's `arena/` as `src/arena`, both builds, the store) to a private dataset `Nico-robot/sock-heist-clip-bench`, and launch one HF Job on it. **STOP until they say yes.**
- [ ] **Step 3: The job.** `hf jobs run` on `hf.co/spaces/pollen-robotics/microduck-arena`, flavor `t4-small`, namespace `pollen-robotics`, timeout `60m`, secret `HF_TOKEN`, env `ARENA_COMMENTARY=0` and `ARENA_CLIP_GPU=1`. Its command downloads and unpacks the bench to `/tmp/bench`. Then, for `after` and then `before`, it runs `env PYTHONPATH=/tmp/bench/src ARENA_FRONTEND=/tmp/bench/<build> arena clip <run id> --store /tmp/bench/store` and prints each render's `clip.json` `timing`. Follow it with `hf jobs logs`.
- [ ] **Step 4: Report** ms/frame before and after per layout, and the longest clip's total wall against the clip job's 30 min. It passes when a frame of `after` costs no more than one of `before`, and the clip, both layouts and its soundtrack, renders in at most 20 min. Otherwise give the numbers and the levers (the crowd's count, fewer trees, the time limit), and change nothing without the owner. On their yes, delete the bench dataset.

---

### Task 7: The owner sees it locally

- [ ] **Step 1:** BUILD. Restart R2 on the demo store (port 8001, this worktree's code, confirmed with `ps -o command -p` on the port's listener). Move aside the reference run's old gym-era clip folder in the store (`clips/01M639ZYYS3QCZRCN9A9Q5`, into SCRATCH). Render it again: `cd WT && env ARENA_FRONTEND=WT/app/dist ARENA_COMMENTARY=0 CHROME=<wrapper> uv run --frozen arena clip 01M639ZYYS3QCZRCN9A9Q5 --store <store>`.
- [ ] **Step 2:** Give the owner the local URLs: the event page of `sock-heist-6m`, and the reference's run page with its new clip. Give the clip's MP4 path too.
- [ ] **Step 3:** Record the state in Plan C's ledger (`.superpowers/sdd/2026-10-28-sock-heist-c-site/progress.md`): C6b and C8 are superseded by Plan F, with Plan F's commits. What is left is Plan E, each step on the owner's yes.
