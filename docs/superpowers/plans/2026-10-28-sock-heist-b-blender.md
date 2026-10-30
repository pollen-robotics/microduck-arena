# Sock Heist B — the nest, the socks and the giant in Blender — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scripted Blender build of the giant microduck's nest woven from socks and of the loose socks
on the floor, exported as two low-poly GLBs. The owner sees renders of them with the giant in place before
anything reaches the site.

**Architecture:** One Blender script, run headless, builds every model from code (curves swept into sock
tubes, bent at the heel, capped at the toe, striped with vertex colours), lays the socks round a bowl to
weave the nest, and exports `sock-nest.glb` and `socks.glb`. With `--render`, it also imports the racers'
own `microduck.glb` at `GIANT_SCALE` into the nest, adds a row of life-size racers on the start line and
the socks on the floor, and renders four views for the owner. `microduck.glb` is only a bank of 38
part meshes with no hierarchy, so the script assembles the duck the way the site does (`app/src/rig.js`):
the 15 bodies of `app/public/robot/kinematics.json` (`pos`, `quat` and `joint` each, relative to the
parent), with each geom's mesh taken from the GLB by name and placed at its own `pos` and `quat`. A pytest
reads the GLBs' own JSON to pin the mesh names and the triangle budget.

**Tech Stack:** Blender 5.2.2 LTS (`/opt/homebrew/bin/blender`, `bpy`), glTF 2.0 exporter, Python 3.12
pytest (struct + json, no Blender needed).

