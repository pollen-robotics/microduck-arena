# Football: two policies, one ball, a Reachy Mini in each goal — design

Date: 2026-10-24. Status: a request for comments from a participant (@jrubiosainz), in a pull
request of its own, on `main` as it stands: it needs no other pull request. It ships the rules,
the simulation, a referee that plays from the shell, and a page that replays a match on a pitch in
the Arena's own stadium. The decisions only the owner can take are listed at the end.

## Why

A race asks a walker to be quick down its lane. Football asks for most of what else a walk is
for: **go somewhere, turn, stop, and stay up**, among boards, a ball and another duck trying to do
the same. A goal reads at a glance in a clip, and a result (won, drawn or lost, by so many goals)
makes a league table.

No published policy has ever seen a ball: its observation is its own body and a velocity command.
So each duck has a coach that reads the pitch and works that command, as a joystick would, and the
kick is assisted: a duck that walks into the ball facing the right way sends it on. What a match
compares is the walk underneath: whether the duck gets to the ball, facing the right way and on its
feet, when its coach asks. The reference walker against itself scores in 9 of 24 plays, past
keepers that make 15 saves.

## Goal, and what this PR is

A command of its own, `arena football`, played three ways:

```
arena football A.onnx B.onnx           # a match: every seed played from both ends
arena football A.onnx B.onnx C.onnx    # a round robin, and its league table
arena football A.onnx B.onnx --watch   # a match, then its plays on a pitch at 127.0.0.1
```

This PR is the rules, the simulation, the referee and a way to watch them. It is not a challenge
on the site:

- `arena/football.toml`: the match, every key checked and any unknown one refused;
- `arena/football.py`: the loader, the model (two ducks, a ball, two keepers, the boards and the
  nets), the coach, the play and its referee, the match, the round robin and the league table, and
  the play and the match recorded for a replay;
- `arena football` in `arena/cli.py`, and its `--watch`;
- `arena/football_watch.py`: the server `--watch` starts on 127.0.0.1, for as long as the command
  runs;
- the page it serves: `app/football.html`, `app/src/football/` (`main.js`, `hall.js`, `plays.js`)
  and `app/public/football.css`, and the venue the viewer builds for it,
  `app/src/football-venue.js`;
- in the app, a fifth page in `app/vite.config.js`, and the football venue in `app/src/viewer.js`;
- `tests/test_football.py`, and the app's tests of the venue and the page;
- this document.

**On `main` alone.** The opening (every run's reset, each duck then held on its mark through the
settle), the checks for a void and a fault (`_diverged`, `_faulted`) and the frame of both ducks
(`_frame`) are football's own, in `arena/football.py`; the page is set in the Arena's trackside
sheet (`race.css`), with what that has no component for in `football.css`. There is no board,
store, record, clip or Space workflow change. The page is built with the site, but plays only what
`arena football --watch` serves: on the Space it says that the match's server did not answer.

**Success.**

- A match loads, compiles, plays and scores deterministically on one platform, through the engine's
  own opening and stepping.
- Goals are scored on the pitch: the reference walker against itself scores in 9 of 24 plays, the
  first at 3.78 s, past 15 saves.
- It ranks: in a round robin with four policies from near the top of the sprint and hill boards, the
  reference wins all four of its matches.
- A match can be watched as it was played: every play, on a pitch in the stadium every challenge is
  shown in, a Reachy Mini in each goal and microducks in the stands all round the pitch.
- Nothing that exists behaves differently.

## Scope guard: nothing that exists behaves differently

- `arena/football.toml` sits beside the code, not in `arena/events/`: it is not an event, so the
  programme, the boards, the store and the Space never see it (`manifest.all_events` does not list
  it). Only `arena football` reads it.
- `arena/football.py` builds on the engine's parts (`course._robot`, `_motorized`, `_compiled`,
  `runner._start`, `_reset_by_mujoco`, `manifest._command`, `manifest.Termination`, …) and changes
  none of them. `run_once`, `run_stage`, the trace and its codec, the golden run and
  `RUNNER_VERSION` are untouched.
- The edits to existing files add to them, and leave what was there as it was:
  - `arena/cli.py`: the `football` command (`_cmd_football`, `_watch_football`, `_football_how`),
    `_entrants`, which loads and names its policies, and `_port`, a port from 1 to 65535;
  - `app/vite.config.js`: `football.html`, a fifth page;
  - `app/src/viewer.js`: the football venue, built in place of a race's course when the event is a
    football match (`isFootball`), and handed the crowd's lighter model for its stands behind the
    goals; `venue.pose(rigs, frame)`, the replay's frame, by which it places the ball and the
    keepers; `venue.crowd`, those stands' crowd, posed and culled with the others; no marker under
    a football match's ducks, the ball being what the eye follows there, so each name plate takes
    its duck's colour; and `spot(i, lift)`, a point `lift` metres above a duck's trunk, so that the
    page's stamp clears the name plate (`PLATE_HEIGHT` and `PLATE_LIFT`, now exported). For every
    other event the viewer is as it was.
- The page's server, `arena/football_watch.py`, stands apart from `arena/web`: no OAuth, no store,
  never deployed. It answers GETs of the match it played and nothing else.

## Rules

- **The pitch**: 2.2 × 1.5 m of turf, each corner cut off 0.25 m along both its sides, inside
  boards 0.2 m high and 0.05 m thick. A goal 0.6 m wide and 0.3 m high in the middle of each end
  board, with a pocket 0.2 m deep behind it, netted on every side but the mouth.
