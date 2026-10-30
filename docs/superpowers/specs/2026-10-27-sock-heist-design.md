# Sock Heist: a 6 m red light, green light under a giant microduck's eye — design

Builds on pull request #3 (red light, green light, by @jrubiosainz) and its spec,
[`2026-10-21-red-light-green-light-design.md`](2026-10-21-red-light-green-light-design.md). That
spec still holds wherever this one does not say otherwise.

## Why

Microducks love to grab socks and carry them to their nest. In Sock Heist, the little microducks
race to steal socks from a giant microduck's nest without being seen by the giant. It is the
contributor's red light, green light, told as a microduck story: a race that asks a policy to stop
on cue, stand still while watched, and start again. No current challenge asks for that. On the
sprint, the leaders win by diving at the line; here they do not get a metre (#3 measured 0/5 for
the sprint's and the hill's leaders).

The owner wants this to be the next challenge after the Tug of War. It should be a show first: the
giant, its nest, the deep quack, the collapse of a duck caught moving, the socks flying when the
winner dives in. And it should be a real training target, so that people train policies for it
rather than enter their walkers as they are.

## The show, as a viewer sees it

1. **The start.** A 6 m concrete race track in a school playground at the microducks' own scale,
   between two crowds of microducks (see "Amendment, 2026-10-29"). Several microducks wait on the
   start line, a lane each. At the far end, centred
   behind the finish line and facing away from the lanes, a giant microduck sits in a nest woven
   from socks. Between the finish line and the nest, socks lie scattered on the floor. The first
   shot shows every competitor and the giant.
2. **Green.** The giant does nothing. Its back and its head face away from the lanes. The ducks run.
3. **Red.** The giant turns its head round over its shoulder to face the lanes, like an owl, with a
   very deep microduck quack (it is a giant). Its body does not move. Every duck must freeze.
4. **Caught.** A duck still moving once the head has turned is caught: all its motors switch off,
   it collapses where it stands, with the microduck fall sound, and it lies there for the rest of
   the replay, under an OUT plate.
5. **Green again.** The head turns back away, and the race goes on.
6. **The winner.** The first duck across the line dives into the socks, and socks fly everywhere.
7. **The end.** The replay goes on until every duck has crossed or is out.

The giant turns at random moments, different on every seed.

## Goals

- A new perpetual race, `sock-heist-6m`, titled "6 m Sock Heist", scored like every race: the
  lowest mean finish time over five seeds, a caught seed counting as the time limit, like a fall.
- The show above, on the event page, the run page and the race clip.
- A training folder for it in microduck-challenges, and a policy trained with that folder that
  becomes the event's published reference.
- All of it on top of the contributor's branch, merged through PR #3 at the end.

## Non-goals

- The policy does not see the giant. As in #3, it sees the light only through its command: on red
  the twist drops to zero. Every published policy can enter as it is.
- The ducks are still each simulated alone, a lane each, as in #3.
- No giant sock, and no trophy to carry. The winner dives into the socks on the floor; that is all.
- No round, no cup: the race is perpetual.

## Anti-goals (a failure even if it works)

- **Closing or replacing the contributor's PR.** The owner will not close #3 because we redid it.
  We add commits on the contributor's branch, keep their twelve commits as they are, and merge #3 itself at the end.
- **A ranking decided by luck.** Every entrant faces the same five timetables.
- **A replay out of step.** Every duck of a replay must freeze to the same giant at the same moment.
- **A giant that reads as anything but a microduck,** or a nest that does not read as socks at a
  glance.
- **Any other event changing behaviour.** #3's scope guard still holds: only an event that declares
  the new tables behaves differently.
- **A clip render that blows its budget** on the HF Job's renderer (see Constraints).
- **French anywhere:** code, UI, comments, docs, commit messages, clips. The site is English only.

## Constraints

- **The branch.** Work on `jrubiosainz/microduck-arena:red-light-green-light`. The PR allows
  maintainer edits. Bring today's `main` in with a **merge**, never a rebase, so their commits keep
  their hashes. The PR's description gives the resolution of the two `viewer.js` hunks it shares
  with the Tug of War. Our Tug of War is not their #2, so the resolution has to be redone against
  `main` as it is. Nothing is pushed to their branch, or anywhere else, without the owner's yes.
