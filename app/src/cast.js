// A performance's troupe on the page: the record's `cast` (arena/store.py RunRecord.cast; a board
// row and a run carry it, a ballot lane carries it anonymous, every policy "self" or "borrowed")
// beside the traces the server sends for it, one per duck. Duck 0 is the star: the entry's own
// policy, the one the followspot follows.

import { isStage, isTug } from "./format.js";
import { TRACE_WIDTH, leadIn } from "./replay.js";
import { ratingLane } from "./tug.js";

/**
 * Every duck of a performance as the stage draws it, in duck order: its trace (after `lead` frames
 * of its settle when `settles` are given, as a clip plays it), how it sounds, the rig it stands on
 * (the event's when the cast names none), its livery, and where its author placed it — null for a
 * run recorded before troupes, which the stage centres on its own path. A duck of the author's own
 * policy wears the entry's livery; a borrowed one the plain `classic`, so the colours stay the
 * author's.
 */
export function stageDucks(cast, traces, settles, { livery, eventRig, lead = 0 }) {
  return cast.map((duck, k) => ({
    trace: settles ? leadIn(settles[k], traces[k], lead, TRACE_WIDTH) : traces[k],
    lead,
    sound: duck.sound,
    rig: duck.rig ?? eventRig,
    livery: duck.policy === "self" ? livery : "classic",
    start: duck.start,
    star: k === 0,
  }));
}

/** The seed every lane of a lights replay plays: the board's leader's trace seed (`row`); none elsewhere. */
export function replaySeed(event, row) {
  return event.lights ? row?.trace_seed : undefined;
}

/**
 * The camera a page films an event with: a sock heist's clip camera, from behind its ducks on the
 * giant, so that the giant stays in the picture with them; null, the page's own close chase, elsewhere.
 */
export function pageCamera(event) {
  return event.lights ? event.clip.camera : null;
}

/**
 * One run as a lane of the viewer, from its traces (api.js, one per duck): on a stage its
 * performance, every duck of its cast; on a tug its two-duck bout and its `string` (ratingLane: the
 * entry on its end of the string, the reference on the other); on a lane the one duck that raced.
 * `lane` is what the page draws it with: run id, name, tier, colour, livery, and on a tug the bout's
 * seed, `traceSeed`; on a lights event the frame its duck was caught on, `caught`, as the trace was served.
 */
export function replayLane(event, cast, traces, lane, string) {
  if (isStage(event)) {
    return { ...lane, ducks: stageDucks(cast, traces, null, { livery: lane.livery, eventRig: event.rig }) };
  }
  if (isTug(event)) return { ...lane, ...ratingLane(traces, null, string, lane) };
  return event.lights ? { ...lane, trace: traces[0], caught: traces.caught } : { ...lane, trace: traces[0] };
}

/** The policies a troupe borrowed from the Hub, each once, in the order its ducks first bring them. */
export function featured(cast) {
  const policies = new Map();
  for (const { policy } of cast) {
    if (policy !== "self") policies.set(`${policy.repo_id}@${policy.revision}`, policy);
  }
  return [...policies.values()];
}

/**
 * Who performs, as a clip's caption says it: the author and the star's policy, then for a troupe
 * how many ducks, featuring the policies it borrowed.
 */
export function credit(run) {
  const who = `@${run.user} · ${run.policy_name}`;
  if (run.cast.length === 1) return who;
  const guests = featured(run.cast).map((policy) => `@${policy.user} · ${policy.policy_name}`);
  return `${who} · ${run.cast.length} ducks${guests.length ? `, featuring ${guests.join(", ")}` : ""}`;
}
