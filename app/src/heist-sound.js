// Sock Heist's sounds: the giant's deep quack where each red begins, each red's own, and the
// microduck's fall where a lane's duck goes out. `heistCues` lists them once, on the race's clock,
// from a timetable and the lanes; the page plays them live (`createHeistSound`, as stage-voice.js
// plays the stage's voices) and the clip's score renders them. Nothing waits on a sound: no Web
// Audio, a muted Arena or a context the browser keeps suspended until a gesture leave the replay
// playing in silence.

import { DUCK_SEED, VARIANTS, ceiling, limiter } from "./duck-voice.js";
import { draw } from "./giant.js";
import { laneOut } from "./lights.js";
import { SAMPLE_RATE } from "./live/score.js";
import { CTRL_DT, frameCount } from "./replay.js";

/** The centre of a quack's playback rate: the duck's own quack slowed to the giant's voice, as the owner picked it by ear on 2026-10-28. */
const GIANT_RATE = 0.3;
/** How far a quack's rate strays either side of GIANT_RATE, as a fraction of it. */
const GIANT_SPREAD = 0.1;

export const FALL_FILE = "microduck-fall.wav";
/** A step longer than this between two frames is a jump, not playback. */
const JUMP_S = 0.25;
/** The sounds under the replay, as the stage voice's (stage-voice.js). */
const GAIN = 0.6;
/** Each kind's level under it: the quack as the synth makes it, the fall as the clip mixes it. */
const LEVELS = { quack: 1, fall: 0.45 };

/** The quack of a seed's `red`th red: one of the synth's chirps and a rate around GIANT_RATE, drawn from the seed and the index so every replay of the seed quacks alike. */
export function quackOf(seed, red) {
  return {
    variant: Math.floor(draw(seed, 2 * red) * VARIANTS.chirp),
    rate: GIANT_RATE * (1 + GIANT_SPREAD * (2 * draw(seed, 2 * red + 1) - 1)),
  };
}

/** A giant's quack: the duck's own chirp of that variant, to be played at the quack's rate. */
export function giantQuack(calls, variant) {
  return calls.chirp(DUCK_SEED, variant, {});
}

/**
 * Every sound of a race in order on its clock: a quack at each red's onset (`lane: null`, with the
 * `variant` and `rate` `quackOf` draws from the seed for that red) and a fall
 * where a lane's duck goes out, at the frame it was caught on or its last when it fell. A duck that
 * crossed, or whose race frames ran to the time limit, falls for nobody. A lane's `lead` frames come
 * before the race clock starts.
 */
export function heistCues(timetable, lanes, length, limitS, seed) {
  const cues = timetable.map(([onset], red) => ({ at: onset, kind: "quack", lane: null, ...quackOf(seed, red) }));
  const limit = Math.round(limitS / CTRL_DT);
  lanes.forEach((lane, index) => {
    if (laneOut(lane, length) == null) return;
    const frames = frameCount(lane.trace) - (lane.lead ?? 0);
    if (lane.caught != null) cues.push({ at: lane.caught * CTRL_DT, kind: "fall", lane: index });
    else if (frames < limit) cues.push({ at: (frames - 1) * CTRL_DT, kind: "fall", lane: index });
  });
  return cues.sort((a, b) => a.at - b.at);
}

export function createHeistSound(loadCalls, { makeContext = () => new AudioContext({ sampleRate: SAMPLE_RATE }), muted, load = (file) => fetch(`/sound/${file}`).then((response) => response.arrayBuffer()) }) {
  let loaded = null;
  let context = null;
  let levels = null;
  const quacks = new Map();
  let fall = null;
  let parts = [];
  let version = 0;
  let last = 0;

  // A suspended context only starts from a resume() asked inside a gesture.
  const gestures = ["pointerdown", "keydown"];
  function resume() {
    context.resume().catch(() => {});
  }
  function stopWaitingForGesture() {
    for (const type of gestures) window.removeEventListener(type, resume, true);
    context?.removeEventListener("statechange", onStateChange);
  }
  function onStateChange() {
    if (context.state === "running") stopWaitingForGesture();
  }

  function halt(part) {
    if (part.source) {
      try {
        part.source.stop();
      } catch {
        // Already ended: nothing to stop.
      }
    }
    part.source = null;
    part.playing = false;
  }

  function silence() {
    parts.forEach(halt);
    parts = [];
  }

  /** Has `part` play from `offset` seconds into its buffer, unless it already does and the clock did not jump. */
  function steer(part, inside, jumped, offset) {
    if (inside === part.playing && !jumped) return;
    halt(part);
    if (!inside || context.state !== "running") return;
    try {
      part.source = context.createBufferSource();
      part.source.buffer = part.buffer;
      part.source.playbackRate.value = part.rate;
      part.source.connect(levels[part.kind]);
      part.source.start(0, offset * part.rate);
      part.playing = true;
    } catch {
      part.source = null;
    }
  }

  function open() {
    context = makeContext();
    const limit = limiter(context);
    const ceiled = ceiling(context);
    limit.connect(ceiled);
    ceiled.connect(context.destination);
    const output = context.createGain();
    output.gain.value = GAIN;
    output.connect(limit);
    levels = {};
    for (const [kind, level] of Object.entries(LEVELS)) {
      levels[kind] = context.createGain();
      levels[kind].gain.value = level;
      levels[kind].connect(output);
    }
    if (context.state !== "running") {
      for (const type of gestures) window.addEventListener(type, resume, true);
      context.addEventListener("statechange", onStateChange);
    }
  }

  return {
    /** The cues now to play (heistCues), each at its second of the race clock. */
    set(cues) {
      silence();
      const mine = ++version;
      if (!cues.length) return;
      loaded ??= loadCalls();
      loaded
        .then(async (calls) => {
          if (mine !== version) return;
          if (!context) open();
          for (const { kind, variant } of cues) {
            if (kind !== "quack" || quacks.has(variant)) continue;
            const samples = giantQuack(calls, variant);
            const buffer = context.createBuffer(1, samples.length, SAMPLE_RATE);
            buffer.copyToChannel(samples, 0);
            quacks.set(variant, buffer);
          }
          if (!fall && cues.some(({ kind }) => kind === "fall")) fall = await context.decodeAudioData(await load(FALL_FILE));
          if (mine !== version) return;
          parts = cues.map(({ at, kind, variant, rate = 1 }) => {
            const buffer = kind === "quack" ? quacks.get(variant) : fall;
            return { kind, rate, buffer, start: at, end: at + buffer.length / SAMPLE_RATE / rate, playing: false, source: null };
          });
        })
        .catch(() => {});
    },

    /** Called every frame with the race's time, or null while the replay does not play. */
    follow(seconds) {
      const jumped = seconds === null || seconds < last || seconds - last > JUMP_S;
      if (seconds !== null) last = seconds;
      const live = seconds !== null && !muted();
      for (const part of parts) {
        const inside = live && part.start <= seconds && seconds < part.end;
        steer(part, inside, jumped, seconds - part.start);
      }
    },

    dispose() {
      silence();
      version++;
      stopWaitingForGesture();
      context?.close().catch(() => {});
    },
  };
}
