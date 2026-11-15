# Versus: the tug of war and the weekly cup — design (2026-10-19)

## Why

The owner, 2026-10-19: the Arena gets a new kind of challenge, the **versus**. Ducks from several
players, each driven by its own published policy, meet in the same physics at the same time. The
first versus is a **tug of war**: two microducks face each other, tied by a string at the base of
the neck, with a pit between them. The one that does not fall in the pit wins.

Two things make a versus hard, and they shape this whole design:

- **Who plays whom.** Ranking every policy against every other is N·(N−1)/2 matches: about 300
  for the ~25 players on the races today, ~5,000 for the ~100 policies. The physics is cheap
  enough; the clips (one HF Job each) and the time to watch are not.
- **Chaos.** A 1 µm change of a start turns one run into another (measured on the rollers,
  2026-10-14). Between two close policies, one bout is close to a coin flip, and a Mac never
  reproduces the Space's x86 numbers.

The owner's answer, refined in this session: a **rating** every policy gets on its own the moment
it is published (bouts against a reference duck), and a **weekly cup** in which the entrants meet in groups
then a knockout, simulated ahead and premiered on the live channel, where Peter & Ray call every
match like a real sports broadcast.

## Words

- **Versus event**: an event whose entries meet each other. `tug-of-war` is the first.
- **Bout**: one tug of war between two ducks, up to the bout time limit.
- **Match**: first to win two bouts, sides swapped between bouts.
- **Reference duck**: a frozen policy shipped with the Arena. Five bouts against it give a policy
  its **rating**, in centimetres of marker displacement (plus a pit bonus).
- **Ring**: the tug's playing area, a square wrestling ring; its **ropes** are the field's edges.
  The line between the two ducks is the **string** (a physical rope since 2026-10-21).
