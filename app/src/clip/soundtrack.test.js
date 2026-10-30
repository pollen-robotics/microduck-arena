import { describe, expect, it } from "vitest";
import { CEILING } from "../duck-voice.js";
import { renderSoundtrack } from "./soundtrack.js";

/**
 * An offline context whose sources log their starts, whose nodes log what they feed (`wiring`),
 * and whose render is `rendered` on both sides.
 */
function fakeContext(log, wiring = [], rendered = (length) => new Float32Array(length)) {
  return class {
    constructor(channels, length) {
      this.length = length;
      this.destination = { name: "speakers" };
    }
    createDynamicsCompressor() {
      return {
        name: "limiter", threshold: {}, knee: {}, ratio: {}, attack: {}, release: {},
        connect: (to) => wiring.push(["limiter", to.name]),
      };
    }
    createGain() {
      return { name: "gain", gain: {}, connect: (to) => wiring.push(["gain", to.name]) };
    }
    createBuffer(channels, length) {
      const data = new Float32Array(length);
      return { data, copyToChannel: (samples) => data.set(samples) };
    }
    createBufferSource() {
      const node = { connect() {}, playbackRate: { value: 1 }, start: (at) => log.push({ at, buffer: node.buffer, rate: node.playbackRate.value }) };
      return node;
    }
    async decodeAudioData() {
      return { decoded: true };
    }
    async startRendering() {
      const side = rendered(this.length);
      return { getChannelData: () => side };
    }
  };
}

describe("renderSoundtrack", () => {
  it("renders a quack from the robot's synth at its instant, with no file to fetch", async () => {
    const log = [];
    const calls = { chirp: () => new Float32Array(480).fill(0.5), wheee: () => new Float32Array(1) };
    const score = { crowd: null, cues: [{ at: 0.5, call: { tag: "chirp", variant: 0, start: 0, end: 1 }, gain: 1 }] };
    const pcm = await renderSoundtrack(score, 1, {
      Context: fakeContext(log),
      load: () => { throw new Error("a voice cue fetched a file"); },
      calls: async () => calls,
    });
    expect(log).toHaveLength(1);
    expect(log[0].at).toBe(0.5);
    expect(log[0].buffer.data).toEqual(new Float32Array(480).fill(0.5));
    expect(pcm).toHaveLength(2 * 48000);
  });

  it("never loads the synth for a clip without a voice", async () => {
    await renderSoundtrack({ crowd: null, cues: [] }, 1, {
      Context: fakeContext([]),
      calls: () => { throw new Error("the synth was loaded"); },
    });
  });

  it("renders the song from the robot's synth at its instant, as long as the performance lets it", async () => {
    const log = [];
    const asked = [];
    const calls = {
      song: (seed, voice, notes, seconds) => (asked.push(seconds), new Float32Array(Math.round(seconds * 48000)).fill(0.25)),
    };
    const sound = { song: [[0.5, 1, 69, 0.7, 0.9, 0]] };
    const score = { crowd: null, cues: [{ at: 0.3, song: { sound, duration: 1, part: { choral: false, variant: 0 } }, gain: 1 }] };
    await renderSoundtrack(score, 2, {
      Context: fakeContext(log),
      load: () => { throw new Error("a song cue fetched a file"); },
      calls: async () => calls,
    });
    expect(asked).toEqual([1]);
    expect(log).toHaveLength(1);
    expect(log[0].at).toBe(0.3);
    expect(log[0].buffer.data).toHaveLength(48000);
  });

  it("sings a troupe's chorus, each duck its own part, every voice through the limiter", async () => {
    const asked = [];
    const wiring = [];
    const calls = {
      song: (seed, voice, notes, seconds, part) => (asked.push(part), new Float32Array(Math.round(seconds * 48000))),
    };
    const sound = { song: [[0.5, 1, 69, 0.7, 0.9, 0]] };
    const cues = [0, 1].map((variant) => ({ at: 0.3, song: { sound, duration: 1, part: { choral: true, variant } }, gain: 1 }));
    await renderSoundtrack({ crowd: null, cues }, 2, {
      Context: fakeContext([], wiring),
      load: () => { throw new Error("a song cue fetched a file"); },
      calls: async () => calls,
    });
    expect(asked).toEqual([{ choral: true, variant: 0 }, { choral: true, variant: 1 }]);
    expect(wiring).toEqual([["limiter", "speakers"], ["gain", "limiter"], ["gain", "limiter"]]);
  });

  it("brings a render the limiter let overshoot under full scale, scaled as a whole", async () => {
    // A chorus of eight's onset through the compressor: 0.35 dB over full scale.
    const loud = (length) => Float32Array.from({ length }, (_, i) => 1.041 * Math.sin(i / 7));
    const pcm = await renderSoundtrack({ crowd: null, cues: [] }, 1, { Context: fakeContext([], [], loud) });
    const peak = pcm.reduce((most, sample) => Math.max(most, Math.abs(sample)), 0);
    expect(peak).toBeLessThanOrEqual(1);
    expect(peak).toBeCloseTo(CEILING, 6);
    expect(pcm[2 * 10] / pcm[2 * 3]).toBeCloseTo(Math.sin(10 / 7) / Math.sin(3 / 7), 6);
  });

  it("renders the giant's quack from the synth's chirp, slowed to its rate", async () => {
    const log = [];
    const calls = { chirp: (seed, variant) => new Float32Array(480).fill(variant + 1), wheee: () => new Float32Array(1) };
    await renderSoundtrack({ crowd: null, cues: [{ at: 2, quack: true, variant: 5, rate: 0.31, gain: 1 }] }, 3, {
      Context: fakeContext(log), load: () => { throw new Error("a quack fetched a file"); }, calls: async () => calls });
    expect([log[0].at, log[0].rate]).toEqual([2, 0.31]);
    expect(log[0].buffer.data).toEqual(new Float32Array(480).fill(6));
  });

  it("leaves a render under the ceiling as it rendered", async () => {
    const quiet = (length) => Float32Array.from({ length }, (_, i) => 0.9 * Math.sin(i / 7));
    const pcm = await renderSoundtrack({ crowd: null, cues: [] }, 1, { Context: fakeContext([], [], quiet) });
    const side = quiet(48000);
    expect(pcm.filter((_, i) => i % 2 === 0)).toEqual(side);
    expect(pcm.filter((_, i) => i % 2 === 1)).toEqual(side);
  });
});
