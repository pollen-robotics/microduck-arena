// The duck's beak and voice on the stage, from a performance's `sound` (arena/timeline.py sound_of;
// a run, a board row, a ballot lane and a workshop evaluation carry it): the pad's two triggers as a
// track of [t, rt, lt] at each change, the song's notes as [t, for, midi, level, open, formant], and
// the knobs of its voice. The rules are microduck's own, at e597877. The pad (padd, robotd): the beak
// opens to the harder-pulled trigger; RT quacks as it crosses PULL on the way up; LT rides the wheee
// while at or over PULL and its release cuts it; one call at a time, a new quack cutting the last and
// a quack during a wheee dropped. The chorale (sounds::chorale, robotd): a note sounds for SUSTAIN of
// its length and the beak follows its vowel; a note holds the speaker, so no call starts inside one,
// a call playing when one starts is cut, and LT still held when it ends rides again. A troupe where
// two or more ducks sing is a chorus: each sings its part in the robot's choral voice. Pure: the
// viewer and the clip hear the same sounds from it.

import { SAMPLE_RATE } from "./live/score.js";
import { CTRL_DT } from "./replay.js";

/** The voice every performer sings in before its knobs: a seed of the robot's `sounds` crate. */
export const DUCK_SEED = 28;
/** Where a trigger counts as pulled: padd's SOUND_THRESHOLD. */
export const PULL = 0.3;
/** The beak's travel, closed to wide open: duck-control's −5° to +30°. */
export const MOUTH_TRAVEL = (35 * Math.PI) / 180;
/** How much of a note sounds before it lets go: the chorale's 92 %. */
export const SUSTAIN = 0.92;
/** How fast the beak follows its trigger: a servo's ease, not a snap. */
const MOUTH_TAU_S = 0.06;
/** How fast the beak follows a sung vowel: robotd's CHORALE_MOUTH_TAU_S. */
const SING_TAU_S = 0.09;
/** The beak in a note's release: a fifth of its vowel's opening, as robotd closes it. */
const RELEASE_OPEN = 0.2;
/** The song's take runs this far past its last note, for the release to fade. */
const TAIL_S = 0.2;
/** A cut sound fades out over this, so it stops without a click. */
const FADE_S = 0.005;
/** The variants of each call in the robot's bank (sounds::variant_count). */
export const VARIANTS = { chirp: 12, wheee: 6 };
/** The mix's ceiling, a little under full scale: no sample of the stage or the clip passes it. */
export const CEILING = 0.99;
/** Where the stage's ceiling starts to bend a sample: under it, the mix passes untouched. */
const KNEE = 0.9;
/** The points of the stage's ceiling curve over -1 to 1; a shaper is a straight line between two. */
const CURVE_POINTS = 4097;

/** The change a track holds at `t`: its last at or before it. */
function pulledAt(track, t) {
  let held = track[0];
  for (const point of track) {
    if (point[0] > t + 1e-9) break;
    held = point;
  }
  return held;
}

/** The note a song sings at `t`, from its start to its end, release included. */
function noteAt(song, t) {
  return song?.find(([start, length]) => start <= t + 1e-9 && t < start + length - 1e-9);
}

/** The beak the triggers ask for at `t`. */
function pulledOpen(track, t) {
  return track ? Math.max(...pulledAt(track, t).slice(1)) : 0;
}

/** The beak the song asks for at `t`: its vowel's opening, a fifth of it in the release, shut between notes. */
function sungOpen(song, t) {
  const note = noteAt(song, t);
  if (!note) return 0;
  const [start, length, , , open] = note;
  return t - start < SUSTAIN * length ? open : open * RELEASE_OPEN;
}

/**
 * The beak's opening, 0 closed to 1 wide open, at each 50 Hz frame of a lane whose trace starts
 * `lead` frames before the performance (a clip's settle, which holds the opening at t = 0): the
 * larger of what the triggers and the song ask, each eased as the robot eases it. Null without a
 * sound, so the lane keeps its beak as the rig made it.
 */
export function mouthTrack(sound, frames, lead = 0) {
  if (!sound) return null;
  const out = new Float32Array(frames);
  const followPull = 1 - Math.exp(-CTRL_DT / MOUTH_TAU_S);
  const followSong = 1 - Math.exp(-CTRL_DT / SING_TAU_S);
  let pulled = pulledOpen(sound.triggers, 0);
  let sung = sungOpen(sound.song, 0);
  for (let f = 0; f < frames; f++) {
    const t = Math.max(0, f - lead) * CTRL_DT;
    pulled += (pulledOpen(sound.triggers, t) - pulled) * followPull;
    sung += (sungOpen(sound.song, t) - sung) * followSong;
    out[f] = Math.max(pulled, sung);
  }
  return out;
}

/**
 * Every call a sound makes before `duration` seconds, in order: { tag, variant, start, end }, `end`
 * being where it is cut — the next call, LT's release, a note, the end of the performance. A quack's
 * own recording may end sooner. The k-th quack plays variant k mod 12 and the k-th wheee k mod 6, so
 * a performance always sounds the same. The song is not in it: songSamples sings it whole.
 */