- **Cup**: one weekly tournament of the event, numbered (#1, #2…): draw, groups, knockout,
  premiere.
- **Premiere**: the scheduled moment the cup's results go public, as the live channel's show.

## Goals

1. Any player can train a tug-of-war policy with the challenge recipe, publish it with
   `uv run publish --enter`, and get within minutes a rating, a board place, points and a clip,
   exactly like a race today.
2. Every week, every player's latest entry is in a cup automatically, plays at least two matches,
   and every match has its clip.
3. The cup is a show: at a fixed time the live channel airs the whole cup, every match in full,
   Peter & Ray at the desk with the cup's state on a big screen behind them, calling each match as
   it plays, with commentary that knows the tournament.
4. The cup machinery (calendar, draw, groups, knockout, secrecy, premiere, cup page) is generic to
   versus events; what is specific to the tug of war (string, pit, judge, reference duck) is the event's.

## Non-goals

- Policies that perceive their opponent (sumo, football…). A tug policy is blind, as every Arena
  policy is today: proprioception and a fixed command. A future versus that needs perception will
  change the observation contract; not now.
- Self-play between two learning policies. The recipe trains against a FROZEN opponent duck (a
  league of frozen opponents comes later).
- Rollers. Pollen's roller reference can neither brake nor reverse; the event is `rig = "legs"`.
- A time limit on the show. The owner: "no limit; we'll set one later when it becomes a problem."
- A Pollen reference in the cups. There is none (owner's decision, below).
- Another versus challenge, or a recurring-automatic anything beyond the weekly cup.

## Anti-goals

- A cup whose results leak before the premiere (an API answer, a clip URL, a board change, a
  commentary line): the premiere is the event.
- A live show that stalls or improvises: nothing on air waits for an LLM or a render.
- A rating or a cup result computed anywhere but on x86 (the Space, or an x86 HF Job running the
  Space's image). Never re-score on the Mac: a Mac re-race diverges from the Space after 1–3 s.
- A training environment whose string, pit or bout differs from the Arena's. Every physics
  difference between training and the Arena has cost a retrain before (the BAM lesson, 2026-09-28).
- Changing any existing event's physics: the golden run and every published run stay as they are.

## Constraints

- The site, code, docs, clips and commentary are English only.
- Events are data (`arena/events/*.toml`, strict loud validation in `arena/manifest.py`).
- Clips render only on HF Jobs (t4-small, at most `ARENA_CLIP_JOBS` in flight, pending markers as
  the to-do list); the Space renders nothing.
- The run log is the private dataset `ARENA_DATASET`; a Space restart rebuilds everything from it.
- The physics is MuJoCo through the troupe machinery (`compile_stage`, `run_stage`, `cast_of`):
  several robots in one model, prefixed `duck{k}/`, colliding with each other. Lone-duck runs stay
  bit-identical.
- Booth commentary is never gated by a script filter; bad lines are fixed in the prompt
  (owner, 2026-10-12). Jokes must land for newcomers.
- No dead code, no just-in-case generality.

## Owner decisions, 2026-10-21 (after the local preview)

The owner watched the game locally and decided three things. They change §1 (course, string,
marker, venue), §2 (the reference duck) and §3 (training), updated in place below. Nothing is
released, so every rating is simply computed again.

1. **A real rope.** The string is no longer a tendon (a maximum distance, drawn as a straight
   line, passing through bodies): it is a physical rope, exactly as prototyped and measured on
   2026-10-21 (the rope study; its numbers are in §1). Same 1.00 m neck to neck, the ducks
   starting where they start today, no extra slack. The owner chose the measured rope (16
   segments, 80 g, normal friction) knowing that it does not prevent crawling (a prone duck lies
   on its rope and pins it by friction) and that its weight hanging in the pit draws stalemates
   into it. The marker is the rope's middle point. The rope's shape is recorded at every control
   step, so the pages, the clips and the live draw it as it really was.
2. **A wrestling ring.** The tug of war gets its own venue: a dark arena, a circular lighting
   truss, LED screens, barricades, and a square ring 3 m × 3 m. The ring is the playing area: no
   more 0.8 m lane and walls; the ring's ropes are the field's edges and the ducks bounce off
   them; the 0.30 m pit crosses the ring in the middle from rope to rope (3 m long). Races and the
   Got a Talent stage keep the daytime stadium. The dark halo under the robots' feet is removed
   from every scene, each scene's lights casting the ducks' real shadows.
3. **Upright ducks for the owner.** The reference duck (the rating's yardstick) and the owner's
   candidates stay on their feet: leaning back like a tug-of-war puller is fine, crawling and
   lying are not. Other players may crawl. An opt-in training knob, "stay upright", off in the
   recipe users get, is on for the owner's trainings. A new upright reference, trained on the
   ring and the rope, replaces t7-250 as the vendored reference (every rating changes); then the
   owner's candidate is trained upright from it and picked as before (gates, round robin; warm
   start wins, runs peak early and decay, so every 250 iterations is judged and the peak kept).

Everything is re-rated and retrained. Plans C and D (cup, show) are unchanged except where they
draw the string or read the course. Plan G (the Arena) and Plan H (the training) implement this.

### My calls (2026-10-21)

The owner approved them all on 2026-10-21, with these four in particular: the upright line
(t10-500's posture is sitting, not leaning), the strongest upright reference even if most
players' ratings start negative, the name "string" on the site, and the decor as built.

- **Rope joints: two hinges, not a ball.** Each joint between segments is two hinges (about y,
  then z), the study's "Ru", instead of a ball joint ("R"). Both were measured equally stable (0
  resets in 40 Arena bouts, ends never more than 1.0024 m apart, ties within 7.0 mm against
  5.5 mm). Ru drops the twist, which a round capsule chain cannot show and which a contact barely
  feels, and it costs less: an Arena bout ×1.38 instead of ×1.54, training throughput ×0.73 instead
  of ×0.42–0.54, nv 76 instead of 91, +0.6 GB instead of +1.0 GB on the L4. It also removes the
  twist inertia that turned mujoco_warp's float32 solve to NaN (2-hinge was NaN-free even without
  armature); the armature stays as measured. Every training of this round runs on it, so the
  throughput decides.
- **Rope numbers, as measured and never lowered** (each step down was unstable at the 5 ms step):
  16 capsules of 6.25 cm, radius 4 mm; 80 g, the two end pieces 15 g each, the 14 others
  3.5714 g; joint damping 0.003 N·m·s/rad on every hinge and armature 1e-6 on every rope degree of
  freedom (the free root too, which has no damping); a free root at the middle segment, two chains of 8 out to the ends; each end
  tied to its duck's `string_end` site by a site-to-site `connect` with solref 0.01; contacts
  contype 0 / conaffinity 1 / priority 1, friction 1 / 0.005 / 0.0001, default solref and
  solimp; each end piece excluded from the trunk it is tied to. The rope starts straight.
- **The ring's edges**: three rigid capsules a side, radius 6 mm, their axes 6, 12 and 18 cm over
  the canvas, post to post on the 3 m square; four corner posts, capsules of radius 2.2 cm, 23 cm
  tall; and behind each side an invisible backstop box, flush behind its ropes, from the canvas to
  the top rope's top. Why the backstop: rigid capsules alone leave 5.4 cm under the bottom rope and
  4.8 cm between two ropes, where a foot, a head or a prone duck pushed sideways can thread through,
  and a duck outside the ring with the string across a ring rope is a bout nobody can read. Behind
  the ropes it changes nothing the viewer sees. The floor still runs 20 m past the ring at the
  canvas's level, so no duck is ever below the floor but in the pit (the judge's "in the pit" is
  a height).
- **Upright, measured** (superseded on 2026-10-22 by walking upright, below): trunk height ≥ 7 cm and tilt ≤ 45°; a duck is **down** once it has not
  been upright for 0.3 s straight (the fall rule's hold). From the robot: standing, the trunk
  stands 11–12 cm; a sweep of the legs robot's poses with only its feet on the floor keeps it at
  7.8 cm or more leaning back up to 45°; the leaning t10-500 sat low at 4.5 cm, tilted 57°, its legs
  carrying it (measured later: no trunk–floor contact); a lying duck sits at 3.6 cm. Tilt is the trunk's angle from vertical,
  as `moments.py` reads it.
- **The knob**: `stay_upright` in the recipe's `challenge.toml`, the cost of going down, in pits.
  0, the users' default, lets a duck crouch, sit or lie as the Arena allows; above 0, going down
  ends the training episode and costs that many pits (the owner trains at 1). The recipe's
  existing reward knob labelled "Stay upright" is relabelled "Keep the trunk level", which is what
  it pays.
- **The new reference** (t15-250 was picked this way; superseded on 2026-10-22, below) is warm-started from t7-250 and trained against the frozen t7-250 (the
  opponent as today), stay upright on. Not self-play: that is a non-goal and new machinery, and
  t7-250 is the yardstick it replaces, so its rating against t7-250 on the new physics measures
  it. Picked by: upright and pulling (gates U and R1), then the highest rating against t7-250,
  a round robin deciding between ratings within 5 cm.
- **The owner's candidate** (t17-250 was picked this way; superseded on 2026-10-22, below): warm-started from the new reference, trained against it, stay upright
  on; gates R1, R2 (rating ≥ +20 cm against the new reference), R3 (≥ 3 of 10 bouts dragging it
  in, a target), plus U; the round robin picks.
- **No slack phase** any more (the string slack until iteration 250): a rope has no limit to lift,
  and every training now starts from a duck that already walks back (t11, taut from the first
  step, passed the gates by 250).
- **Taut**, for the judges: the string's ends at least 0.98 m apart. An 80 g rope sags: 0.98 m is
  about 1.1 N of pull, the mean pull of two reference ducks on it; the tendon's 0.995 m would ask
  about 2.5 N.
- **Trace**: a tug's bout file gains `string`, (frames, 17, 3), and `string_settle`, (settle + 1,
  17, 3), float16 like the ducks (0.24 mm off): a 45 s bout grows from 96 KB to 228 KB. The key's
  presence is the version: every stored race and performance stays as it is; a tug trace always
  carries its string (none exists in production; test fixtures are rebuilt with one).
- **Names**: in code and on the site the line between the ducks keeps its name, the string
  (`string_m`, `string_end`, `buildString`); "rope" in the owner's words is the string here, and
  the ring's edges are the ropes. A tug's `[course]` is `ring_m`, `pit_m`, `pit_depth_m`,
  `string_m`; `length_m`, `width_m` and `wall_height_m` go. The string's and the ring's numbers
  are code constants (the measured, stable ones), not event data.
- **Stability**: the Arena's string is checked again on the study's 40 bouts (0 resets, ends at
  most 1.0030 m apart, ties within 1 cm) before anything trains on it; any later change of its
  numbers repeats that check.
- The venue mockup's open decor questions (the jury at ringside, the pads' colour, the screens, the
  portrait clip's near rope, a wide establishing shot) stay as built; they block nothing.

## Owner decisions, 2026-10-22 (walking upright)

A posture probe (2026-10-22) measured how the owner's ducks pull. The reference t15-250, the
candidate t17-250 and the users' t19-250 do not lean back: they bow forward 33–44° towards the
other duck, the neck swung 50–85° further down, the trunk at 7–8 cm. The head is planted beak-down
on the floor 12 cm ahead of the trunk in 77–83 % of the frames. It carries about 40 % of the floor
load, gives about half of the backward friction, and rests on the string, pinning it. The feet
slide: 58–73 % of their travel happens while they touch the floor. The robot walking backwards
(BEST_alpha_walking at −0.40 and −0.60 m/s) holds its head at 23.6 cm, its trunk at 12 cm, pitched
−3 to +2°, its feet under the trunk, only the feet on the floor, and steps: 3 % of its foot travel
happens in contact. The owner decided three things. They change §2 (which duck the reference is)
and §3 (how the owner's ducks train), updated in place below. Nothing is released, so every rating
is simply computed again.

1. **Walking upright, for the owner's ducks.** "The robot still uses its head to pull. I want it to
   stay standing; it should just walk backwards while pulling." The Arena's reference duck and the
   owner's candidate train to walk upright like the robot's normal gait (the option "like its
   normal walk"):
   - the head high (≥ 18 cm) and the trunk at 10 cm or more;
   - pitched between 10° bowed towards the opponent and 20° leaning back away from it, rolled 10°
     at most;
   - the neck and head pitch within 30° of STAND;
   - only the feet on the floor, stepping rather than sliding.
2. **Other players stay free.** A head on the floor is allowed and the Arena's rules do not change:
   only the pit decides. Accepted: head-planting ducks will beat the upright reference easily, so
   many ratings will be very positive.
3. **The rope and the scene stay as they are.** No change to the Arena's physics or venue.

### My calls (2026-10-22)

- **Walking upright, measured.** A frame is **upright** when all of these hold:
  - the trunk at z ≥ 0.10 m;
  - the pitch in [−10°, +20°];
  - |roll| ≤ 10°;
  - the head's centre of mass (body `jaw_soft`) at z ≥ 0.18 m;
  - `neck_pitch` and `head_pitch` within 30° (0.5236 rad) of STAND (both 0.349 rad);
  - no part of the duck but its feet (bodies `ankle_left`, `ankle_right`) touching the course.

  The bands come from the walker's envelope over six runs: trunk 11.0–12.4 cm, pitch −2.7..+2.1°,
  roll ≤ 4.7°, head 22.6–24.1 cm, neck −4.7..+11°, head pitch −8.3..+5°, only the feet down. Each
  band leaves 1 cm to 7° of margin. The +20° of leaning back is a physics estimate, not a
  measurement, since no walker ever pulled: a ~2.5 N string held at the 15 cm tie needs the centre of
  mass about 5 cm behind the feet. A duck is **down** once it has not been upright for 0.3 s straight
  (15 control steps), the hold the fall rule and the 2026-10-21 rule use.
- **The pitch's sign.** + is the trunk's top leaning away from the opponent. The pitch is read off
  the trunk quaternion (w, x, y, z) as asin(2(xz − wy)): the z of the trunk's forward axis, R[2,0].
  A duck faces its opponent, the west one east and the east one west, so its forward axis points at
  the other duck. Training reads the same number from projected gravity, asin(−g_b[0]). Roll is
  asin(2(yz + wx)) = asin(−g_b[1]).

  Checked three ways:
  - numerically, on rotations of known sign: a 30° nose-down gives −30°, a 20° nose-up gives +20°;
  - on the walker: −1 to 0° backwards, +1° forwards;
  - on t17-250, bowed with its head 12 cm ahead of its trunk and on the floor (`side_t17_8s.png`):
    −37 to −38°.

  t6-500, lying back on its trunk, reads +19°.
- **Only the feet: kept in the training rule.** The height bands do not exclude every contact but the
  feet's, so the training reads a contact sensor. The probe's own runs could not settle it: only
  the walker's frames held the bands there, and they were all feet-only. So the duck was posed at
  random in the Arena's model: 200,000 poses within every band, the leg joints anywhere in their
  ranges.
  - The head and the trunk never touched the floor.
  - A shin (`leg`, `leg_2`) touched it in 2.2 % of the poses, always with the trunk at 10.0–11.1 cm
    and a foot down: a kneel.

  The sensor covers every robot body but the feet, against the course; `check.py` recomputes the
  same contacts from a bout's trace.
- **Stepping, not sliding, is judged, not trained.** It is not a termination. `check.py` measures it
  (clear touch-downs per second, the share of foot travel made in contact), and gate S reads it.
  The probe's feet-position band (−3 to +6 cm ahead of the trunk) is not part of the rule: the pitch
  and height bands already reject the bow (t17-250: 0 % of frames on each).
- **One rule.** The walking-upright rule replaces the 7 cm / 45° one. The knob keeps its name
  `stay_upright` and its label "Stay upright": 0.0 for users, 1.0 for the owner's trainings, the
  cost of going down in pits.
- **The reference's warm start: the walker.** BEST_alpha_walking is the only policy found walking
  backwards. It stands still at the tug's −0.30 and walks back at −0.40. It is vendored into the
  challenge as `walker.onnx` (the same exporter's graph: `load_actor` reads it, 7e-7 from
  onnxruntime) and started by a second actor class, `WalkerActor`.
  - **Its normalizer count** is the reference's (t15-250's 502 rollouts × 24 × 4096). Its own count
    is unknown. What matters is that PPO's first update does not replace its statistics with one
    batch's, and t15–t17 warm-started with that inertia.
  - **The tug's commands sit inside its statistics**: vx −0.30 against a mean of 0.04 and a std of
    0.21; the head commands against stds of 0.14 to 0.60; the body commands against t15-250's own
    stds.
- **The opponent while training the reference: the frozen walker.** Measured in two Arena bouts of
  the walker against itself: both stay 100 % upright and neither stands still, both step
  (3.5–3.7 steps/s, 7–9 % of the travel sliding). Against t15-250 the walker is dragged into the pit
  in 5–6 s, still upright. A training names its opponent's ONNX on the command line
  (`--env.actions.opponent.onnx walker.onnx`, a file beside `opponent.py`). The run's provenance
  records the command, so a model card's Reproduce carries it.
- **The owner's candidate** is warm-started from the new reference and trained against it, with
  stay upright 1.0. It starts as a duck that already pulls upright; the walker never pulled.
- **The command stays the event's −0.30.** The Arena sends −0.30 to every duck, and a training at
  another speed would teach a command the Arena never sends. The walker stands still at −0.30, so
  RL must learn to step back under load (walking back pays 3.0).
- **Win ground 4.0 from the first training**: the owner's recipe since t15. At 2.0 and on its
  feet, t13 and t14 never loaded the string.
- **Gates** for the new reference and the candidate, over `check.py`'s 10 bouts:
  - **U2** (walking upright): in at least 9 of the 10 bouts, upright for at least 90 % of A's frames
    and never out for 0.3 s (the 15th step ends a training episode).
  - **S** (stepping): in at least 8 of the 10, at least 2 clear touch-downs a second and at most
    20 % of the foot travel in contact. A duck whose feet travel under 1 cm/s is standing still
    and passes. An S pass resting on "standing still" in more than 2 of the 10 bouts is not walking
    (t21-250 was ruled out on this).
  - **R1**: no NaN, and at least 8 of 10 bouts backed +2 cm by 2 s.
  - **R2** and **R3**, for the candidate only: a rating of +20 cm or more against the new reference,
    and 3 of 10 pits as a target.

  The candidate must also pass U2 and S over every round-robin bout (Plan H's ruling).
  The candidate's U2 is also a gate against a head-planter (t15-250), as the reference's is.
  - **The reference's U2, S and R1 are judged against the walker**, its training opponent. Its U2
    against t15-250, a planter, is also a gate (CHECK, 10 bouts, B the default): every player's
    replay shows the reference, so it must stay upright even when it loses.
  - **The reference is ranked** by its rating against t15-250 (the Arena's yardstick until the
    hand-over), with a round robin between ratings within 5 cm.
  - **Runs peak early**: checkpoints 250, 500, 750 and 1000 are judged. Three trainings in a row
    without a passing checkpoint: report to the owner and wait.
- **The judges' tool** is `check.py`'s posture line: upright share, longest stretch out, feet-only
  share, steps a second and slide. `posture_probe.py` stays a scratch diagnostic.
- **Hand-over.** The new reference replaces t15-250 in both repos, and every rating changes. The
  users' recipe keeps warm-starting from `reference.onnx` (now upright), with stay upright 0 and
  Win ground 2.0, and one training re-verifies it. Once the reference is handed over, nothing
  shipped uses the walker: `WalkerActor`, `walker.onnx` and the opponent's ONNX field go, and the
  reference's training commit and command, named in its provenance, keep them.

## 1. The tug of war (owner-decided scene, builder-tuned numbers)

**Course: a wrestling ring, cut by a pit** (owner, 2026-10-21; until then the race lane of layout
"A", 0.8 m between walls). The ring, 3 m from rope to rope, is the whole playing area; its ropes,
three a side, are the field's edges and the ducks bounce off them. The pit, 0.3 m wide, crosses the
ring in the middle from rope to rope. The walls were there so that drift could not decide a bout;
in the ring a drifting pair meets the ropes 1.5 m out, far more room than two ducks pulling use.

**Venue** (owner, 2026-10-21): the tug of war has its own, a dark arena round the ring: a circular
lighting truss over it, LED screens, barricades, the crowd on all four sides, the jury's desk at
ringside. Races and the Got a Talent stage keep the daytime stadium. No scene draws a dark halo
under the ducks' feet any more: each scene's lights cast their real shadows.

**Ducks: face to face, like a real tug of war** (owner). Each pulls by walking backwards. The
existing walking policies cannot compete; every entrant trains a new policy.

**String**: from the base of one duck's neck to the base of the other's, 1.00 m, straight at the
start, with a red marker at its middle; pit 0.3 m wide and 0.3 m deep, so that a duck in it is
unmistakably below the floor. Since 2026-10-21 (owner) the string is a physical rope, MuJoCo
bodies rather than a tendon: 16 capsule segments tied to both necks (numbers in the 2026-10-21
calls). It sags under its weight, touches the ducks, the floor, the pit and the ring's ropes, can
be stepped and lain on, and never passes through a body. Measured: a prone duck lies on it and
pins it by friction (so it does not stop crawling), and its weight hanging into the pit draws both
ducks towards it (about 1 N), so even bouts end in a late pit more often; the owner took both. The
**marker** is the rope's middle point (its x is what the judge reads; it agreed with the ends'
midpoint to 0.55 cm on average and never flipped a verdict in the study). The rope's 17 points are
recorded at every control step, settle included, and the viewer draws the string through them.

**Command**: the Arena sends every duck the same fixed command, declared in the event's
`[command]` like any event; its value is the one the training recipe uses. There is no speed
sweep in a versus.

**Judge** (my call on the details):

- The first duck in the pit loses the bout: a duck is in when its trunk goes below the floor level
  over the pit. **Only the pit decides** (owner, 2026-10-20, evening): a duck knocked over, sitting
  or lying on the platform stays in play and can still be dragged in. An earlier rule ("a fall
  loses") was tried and removed the same day: the first trained policies then dived face-down just
  under the fall line and held by friction anyway; the owner's ruling is that going down to hold
  is a viable strategy, and the point of the game is to drag the opponent into the pit.
- At the bout time limit (45 s, owner 2026-10-20 night: a 20 s bout never left time to drag anyone in), if nobody is in the pit, the duck the marker moved
  away from loses: as in a real tug of war, the winner pulls the marker (the string's middle
  point) to their side of the pit's centre line.
- Both in the pit on the same control step: the marker's side decides. A marker exactly back at the
  centre makes a drawn bout, which counts for nobody; the match goes on (at most five bouts), and a
  match still undecided after them goes to more bouts won, then the higher rating. (A rule that
  never needs a replay.)
- **A fault loses the bout on its step**, before the pit (owner, 2026-10-26, "corrige la faille",
  found by @jrubiosainz's duel, PR #2): a duck that gives no valid action, an action that is not a
  number, a policy that fails to answer, one answer longer than a second, or more thinking over
  the bout, settle included, than the bout lasts (owner, 2026-10-27: a time limit before the
  release). Both at once: nobody wins the bout. MuJoCo drives no motor while one command is not a
  number, so a NaN duck froze the reference and rated -0.1 cm; a hanging policy held a cup for good.
- **A step MuJoCo has to reset** ends the bout with nobody winning it, its frame left out.

**Match** (my call): first to two bouts, sides swapped after each bout. Each bout's seed derives
from the cup's secret (section 4), the match and the bout, so a whole cup replays identically on
x86.

## 2. The rating: bouts against the reference duck (owner, 2026-10-20 night)

The event's own board is a rating, like a race's time, so everything the races have works for it
unchanged: entry, five seeds, board, points, clip, live rotation, commentary. The first design (a
"pulling bench": one duck against a ramping winch, rated by the force it held) was dropped the
same night: a duck lying down held the winch by friction (~5.2 N) about as well as any trained
duck, so the rating separated nobody, and training against a winch never taught a duck to pull
another one.

- **The reference duck**: a frozen policy shipped with the Arena (its ONNX vendored like the
  golden walker), first our own checkpoint that walks backwards and pulls the string taut (t7-250
  of the tug recipe). Changing it later changes every rating, like a runner version. Owner,
  2026-10-21: the reference stays on its feet. t7-250 dives prone in the first half second, so a
  new reference, trained upright on the ring and the rope (§3), replaces it before the release;
  every rating changes, none is released yet. Owner, 2026-10-22: the reference walks upright, as
  the robot walks. t15-250, which replaced t7-250, pulls bowed forward with its head planted on the
  floor, so a reference trained to the walking-upright rule (§3) replaces it in turn; every rating
  changes again.
- **Score per seed**: one bout (the tug's own physics, 45 s) between the entry and the reference,
  sides alternating with the seed. The score is the marker's displacement towards the entry at the
  end of the bout, in centimetres (negative when the reference pulled it away), plus a bonus when
  the reference is dragged into the pit (and the same malus when the entry is). A fault scores
  minus two pit bonuses (-200 cm), beyond any bout played out; in a rating bout a fault of either
  duck and a MuJoCo reset are the entry's (2026-10-27), since the reference never causes one on its
  own: a duck at -inf on every joint made MuJoCo reset on the first step and rated 0.0 cm, above
  every duck that pulls and loses.
- **Rating**: the mean over five seeds, in centimetres; higher is better.
- **Clip**: the entry's median bout against the reference — a real tug of war, two ducks, the
  string as it lay and the marker, in the ring. Landscape and vertical, on the HF Job, like every run.
- **What it is not**: one fixed opponent is not the whole field; the rating says how well a duck
  pulls against the reference; the cup says who wins.
- The pit bonus is the builder's: 100 cm, since while the losing duck is out of the pit the marker
  stands at most 65 cm (half the string plus half the pit) towards the winner, so a pit finish
  outweighs any marker margin. The rope's middle point is never farther than half the string from
  the loser's neck, so the bound holds.

## 3. Training, and the first candidate

- A `tug_of_war` challenge in `microduck-challenges` (the usual folder). The duck trains
  **against another duck** (owner, 2026-10-20 night): the Arena's own bout — the same string, pit,
  ring and 45 s — with a frozen opponent policy on the other end, first the reference duck (our
  walking-back t7-250). Later the opponent can be chosen, even switched during training, among the
  best checkpoints and the published models (a league); not in the first version.
- The workshop's Test step rates a checkpoint against the reference locally (indicative: a Mac is
  not the Space).
- **No Pollen reference in the cups** (owner). We train one policy with the recipe and the owner
  publishes it **under his own name (Nico-robot) as the first candidate**. The release does not
  wait for a strong one: the best duck available at release time is the first candidate, and the
  recipe keeps improving after.
- (2026-10-20 night, measured) A learner warm-started from the reference beats one trained from
  scratch; runs peak early and decay, so every 250 iterations is judged and the peak kept. The
  recipe users get warm-starts from the reference.
- (Owner, 2026-10-21; the rule since 2026-10-22) The training scene is the ring and the rope, the Arena's own. An opt-in
  knob, **stay upright**, off in the recipe users get, ends a training episode when the learner
  is not walking upright for 0.3 s straight and costs it a pit. Walking upright means: trunk at 10 cm or more, pitched
  between 10° forward and 20° back, rolled 10° at most, the head's centre of mass at 18 cm or
  more, neck and head pitch within 30° of STAND, only the feet touching the course. The reference
  and the owner's candidates train with it on, so they walk upright as the robot walks; other
  players may crawl or plant their heads. The judge also reads stepping: touch-downs per second
  and the share of foot travel made in contact. Order (2026-10-22):
  - A new reference is warm-started from the walker (BEST_alpha_walking) and trained against the
    frozen walker with the knob on. It is judged every 250 iterations: walking upright, stepping,
    pulling, and its rating against t15-250. It replaces t15-250 in the Arena and as the recipe's
    opponent and warm start.
  - Then the owner's candidate is warm-started from the new reference and trained against it with
    the knob on, picked by the gates and a round robin.
  - Then the users' recipe, knob off, is trained once against the new reference to verify it.

  (2026-10-21: the rule was a trunk under 7 cm or tilted past 45°. t15-250 and t17-250, picked
  under it, pulled bowed onto their heads.)

## 4. The weekly cup

**Calendar** (owner: weekly; the slot is my call, set in the event file): premiere every Friday at
18:00 Europe/Paris, entries close at 16:00. The two hours let the Space simulate the cup, the
HF Jobs render its clips and the writer write the show.

**Entrants**: owner-approved — publishing on the event is entering the cup. At close, each player's
latest non-withdrawn entry on the current runner version is their duck for that cup; a player who
publishes nothing new plays again with the same duck. One duck per player. Fewer than 4 entrants:
no cup that week, and the page says so.

**Withdrawals** (owner approved my recommendation): an entry withdrawn before close is not in the
cup. Once the cup is drawn it is frozen: a withdrawal between close and premiere, or after, changes
nothing in it — no recomputation, no forfeit, its matches stay on the page, the live and in the
points, like a sports result. The board and the live rotation outside the cup keep today's
withdrawal rules.

**The cup's secret** (my call): at close, the Space draws a random secret and stores it with the
cup in the private dataset. The draw and every bout seed derive from it. Before the premiere nobody
can compute the cup on their own x86 machine from the public code, policies and entrant list, and
no player can tune a checkpoint against known seeds before close. Once the final has aired, the
secret is published with the results, so anyone can re-race the cup on x86.

**Draw** (owner's idea, details mine): a random draw from the cup's secret, World-Cup style:
entrants sorted into pots by rating, one per pot in each group.

**Format** (my call): G groups, G the largest power of two that leaves at least three ducks per
group (4–5 entrants → 1 group, 6–11 → 2, 12–23 → 4, 24–47 → 8 …). Every group plays a full round
robin; the top two go through to a knockout of 2G (crossed: a group winner meets another group's
runner-up). Group ranking: matches won, then bouts difference, then head-to-head, then rating.
With 25 entrants: 8 groups of 3–4, ~27 group matches, a 15-match knockout, ~42 clips.

**Computation**: at close, the Space computes the whole cup at once (all group matches, then the
knockout they lead to), records it in the dataset, owes a clip per match, and has the show's
commentary written. A restart during the window resumes from the dataset without changing a
result (every seed and the draw derive from the stored secret).

**The running order** (my call): once everything is ready, the cup gets a running order: every
segment of the show in sequence with its start time, each match's reveal time being the moment its
clip has finished airing (its clip may be loaded from 30 s before it starts). In stage 2 the running order is just the match clips back to back from the
premiere; stage 3 inserts the desk segments into the same running order, it does not replace it.

**Revealed match by match, as it airs** (my call, from the owner's "like a real sports live"):
before the premiere, no API answer, board, profile, clip URL or live slot reveals a match result, a
trace or a clip. During the show, a match becomes public — on the cup page, its match page, the
players' profiles — at its reveal time, the moment its clip has finished airing, so a viewer who opens the cup page mid-show sees the cup as
far as it has aired, never the champion before the final. The cup's points land when the final
airs. The dataset is private; the Space serves the cup's state as of "now".

**If something is late** (my call): the premiere waits until every match clip and every line of
the show is ready; until then the page and the live say "starting soon". The booth is waited for
30 minutes past the premiere at most (owner, 2026-10-27): then the matches air without the desk or
the calls, rather than the live standing by for as long as the router is down. Clip jobs run 16 at
once (owner, 2026-10-27, "plus de clips"): a 23-entrant cup owes 62 match clips, about two hours
of jobs four at a time. Cup clip jobs are
relaunched without the usual three-try limit. Cup N+1 never premieres before cup N has. Nothing
airs with a hole in it.

**Points** (my call): the rating board earns what a race board earns today (first event, runs,
own best, podium held). Each cup adds receipts on the podium scale: champion 250, finalist 150,
each semi-finalist 100.

## 5. The cup page

A page per cup, in the Arena's own look (few buttons, only what is needed when it is needed — the
owner's standing direction for new pages), in two states (wireframes shown and accepted in
session, kept locally under `.superpowers/brainstorm/`, `cup-page.html`):

- **Before the premiere**: cup number, close and premiere times, a countdown, the entrants ranked
  by rating, how to enter in one line. Between close and premiere it stays in this state.
- **After**: the champion, the groups with their standings, the knockout bracket; every match
  opens its own page with its clip and its bouts, like a run page today.

The event's card on the home wall shows the next cup's countdown. A player's profile lists their
cup results.

## 6. The show on the live channel

Owner: "during the event Peter & Ray watch each match and comment on it like a real sports live.
Behind the commentators you can see the state of the competition with the entrants and their
progress. They can comment on the tournament with the information they need to be interesting
and in context for the stage the tournament is at." Wireframe accepted in session
(`cup-live.html`, same place).

- **Programme**: from the premiere time, the channel airs the cup and nothing else: an opening
  (the field, the draw, the favourites), then every match in order, group recaps between rounds,
  the knockout, the final, the champion, a close. Every match in full; no time limit.
- **The desk**: during a cup, a big screen on the booth's back wall (in place of the pegboard)
  shows the cup's state as of that moment — groups, then the bracket — with the next match
  highlighted.
- **The match**: its clip full screen with the bouts' score bug; Peter & Ray call it **while it
  plays**, their lines timed to moments found in the bouts' traces (the marker moving, a lead
  changing hands, a slip, a duck at the edge, the drop into the pit), in their droid voices with captions as
  today. This play-by-play is new: today they only talk between clips. It belongs to the live
  page, not to the mp4 (my call: the match clip is a clean clip, like every clip).
- **What the writer knows**: the stage of the cup, the group standings and the bracket, ratings
  (favourite, underdog), every result earlier in this cup, earlier cups (defending champion,
  rematches, streaks), the players' profile facts. Never anything later than the match being
  called: no spoilers.
- **Written ahead**: every line of the show is written during the window between close and
  premiere and stored with the cup. The show plays from the store; it never waits on an LLM.
- **After the premiere**: the cup's match clips join the channel's ordinary rotation until the
  next cup; the rated runs' clips (each the entry's median bout against the reference duck) are in
  the rotation all along, like race clips.

## Delivery: three stages, built in parallel, released together

The owner: the three stages are built in parallel and everything is pushed together at the end.
Stages 2 and 3 do not wait for a good policy: they are developed and tested locally with the
first training's intermediate checkpoints as stand-in entrants. Paid trainings on HF Jobs have no
budget limit (owner).

1. **The tug and its rating.** The course (lane + pit; the ring + pit from 2026-10-21), the string, the rating by bouts against the reference duck (first built as a winch bench, replaced 2026-10-20 night), the event with
   its rating, board, clips and commentary; the `tug_of_war` challenge recipe; the first
   candidate trained and published by the owner. The match itself (two ducks, the judge) is built
   here too, since the cup and the rating both play it.
2. **The weekly cup.** Calendar, entrants, draw, groups and knockout, computation, secrecy, match
   clips, cup page and match pages, points, the home countdown. Without stage 3, the premiere is
   the moment the page flips and the matches join the live rotation.
3. **The show.** The cup programme on the live, the desk screen, the play-by-play, the writer's
   tournament context.

The release is one push of main (which deploys the Space), then the wheel and the challenges
relock as usual, then the owner publishes the first candidate.

## Decided by the owner (this session)

- The versus concept; the first versus is a tug of war over a pit, string at the base of the neck,
  several players' policies in one physics.
- A dated tournament, draw, groups, then winners against winners (his idea); weekly.
- A rating per model at publication, from the pulling bench, instead of a sparring match.
- Face to face, pulling backwards; every entrant trains a new policy.
- Course A: the race lane with walls, cut by a pit (superseded 2026-10-21 by the ring).
- Publishing on the event enters the cup.
- The show: Peter & Ray call every match like a live sport, the cup's state behind them,
  tournament-aware commentary; no time limit for now.
- No Pollen reference in the cups; we train a model and the owner publishes it under his name as
  the first candidate.
- No limit on paid trainings; the three stages are built in parallel (stand-in checkpoints) and
  pushed together at the end.
- Only the pit decides, on the bench and in a bout: a fall does not lose (2026-10-20, evening; it
  reverses the "a fall loses" decision of the same morning).
- The policies must really pull: the recipe is retrained so the ducks walk back and tighten the
  string, judged by bouts that end in the pit, not by the marker's drift (2026-10-20, evening).
- 2026-10-20 night: bouts last 45 s; the rating is five bouts against a frozen reference duck (cm
  of marker displacement + a pit bonus), the winch bench is dropped; training is against a frozen
  opponent duck (first the reference, later a league of checkpoints and published models); the
  release does not wait for a strong trained duck.
- A drawn cup is frozen: withdrawals after close change nothing in it.
- 2026-10-21, after the local preview: the string is a physical rope as measured (16 segments,
  80 g, normal friction), knowing it does not stop crawling and draws stalemates into the pit; the
  marker is its middle point and its shape is recorded and drawn; the tug's own venue, a wrestling
  ring 3 m square whose ropes are the field's edges, the pit across it from rope to rope (course A
  superseded); the halo under the ducks' feet removed in every scene; the reference and the
  owner's candidates stay on their feet (leaning back allowed) through an opt-in "stay upright"
  training knob, off for users; a new upright reference replaces t7-250; everything re-rated and
  retrained.
- 2026-10-22, after the posture probe: the owner's ducks (the reference and his candidate) walk
  upright like the robot's normal gait, head high, trunk up, only the feet on the floor, stepping
  rather than sliding; other players stay free (a head on the floor allowed, only the pit decides),
  knowing head-planting ducks will beat the upright reference easily; the rope and the scene stay.
- 2026-10-26, after @jrubiosainz's duel (PR #2): a fault (an action that is not a number) loses the
  bout at once and costs two pit bonuses in a rating; cup #1 premieres on Friday 6 November.
- 2026-10-27, after the pre-release review: a time limit on the policies before the release (a
  policy that fails or thinks too long faults); a MuJoCo reset is the entry's fault in a rating;
  clip jobs 16 at once; the booth waited for 30 minutes past the premiere at most.
- 2026-11-14, after @jrubiosainz's issue #8: on air a duck is billed with its player,
  "<policy name> (@<user>)", wherever its match is announced (its title, so its clip's card), on its
  clip's stamp and on the desk's cup screen; the score bug, the plates over the ducks and the call
  lines keep its policy's name.

## My calls (the owner may object)

- String ≈ 1 m taut, pit 0.3 m, the 100 cm pit bonus, the marker rule, tie-breaks (the 45 s bout
  limit is the owner's).
- A match's result is revealed when its clip has finished airing (its clip may load 30 s before it
  starts); the knockout bracket keeps group-mates apart until the final; on air, ducks are named by
  their policy names (with the player's handle when two entrants of a cup share one) on the score
  bug, their plates and in the calls, and billed with their players elsewhere (2026-11-14).
- Matches first to two bouts, sides swapped; seeds from cup/match/bout.
- Legs only; a fixed command; no sweep.
- Friday 18:00 Europe/Paris premiere, 16:00 close; no cup under 4 entrants.
- The group-count rule, top two through, crossed knockout, group tie-breaks.
- Points per cup on the podium scale (250 / 150 / 100 per semi-finalist).
- A secret drawn at close seeds the draw and the bouts; published after the final.
- Results revealed match by match as the show airs, from a running order fixed before the
  premiere; points land with the final.
- The premiere waits for every clip and every line; cup clips retried without limit; cup N+1
  never premieres before cup N.
- The play-by-play lives in the page, not in the mp4.
- After the premiere the cup's matches join the rotation until the next cup.
- 2026-10-21: see "My calls (2026-10-21)" above (rope joints and numbers, the ring's edges,
  upright thresholds, the knob, the reference's and the candidate's training, the trace, names).
- 2026-10-22: see "My calls (2026-10-22)" above (the walking-upright rule and its sign, the
  feet-only sensor, stepping judged not trained, the walker as the reference's warm start and
  opponent, the gates U2, S, R1–R3, the hand-over).

## Left to the builder

- The string, pit, bonus and judge numbers, tuned on the first trained policy; the attach body
  for "the base of the neck".
- How a cup, its matches and its show are laid out in the dataset and served by the API.
- The match clip's composition (bouts chained, score bug, intro/outro) within the clip contract.
- How moments are detected in a bout's trace for the play-by-play.
- The cup page's and the desk screen's visuals, within the Arena's look.
- Whether the Space or an x86 HF Job on the Space's image computes the cup, as long as it is x86
  and the result is the same.
