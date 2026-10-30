// The whole soundtrack in one offline render: the stadium's voices under a
// continuous direction, every cue at its instant — every duck of a troupe
// beside the others — and the troupe's limiter at the end, the render then
// scaled under its ceiling if an onset got through, so no sample reaches ±1
// (the live programme refuses a clip that clips). No segments, no smoothing
// afterwards, no mixing left to ffmpeg.

import { olaAt, scheduleOla } from "../crowd-behaviour.js";
import { callSamples, limiter, songSamples, underCeiling } from "../duck-voice.js";
import { giantQuack } from "../heist-sound.js";
import { SAMPLE_RATE } from "../live/score.js";
import { loadCalls } from "../live/voice.js";
import { stadiumDirection } from "./direction.js";
import { StadiumAmbience, prepareStadium } from "./stadium.js";

const RATE = 48000;
/** The stadium's own volume scale (0–100): half, so its protection compressor
 * leaves the crowd room to build to the line instead of flattening it at 8 s. */
const CROWD_VOLUME = 50;
/** Past the stadium's own ceiling, making up the half: the bed sat at -45 dBFS at 30, under every cue by 25 dB. */
const CROWD_GAIN = 3;
/** Scheduling horizon, from renderStadium: keeps the engine's active nodes bounded. */
const BATCH_S = 0.5;

const fetchWav = (file) => fetch(`/sound/${file}`).then((response) => response.arrayBuffer());

function interleave(buffer) {
  const left = buffer.getChannelData(0);
  const right = buffer.getChannelData(1);
  const pcm = new Float32Array(left.length * 2);
  for (let i = 0; i < left.length; i++) {
    pcm[2 * i] = left[i];
    pcm[2 * i + 1] = right[i];
  }
  return pcm;
}

/** A sound of the robot's synth as a buffer: mono, which the context spreads to both sides. */
function synthBuffer(context, samples) {
  const buffer = context.createBuffer(1, samples.length, SAMPLE_RATE);
  buffer.copyToChannel(samples, 0);
  return buffer;
}

/** Interleaved stereo float32 at 48 kHz, exactly `seconds` long. */
export async function renderSoundtrack(score, seconds, { Context = OfflineAudioContext, load = fetchWav, calls = loadCalls } = {}) {
  const context = new Context(2, Math.ceil(seconds * RATE), RATE);
  const limit = limiter(context);
  limit.connect(context.destination);

  // The synth only for a clip whose duck or giant makes a sound: every other race and silent performance skips it.
  const synth = score.cues.some((cue) => cue.call || cue.song || cue.quack) ? await calls() : null;
  const cues = await Promise.all(
    score.cues.map(async (cue) => ({
      ...cue,
      buffer: cue.call
        ? synthBuffer(context, callSamples(synth, cue.call, cue.voice))
        : cue.quack
          ? synthBuffer(context, giantQuack(synth, cue.variant))
          : cue.song
          ? synthBuffer(context, songSamples(synth, cue.song.sound, cue.song.duration, cue.song.part))
          : await context.decodeAudioData(await load(cue.file)),
    })),
  );
  for (const cue of cues) {
    const source = context.createBufferSource();
    source.buffer = cue.buffer;
    if (cue.rate) source.playbackRate.value = cue.rate;
    const gain = context.createGain();
    gain.gain.value = cue.gain;
    source.connect(gain);
    gain.connect(limit);
    source.start(cue.at);
  }

  if (!score.crowd) return underCeiling(interleave(await context.startRendering()));

  for (let t = 0; t < seconds; t += 28) {
    const { start } = olaAt(t);
    if (start < seconds) scheduleOla(context, limit, start);
  }
  await prepareStadium(Context);
  const crowd = context.createGain();
  crowd.gain.value = CROWD_GAIN;
  crowd.connect(limit);
  const engine = new StadiumAmbience(context, {
    direction: stadiumDirection(score.crowd),
    seed: score.seed,
    volume: CROWD_VOLUME,
    destination: crowd,
  });

  // renderStadium's batching: schedule half a second ahead, suspending one
  // render quantum before each horizon, because Chrome rounds suspension
  // times to block boundaries.
  const end = seconds - 0.09;
  const queue = (time) => {
    engine.scheduleUntil(Math.min(time, end));
    if (time >= end) engine.stop(end);
  };
  queue(BATCH_S);
  const pauses = [];
  for (let time = BATCH_S; time < seconds; time += BATCH_S) {
    pauses.push(context.suspend(time - 128 / RATE).then(() => {
      queue(time + BATCH_S);
      return context.resume();
    }));
  }
  try {
    const [buffer] = await Promise.all([context.startRendering(), ...pauses]);
    return underCeiling(interleave(buffer));
  } finally {
    engine.dispose();
  }
}
