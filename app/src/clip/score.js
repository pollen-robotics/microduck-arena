// What the clip sounds like, decided before a frame is drawn: the crowd's
// direction and every cue at its instant. Pure. Each sound source is a
// function here and a name in the event's [clip] sounds.

import { choirOf, voiceEvents } from "../duck-voice.js";
import { isStage, isTug } from "../format.js";
import { FALL_FILE, heistCues } from "../heist-sound.js";
import { timetableOf } from "../lights.js";
import { CTRL_DT, frameAt, frameCount } from "../replay.js";
import { BOUT_WORDS } from "../tug.js";

/** Cue gains, measured on a real render: the horn 5 dB over the crowd's surge,
 * the victory level with the crowd's cheer, and the fall — over a crowd gone
 * quiet — just over the stamp, and the duck's voice at the synth's own level, under the limiter. */
const GAINS = { horn: 2, stamp: 0.6, victory: 7, fall: 0.45, voice: 1, quack: 1 };
/** How often the crowd learns where the duck is, in seconds of tape. */
const PROGRESS_EVERY_S = 0.5;

function fnv(text) {
  let hash = 2166136261;
  for (const byte of new TextEncoder().encode(text)) hash = Math.imul(hash ^ byte, 16777619) >>> 0;
  return hash;
}

/** The author's progress down the course, sampled every PROGRESS_EVERY_S of the tape; the tape
 * can run on past the author's lane, which holds its last frame. */
function progress(trace, plan, lengthM, start) {
  const samples = [];
  for (let t = 0; t <= plan.steps * CTRL_DT; t += PROGRESS_EVERY_S) {
    const step = Math.min(plan.steps - 1, frameCount(trace) - 1, Math.round(t / CTRL_DT));
    const value = Math.max(0, Math.min(1, frameAt(trace, step)[0] / lengthM));
    samples.push({ second: start + t, value });
  }
  return samples;
}

const SOURCES = {
  // Nicolas's samples carry their own stadium echo.
  horn: ({ start }) => [{ at: start, file: "air-horn.mp3", gain: GAINS.horn }],
  verdict: ({ end, verdict }) => [
    { at: end, file: "stamp.wav", gain: GAINS.stamp },
    verdict === "pass"
      ? { at: end + 0.16, file: "microduck-victory-echo.mp3", gain: GAINS.victory }
      : { at: end + 0.16, file: FALL_FILE, gain: GAINS.fall },
  ],
  // The giant's quack at each red and a fall where a duck goes out, on the race's clock.
  giant: ({ run, lanes, performed }) =>
    heistCues(timetableOf(run.event, run.trace_seed), lanes, run.event.length_m, run.event.time_limit_s, run.trace_seed).map(({ at, kind, variant, rate }) =>
      kind === "quack"
        ? { at: performed + at, quack: true, variant, rate, gain: GAINS.quack }
        : { at: performed + at, file: FALL_FILE, gain: GAINS.fall }),
};

/**
 * The stamp the clip lands, and whether it lands as a pass: a race won or a DNF, a performance
 * given or cut short, and a rated tug run as its replayed bout ended: a pass for a win.
 */
export function clipVerdict(run) {
  if (isTug(run.event)) {
    const { status } = run.per_seed.find((seed) => seed.seed === run.trace_seed);
    return { stamp: BOUT_WORDS[status].toUpperCase(), pass: status === "won" || status === "pit_won" };
  }
  const pass = run.seeds_finished > 0;
  if (isStage(run.event)) return { stamp: pass ? "WELL DONE" : "CUT SHORT", pass };
  return { stamp: pass ? "VICTORY" : "DNF", pass };
}

/**
 * `trace` is the author's lane, settle included; `ducks` the stage's troupe in duck order (cast.js
 * stageDucks), each with how it sounds, and none for a race or a tug. `lanes` is every lane of a
 * Sock Heist race on the replay's seed: its trace and the frame its duck was caught on.
 */
export function clipScore({ run, plan, trace, ducks, lanes }) {
  const sounds = run.event.clip.sounds;
  const verdict = clipVerdict(run).pass ? "pass" : "fail";
  // A stage and a tug have no course to go down: their crowd answers the verdict alone.
  const still = isStage(run.event) || isTug(run.event);
  const start = plan.intro / plan.fps;
  const end = plan.tapeEnd / plan.fps;
  // The performance starts on the tape after the settle; its length is the author's trace, cut short or not.
  const performed = start + plan.settle * CTRL_DT;
  const context = { start, end, verdict, run, lanes, performed };
  const length = (plan.steps - plan.settle) * CTRL_DT;
  // Every duck's calls and song, as on the stage: two or more singers sing their parts as a chorus.
  const choral = choirOf(ducks);
  const voice = ducks.flatMap(({ sound }, index) => [
    ...voiceEvents(sound, length).map((call) => ({ at: performed + call.start, call, voice: sound.voice, gain: GAINS.voice })),
    // A song is one take from the performance's start, the duck's part of the chorus or solo.
    ...(sound?.song ? [{ at: performed, song: { sound, duration: length, part: { choral, variant: index } }, gain: GAINS.voice }] : []),
  ]);
  return {
    // The same run always sounds the same, whichever layout renders it.
    seed: fnv(run.run_id),
    crowd: sounds.includes("crowd")
      ? { start, end, verdict, progress: still ? [] : progress(trace, plan, run.event.length_m, start) }
      : null,
    cues: [...sounds.flatMap((name) => SOURCES[name]?.(context) ?? []), ...voice],
  };
}

/** A cup's match: someone always wins it, so its crowd cheers at the outro, where the stamp lands. No course to go
 * down, no voices. */
export function matchScore({ match, plan }) {
  const sounds = match.event.clip.sounds;
  const context = { start: plan.intro / plan.fps, end: plan.tapeEnd / plan.fps, verdict: "pass" };
  return {
    seed: fnv(match.match_id),
    crowd: sounds.includes("crowd") ? { ...context, progress: [] } : null,
    cues: sounds.flatMap((name) => SOURCES[name]?.(context) ?? []),
  };
}