export function voiceEvents(sound, duration) {
  const track = sound?.triggers;
  if (!track) return [];
  const song = sound.song ?? [];
  const calls = [];
  const count = { chirp: 0, wheee: 0 };
  const cut = (at) => {
    const last = calls.at(-1);
    if (last && last.end > at) last.end = at;
  };
  const begin = (tag, start) => {
    cut(start);
    calls.push({ tag, variant: count[tag]++ % VARIANTS[tag], start, end: duration });
  };
  // Every instant something can change: a trigger moves, a note starts or ends.
  const instants = [...new Set([...track.map(([t]) => t), ...song.flatMap(([t, length]) => [t, t + length])])]
    .sort((a, b) => a - b);
  let rt = 0;
  let riding = false;
  for (const t of instants) {
    if (t >= duration - 1e-9) break;
    const [, pulledRt, pulledLt] = pulledAt(track, t);
    if (noteAt(song, t)) {
      // The note has the speaker: what plays stops here, and a pull now is not heard.
      cut(t);
      riding = false;
      rt = pulledRt;
      continue;
    }
    // robotd's order: the wheee first, then the one-shots, which see the ride this instant started.
    if (pulledLt >= PULL && !riding) begin("wheee", t);
    if (pulledLt < PULL && riding) calls.at(-1).end = t;
    riding = pulledLt >= PULL;
    if (pulledRt >= PULL && rt < PULL && !riding) begin("chirp", t);
    rt = pulledRt;
  }
  return calls;
}

/** The last `FADE_S` of `samples` faded out, so a cut ends without a click. */
function fadeOut(samples) {
  const fade = Math.min(samples.length, Math.round(FADE_S * SAMPLE_RATE));
  for (let i = 0; i < fade; i++) samples[samples.length - 1 - i] *= i / fade;
  return samples;
}

/**
 * The samples a call plays, from the robot's synth (`calls`, live/voice.js loadCalls) in the voice
 * the performance tunes: the quack as recorded, the wheee's start then its loop over and over; cut
 * at its `end`, with a short fade.
 */
export function callSamples(calls, { tag, variant, start, end }, voice = {}) {
  const room = Math.max(1, Math.round((end - start) * SAMPLE_RATE));
  let whole = tag === "chirp" ? calls.chirp(DUCK_SEED, variant, voice) : calls.wheee(DUCK_SEED, variant, 0, voice);
  if (tag === "chirp" && whole.length <= room) return whole;
  if (tag === "wheee") {
    const ride = calls.wheee(DUCK_SEED, variant, 1, voice);
    const grown = new Float32Array(Math.max(room, whole.length));
    grown.set(whole);
    for (let at = whole.length; at < room; at += ride.length) grown.set(ride.subarray(0, room - at), at);
    whole = grown;
  }
  return fadeOut(whole.slice(0, room));
}

/**
 * The song as one take from the performance's t = 0, in the voice it tunes, to its last release —
 * or to `duration`, where a cut-short trace stops it, faded. In a chorus (choirOf) it is the duck's
 * part `variant`. Never empty; null without a song.
 */
export function songSamples(calls, sound, duration, { choral = false, variant = 0 } = {}) {
  if (!sound?.song) return null;
  const [start, length] = sound.song.at(-1);
  const seconds = Math.max(1 / SAMPLE_RATE, Math.min(duration, start + length + TAIL_S));
  return fadeOut(calls.song(DUCK_SEED, sound.voice ?? {}, sound.song, seconds, { choral, variant }));
}

/**
 * Whether a troupe sings as a chorus: two or more of its ducks have a song. In a chord the
 * robot tames vibrato, buzz, jitter and breath, which would sour the tuning (sounds::Stream::choral);
 * a lone singer keeps them.
 */
export function choirOf(ducks) {
  return ducks.filter((duck) => duck.sound?.song).length > 1;
}

/**
 * The limiter the troupe sings through, on `context`: hard and fast, just under full scale, so a
 * chorus of ducks stays under it while one duck at the synth's own level passes. The stage and the
 * clip's soundtrack each end their mix with one, then with a ceiling: a compressor lets a fast onset
 * through for a millisecond, which a chorus of eight takes 0.35 dB over full scale.
 */
export function limiter(context) {
  const node = context.createDynamicsCompressor();
  node.threshold.value = -3;
  node.knee.value = 0;
  node.ratio.value = 20;
  node.attack.value = 0.001;
  node.release.value = 0.1;
  return node;
}

/**
 * The stage's ceiling after its limiter, on `context`: a shaper that passes the mix untouched up to
 * KNEE and bends a louder sample smoothly towards CEILING, never reaching it; past full scale it
 * holds its curve's ends. It works sample by sample, as a live mix must.
 */
export function ceiling(context) {
  const node = context.createWaveShaper();
  const room = CEILING - KNEE;
  node.curve = Float32Array.from({ length: CURVE_POINTS }, (_, i) => {
    const input = (2 * i) / (CURVE_POINTS - 1) - 1;
    const over = Math.abs(input) - KNEE;
    return over <= 0 ? input : Math.sign(input) * (KNEE + room * Math.tanh(over / room));
  });
  return node;
}

/**
 * The clip's rendered mix under CEILING, in place: scaled as a whole when its peak passes it, which
 * changes its level and nothing else, and left as it is otherwise. The clip has its whole mix in
 * hand; the stage does not.
 */
export function underCeiling(samples) {
  let peak = 0;
  for (const sample of samples) peak = Math.max(peak, Math.abs(sample));
  if (peak > CEILING) {
    const gain = CEILING / peak;
    for (let i = 0; i < samples.length; i++) samples[i] *= gain;
  }
  return samples;
}