- **The ball**: 7 cm across and 30 g, a hollow shell (a shell's inertia) that rolls on: sliding
  friction 0.8, spin and rolling friction 0.002, MuJoCo's full friction cone (`condim` 6).
- **The keepers**: a Reachy Mini in each goal; to the physics, a cylinder 0.16 m across, 0.26 m
  tall and 1.5 kg on a rail along the goal line, its axis 0.02 m in front of the line. The rail
  stops 0.08 m short of each post (±0.14 m from the middle), so there is room either side of a
  keeper. A position servo (kp 400, kv 40, at most 40 N) sends it toward where the ball was 0.4 s
  before, across the goal, no faster than 0.25 m/s. It never touches the turf, the boards or the
  nets: it rides 2 mm up and is kept out of contact with the course. A ball held against a keeper
  for 0.02 s is cleared: sent back up the pitch at 1.2 m/s, within 40° of straight on; that keeper
  then clears nothing more for 1 s.
- **The start**: duck k kicks off from end k, its trunk 0.45 m behind the centre spot, facing the
  goal it attacks: duck 0 from −x, attacking the goal at +x. The ball is on the centre spot. Both
  ducks settle for 0.5 s, untimed, asked to stand still, each held on its mark, after every run's
  reset and perturbation (0.01 rad a joint, 2° of yaw). At the horn both are let go.
- **The coach**. From the horn, each duck's policy is asked a forward speed and a turn rate by its
  coach, every control step; the rest of its command stays at zero. The coach:
  - aims 0.12 m inside the goal its duck attacks, 0.095 m in from a post (the ball's radius and
    6 cm), beside the keeper on whichever side has the wider gap. It changes side only for a gap
    8 cm wider. On odd seeds both coaches start aiming to their own duck's left, on even seeds to
    its right: a play's kick-off is the same seen from either end;
  - heads for a spot 0.12 m behind the ball on the line from its aim; round the ball, 0.18 m out to
    the side, while its duck is not behind it; and on through the ball, to 0.3 m past it, once its
    duck is behind it within 6 cm of that line (12 cm to stay on it): dribbling;
  - keeps every target 0.12 m inside the boards and the corner cuts, and treats each goal's mouth
    as board: it never walks a duck into a net;
  - asks only for what the reference walker does, outside its dead zones: 0.6 m/s with a turn of up
    to 1.0 rad/s while its target is within 0.5 rad of its heading, else 0.3 m/s and 2.0 rad/s.
    Within 0.12 m of a board its duck faces, it asks for no step on, or for −0.5 m/s if the duck is
    square on to the board and its target more than 0.5 rad off its heading; and it turns at
    2.0 rad/s.
- **The strike**. A duck on its feet, alone on the ball, the ball within 60° of its heading and its
  cooldown over, strikes the ball:
  - a shot, within 1.0 m of the goal line it attacks and facing its coach's aim within 20°: at the
    aim, at 1.2 m/s; then nothing more from that duck for 0.6 s;
  - else a touch, facing the goal's middle within 60°: along its heading at 0.6 m/s; then nothing
    for 0.4 s;
  - each within 6° of its line, at 90–110 % of its speed, rolling. Two ducks on the ball at once:
    nobody strikes.
- **The referee** looks after every control step (0.02 s), in this order:
  - a simulation that MuJoCo had to reset is void: no goal;
  - a duck whose action is not a number (a servo command MuJoCo refuses, `_faulted`)
    has faulted, and the other end is given the goal; two at once, no goal;
  - the strike, as above;
  - a stuck ball, put back: one that has not moved 5 cm in 3 s, all the while within 0.35 m of a
    duck on its feet;
  - the keepers' saves;
  - a ball out of play, put back: over a side board by 0.15 m, 0.1 m through the turf, 0.3 m past
    the back of a goal, or over an end board beside a goal or above its bar;
  - a goal: the ball wholly over a goal line, between the posts and under the bar. It counts for the
    end attacking that goal, whoever sent it in;
  - every event's fall rule (projected gravity's z above −0.5 for 0.3 s in a row, from the horn): a
    duck that goes down stays down for the rest of the play, asked to stand still, its goal left to
    its keeper. Both down: no goal.
- A ball put back is put down at rest, 5 mm above the turf, on whichever of five spots (the centre
  spot, and (±0.75, ±0.45) m) is nearest to where it was and has no duck within 0.25 m, standing or
  down; the nearest of all five if none is free.
- The first goal ends a play. The whistle, at 20 s, ends a play nobody has scored in.
- **A match** plays every seed (1, 2, 3) twice, the policies swapping ends: six plays, so six goals
  at most. The policy with more goals wins the match.
- **A round robin** plays every pair once. The table is a league's: 3 points for a win and 1 for a
  draw, then goal difference, goals scored, and name.

## Decisions taken

Numbers said to be *while the rules were set* come from the prototype this engine was ported
from: the reference against itself, on seeds 1–16 or 1–24, each played from one end. Its strikes
and saves drew on a random stream of their own; given that stream, the engine plays the
prototype's 24 plays of the shipped rules exactly, each ending the same way on the same step. On
the engine's own stream (`_strike_rng`), the same 24 seeds give 9 goals rather than 10. The rest
are the shipped match's.