- **The owner's local `main` has uncommitted work that is not ours.** Work only in the worktree
  `.claude/worktrees/sock-heist`, never in the main checkout.
- **The Arena is the reference.** Never port from or cite duckJam.
- **Clips render on a t4-small HF Job** (EGL), and since the 216-seat crowd a frame's cost is
  vertices, not fill. The nest and the socks must be low-poly and instanced; measure a clip frame
  before and after.
- **The Space's store pays per file** on every refresh (snapshot download, one HEAD per file). Keep
  one trace file per run, even with five seeds in it.
- **Physics differs between Mac and the Space's x86.** Every number that ships (time limit, sweep,
  reference score) is measured on x86, as #3 did on a cloud VM and as the runner v5 re-measure did
  on an HF Job.
- **Clips are deterministic.** Anything animated on the page (the head, the socks flying) is a pure
  function of the replay's clock, so a clip frame renders the same every time.
- **No dead code.** What #3 built and this design no longer needs is removed, not left behind.
- New binary assets (GLB, WAV, WEBP) go through Git LFS, as `.gitattributes` does for the existing
  ones.

## Decisions taken by the owner

| Decision | What it rules out |
| --- | --- |
| Perpetual race | A round or a cup. |
| 6 m lane | #3's 15 m. |
| The watcher is a giant microduck in a nest woven from socks, modelled in Blender | #3's giant Reachy Mini caller. |
| Layout A: the nest closes the far end, centred behind the finish line, facing away from the lanes; the socks lie between the line and the nest | A nest at the side of the lane. |
| On green the giant does nothing, back and head turned away; on red it turns its head to the lanes with a very deep microduck quack | A giant that moves its body, counts or sings. |
| The giant's turns are random, different per seed | #3's single timetable shared by every seed. |
| A caught duck has all its motors switched off and collapses, with a microduck fall sound | #3's caught duck that ends its trace standing. |
| The first across the line dives into the socks and the socks fly | No effect on arrival. |
| The replay runs until every duck has crossed or is out | A replay that stops at the winner. |
| ~~Reachy Mini judges and the crowd, as on the other races~~ (superseded 2026-10-29) | An empty venue. |
| 2026-10-29: a venue of its own, a school playground at the microducks' scale: a concrete track, a random crowd of microducks along both edges, a building on the left, a wooden fence on the right, a park behind the giant; no Reachy Mini judges | The Arena's gym, stadium, stands, judges and sponsors on this event. |
| 2026-10-29: the pages' default 3D view stands behind the microducks and looks at the giant | The close chase that leaves the giant out of the picture. |
| 2026-10-29: every red's quack differs, drawn from the replayed seed and the red's index, its chirp variant and its pitch round 0.30 | One quack for every red. |
| No giant sock | A sock to carry or a trophy. |
| Named Sock Heist | "Red Light, Green Light". |
| People must train real policies for this event, so the challenge ships a training folder, and we verify it by training a policy ourselves; that policy, not the walker, is the published reference | A launch with no training path, or the walker as the reference. |
| The release waits for the trained policy; it only has to be good enough; up to 10 trainings | Launching with the walker as the reference; an open-ended training loop. |
| Build on #3's branch and merge #3 at the end | Closing #3, or re-doing it on a branch of ours. |
| Blender may be used for any other piece of the venue that needs it | — |

## Design

### What stays from #3

- `[lights]` as the mechanism: the command's twist drops to zero on red; nothing counts while the
  head turns (`turn_s`, 0.4 s); the mark is the trunk's floor position when the head has finished
  turning; drift beyond `tolerance_m` (3 cm) is caught; caught is a fourth status, scored like a
  fall; it is judged after the fall and before the finish; the duck settles standing and the clock
  starts on a green; a short first green, so that a duck bolting off the line has to stop as hard as
  it started.
- `[steering]`, the lane's heading hold: #3 measured that no policy walks straight unaided, and 6 m
  is still well past the 0.8 m in which the reference turned into a wall.
- The trace stored float32 for arrays with a value of 4 or more: a 6 m lane has positions up to 6.
- The scope guard: every new line behind `lights is not None` or `steering is not None`; the
  sweep, the golden run and `RUNNER_VERSION` unchanged for every other event; a stage refuses both.
