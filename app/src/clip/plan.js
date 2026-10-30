// The clip's frame plan: a title over the waiting ducks while the camera travels
// to the chase, the tape at life speed, an outro while the rest of the race runs on,
// and where the outro's stamp lands. Pure, so the recorder's expectations and
// the page's drawing are pinned by one test.

import { isTug } from "../format.js";
import { CTRL_DT } from "../replay.js";
import { entrySide } from "../tug.js";

export const FPS = 25;
export const INTRO_S = 3;
/** The camera's travel to the chase, inside the intro: it settles before the start. */
export const TRAVEL_S = 2.4;
export const OUTRO_S = 2.5;
/** Trace frames per clip frame: the trace is 50 Hz, the clip 25 fps. */
export const STRIDE = Math.round(1 / FPS / CTRL_DT);

/**
 * `frames` is the length of the tape to show: the author's trace, or on a lights event the longest
 * lane's, every lane played till it is decided; `tapeMaxS` the event's ceiling;
 * `settle` the frames of untimed settle the lanes play first (leadIn), so the
 * tape starts where the simulation did. A run longer than the ceiling — a
 * timeout — is cut there and stamped anyway: the verdict is the record's, not
 * the tape's.
 */
export function clipPlan(frames, tapeMaxS, settle) {
  const steps = settle + Math.max(1, Math.min(frames, Math.round(tapeMaxS / CTRL_DT)));
  const intro = FPS * INTRO_S;
  const tape = Math.ceil(steps / STRIDE);
  const outro = Math.round(FPS * OUTRO_S);
  const total = intro + tape + outro;
  return {
    fps: FPS,
    stride: STRIDE,
    settle,
    steps,
    intro,
    travel: FPS * TRAVEL_S,
    tape,
    outro,
    frames: total,
    seconds: total / FPS,
    tapeEnd: intro + tape,
    poster: intro + Math.floor(tape * 0.6),
  };
}

/** The trace step clip frame `i` shows. The clock runs on through the outro:
 * the author's lane holds its last frame, as the player holds any finished
 * lane, while the rivals still racing go on. */
export function stepAt(plan, i) {
  if (i < plan.intro) return 0;
  return (i - plan.intro) * plan.stride;
}

/** How far through its travel to the chase the camera is at clip frame `i`, 0 to 1. */
export function travelAt(plan, i) {
  return Math.min(1, i / plan.travel);
}

export function actAt(plan, i) {
  return i < plan.intro ? "intro" : i < plan.tapeEnd ? "tape" : "outro";
}

/** The viewer lane the outro's stamp lands on: a tug's one lane holds both ducks, the entry's is on
 * its side of the string; a race's is the author's, the last of the lanes. */
export const stampLane = (run, laneCount) => (isTug(run.event) ? entrySide(run.trace_seed) : laneCount - 1);

/** How far inside the screen's edges the outro's stamp keeps, in CSS pixels. */
const STAMP_MARGIN = 36;

/**
 * Where the outro's stamp lands, as fractions of the screen: on the duck's `spot`
 * (fractions). A race's and a stage's stay there, as they always have. A tug's,
 * whose duck stands to one side of the frame, low in the pit or near an edge, is
 * moved no further than it takes to stand whole inside the screen, STAMP_MARGIN
 * from its edges and above `floor`, the pixels from the screen's top to where the
 * figures band starts to cover it. `stamp` and `screen` are sizes in pixels.
 */
export function stampAt(event, spot, stamp, screen, floor) {
  if (!isTug(event)) return spot;
  const keep = (at, size, room) => Math.min(room - STAMP_MARGIN - size / 2, Math.max(STAMP_MARGIN + size / 2, at));
  return {
    x: keep(spot.x * screen.width, stamp.width, screen.width) / screen.width,
    y: keep(spot.y * screen.height, stamp.height, Math.min(floor, screen.height)) / screen.height,
  };
}