| Decision | Why, and what it rules out |
| --- | --- |
| **One a side, and the first goal ends a play** | A play asks one question, who scores first if anyone, and six plays make a match. Nobody has to walk back to a kick-off, and a fallen duck is never left lying in a running game. Rules out teams, and a running score with kick-offs after each goal. |
| **The policy walks; a coach steers** | No published policy has seen a ball. The observation is unchanged, so every published policy can enter as it is. The coach, in the referee's code, works only the forward speed and the turn rate, as a joystick would, and it is the same coach for both ducks: what differs is how each walk answers it. Rules out a ball, a goal or an opponent in the observation, and retraining for the format. |
| **Commands outside the walker's dead zones** | Measured on the reference walker, standing: asked 0.15 or 0.2 m/s forward, it does not move; 0.3 m/s gives 0.14 m/s, 0.6 gives 0.27 and 0.8 gives 0.35. Asked to turn on the spot at 0.5–1.0 rad/s, it barely turns; 1.3 rad/s gives 0.8, 2.0 gives 1.29 and 3.0 gives 2.0. A first coach that asked for at most 1.0 rad/s, and slowed its duck by the cosine squared of its heading error, stood its duck "turning" without turning. So the coach walks at 0.6 m/s, and turns at 0.3 m/s and 2.0 rad/s. |
| **An assisted strike** | A walk only pushes a ball, which stalls against a keeper or beside a post. While the rules were set, the reference against itself scored 0 goals in 16 plays with no strike, and 1–4 with the keeper slowed to 0.08–0.12 m/s and 0.6 s behind the ball. A kick on contact, in range of the goal and on target: about 20 kicks and 1–5 goals in 16, the ducks circling the ball about 75 % of the time. Touches too, on this smaller pitch: 1–3 goals. Shots at the coach's aim once lined up within 20°, with the coach's sharper turn: 8 goals in 16. The referee decides where a struck ball goes; getting to it, on its feet and facing the right way, is the policy's. Rules out a real kick, for now. |
| **Two ducks on the ball: nobody strikes** | Whose kick a scramble is cannot be decided without favouring one end. While the rules were set, 24 plays of the reference against itself: 10 goals with the rule (6 from end 0, 4 from end 1), 11 without (4 and 7). |
| **Coaches mirrored through the centre spot** | With both coaches aiming beside the same post of the world, a kick-off seen from end 1 was not end 0's, and the reference against itself scored 3 goals from one end and 8 from the other (24 plays, while the rules were set). Mirrored, both aiming to their own left on odd seeds and to their right on even ones: 6 and 4. As shipped, on seeds 1–24: 3 and 6. A match plays every seed from both ends, so neither policy keeps one end's start perturbation or servo delays, which each duck draws from its own end's streams (`arena.runner._streams`). |
| **A Reachy Mini in each goal, on a rail, a step behind the ball** | A keeper as quick as the ball leaves nothing to score, and one that stands still makes a shooting gallery. On a rail along its line, it covers the middle and leaves room at either post. Going where the ball was 0.4 s before, no faster than 0.25 m/s, it can be beaten by a ball moved across it. The reference against itself: 9 goals and 15 saves in 24 plays. To the physics it is a cylinder; on the page, the Reachy Mini the jury is. |
| **A keeper touches nothing but the ball and the ducks** | While the rules were set, a keeper that reached into its goal's roof was held there by friction: 38 N moved it 4 mm, and the goals scored then went in past a keeper that did not move. Now it rides 2 mm up, out of contact with the whole course, under a bar 0.3 m high. |
| **A goal through the mouth; a hollow ball; boards 0.2 m high** | While the rules were set, a livelier ball flew over the boards, and a referee that counted any ball past the line gave 14 goals in 16 plays, 13 of them to one end. So a goal is the ball wholly over the line, between the posts and under the bar, and a ball past an end line anywhere else is out of play. The ball is a 30 g shell that rolls, and the boards are 0.2 m high: at 0.12 m, ducks turning hard against them fell. None of the 72 plays measured with the reference went out of play. |
| **The referee puts a stuck ball back** | A ball pinned against a board, or between two ducks, stops a play, and the walkers seldom free it. After 3 s it is put down on the nearest free spot, and the play goes on. The reference against itself: 13 stuck balls put back in 24 plays. |
| **A duck down stays down; both down, no goal** | Every event's fall rule, with the same numbers. A fallen duck does not get up, so it is out of the play and its goal is left to its keeper; but the play goes on, and a goal is still scored on the pitch. Against the two leaders, which went down in every play, the reference scored in 9 of 24 plays each, at 4.38–19.28 s. Both down, nothing more can happen: no goal. Rules out a fall given away as a goal. |
| **Held on its mark until the horn** | Asked to stand through the settle, a policy that does not listen walks off before the clock starts; held, every play starts at the horn with both ducks where they were put and the ball between them. The two leaders, which walk off their marks if not held (as measured for the tug of war, in #2), go down soon after the horn: here in all 48 of their plays against the reference, at 0.48–1.44 s. Not measured here without the hold. |
| **A 20 s whistle** | While the rules were set, plays of 30 s gave the reference against itself the same 10 goals in 24 as 20 s did, and 6 plays with both ducks down rather than 4: longer plays added falls, not goals. As shipped, the last goal came at 18.60 s. |
| **Goals, and a league's points** | A match is won on goals. The table counts matches as a league does, 3 points a win and 1 a draw, then goal difference and goals scored: a 3–0 counts for more than a 1–0 only on a tie. |
| **A void play: no goal. A fault gives the goal away** | A simulation that MuJoCo had to reset leaves nothing to judge. A policy whose action is not a number leaves MuJoCo driving no servo at all, its rival's included, so the rival is given the goal; two at once, nobody. None of the 96 plays measured was void or faulted. |

## What was measured

The match as shipped, on a Mac (Darwin-arm64) with MuJoCo 3.10.0, onnxruntime 1.24.4 and numpy
2.4.1: 24 plays of each pair below, seeds 1 to 24 once each, the first-named policy kicking off
from end 0. (A match plays three seeds from both ends; these are 24 seeds from one end.) The
entrants: the reference walker (`BEST_alpha_walking.onnx`, the golden run's policy), two policies
from near the top of the sprint board (0.860 s, *sprint-a* and *sprint-b*), and two from near the
top of the hill board (0.780 s, *hill-a* and *hill-b*).

| End 0 v end 1 | Goals (end 0–end 1) | Whistle | Both down | Saves | Stuck balls put back | Plays with end 0's duck down / end 1's | Wall time |
| --- | --- | --- | --- | --- | --- | --- | --- |
| reference v reference | 9 (3–6) | 12 | 3 | 15 | 13 | 4 / 4 | 9.1 s |
| sprint-a v reference | 9 (0–9) | 8 | 7 | 18 | 14 | 24 / 7 | 8.4 s |
| hill-a v reference | 9 (0–9) | 9 | 6 | 21 | 9 | 24 / 6 | 8.2 s |
| sprint-a v hill-a | 0 | 0 | 24 | 0 | 0 | 24 / 24 | 0.8 s |

- The reference against itself scored at 3.78, 3.78, 5.02, 6.10, 6.30, 6.78, 15.92, 16.82 and
  18.60 s. It took 21 shots (10 from end 0, 11 from end 1) and 118 touches. A duck went down in 5
  of the 24 plays, both in 3 of them.
- Against the leaders, the reference scored 9 in 24 against each: at 5.04–19.28 s against
  sprint-a, and 4.38–18.34 s against hill-a. The leaders went down in every play, sprint-a at
  0.48–1.44 s (median 0.56) and hill-a at 0.56–0.76 s (median 0.60), and never struck the ball. The
  reference, alone on the pitch, still had to beat a keeper (18 and 21 saves), and went down itself
  in 7 plays against sprint-a (at 4.6–18.8 s) and 6 against hill-a (at 4.18–18.02 s).
- Between two leaders, both went down in every play, and nobody scored.
- No ball went out of play in the 72 plays with the reference, and none of the 96 plays was void or
  faulted. A play played again ends the same, at the same step.
- A match between walkers takes about 2 s on a Mac (0.38 s a play), and one between ducks that go
  down at once about 0.2 s.

A match from the shell, the reference against itself (two files with the same name are told apart
by their position):

```
$ arena football reference.onnx reference.onnx
Football: seeds 1, 2, 3, each played from both ends; the first goal ends a play, the whistle at 20 s
seed 1  reference (1) | reference (2)  goal, reference (1), at 3.78 s
seed 1  reference (2) | reference (1)  goal, reference (2), at 3.78 s
seed 2  reference (1) | reference (2)  both down at 12.42 s: no goal
seed 2  reference (2) | reference (1)  both down at 12.42 s: no goal
seed 3  reference (1) | reference (2)  goal, reference (2), at 16.82 s
seed 3  reference (2) | reference (1)  goal, reference (1), at 16.82 s
reference (1) 2–2 reference (2)
```

With one policy at both ends, swapping ends changes nothing but the names: each seed's two plays
are one play, and a policy against itself draws every seed. Against a leader, renamed:

```
$ arena football sprint-a.onnx reference.onnx
Football: seeds 1, 2, 3, each played from both ends; the first goal ends a play, the whistle at 20 s
seed 1  sprint-a | reference  goal, reference, at 11.36 s
seed 1  reference | sprint-a  both down at 4.58 s: no goal
seed 2  sprint-a | reference  goal, reference, at 5.66 s
seed 2  reference | sprint-a  both down at 5.66 s: no goal
seed 3  sprint-a | reference  goal, reference, at 6.26 s
seed 3  reference | sprint-a  goal, reference, at 5.46 s
sprint-a 0–4 reference
```

(Seed 2's two plays ending on the same step is a coincidence: they are different plays.) A round
robin of the five files:

```
$ arena football reference.onnx sprint-a.onnx sprint-b.onnx hill-a.onnx hill-b.onnx
Football: seeds 1, 2, 3, each played from both ends; the first goal ends a play, the whistle at 20 s
reference 4–0 sprint-a
reference 2–0 sprint-b
reference 3–0 hill-a
reference 1–0 hill-b
sprint-a 0–0 sprint-b
sprint-a 0–0 hill-a
sprint-a 0–0 hill-b
sprint-b 0–0 hill-a
sprint-b 0–0 hill-b
hill-a 0–0 hill-b

 #  policy     won  drawn  lost  for  against  points
 1  reference    4      0     0   10        0      12
 2  hill-b       0      3     1    0        1       3
 3  sprint-b     0      3     1    0        2       3
 4  hill-a       0      3     1    0        3       3
 5  sprint-a     0      3     1    0        4       3
```

It took 7.3 s. The leaders draw 0–0 among themselves, every play ending with both down, and are
told apart only by how many goals the reference put past them.

**One platform.** These numbers are from a Mac, where a match played again comes out the same.
Physics on two platforms part ways within seconds, as `arena/golden.py` records for the sprint, so
a play that lasts seconds can end differently on Linux-x86_64, the Space's platform. Not measured
there.

## Design

### 1. The format: `arena/football.toml` (`load_football`)

- Top level: `id`, `title`, `rig`, `kind`, `time_limit_s` (the whistle) and `seeds`. Then
  `[command]` and `[start]` (`keyframe`, `settle_s`, `setback_m` and `[start.perturbation]`);
  `[pitch]`, `[goal]`, `[ball]`, `[keeper]`, `[save]`, `[strike]` and `[restart]`, each read into
  a dataclass of its own; and `[termination]`, as an event's.
- Validation, each refusal a `ManifestError` naming the file:
  - every table is a table, and unknown keys are refused at every level;
  - `id` is a non-empty name, `rig` and `kind` among a manifest's, and `seeds` a non-empty list of
    distinct whole numbers;
  - `fall_gravity_z` is a number strictly between −1 and 1, and `fall_hold_s` at least one control
    step (0.02 s);
  - every other number is finite and positive. The ball's spin and rolling friction, how far a
    keeper stands in front of its line, the strike's scatter, the settle and the perturbation may
    be zero. A boolean is not a number;
  - the pieces fit together: some end board between each goal's mouth and the corner cuts, some
    side board between the cuts, a rail for each keeper (its goal wider than the keeper and the
    gaps at both posts), and a ball that fits under the bar;
  - each duck starts with room in front of its own keeper, and the restart spots are on the pitch,
    inside the corner cuts;
  - the strike's three angles are under 180°, and the save's cone is under 90°.
- A `Football` carries a `manifest.Start` and a `manifest.Termination`, for the runner's opening
  and every event's fall rule. Two measures follow from the rest: `keeper_x_m`, how far from the
  centre spot each keeper's rail runs, and `rail_m`, how far a keeper can slide from the middle of
  its goal, either way.
- `load_football()` reads `arena/football.toml` (`FOOTBALL_TOML`); given a path, it reads that
  file instead, as the tests do to try a malformed match.

### 2. The model (`compile_football`)

- Duck 0 is the rig's MJCF with its servos as motors (`course._motorized`), as in every event. The
  model has the physics step and a `course` body that holds the floor, the boards and the nets:
  `board_boxes()` (the two side boards, the end boards either side of each goal, and the four
  corner boards: 10) and `net_boxes()` (each goal's back, sides and roof: 8). Those two functions
  serve both the physics and the page that draws the pitch.
- Duck 1 is the same rig, attached under its prefix on the far side of the centre spot and turned
  180°: the two face each other across it.
- The ball: a free body, a sphere of the ball's radius and mass with a shell's inertia
  (`mjINERTIA_SHELL`), `condim` 6 and friction (0.8, spin, roll).
- A keeper in each goal, `keeper0` at −x and `keeper1` at +x, on the line `keeper_x_m` from the
  centre spot: a cylinder 2 mm off the turf on a slide joint across the goal, limited to
  ±`rail_m`, and excluded from contact with the `course` body, so that it touches the ball and the
  ducks and nothing else. Its servo is a position actuator (kp 400, kv 40), its force limited to
  ±40 N.
- A `mark` for each duck, a mocap body, and a weld `hold` from the duck's trunk to its mark, off
  until the opening switches it on.
- The keyframe stands both ducks in the default pose, `setback_m` either side of the centre spot
  and facing each other, with the ball on the spot and both keepers mid-goal.

### 3. The play (`run_play`)

- The opening (`_opening`) is every run's reset, perturbation and servo delays (`runner._start`,
  given the ducks' yaws, `YAWS_DEG`); then the settle, each duck held on its mark and asked to
  stand, its policy running on through the hold as through any settle. At the horn the holds are
  switched off.
- Then (`_Pitchside.play`), every control step:
  - the keepers: both servos are sent towards the ball's y as it was `lag_s` before, clipped to the
    rail, each target moving no farther in a step than `speed_m_s` allows;
  - each duck's command: its coach's forward speed and turn rate, no sideways speed, and the head
    and body as `[command]` has them; a duck that is down is asked to stand still;
  - the step; then a void (`_diverged`), a fault (`_faulted`), and the referee's look (`judge`).
- `judge`, at the ball where the step left it:
  - the strike (`_strike`), from the contacts with the ball: exactly one duck touching it, on its
    feet, its cooldown over, the ball within `front_deg` of its heading. A shot, within
    `shot_range_m` of the goal line it attacks and facing its coach's aim within `align_deg`, goes
    at the aim at `shot_speed_m_s`; else a touch, its heading within `touch_cone_deg` of the goal's
    middle, goes along its heading at `touch_speed_m_s`. Either way the line is turned by up to
    `noise_deg` and the speed scaled by 0.9–1.1, and the ball is set rolling; then that duck's
    cooldown (`shot_cooldown_s` or `touch_cooldown_s`), and a `shot` or a `touch`;
  - a stuck ball (`_unstick`): one that has not moved 5 cm in `stall_s`, a duck on its feet within
    `jam_m` of it all the while, is put back: a `stall`. A ball is put back (`_restart`) at rest on
    one of five spots, the centre spot and one in each quarter of the pitch
    (±`spot_x_m`, ±`spot_y_m`): the nearest with no duck within `free_m` of it, on its feet or
    down, or the nearest of all if none is free;
  - the saves (`_saves`): a ball against a keeper for `hold_s`, that keeper's cooldown over, is
    sent up the pitch at `speed_m_s`, within `cone_deg` of straight on: a `save`;
  - a ball out of play (`_out`) is put back: an `out`, and nothing more that step;
  - a goal: the ball's centre over a goal line by its radius, which counts only in the goal's
    mouth, between the posts and under the bar; anywhere else, the ball is out. Over the line at
    +x, end 0 has scored; at −x, end 1;
  - the falls (`_falls`): every event's rule, counted from the horn. A duck down stays down: a
    `fall`. Both down ends the play.
- The scatter on strikes and saves is drawn from a stream of its own (`_strike_rng`: the match's id,
  the seed and 4, after the runner's `_streams`), so no duck's start or servo delays move with it.
- The coach (`_Coach`) is the one the rules describe. Given its duck's position and heading, the
  ball, and where the keeper it shoots past stands, it picks its aim, then its target (behind the
  ball, round it, or through it), kept inside the boards (`_inside`), and answers a forward speed
  and a turn rate (`_drive`); facing a board, it stops its duck or backs it off, and turns it hard
  (`_wall`, where a goal's mouth counts as board).
- `Play(seed, scorer, end, time_s, events)`: the scorer is an end (or `None`), and `end` is
  `"goal"`, `"fault"`, `"down"`, `"whistle"` or `"void"`. A fault's goal is the other end's; two
  at once, nobody's. `events` (`Event(time_s, kind, k)`) are what the referee saw: shots, touches,
  saves, falls, a ball out and a ball stuck, each with the end (`k`) whose duck struck the ball or
  went down, or whose keeper saved it, and `None` for a ball put back.

### 4. The match, the round robin and the table

- `play_match(football, a, b)` plays every seed from both ends on one compiled model, A from end 0
  first. `Played.scorer` turns the scoring end into A or B; `Match.goals` counts A's goals and B's,
  one a play at most, since the first goal ends it; and `Match.winner` is whoever has more, or
  nobody.
- `round_robin(football, policies)` plays every pair once, on one model.
- `standings(names, matches)` counts each policy's matches won, drawn and lost, its goals for and
  against, and its points (3 a win, 1 a draw), and sorts by points, then goal difference, then
  goals scored, then name.

### 5. The shell (`arena football`)

- `_cmd_football` checks what it is given before anything is played: two policies or more, and
  `--watch` with exactly two, on a free port (`_port`: a whole number from 1 to 65535).
  `_entrants` loads and names the policies: two files with the same name are told apart by their
  position.
- Two policies: a heading (the seeds, each played from both ends, the first goal ending a play,
  the whistle), a line per play (the seed, who kicked off from each end, and how the play ended,
  as `_football_how` says it), then the score.
- Three or more: each match's score, then the table: won, drawn, lost, for, against and points.

### 6. Watching a match (`arena football A B --watch`)

- Two policies only, a free port (`--port`, 8767 by default, clear of the workshop's 8765 and the
  tug of war's 8766 in #2), the match played and printed, then served on 127.0.0.1 until Ctrl-C,
  and a browser opened on it unless `--no-browser` is given.
- `record_match` is `play_match` with every play recorded (`record_play`). A recorded play is
  `run_play`'s: the same opening and the same referee, which appends each step it judges as a frame
  of both ducks (`_frame`, `TRACE_WIDTH` each) and a frame of the props (`PROP_WIDTH`, 9: the
  ball's position and quaternion, then each keeper's place on its rail). Recording only reads the
  physics, so the play is the same recorded or not. `Recorded` holds the play, its settle's frames,
  its trace, the props at kick-off (`kickoff`, where they stand through the settle) and its props.
  A goal runs on for `TAIL_S` (1.5 s), both ducks asked to stand still and the keepers tracking the
  ball, so a replay shows the ball in the net; the tail stops if the simulation diverges. No other
  ending has a tail, and a void play's last step, the one MuJoCo had to reset, is not recorded.
- `arena/football_watch.py` (`create_football_app`) answers from memory:
  - `/api/football`: the match (its id, title, rig, control step and whistle) and the two
    names; the pitch as built (its measures, and the boards and nets where `board_boxes` and
    `net_boxes` put them); the goal's measures, the ball's radius, and the keepers' size, line and
    rail; how far from the centre spot the ducks start, the fall rule's hold, and the goals each
    policy scored; and each play: its seed, who kicked off from each end, the scorer, how and when
    it ended, what the referee saw, the props at kick-off, and how many frames its settle and its
    play have;
  - `/api/football/plays/{k}/trace` and `/api/football/plays/{k}/settle`: the frames, as every
    trace is served (`routes_read.frames_response`); `/api/football/plays/{k}/props`: the props,
    little-endian float32, frame by frame, their count and width in the headers;
  - 404 for a play the match does not have;
  - `/`: `football.html`, from the built site. Without a build, `/` answers 503 and says how to
    build it.
- The venue (`app/src/football-venue.js`) is drawn from the pitch the server describes, where the
  physics has it: turf mown in stripes and cut at the corners; the pitch's outline, the halfway
  line, the centre circle and spot, and each penalty area and its spot, painted on it; glass
  boards under a cyan cap, so that a duck by the near board is not hidden; white posts and string
  nets round each goal's pocket; and the ball, white with black panels. In each goal a Reachy
  Mini, the jury's model cloned with its shell tinted lime (keeper 0, on the left) or magenta
  (keeper 1), slides along a steel rail, its head turned to watch the ball as far as its neck
  goes. Round the pitch the viewer builds what every event has: the hall, the jury, and the
  stadium's stands, six tiers of microducks along each side, the near one set back behind the lens.
  The venue adds a stand behind each goal, from the stadium's own parts (`buildStand`, `seats`,
  `crowd`), so that `stadium.js` is as it was: a side stand turned end on, its first tier 0.1 m
  beyond the venue's end and its back short of the hall's end wall, six tiers of eight microducks
  facing the pitch. About 1.9 m across, it stops inside the floor's edge, clear of the far side's
  rail and cones, which run on past the pitch's ends. Their one crowd cheers and does the wave with
  the others, without speech bubbles, which would pop up at the very moment the side stands' do.
- The camera stands on the near side, square to the pitch, 2.15 m out from its long axis and 1.2 m
  up, aimed 0.37 m above the turf. It follows the ball along the pitch: the ball's x smoothed over
  0.6 s either side, three quarters of the way, and no farther than 0.55 m from the centre spot,
  so that a goal and the half it is in fill the picture. A drag lets it go, and "Back to the
  touchline" brings it back.
- The crowd rises at the horn, builds as the ball nears either goal, cheers a goal (one given for a
  fault too) and mourns a play both ducks went down in. The whistle, two faults and a void play
  leave it nothing to feel.
- The page (`app/football.html`, `app/src/football/`, `app/public/football.css`) is set in the
  Arena's trackside sheet (`race.css`), with a sheet of its own (`football.css`) for what the
  Arena has no component for. On the left is the stage, under the match's name and facts (the
  pitch, the goals, the whistle and the plays), with the play's clock. On the right are the goals
  in the scoreboard's flip tiles, the plays (who kicked off from each end, and how each ended),
  Pause and Replay play, and the rules in a few lines, the lime and magenta keepers named in their
  colours. The plays play in order, the next 2.5 s after the last has ended, until the visitor
  picks one or pauses.
- While a play is on, a caption says the last thing the referee saw, for 1.4 s, in its duck's
  colour or its keeper's: "A shoots", "Saved!", "B down", "Out" or "Ball back in". A touch is not
  news. Once the play is decided, the stage says so: a "Goal!" or "Given" stamp in the scorer's
  colour over its duck, or a "Both down", "No goal" or "Void" stamp; and the verdict in full,
  opposite the clock.

## Testing

**pytest** (`tests/test_football.py`, 54 tests):

- the shipped match loads with what it declares, its keepers' line and rails among it, and it is
  not an event: `manifest.all_events` does not list it;
- each malformed match below is refused, with its message: an unknown rig, a seed twice, an unknown
  key, a ball of no mass, a goal too wide for its end boards, corners that leave no side board, a
  keeper too wide to have a rail, a ball too big to fit under the bar, a start with no room in
  front of the keeper, a restart spot off the pitch, a save cone of 90°, a strike's front of 180°,
  a fall hold under one control step, and a fall line of −1.5;
- the model: both ducks, the ball and both keepers; the 18 boards and nets where `board_boxes` and
  `net_boxes` put them; each keeper on its line, its rail ±`rail_m`; and the ball's size;
- the kick-off: each duck at its end's setback, facing the other within 10°, and the ball on the
  centre spot;
- the referee, the ball put somewhere the moment the settle is over: all the way over either goal
  line, it is a goal for the end attacking it, on the first step, and on the line it is not; over a
  side board it is out, and on the nearest free spot the step after; over an end board beside a
  goal it is out; and rolled at a keeper, it is cleared back up the pitch;
- the falls: a duck that lies down is down once, and the play goes on to the whistle; two that lie
  down end the play goalless;
- a policy whose action is not a number gives every play of a match away at the first timed step,
  and two such give nobody the goal; a simulation MuJoCo resets from the first step is void, with
  no frames recorded;
- the play: the same every time and the same recorded, with a frame for every step judged and the
  tail's, the props at kick-off through the settle, and the keepers never off their rails; a goal
  recorded runs on for the tail, the ball still in the pocket at its end;
- the match: every seed from both ends, a seed's two plays the same play when one policy is at both
  ends; a goal counted for whoever kicked off from the scoring end; and the table's points, its
  ties broken on goal difference, then goals, then name;
- the shell: each way a play ends, a goal at either end and a fault by one or both included, as
  `_football_how` says it; a match prints every play and the score, and three policies print the
  scores and a table, without the plays; before anything is played, one policy is refused, and so
  are `--watch` with three, a port outside 1–65535 or one that is not a number, and a busy port;
- watching: the server answers the summary (the pitch, its boards and nets, the keepers, and the
  plays with who kicked off from each end), the three kinds of frames for every play (exactly as
  recorded) and the page, and 404 for a play the match does not have; unbuilt, the page says how to
  build it; `--watch` plays the match, prints it and serves it.

**vitest** (`app/`):

- the venue (`football-venue.test.js`, 47 tests): the layout, the stadium set out beyond the side
  boards, and a football match's event told from a race's or a stage's; the turf narrowed over the
  cuts, the boards' outline, and the stripes; the nets' strings; the props on each frame; the
  camera, following the ball smoothly and only so far, and where it stands; the ball's way to
  either goal as the crowd hears it, and the crowd's direction: a goal cheered, a given one too,
  a play both ducks went down in mourned, and nothing felt for the whistle, two faults or a void
  play, nor before the horn; a keeper's head watching the ball within its neck's reach; the ball;
  a keeper, the jury's model with its shell tinted; and the venue as built: the boards and nets
  where the physics has them, the ground and the floor, the ball and the keepers placed from the
  props, their heads turned, the camera following, a venue built without the Reachy Mini's model
  (the rails, no keepers), the crowd cheering a goal, and everything built disposed of but the
  model the jury shares; and the stands behind the goals: none without the crowd's model; two,
  mirrored, beyond the ends, wider than the boards, inside the floor's edge and short of the hall's
  end walls, casting shadows, their boxes clear of every mesh the stadium sets out but its crowd;
  96 seats, none on the pitch's axis, each on a tier and facing the pitch; the wave standing them
  up, at the end it sets off from first; a camera facing one end drawing only that end's 48, and
  every seat given back as it was; and what they build disposed of, but not the crowd's model;
- the page (`football/plays.test.js`, 19 tests): each policy's end, livery and colour, and each
  keeper's colour; the play as the viewer's event and lanes, its kick-off and decision; what the
  referee said of it, a fault and a void play included; its clock; the score as the plays are
  decided; and the captions; and (`football/hall.test.js`, 10 tests) its frame as DOM: the strip,
  the match's name and facts, the goals' tiles, the plays, the clock, caption, stamp and verdict,
  the way back to the touchline, the transport and the rules, and the keepers named in their
  colours.

The app's whole suite passes: 898 tests in 80 files.

The plays in these tests are cut short or ruled at once: the ball put where the referee must rule,
or a match of one or two seeds and 0.2–1 s, with the reference walker, a policy that holds the
default pose, one that lies down, or one whose action is not a number. One full play of the
reference against itself is played twice, then recorded, to show that it comes out the same each
time. None asserts how a full play between real policies ends, since the platforms' physics part
ways.

## Left to the owner

- **The board's format.** A perpetual league, a ladder, an Elo rating, a gauntlet, or a round of
  its own. A match between walkers takes about 2 s on a Mac, and the round robin of five above
  took 7.3 s; a full round robin of n entries is n(n−1)/2 matches.
- **A policy that sees the ball.** Today a coach steers, so every published policy can enter as it
  is. A policy that played football by itself would need the ball, the goals and its rival in its
  observation: a new observation, and policies trained for it.
- **A real kick.** The strike is assisted: once a duck has got to the ball facing the right way,
  the referee decides where it goes. A kick from the duck's own legs belongs with a policy that
  sees the ball.
- **Whose coach.** The coach is the referee's, the same at both ends. An entry could bring its
  own, and a match would then compare coaches as well as walks.
- **Kick-offs, and getting up.** A running score, with a kick-off after each goal, and a duck that
  gets up after a fall would make longer matches. Both need a duck that walks back to a mark or
  gets up, and a rule for when it is back in play.
- **The hold.** Held through the settle, the leaders go down within 1.44 s of the horn. The
  alternatives: no hold, or a duck that leaves its mark during the settle gives the goal away, as
  a false start.
- **The stands behind the goals.** The football venue builds them from the stadium's parts, and
  leaves `stadium.js`, which every event shares, as it was. They seat 96 more microducks: timed
  with SwiftShader, the Space's renderer, in headless Edge on a Mac (a 1131×918 stage), a frame
  took 1.0–1.2 s with them and without them alike, the difference lost in the machine's load.
  Built without the crowd's model, the venue has none.
- **Tie-breaks.** By name, after points, goal difference and goals scored; head-to-head or a
  play-off would be fairer.
- **Integration.** `compile_football` beside `compile_stage` in `arena/course.py`, and the play
  beside `run_stage` in `arena/runner.py`, with a two-duck trace and the props beside it. Then
  records, a board, the page played from those records rather than from `--watch`, a clip of the
  ducks and the ball, the commentary, and a worker that plays the matches as entries arrive.
- **One platform.** A board must play all its matches on one platform (the Space's), or a rematch
  could disagree with the result on the board.
- **Beside the tug of war (#2) and red light, green light (#3).** The pull requests are
  independent, and any of them can be merged first. Football and #2 both add a command to
  `arena/cli.py` with the same port check (`_port`), a page to `app/vite.config.js` and a venue
  to `app/src/viewer.js`, so whichever lands second keeps both in those three files, with one
  `_port`. Football and #3 meet only in `app/src/viewer.js`, at the two places where #3 meets #2:
  the name plate, where a football duck, which has no follow-spot, keeps its own colour, and the
  chase camera's call, where `venue?.camera` goes inside #3's `inRoom`. The football camera
  stands 1.2 m up, under the 2.03 m ceiling #3 gives the hall, and straight across from the ball,
  so `inRoom` leaves it where it is: stills of that merge differ from football's alone only in the
  crowd, which differs as much between two loads of one build. Both merges were made and tested:
  with #2, `vitest` (944 tests), the build, and `pytest` on both matches (134) pass; with #3,
  `vitest` (929), the build, and `pytest` on football, the lights and steering (106) pass.
  Football keeps its own opening, void and fault checks and frame of both ducks in
  `arena/football.py`, much as #2's `arena/duel.py` has them; once both are in, they could share
  one copy.

## Out of scope

- Teams, with several ducks a side.
- New observations: a policy never sees the ball, the goals or its rival.
- Rollers: the match is declared, and was measured, on legs.
- The site: records, boards and clips. The page plays only what `arena football --watch` serves
  on 127.0.0.1.
- Real robots.
