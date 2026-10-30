# Red Light, Green Light: a race a caller can stop — design

Date: 2026-10-21, revised 2026-10-24 for a 15 m lane. Status: proposed by a participant
(@jrubiosainz) in a pull request; awaiting the owner's review.

## Why

Every race on the Arena asks the same thing of a walk: get to the line as fast as possible and stay
up. The sprint's leaders now win by diving at the line. This proposal adds a challenge borrowed from
the playground game, which asks for what no current challenge does: **stop on a cue, stand still
while someone watches, and start again**, some fifteen times on the way. Stopping on command is
something a real robot needs. The game reads at a glance in a clip. It also reuses the lane, the
sweep, the scoring, the board and the pages almost as they are.

## Goal

A new perpetual race, `red-light-green-light-15m`: 15 m on flat ground, on legs, with two and a half
minutes to cross. A giant Reachy Mini stands past the finish line. On green it counts with its back
to the lanes. On red it turns round, and a duck it sees moving is caught. The lane keeps each duck
pointed down it, so that walking fifteen metres straight is not what is tested. The lowest mean
finish time wins, as on every race.

**Success.**

- The event loads, scores, ranks, replays and clips like any race, through the same code paths.
- The reference walker (`arena/assets/policies/BEST_alpha_walking.onnx`, the golden run's policy)
  finishes every seed it is scored on in a little over a minute, on both platforms: five of five on
  a Mac and five of five on Linux-x86_64, the Space's platform. Over 32 more seeds at that command
  it finishes every one on a Mac, and 31 on x86, where it fell once.
- Policies that win elsewhere by diving or charging do not finish it, on either platform: it rewards
  another skill.
- Every other event is untouched: same steps, same golden run, same records, and the same traces
  while its ducks keep within 4 m of the origin, as they do on their courses.

## Scope guard: events with `[lights]` or `[steering]` only

Only a manifest with a `[lights]` or a `[steering]` table behaves differently. For every other
event:

- `run_once` takes exactly the steps it takes today: every new line is behind `lights is not None`
  or `steering is not None`;
- the sweep, the golden run and `RUNNER_VERSION` (4) do not change;
- the trace is stored as before while every value in it is under 4, as a duck's position is on
  every other shipped course (lanes of 1.5 and 2 m, a 2.6 × 3.8 m stage). An array holding a value
  of 4 or more, a duck that strayed 4 m from the origin, off its course, is stored float32, and
  decodes to float32 as every array does;
- the API's summary of a lane event answers `"lights": null`, and a stage's has no `lights` key, as
  before; the pages draw no caller and mark no duck out. Every summary's clip settings gain three
  keys, `speed` (1), `track` (false) and `hold` (null), with which a clip films as before;
- the pages' camera is drawn back into the gym (`inRoom`) only from beyond its end wall or above
  its lamps, where no other event's camera goes while its ducks stay on their courses: the end
  wall stands 2 m behind every start line and the camera's ceiling is 2.03 m, while a chase stands
  at most 0.35 m behind and 0.34 m above its duck, and a clip's opening sweep, swinging out and up
  from it, stays under 1.9 m. The roller hall declares no room, so its camera is never moved.

A stage refuses `[lights]`, `[steering]` and a clip speed other than 1. A test keeps every shipped
event other than this one free of lights and of steering.

## Decisions taken

| Decision | Why, and what it rules out |
| --- | --- |
| **The policy sees the light through its command** | On red the command's twist (forward, lateral, yaw) drops to zero, and head and body stay as declared. The 61-D observation is unchanged, so every published policy can enter as it is. A walk that obeys a zero command and starts again cleanly does well. Rules out a new observation, a new rig and retraining for the format. |
| **The timetable is declared in the event and the same on every seed** | One caller times every lane of a replay, and a page draws the light from the event alone: no new field in a record, a trace or a timeline. Six phases of unequal length (green 0.6–3.0 s, red 1.4–2.4 s, a 23.8 s cycle) keep the rhythm irregular. Rules out a random timetable per seed. |
| **The caller takes 0.4 s to turn round, and nothing counts while it turns** | A walking duck cannot stop dead: the turn is its stopping distance. Rules out a judgement no walk could meet. |
| **The mark is where the trunk stands when the caller faces the lanes, and 3 cm of drift is allowed** | Measured on the floor plane only (x, y), so bobbing does not count. Swaying in place and a settling shuffle stay inside 3 cm, and a step forward does not. |
| **Caught is a fourth status, scored like a fall** | `RunOutcome.status` gains `"caught"`. Its `time_s` is `None`, so the seed counts as the time limit, like a fall or a timeout. Scoring, ranking, the board and the records need no change. |
| **Caught is judged after the fall and before the finish** | Within one step: NaN, fall, caught, then progress. A duck seen moving does not get to cross the line on that step. A duck still coasting while the caller turns is not seen, and if it crosses then, it has finished. |
| **The duck settles standing and the clock starts on a green** | The settle uses the red (standing) command, so nobody gets a flying start. |
| **A 15 m lane** | On the show the field is long and the game lasts minutes. The first draft's 2.5 m was a few greens of walking, over almost as soon as it began. A 30 m draft went the other way: a two-minute race, filmed in some 38 s even at four times life, felt long. At 15 m a duck that crosses in about a minute stops for some fifteen reds, so the race is decided by stopping again and again, not by one start, and its clip lasts some 22 s. Rules out a race short enough to cross in a few greens. |
| **A short first green** | The caller first faces the lanes at 1.0 s (0.6 s of green plus the 0.4 s turn). From a standing start, the dives that win the sprint are about 2 m out after a second, so a duck that bolts off the line has to stop as hard as it started. Rules out a start that one bolt can win. |
| **A 150 s limit, and the sprint's sweep (0.20 to 1.20 m/s)** | Green is 12.4 s of every 23.8 s. The reference crosses in about 65 s at 0.95 m/s, and in 131 s at 0.45 m/s, the slowest command it finishes at. Two and a half minutes leaves room for slower walks, and the sweep rewards a fast walk that can still stop. |
| **The lane holds each duck's heading (`[steering]`)** | No policy walks fifteen metres straight unaided. Asked for a yaw rate of zero, the reference's heading wanders tens of degrees within a few metres: without help, at 0.95 m/s, the command it is scored at, it turned 126–171° off the lane within 0.8 m on every one of five seeds, into a wall, and fell or was caught there; at 0.30 m/s, the first draft's speed, it fell on one seed and was caught against a wall on another. On a lane that declares `[steering]`, the command's yaw rate turns the duck toward the lane's centre line 0.5 m ahead, at a gain of 2 and at most 1 rad/s. It is mjlab's heading command (`heading_control_stiffness`) aimed down the lane, and 1 rad/s is within the yaw rates the reference was trained on (`ang_vel_z` from −1 to 1). The policy still sees only its command, so every published policy can enter as it is. Rules out a wider lane, which only puts the wall off, and asking entrants to steer by themselves, which needs a new observation. |
| **The hold steers only the steps the duck walks** | Not the settle, where it stands on the line, and not a red, where a yaw rate would ask it to turn on the spot while the caller watches. Its forward speed is still the sweep's. A `[command]` that declares a yaw rate is refused: the hold would overwrite it on every step it walks. |
| **A trace array with a value of 4 or more is stored float32** | float16, the trace's format on the wire, places a value to under a millimetre below 4, but only to 4 mm between 8 and 16: a duck near the line would be drawn jittering. Each array is judged alone (the trace, its settle), and every array still decodes to float32, so no reader changes. Rules out a new trace version. |
| **The clip is a time-lapse** | `[clip] speed = 4` films the whole race four times faster than life: four times the stride through the trace per clip frame, so every frame still lands on a trace step, and a 65 s race takes some 22 s. The clock on screen reads the race's time, with "×4" beside it. A stage keeps a speed of 1, in time with its voices. Rules out a clip cut after the first metres, as a 12 s tape would be. |
| **The caller is giant on a long lane** | `callerSize(length)`, `min(2.5, max(1, length / 6))`: Reachy Mini's own size up to 6 m, 2.5 times it from 15 m, about a metre tall over ducks of 0.37 m, as the show's doll stands over its field. The chase camera sees it down the lane from the first shot. A lane of 6 m or less draws it as the first draft did. |
| **The chase camera films the field from behind, and holds** | A clip races its run against the three ranked just under it, a lane each, as every race's clip does. Over several lanes a chase that `track`s follows the hindmost duck rather than the leader (`packChase`), so that the field walks ahead of it toward the caller, but never one more than 3 m behind the leader: a duck caught or fallen far back is left behind, in a pan rather than a cut. It stands back far enough to fit every lane across the picture, rising so that it looks down at them as steeply, but no farther than 3 m: a narrower, vertical picture shows fewer lanes rather than smaller ducks, and keeps the clip's own run in it. Over one lane it keeps the leader in the middle of the picture as it drifts across its lane, averaged over a second either side so that a stride's sway does not shake it (`chaseAcross`). `hold = 0.8` stops the camera 0.8 m short of the line and lets the field walk on to it, so that the caller stays whole in the last shot. The camera never stands beyond the gym's end wall behind the start or above its lamps (`inRoom`): it is drawn in along its line of sight, so it looks at the same spot as steeply. `track` and `hold` are off by default, and a chase without them films as before. |
| **A duck that is out says so** | On a race with lights, a lane whose trace ends short of the line, as a duck caught, fallen or out of time does, hangs "name · OUT" over its duck from its last frame (`outAt`), where a replay holds it standing mid-course. It is read from the trace alone: no new field in a record or a trace. Rules out a caught duck that just stands there, as if it were still racing. |
| **The page draws the caller, from the event** | `app/src/lights.js` does the same whole-step arithmetic as the runner, so the drawn light changes on the step the runner's does. Rules out recording the light in the trace. |

## What was measured

The event as shipped, scored with `evaluate()` (the full sweep, three finalists, five seeds).

**On a Mac (Darwin-arm64), MuJoCo 3.10.0:**

| Policy | Command | Seeds | Score |
| --- | --- | --- | --- |
| The reference walker (`BEST_alpha_walking.onnx`) | 0.95 m/s | 5/5 finished, 64.50–64.78 s | 64.616 s |
| A sprint-board policy (0.860 s on the sprint) | — | 0/5: fell about 0.6 m out | 150 |
| A hill-board policy (0.780 s on the hill) | — | 0/5: fell about 0.2 m out | 150 |

The reference's sweep is wide. From 0.20 to 0.40 m/s it runs out of time: it does not move at 0.20,
and gets 5 to 14.8 m from 0.25 to 0.40. From 0.45 to 1.00 m/s it finishes, in 131 s down to 63 s.
At 1.05 m/s it falls about a metre out, and from 1.10 m/s it is caught in the first red, still
coasting some 0.35 m out: a walk that fast cannot stop in the turn. Over 32 more seeds (0 to 31) it
finishes every one, at 0.90 m/s (68.1–68.5 s) and at 0.95 m/s (64.2–66.5 s).

The two board policies fall at the same spot at every command of the sweep. Without the hold, the
sprint-board policy dives 1.7 to 2.1 m, turned 113–178° from the lane, then is caught or falls at
every command: the hold's yaw rate tips it over sooner, but it is not what stops it.

**Without the hold** (the reference on the same lane and lights): at 0.95 m/s, the command it is
scored at, every one of seeds 1 to 5 turned 126–171° from the lane within 0.8 m, into a wall, where
four fell and one was caught. At 0.30 m/s, the first draft's speed, seed 1 fell at 1.2 m, turned
123°; seed 2 walked into a wall, turned 103°, and was caught there at 2.5 m; seeds 3 to 5 kept
within 31° of the lane and ran out of time 9.6–9.7 m out, as the reference does at that speed with
the hold.

**The hold**, with the reference on seeds 1 to 3. As shipped (a lookahead of 0.5 m, a gain of 2, at
most 1 rad/s):

| Command | Finish | Widest from the centre line |
| --- | --- | --- |
| 0.60 m/s | 99.4–99.8 s | 0.15 m |
| 0.80 m/s | 78.3–78.7 s | 0.22–0.23 m |
| 0.90 m/s | 68.3–68.5 s | 0.25–0.27 m |
| 1.00 m/s | 62.9–63.2 s on seeds 1 and 3 | 0.30 m |

At 1.00 m/s seed 2 turned 136° into a wall within its first metre and fell: capped at 1 rad/s, the
hold cannot always bring round a walk that fast. At half the hold (a gain of 1, at most 0.5 rad/s)
the reference finishes every seed up to 0.65 m/s, but wanders up to 0.34 m from the centre line;
at 0.70 m/s one seed of three turns 135° and is caught 12.6 m out, and from 0.80 m/s every seed
falls or is caught.

**On Linux-x86_64, MuJoCo 3.10.0** (the Space's platform, on a cloud VM):

| Policy | Command | Seeds | Score |
| --- | --- | --- | --- |
| The reference walker | 0.95 m/s | 5/5 finished, 64.52–64.72 s | 64.596 s |
| The sprint-board policy | — | 0/5: fell about 0.6 m out | 150 |
| The hill-board policy | — | 0/5: fell about 0.2 m out | 150 |

The reference's sweep gives the Mac's verdict at every command: out of time from 0.20 to
0.40 m/s, finished from 0.45 m/s (131.4 s) to 1.00 m/s (60.4 s), within 0.3 s of the Mac's time up
to 0.95 m/s and 2.5 s faster at 1.00 m/s, a fall about a metre out at 1.05 m/s, and caught in the
first red from 1.10 m/s, some 0.4 m out. Over the same 32 more seeds it finishes every one at
0.90 m/s (68.1–68.5 s), and all but one at 0.95 m/s (64.4–66.8 s): on seed 7 it fell 8.05 m out.
The reference was not trained to stop and start again, and does now and then fall doing it; the
seeds it is scored on finish on both platforms. The two board policies fall where they do on the
Mac, at every command.

Physics on the two platforms diverge after 1–3 s, as `arena/golden.py` records for the sprint, so
the numbers above are per platform. The Space's are the ones that count.

**Earlier drafts.** The first, a 2.5 m lane with a 60 s limit and no hold, scored the reference
39.448 s at 0.30 m/s on a Mac and 43.596 s on x86. A 30 m lane with a 300 s limit and the hold
scored it 130.376 s on a Mac and 130.308 s on x86, at 0.95 m/s.

## Design

### 1. The format (`arena/manifest.py`, `arena/events/red-light-green-light-15m.toml`)

- `Lights(green_s, red_s, turn_s, tolerance_m)`, frozen. `Manifest.lights` is `None` unless the
  event has the table, and `Lights.to_dict()` serialises it for the API.
- Phase k is green for `green_s[k]`, then red for `red_s[k]`. The phases repeat until the time
  limit.
- Validation, each refusal naming the file:
  - the table is a table, and has no unknown keys;
  - `green_s` and `red_s` are non-empty lists of positive seconds, of the same length, each a
    whole number of 0.02 s control steps, so the light changes on a step and nowhere in between;
  - `turn_s` is zero or more, a whole number of steps, and shorter than every red, or the caller
    never looks;
  - `tolerance_m` is a positive distance;
  - a stage refuses `[lights]`: it has no line to walk to.
- `Steering(lookahead_m, gain, max_yaw_rate)`, frozen. `Manifest.steering` is `None` unless the
  event has the table, and `Steering.to_dict()` serialises it. Any lane may declare it, with lights
  or without. Validation, each refusal naming the file:
  - the table is a table, and has no unknown keys;
  - all three are positive numbers;
  - `[command]` vel's third value, the yaw rate, is 0: the hold owns it;
  - a stage refuses `[steering]`: it has no lane to hold a heading down.
- `ClipConfig.speed` is a whole number of at least 1 (TOML's `true` is refused rather than read as
  1), and 1 for a stage. A chase's `ClipCamera.track` is true or false, and its `hold` a distance of
  at least 0 m, or none; the camera serialises both.
- The event: `order = 50`, perpetual, legs, a 15 × 0.8 m lane with 0.15 m walls, 150 s,
  `mean_finish_time`, seeds 1 to 5, the sprint's start (STAND, settled 0.5 s, perturbed 0.01 rad
  and 2°) and sweep, and:

  ```toml
  [lights]
  green_s     = [0.6, 2.4, 1.6, 3.0, 2.0, 2.8]
  red_s       = [1.6, 2.0, 1.4, 2.4, 1.8, 2.2]
  turn_s      = 0.4
  tolerance_m = 0.03

  [steering]
  lookahead_m  = 0.5
  gain         = 2.0
  max_yaw_rate = 1.0

  [clip]
  tape_max_s = 150.0
  speed      = 4

  [clip.camera]
  kind          = "chase"
  back          = 2.1
  height        = 0.86
  side          = 0.1
  target_height = 0.4
  track         = true
  hold          = 0.8
  ```

### 2. The simulation (`arena/runner.py`)

- `_LightSteps.of(lights, steps)` lays the timetable over a run's timed control steps as three
  boolean arrays. `red` marks the steps when the duck is asked to stand. `mark` marks the step
  that ends as the caller finishes turning round, which is the last green step when there is no
  turn. `watch` marks the steps from then to the end of the red.
- `_steered(steering, data, adr, command)` reads the trunk's lateral position `y` and its yaw at
  the start of the control step, the state the duck observes, and returns the command with its yaw
  rate set to `clip(gain · wrap(atan2(−y, lookahead_m) − yaw), ±max_yaw_rate)`.
- `run_once`, only when the event has lights:
  - the duck settles with the standing command (the event's command, twist zeroed);
  - each step, it gets the standing command on red and the event's command otherwise;
  - after the fall check, a `mark` step records the trunk's x and y. On a `watch` step, a trunk
    more than `tolerance_m` from its mark ends the run as `"caught"`, with `time_s = None` and the
    progress where it stood.
- `run_once`, only when the event has steering: each timed step that is not red, the duck gets
  `_steered`'s command. The settle and the reds are not steered.
- Unchanged: `evaluate()` (caught counts as the limit, like a fall), `run_stage`, the golden run
  and `RUNNER_VERSION`.

### 3. The trace (`arena/trace.py`)

- `encode` stores each array float16, as before, unless it holds a finite value of 4 or more
  (`FLOAT16_REACH`), which it stores float32. NaNs from a solver explosion do not count.
- `decode` is unchanged: every array comes back float32.

### 4. The Arena (`arena/web/routes_read.py`, `arena/commentary/`)

- `event_summary` carries `lights`, or `null`, and the clip's `speed`, `track` and `hold`.
- The commentary:
  - `nature()` describes the game ("a 15 m game of red light, green light: walk on green, stand
    still on red", tag `lights`);
  - `_result` names the caught seeds next to the falls (tag `caught`);
  - three lore lines are tagged `lights` and `caught`.

### 5. The site (`app/src/`)

- `lights.js`: `lightAt(lights, seconds)` returns `{ red, facing, watching }` for a moment of the
  race. `facing` eases from 0 (back to the lanes) to 1 over `turn_s`. Before the start, the caller
  counts with its back turned. `outAt(trace, length)` is the frame from which a lane's duck is out:
  its last, when its trace ends more than 5 cm short of the line, and otherwise none.
- `caller.js`: `buildCaller(model, lights, length, edge)` builds a Reachy Mini (the judges' model)
  at `callerSize(length)` on a step past the line, a post with a red and a green lamp beside it,
  and a strip along the far edge of the lanes, from the start line to the post, which shows the
  light wherever the camera is. `pose(seconds)` turns the caller and lights the lamps and the
  strip. Its antennas wiggle while it counts.
- `viewer.js` builds the caller on any race whose event has `lights`, and poses it on the replay's
  clock less the lanes' lead. On such a race, a duck whose trace ends short of the line has a
  second plate, "name · OUT", which takes over from its name plate at `outAt`. Its chase camera:
  - `cameraPose(spec, lead, sideOffset, rise, across, fit)` sets the camera and its target
    `across` metres to the side, and backs off to `fit`, rising with it, when it stands closer;
  - `chaseAcross(lanes, seconds)` is the leader's lateral position in the scene, averaged over a
    second either side (every fifth step, with raised-cosine weights), so that it follows a drift
    rather than a stride's sway, and pans rather than cuts when another duck takes the lead;
  - `packChase(xs, zs, aspect, fov, back)` is what a tracking chase over several lanes follows:
    the hindmost duck, but none more than 3 m behind the leader; how far back it stands to fit
    every lane, at most 3 m and never behind `back`; and where it centres across them, keeping the
    last lane, the clip's own run, in a picture too narrow for them all;
  - a chase that `track`s uses `packChase` over several lanes and `chaseAcross` over one, and one
    that `hold`s stops `hold` metres short of the line;
  - `inRoom(pose, room)` draws a camera standing beyond the gym's end wall or above its lamps in
    along its line of sight, and leaves any other where it is.
- `gym.js`: the gym gives its `room`, where a camera may stand: in front of the wall bars on the end
  wall behind the start, and 0.2 m under the lamps.
- `clip/plan.js`: `clipPlan(frames, tapeMaxS, settle, speed)` strides `speed` times as far through
  the trace per clip frame. `clip/score.js` hears the progress every half second of tape, in the
  tape's own seconds. `clip/main.js` passes the event's speed, writes "×4" after the clock in a
  time-lapse, and gives each lane its settle as `lead`, so that the light keeps the race's clock in
  a clip.
- `share.js`: a run that finished no seed says "it got caught moving on a red light" when that is
  what stopped it. `run.js` already shows each seed's status.
- `roundcard.js`: the card's accent (lime), call to action ("Green light!") and title, with art in
  `app/public/cards/red-light-green-light-15m.webp`.

### 6. Docs (`docs/guides/challenges/red-light-green-light-15m.md`)

The guide explains the light, the turn, the 3 cm, the timetable, the lane's heading hold and the
scoring. It points to the sprint's workshop template for training, since this challenge has none
yet, and asks for a walk that holds still on a zero command and turns on a turn command.
`guides.test.js` knows the new guide.

## Testing

- **pytest** (`tests/test_lights.py`):
  - the event loads with its lights, they serialise, and no other shipped event has lights;
  - the event is filmed whole, as a time-lapse, by a chase that tracks its field and holds short of
    the line;
  - every malformed `[lights]` is refused, with its message, and a stage refuses lights;
  - `_LightSteps`: the timetable cycles its phases over the steps; with no turn the mark is the
    last green step and the whole red is watched; a red the run ends inside its turn is never
    watched;
  - `run_once`, with the reference walker on the event cut to 3 s: the policy's observed twist is
    the standing one through the settle and every red step, and the walk on every green step; at
    a tolerance nothing meets, the duck is caught on the first step the caller watches, and not
    one before;
  - the shipped event runs end to end with the reference walker. The test does not assert which
    end it meets, since the platforms' physics part ways within seconds.
- **pytest** (`tests/test_steering.py`):
  - the event holds its ducks' heading, and no other shipped event does;
  - `[steering]` loads and serialises; a stage refuses it; it must be a table; a declared yaw rate
    is refused, and so is every malformed value, with its message;
  - `_steered` turns the duck toward the centre line ahead, no faster than its cap, and round the
    short way when it faces back up the lane;
  - `run_once`, with the reference walker on the event cut to 3 s: the observed yaw rate is zero
    through the settle and every red step, and steered on every green step;
  - twenty seconds of the event at 0.8 m/s: the duck is still within 0.25 m of its centre line (on
    seeds 1 to 10 it strays 0.18 to 0.22 m from it), and facing down the lane.
- **pytest, updated:**
  - `test_manifest.py`: a chase can track and hold; a long race is filmed as a time-lapse; a
    performance is filmed at speed 1;
  - `test_trace.py`: a long lane's trace is stored float32 while its settle need not be; a solver
    explosion's NaNs leave a short trace float16;
  - the course tests list the new event; `routes_read` carries `lights` (and `null` elsewhere) and
    the clip's new keys; the commentary names caught seeds and their tag.
- **vitest:**
  - `lights.test.js`: green before and at the start; red on exactly the steps the runner judges
    red; the turn, and watching only once it is done; the turn back on green; the cycle repeating;
    a caller that takes no time to turn; `outAt` leaving a duck that reached the line in, wherever
    it set off, putting one whose trace ends short of it out from its last frame, and saying
    nothing of an empty trace;
  - `caller.test.js`: where the caller stands, and how large over a long lane; which way it faces;
    the lamps and the strip following the light; the strip along the far edge from the start line
    to the post; the antennas; `dispose` leaving the shared model whole;
  - `viewer.test.js`: a tracking chase centred across the lanes where it is told, its side offset
    kept, backing off and rising to fit its lanes but never coming closer; `chaseAcross` centring
    on the line its leader walks, seeing through a stride's sway, following a drift, and panning
    when another duck takes the lead; `packChase` following the hindmost duck but leaving one more
    than 3 m behind, standing back just far enough to hold every lane in a landscape picture, no
    farther than 3 m in a narrower one, keeping the last lane's duck in it, and no nearer the wall
    than it is told; `inRoom` leaving a camera inside the room, and any camera of a hall without
    one, where it is, and drawing one beyond the wall or above the lamps in, looking at the same
    spot as steeply;
  - `clip/plan.test.js` and `clip/score.test.js`: a time-lapse's stride, every clip frame on a
    trace step, and its progress heard in the tape's own seconds;
  - `share.test.js`, `roundcard.test.js`, `guides.test.js`.
- **Seen before it was called done.** In a local store, on `arena serve` and with `arena clip`
  (headless Edge as `$CHROME`):
  - the reference's run against three slower runs ranked under it, 65 s filmed whole in some 22 s,
    in a landscape and a vertical clip: the giant caller past the line in sight as soon as the
    opening sweep comes down behind the field, the lamps and the strip in step with the replay, the
    four lanes in the picture, a duck caught early marked "OUT" and left behind as the camera
    follows the field, the camera stopping short of the line, and the vertical clip keeping the
    run's own duck in the picture;
  - on the first draft's 2.5 m lane, a sprint policy's run, caught moving: the light red and the
    caller facing the lanes when the verdict comes.

## Left to the owner

- **The card art** is generated, and is easy to replace.
- **A workshop template** in microduck-challenges: a walker trained to stop on a zero command,
  start again and turn on a yaw command, with the command switched at random during training.
  Until then the guide points to the sprint's template.
- **What an evaluation costs.** The Space evaluates a submission in its request (`routes_submit`).
  At 15 m the reference's evaluation took 27 s of one Mac core, and 107 s of one of the cloud VM's
  32 vCPUs while the other 31 were busy; a policy that falls at once takes a few seconds at most.
  Fewer sweep steps or finalists would cut it.
- **The length** is one line of the event, with a time limit to match. 30 m was tried: the race
  took two minutes, its clip 38 s, and both felt long, and it took twice as long to evaluate.
- Whether the event is perpetual, as proposed, or a round.

## Out of scope

- New observations: a policy never sees the caller, a clock or the lane, only its command.
- A random timetable per seed.
- Several ducks in one simulation, on one floor, eliminated as they are caught: a clip races
  separate runs side by side, each simulated alone, as every race's clip does.
- Rollers: the event is on legs.
- Real robots.