- The crowd's behaviour (stadium.js `crowd`), in the playground (amendment, 2026-10-29). The
  stadium, the gym and the judges no longer stand round this event.
- The chase camera from behind the field (`track`, `hold`, `packChase`, `chaseAcross`,
  `inRoom`), retuned so that the first shot shows every lane and the giant whole, and the last
  shot the dive into the socks (reframed in the playground, amendment 2026-10-29).
- The OUT plate over a duck that is out, the booth's caught seeds, the share text, the round card,
  the guide: renamed and re-told for Sock Heist.

### What changes

**The timetable is random per seed.** `[lights]` declares ranges instead of a list: the length of
a green, the length of a red, and the first green's (short). The runner draws each seed's timetable
from a generator seeded by the evaluation seed, so every entrant faces the same five timetables,
and two seeds differ. The ranges are tuned on x86 so that the reference walker crosses on every
seed, with about one red per metre walked, as #3 had on 15 m: some 5 to 7 reds per crossing at
the walker's pace. The owner shortened the lane because 15 m felt long; a red every few strides
on 6 m would make the race as long again.

**Every seed's trace is kept, in one file.** Today a run stores the trace of one seed, its
lower-median finisher (`pick_trace_seed`). Here, the lanes of one replay come from different runs,
and each must have faced the giant at the same moments, so they must all be on the same seed. On an
event with `[lights]`, the run's trace file holds all five seeds; on any other event it is as
before. A replay picks one seed and plays every lane on it:

- a run's page and its clip: the run's own trace seed, for the run and the three ranked under it;
- the event page: the leader's trace seed, for the podium.

Each seed's trace carries its timetable, so the page draws the giant from the trace and never
re-derives a random draw in JavaScript.

**A caught duck collapses.** On the step it is caught, the runner switches off every actuator of
that duck (no torque, no position hold) and simulates on for long enough to record the collapse
until it lies still, then ends the run as `"caught"`. The trace records the step it was caught on,
so the page knows when to hang the OUT plate and play the sound: "the trace ends short of the line"
no longer marks it, since the trace now goes on past the catch.

**The giant replaces the caller.** `caller.js` and its Reachy Mini, the lamps, the post and the
light strip all go. In their place: the giant microduck, built from the racers' own model
(`microduck.glb`) at 4 to 5 times their size, chosen so that it dominates the lane and stays whole
in the shot. It sits in its nest with its back to the lanes. On red, its head turns over its
shoulder towards the lanes in `turn_s`, and back when the red ends. Nothing else of it moves.

**The nest and the socks are new models, made in Blender.** A nest woven from socks, sized for the
giant, its legs hidden in it, and a handful of loose sock models instanced over the floor between
the finish line and the nest. The ground may need to run further than `OVERRUN` past the line on
this event to hold them. Any other piece of the venue that needs a model may be made the same way.
The Blender work is scripted (`blender -b -P …`) and the script is committed, so that the assets can
be rebuilt. The owner sees renders of the nest, the socks and the giant in place **before** they are
integrated in the site.

**The sounds.**
- The giant's quack: the microduck voice the site already synthesises (`duck-voice.js`,
  `microduck-voice.wasm`, the quack of Got a Talent), pitched far lower, at the start of each turn
  of the head towards the lanes, each red's quack its own (amendment, 2026-10-29).
- A duck going out, caught or fallen: `microduck-fall.wav`, which the race clip already plays for a
  duck that does not finish.
- On the page as in the clip.

**The dive.** When the first duck crosses the line, the socks near its lane fly up and fall back,
as if it had dived into them. It is a visual effect of the site, a pure function of the time since
it crossed; the physics knows nothing of it.

**The clip.** The owner wants to see the end of the match, so on this event the clip runs until
every lane is decided: crossed, caught, fallen, or out of time at the limit. Today `clipPlan`
stops the tape at the end of the clip's own run, plus its outro; here it stops at the end of the
slowest lane. The clip plays at 1×: #3's time-lapse (`[clip] speed`) was for a minute-long race
on 15 m, and it goes, with its code. A rival that never moves and is never caught is only out at
the limit, so the time limit also bounds the clip: it is set so that the walker crosses every seed
with a margin, and no longer. The clip's render must still fit the HF Job's timeout; measure it on
the longest case, a lane out of time.

