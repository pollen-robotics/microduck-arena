// Sock Heist: what the giant's head shows at a moment of a race, and the frame a duck is out from.
// The timetable is one seed's, served by the Arena (arena/lights.py served): a list of
// [onset_s, length_s] reds, in seconds on the runner's control steps. The page never draws one.

import { CTRL_DT, frameAt, frameCount } from "./replay.js";

// How far short of the line a duck's trunk may end its trace and still have finished: the runner
// judges progress from where the duck stood once settled, millimetres from its trace's first frame.
const REACHED_M = 0.05;

const smooth = (x) => x * x * (3 - 2 * x);
const steps = (seconds) => Math.round(seconds / CTRL_DT);

/**
 * The light `seconds` into the race on `timetable`. `red` is the light; `facing` is how far round
 * the head is, 0 away from the lanes and 1 facing them: it turns round over `turnS` as a red
 * begins, and back as it ends. `watching` is when a duck can be caught: from the moment the head
 * faces the lanes to the end of the red. Before the start the head is away.
 */
export function lightAt(timetable, turnS, seconds) {
  if (!(seconds >= 0)) return { red: false, facing: 0, watching: false };
  const turn = steps(turnS);
  const clock = seconds / CTRL_DT;
  // The step whose frame a replay shows at `seconds`, safe from a boundary's rounding.
  const step = Math.floor(clock + 1e-6);
  const turned = (start) => (turn > 0 ? smooth(Math.min(1, Math.max(0, clock - start) / turn)) : 1);
  let last = null;
  for (const [onsetS, lengthS] of timetable) {
    const onset = steps(onsetS);
    if (onset > step) break;
    last = [onset, steps(lengthS)];
  }
  if (!last) return { red: false, facing: 0, watching: false };
  const [onset, length] = last;
  if (step < onset + length) return { red: true, facing: turned(onset), watching: step >= onset + turn };
  return { red: false, facing: 1 - turned(onset + length), watching: false };
}

/**
 * The frame of `trace` from which its duck is out of a `length` metre race, or null if it reached
 * the line. A duck the giant caught moving is out from `caught`, the frame it was caught on, wherever
 * its collapse then carries it. Otherwise it is out from its last frame when the trace ends short of
 * the line, as a duck that fell or ran out of time does (arena/runner.py). A replay holds a lane's
 * last frame (replay.js Player), so from that frame on the duck stands still, out.
 */
export function outAt(trace, length, caught) {
  const last = frameCount(trace) - 1;
  if (last < 0) return null;
  if (caught != null) return caught;
  return frameAt(trace, last)[0] - frameAt(trace, 0)[0] < length - REACHED_M ? last : null;
}

/** `outAt` for a lane, whose caught frame counts from its trace's frame 0 after its settle lead-in. */
export function laneOut(lane, length) {
  return outAt(lane.trace, length, lane.caught == null ? null : lane.caught + (lane.lead ?? 0));
}

/**
 * Who crossed a `length` metre race's line first: a finisher's trace ends as it crosses
 * (arena/runner.py), so it is the finished lanes' fewest frames, `frame` the index of that last
 * frame, and every lane that crossed on it. None when no lane finished.
 */
export function firstAcross(lanes, length) {
  let first = null;
  lanes.forEach((lane, i) => {
    const frames = frameCount(lane.trace);
    if (!frames || laneOut(lane, length) != null) return;
    if (!first || frames - 1 < first.frame) first = { frame: frames - 1, lanes: [i] };
    else if (frames - 1 === first.frame) first.lanes.push(i);
  });
  return first;
}

/** The served timetable of `seed`, none when the event serves none for it. */
export function timetableOf(event, seed) {
  return event.lights.timetables[seed] ?? [];
}