**Spec:** `docs/superpowers/specs/2026-10-27-sock-heist-design.md` ("The nest and the socks are new
models, made in Blender", Anti-goals: "a nest that does not read as socks at a glance").
**Contract:** `docs/superpowers/plans/2026-10-28-sock-heist-interfaces.md` ("Venue assets").

## Global Constraints

- The contract's rules apply: English only, unsigned commits in the repository's style,
  `/usr/bin/git`, tests in the foreground, no dead code.
- Files: `scripts/sock_heist_venue.py`, `app/public/venue/sock-nest.glb`, `app/public/venue/socks.glb`,
  `tests/test_venue_assets.py`. Renders go to the session scratchpad, never into the repository.
- Budget: the nest at most 6 000 triangles; each sock at most 400; 3 to 5 sock meshes `sock_0`… The
  socks are instanced on the site, so a sock's budget is per model, not per sock laid.
- Materials: vertex colours (`COLOR_0`) on one plain material per GLB, roughness 0.9, metalness 0. No
  image texture, no normal map.
- glTF axes: Y up, metres. The nest's origin at its floor centre, +X pointing away from the lanes. Each
  sock's origin at its floor contact, lying flat.
- Sizes are taken from the racer, never typed in. The script measures the assembled duck's bounding
  box at its standing pose (every joint at 0; Plan C measured it at 0.123 × 0.274 × 0.144 m, the
  middle figure its height), and the giant is that box times `GIANT_SCALE` = 4.5 (about 1.23 m tall).
  The nest's inner radius fits the giant's footprint plus 10 %. Its rim rises to the giant's hip, so
  its legs are hidden.
- The head turns at the rig's `head_yaw` joint (the body that carries it in `kinematics.json`), to the
  joint's own limit of −2.967 rad (170°). Plan C turns it there too: at that angle the face points
  back at the lanes.
- Palette: the socks are the colours of the house and of a laundry basket: lime `#c8ff2e`, white,
  charcoal `#2b2d33`, a red `#ff2b2b`, a sky blue; stripes, heels and toes in a second colour. The nest
  must read as socks at a glance: whole socks, heels and toes visible, not a rope of yarn.
- The script is deterministic (a fixed `random.Random(0)`), so a rebuild gives the same files.

## Review Focus

1. **A nest that reads as a bowl of rope, not socks** (owner's anti-goal): Task 2's renders include a
   close view where heels and toes are visible. It is judged by the owner, not by a test.
2. **A budget blown by the weave** (dozens of socks in the nest): Task 1's
   `test_the_nest_keeps_its_triangle_budget`.
3. **Axes swapped on export** (a nest lying on its side on the site): Task 1's
   `test_the_nest_stands_on_the_floor` (the nest's Y extent is its height, min Y ≈ 0).
4. **The giant out of proportion with its nest** (legs showing, or swallowed): Task 2's side render,
   checked by the owner.
5. **A GLB committed outside LFS:** Task 3's `git lfs ls-files` check.

---

### Task 1: The script builds the socks and the nest

**Files:**
- Create: `scripts/sock_heist_venue.py`
- Create: `tests/test_venue_assets.py`
- Create (generated): `app/public/venue/sock-nest.glb`, `app/public/venue/socks.glb`
- Modify: `.gitattributes` (one line: `app/public/venue/*.glb filter=lfs diff=lfs merge=lfs -text`)

**Interfaces:**
- Produces: the two GLBs as the contract lays them out (mesh `nest`; meshes `sock_0`…`sock_{n-1}`).
- Produces: `blender -b -P scripts/sock_heist_venue.py -- <out dir> [--render <render dir>]`.

- [ ] **Step 1: Write the failing test** `tests/test_venue_assets.py`. It reads each GLB's JSON chunk
  (12-byte header, then the first chunk: `struct.unpack("<II", ...)` length and type `JSON`) and
  counts triangles per mesh from its primitives' index accessor `count // 3`.

```python
VENUE = Path(__file__).parent.parent / "app" / "public" / "venue"

def test_the_nest_is_one_mesh_named_nest():
    assert [m["name"] for m in gltf(VENUE / "sock-nest.glb")["meshes"]] == ["nest"]

def test_the_nest_keeps_its_triangle_budget():
    assert triangles(gltf(VENUE / "sock-nest.glb"), "nest") <= 6000

def test_the_socks_are_three_to_five_models_within_budget():
    names = [m["name"] for m in gltf(VENUE / "socks.glb")["meshes"]]
    assert 3 <= len(names) <= 5 and names == [f"sock_{k}" for k in range(len(names))]
    assert all(triangles(gltf(VENUE / "socks.glb"), name) <= 400 for name in names)

def test_the_nest_stands_on_the_floor():
    lo, hi = bounds(gltf(VENUE / "sock-nest.glb"), "nest")  # POSITION accessor min/max
    assert abs(lo[1]) < 0.01 and hi[1] - lo[1] < hi[0] - lo[0]  # on the floor, wider than tall

def test_every_venue_model_is_vertex_coloured():
    for name in ("sock-nest.glb", "socks.glb"):
        assert all("COLOR_0" in p["attributes"] for m in gltf(VENUE / name)["meshes"] for p in m["primitives"])
```

- [ ] **Step 2: Run it to see it fail.**
  Run: `cd /Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist && uv run --frozen --extra dev pytest -q tests/test_venue_assets.py`
  Expected: FAIL, no such file `sock-nest.glb`.

- [ ] **Step 3: Write `scripts/sock_heist_venue.py`.** Its parts, each a function:
  - `racer(angles: dict[str, float]) -> bpy.types.Object`: imports `app/public/robot/microduck.glb`
    once (the part meshes, by name), then builds the duck from `kinematics.json`. Each body is an
    empty parented to its parent's empty at the body's `pos`/`quat` (MuJoCo order w, x, y, z).
    A jointed body adds its hinge rotation `angles.get(joint name, 0)` about `joint.axis`, at
    `joint.pos`. Each geom is a linked copy of its mesh at its `pos`/`quat`, with its `color`. The
    glTF importer turns Y up into Z up. Read how `app/src/rig.js` places a GLB part
    (`rigGeometries`, `attachMeshes`), and undo the same frames. The check: rendered alone, the
    duck stands upright with its feet on the floor and its face toward +X.
  - `racer_box() -> (width, height, depth)`: the world bounding box of `racer({})`. The giant's box
    is that times 4.5.
  - `sock(variant: int) -> bpy.types.Object`: a Bézier curve, the leg straight, a bend of about 90°
    at the heel, the foot, with a circular bevel (8 sides) and a rounded toe cap. Stripes and a
    contrasting heel and toe come from vertex colours along the curve's length. Variants differ in
    length (ankle to knee socks), colours and stripes. At most 400 triangles once converted to a mesh.
  - `nest(box) -> bpy.types.Object`: socks laid in overlapping rings round a shallow bowl. Each ring
    is a few sock copies bent along the circle, tilted and offset, with a random sock variant and
    phase, so that heels and toes stick out along the rim. Joined into one mesh `nest`, origin at the
    floor centre, rim height at the giant's hip, inner radius the giant's footprint plus 10 %.
    The weave's sock count is set by the budget: at most 6 000 triangles in all, so each nest sock uses
    the low-resolution version (bevel 6 sides, fewer curve points).
  - `export(objects, path)`: glTF binary, `export_yup=True`, vertex colours on, no materials but the
    one plain material, applied modifiers, no animation. The node carrying each mesh bears the mesh's
    name (`nest`, `sock_k`): three.js names an object after its node, and Plan C finds them by name.
  - `render(out)`, only with `--render`: the venue on a grey floor. The giant is `racer({})` at 4.5×,
    sunk into the nest to the hip, its centre 1.7 m past the finish line (Plan C's `GIANT_BEHIND_M`),
    facing +X (away from the lanes). Socks lie on the floor between the finish line and the nest.
    Four life-size racers stand on a start line 6 m before it. The renders, Eevee at 1600 × 900, are:
    `chase.png` from behind the start line at the race camera's height (#3's `[clip.camera]`: back
    2.1, height 0.86), `three-quarter.png`, and `close.png` on the rim, where the heels and toes show.
    A fourth, `turned.png`, uses `racer({"head_yaw": -2.967})`: the head turned over its shoulder
    toward the lanes.
  - The command line after `--`: the out dir for the GLBs, `--render <dir>` for the renders.

- [ ] **Step 4: Build.**
  Run: `cd /Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist && blender -b -P scripts/sock_heist_venue.py -- app/public/venue --render /private/tmp/claude-501/-Users-nicolasrabault-Projects-HuggingFace-microduck-arena/67e38f06-738a-416e-a1fe-9ac25e562f3b/scratchpad/venue`
  Expected: the two GLBs, four PNGs, and the printed triangle counts and the giant's height.

- [ ] **Step 5: Run the test to see it pass.** Same command as Step 2. Expected: 5 passed.
  Then `uv run --frozen ruff check scripts/sock_heist_venue.py tests/test_venue_assets.py`. The
  script imports `bpy`, which ruff does not resolve, and that is fine.

- [ ] **Step 6: Do not commit yet.** The owner sees the renders first (Task 2).

---

### Task 2: The owner sees the renders (gate)

**Files:** possibly `scripts/sock_heist_venue.py` and the regenerated GLBs, from the owner's notes.

- [ ] **Step 1:** Send the four renders to the owner (SendUserFile, or their absolute paths) with one
  line each: what it shows, the triangle counts, the giant's size (its height in metres against a
  racer's). Ask what to change. Questions: does the nest read as socks, is the giant the right size,
  are the colours right.
- [ ] **Step 2:** Apply the notes in the script, never by hand in Blender, and rebuild (Task 1 Step 4).
  Re-run Task 1's test. Send the new renders. Repeat until the owner says yes.
- [ ] **Step 3:** Record the owner's yes, and the date, in the commit message of Task 3.

---

### Task 3: Commit the venue models

**Files:** `scripts/sock_heist_venue.py`, `tests/test_venue_assets.py`, `app/public/venue/sock-nest.glb`,
`app/public/venue/socks.glb`, `.gitattributes`, `app/public/ASSETS.md` (one row: `venue/*.glb`,
"Built by `scripts/sock_heist_venue.py` in Blender 5.2.2; rebuild with the command in its docstring").

- [ ] **Step 1:** `cd /Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist && /usr/bin/git add .gitattributes scripts/sock_heist_venue.py tests/test_venue_assets.py app/public/venue/sock-nest.glb app/public/venue/socks.glb app/public/ASSETS.md`
- [ ] **Step 2:** `/usr/bin/git lfs ls-files | grep venue/` lists both GLBs. If not, the
  `.gitattributes` line is wrong: fix it and re-add.
- [ ] **Step 3:** Commit, for example: `The giant's nest woven from socks and the loose socks on its floor,
  built by a Blender script and approved by the owner on <date>: two low-poly vertex-coloured GLBs`.