**The commentary.** `nature()` tells the story in one line a newcomer understands (little
microducks sneaking up to steal socks from a giant microduck's nest; freeze when it looks). The
lore lines tagged `lights`/`caught` are rewritten to match. The newcomer humour rules hold: no joke
that needs to know the characters. Bad lines are fixed in the prompt, never filtered by a check.

**The names.** Event id `sock-heist-6m`, title "6 m Sock Heist", the guide
`docs/guides/challenges/sock-heist-6m.md`, the card `app/public/cards/sock-heist-6m.webp`. Every
"red light, green light" name of #3 in code and docs is renamed; the mechanism's own names
(`lights`, `caught`) may stay where they name the mechanism.

**The card.** A generated illustration in the style of the other cards (the recipe in the owner's
notes for event cards), which the owner may replace with their own.

### The training folder and the reference

In `pollen-robotics/microduck-challenges`, a folder `src/microduck_challenges/sock_heist_6m/`,
built like the sprint's (`AGENTS.md`, `challenge.toml`, `env.py`, `tasks.py`) and listed in the
repository's `AGENTS.md`. Its environment reproduces the event's rules as the policy meets them:
a forward command held on the lane's heading by the same hold, dropping to zero on red at random
moments drawn from the event's ranges, a reward for standing within the tolerance while watched
and for progress on green, and the caught rule as a termination. Its guide says what the policy
sees (only its command), the time it has to stop, what gets it caught, and what is known to work.

We then train a policy with that folder, as the Tug of War's candidate was trained (HF Jobs under the
`Nico-robot` namespace, the owner's grant), and evaluate it on the Space's platform. The owner wants a microduck good enough, not the
best one: the bar is to finish every seed and beat the reference walker's score. The first policy
that clears it is the event's published reference, in place of the walker, and training stops
there. The owner allows up to **10 trainings**; if none clears the bar, we go back to the owner with
the results. **The release waits for this policy.** What the folder's `AGENTS.md` says is known to
work is written from these trainings.

### Release

Once the trained reference has cleared its bar, and on the owner's yes at each step, as for the
previous challenges: push our commits to the
contributor's branch, so #3 updates; rename the PR's title and rewrite its description for Sock
Heist, crediting the contributor's design; merge #3 with a merge commit (not squash, not rebase)
so their commits stay in `main`; bump the Arena's version (a new minor), release the wheel, relock
and push microduck-challenges with the new folder; publish the reference.

## Amendment, 2026-10-29: the playground, the page's camera, the giant's quacks

The owner saw the site locally with Plans A to D done and asked for three changes, **on Sock Heist
alone**: no other event changes in any way, and everything new runs behind `event.lights`, as the
rest of this design does.

### A venue of its own: the microducks' school playground

Sock Heist leaves the Arena's gym and stadium. It races in a venue built for it, as the Tug of War
races in its ring: a **school playground at the microducks' own scale**. Nothing of the existing
venue is reused: no gym, no stands, no rail or cones, no Reachy Mini judges, no sponsors. The giant,
its nest and the loose socks stay exactly as the owner approved them on 2026-10-29.

Seen from behind the start, looking down the lanes at the giant:

- **The track.** The lanes run on a concrete race track: grey, plain, its lines painted on it. The
  giant in its nest and the socks before it close the far end.
- **Behind the giant, a park:** grass and trees. The concrete stops a little past the nest and the
  grass begins.
- **Along both sides of the track, a crowd of microducks** at the track's edge, placed at random as
  along a street race: no stands, no seats, a few ragged rows with gaps. They behave as every other
  crowd of microducks in the Arena (stadium.js `crowd`): sitting, standing up and cheering as the
  race goes on, their bubbles, their fidgets.
- **Behind the crowd,** a school building on the left (−z, the far side from the chase camera's
  side offset) and a wooden fence on the right (+z).
- **Behind the start,** off camera most of the time: the concrete goes on; no crowd there.

**The scale is the microducks'.** A racer stands 0.27 m, the seated giant 0.93 m. The giant stays the
tallest thing in the scene: the building, the fence, the trees and anything else are sized for
microducks, and none stands taller than the seated giant.

**Daylight, outdoors,** under the blue sky the other races have, the sun casting the racers', the
crowd's and the giant's shadows as on any race.

**How it is made.**

- **In Blender.** `scripts/sock_heist_venue.py` builds the playground alongside the nest and the
  socks, into one more GLB, `app/public/venue/playground.glb` (Git LFS): the ground (concrete and
  grass), the building, the fence and the trees. Low-poly, vertex-coloured like the nest, and
  instanced: a model repeated (a tree, a fence panel) is one mesh drawn many times, never copies
  merged into one heavy mesh.
- **The crowd's spots** are drawn once, in the script, from a fixed seed, and exported in the GLB
  (each spot its position and the way it faces). The site draws and animates a microduck of the
  crowd on each spot with stadium.js `crowd`, and the renders put a microduck on the same spots, so
  that the owner approves the crowd the site will show.
- **The sides follow the track's edge.** A page plays from one lane (the workshop) to four (a run
  page, its clip) and, on the event page's board sheet, as many as are ticked. As the stadium does
  today, the site stands each side of the playground (its crowd, then the building or the fence) at
  the edge of the lanes it draws, so that the crowd always stands at the track's edge; the park and
  the concrete run wide enough for any of them. The Blender script builds each side in its own frame,
  from the track's edge outwards, and its renders assemble the playground the way the site does, on
  four lanes. The site still paints the lines (start, finish, each lane's coloured stripe) on the
  concrete, since their number changes from page to page.
- **Its cost.** A clip frame's cost is vertices. The playground, its crowd included, is measured
  against the gym's version of Sock Heist on the local bench (the owner's notes, "Clip frame cost
  under SwiftShader": CPU seconds per frame, SwiftShader, frames interleaved) and then on one
  t4-small HF Job, on the owner's yes. Passed when a frame costs no more than the gym's and the
  longest clip, both layouts and its soundtrack, renders in at most 20 min (the clip job times out
  at 30). This replaces Plan C's C8.
- **Gate: the owner sees renders before anything reaches the site** — at least the view from
  behind the start, as the page's camera will see it, a three-quarter view of the whole playground,
  and a close view of the crowd at the track's edge — with the triangle counts. Their notes are
  applied in the script, never by hand in Blender.

**What leaves Sock Heist's path.** Every line that only Sock Heist used and the playground replaces
is deleted, its tests with it: the gym's longer hall past the nest, the ground run on past the nest
(`floorBeyond`, `buildCourse`'s `beyond`) if the playground's own ground makes it pointless, and
anything else C4 added for the heist in the gym. What other events still use stays, unchanged: the
gym, the stadium, the judges and the room's limits on the camera (`inRoom`) are only taken off the
heist's path.

### The page's camera: behind the microducks, on the giant

On the event page, the run page and the workshop, the default 3D view of a Sock Heist race stands
behind the microducks and looks down the lanes at the giant, so that the giant is in the picture
with the ducks for the whole replay. Today's close chase, behind the leader and looking down at it,
leaves the giant out. The viewer still drags the camera, and the page still swings it once to show
it can be moved, as on every race.

**The clip is reframed in the playground:** its first shot holds every lane and the giant whole; its
last shot, the dive into the socks. In the vertical clip, as Plan C had it, the first shot holds the
author's duck and the giant whole: every lane across a portrait picture would stand the camera some
9 m back and make the ducks specks. In the gym, C6b found two limits: the end wall behind the start
held the camera too close to fit every lane, and packChase (PACK_REACH, 3 m) kept the camera behind
a trailing lane, so that the dive was filmed from about 5 m. The playground has no wall behind the
start; the second limit is the builder's to lift on a lights event (the field's camera may leave a
trailing duck behind once the first duck nears the line, for instance), without changing how any
other race is filmed.

**Gate: the owner sees the camera's captures** — the page's default view at the start, mid-race on
a red and at the finish; the clip's first shot, a red, a caught duck lying under its OUT plate, the
dive and the last frame, in both layouts — before anything is committed. C6b's uncommitted retune
of `[clip.camera]` in the gym is dropped.

### The giant's quacks

Each red's quack differs. For each red, the chirp's variant (any of the synth's 12) and its playback
rate, a little either side of the 0.30 the owner chose, are drawn from the replay's seed and the
red's index by a fixed integer hash: never `Math.random`, never the wall clock. A page and a clip
replaying the same seed quack the same quacks, so clips stay reproducible. Every lane of a replay
plays one seed already, so a replay has one sequence of quacks.

### The owner's decisions (2026-10-29)

| Decision | What it rules out |
| --- | --- |
| A venue of its own, modelled in Blender, script committed as `scripts/sock_heist_venue.py`, low-poly and instanced | Reusing the gym, the stadium, the stands, the judges or the sponsors |
| A school playground at the microducks' scale: a concrete track, a park with grass and trees behind the giant, a building on the left, a wooden fence on the right | A playground at human scale; any piece taller than the giant |
| A crowd of microducks along both edges of the track, placed at random as along a street race, behaving as every other crowd | Stands, seats, an empty track |
| No Reachy Mini judges | — |
| The giant, its nest and the socks as approved | Remodelling them |
| The pages' default 3D view behind the microducks, looking at the giant | The close chase on the leader |
| The clip: first shot every lane and the giant whole, last shot the dive | — |
| Each red's quack varies (variant and a little pitch round 0.30), drawn from the replayed seed and the red's index | A random draw at play time; one quack for all |
| Gates: renders before integration, camera captures, the HF Job's cost measure on the owner's yes | — |

### My calls (2026-10-29)

- The building is on −z, the fence on +z: −z is the viewer's left for a camera behind the start
  looking down the lanes (+x).
- Daylight under the races' sky; the playground's sun casts shadows as the races' does.
- The crowd's spots come from the Blender script, so the renders and the site show one crowd; each
  side stands at the edge of the lanes drawn, as the stadium's stands do, so no page needs a cap on
  its lanes.
- The crowd is about as large as the stadium's (216), fewer if the cost measure asks for it.
- The quack's rate within ±10 % of 0.30 (0.27 to 0.33), every chirp variant allowed. A WAV of one
  seed's quacks goes to the owner to hear; it is not a gate.
- The vertical clip's first shot holds the author's duck and the giant, not every lane.
- The pass mark of the cost: no dearer a frame than the gym's version, and the longest clip in
  20 min on the t4-small job.

### Left to the builder (2026-10-29)

- The playground's layout and sizes within the description above: the building's and the fence's
  shape and distance from the track, how many trees and of how many models, where the concrete
  meets the grass, the crowd's count, rows and gaps, the triangle budget of each model.
- How the spots ride in the GLB, and how the instancing is exported and loaded.
- How the page's camera keeps the giant in the picture, and how the clip's camera reaches the dive.
- The hash that draws each quack.

## My calls (the owner did not decide these)

- Every seed has its own timetable, the same for every entrant.
- Five traces in one file per run on this event; a replay plays every lane on one seed (the run's
  trace seed on a run page and its clip, the leader's on the event page).
- The timetable rides in the trace; the page never re-draws it.
- The giant turns its head like an owl, about half a turn over its shoulder; its body never moves.
- The giant and its quack are the only signal: no lamps, no light strip.
- The giant is the racers' model at 4 to 5 times their size.
- Only the first duck across makes the socks fly.
- The fall sound plays for any duck going out, caught or fallen.
- The crowd behaves as on any race.
- About one red per metre walked, 5 to 7 per crossing at the walker's pace.
- The clip runs to the slowest lane at 1×, the time-lapse goes, and the time limit is kept just
  long enough for the walker so that a stalled rival does not make a long clip.
- "Good enough" means finishing every seed on the Space's platform and beating the walker's score.
- The card art is generated, for the owner to replace if they want.

## Left to the builder

- The timetable's ranges and the time limit, measured on x86 so that the reference walker crosses
  every seed.
- The giant's exact size and placement, the nest's and the socks' shapes and polygon budget, the
  ground's overrun, the camera's retune.
- How five seeds sit in one trace file, and how the API serves one seed of it.
- How long a caught duck is simulated on after its motors go off.
- The quack's pitch and the dive's look, within the description above.
- The training environment's rewards and curriculum.
