import { describe, expect, it } from "vitest";
import { heistCues, createHeistSound, quackOf } from "./heist-sound.js";
import { TRACE_WIDTH } from "./replay.js";

/** A trace of `frames` frames, the trunk going from x 0 to `to`. */
function walk(frames, to) {
  const trace = new Float32Array(frames * TRACE_WIDTH);
  for (let i = 0; i < frames; i++) trace[i * TRACE_WIDTH] = (to * i) / Math.max(1, frames - 1);
  return trace;
}

const T = [[0.6, 1.6], [4.2, 2.0]];
const TWELVE = Array.from({ length: 12 }, (_, k) => [1 + 3 * k, 1.6]);
const at2 = (cues) => cues.map(({ at, kind, lane }) => [Number(at.toFixed(2)), kind, lane]);

describe("quackOf", () => {
  it("gives every red a chirp of the synth's and a rate within a tenth of the owner's", () => {
    for (let red = 0; red < 50; red += 1) {
      const { variant, rate } = quackOf(3, red);
      expect(Number.isInteger(variant) && variant >= 0 && variant < 12).toBe(true);
      expect(rate).toBeGreaterThanOrEqual(0.27);
      expect(rate).toBeLessThanOrEqual(0.33);
    }
  });
  it("is the same for the same seed and red, and varies from red to red and seed to seed", () => {
    expect(quackOf(3, 4)).toEqual(quackOf(3, 4));
    expect(new Set(TWELVE.map((_, red) => quackOf(3, red).variant)).size).toBeGreaterThanOrEqual(4);
    expect(TWELVE.map((_, red) => quackOf(3, red))).not.toEqual(TWELVE.map((_, red) => quackOf(4, red)));
  });
});

describe("heistCues", () => {
  it("hands each quack its red's variant and rate, on the replay's seed", () => {
    const quacks = heistCues(TWELVE, [], 6, 60, 3);
    expect(quacks.map(({ variant, rate }) => ({ variant, rate }))).toEqual(TWELVE.map((_, red) => quackOf(3, red)));
  });
  it("quacks where each red begins and falls where a duck goes out, in race order", () => {
    const lanes = [
      { trace: walk(300, 6.05), caught: null }, // crossed
      { trace: walk(150, 2.0), caught: 50 }, // caught on the first red's first watched step, then collapsed
      { trace: walk(120, 1.5), caught: null }, // fell
    ];
    expect(at2(heistCues(T, lanes, 6, 60, 3))).toEqual([[0.6, "quack", null], [1, "fall", 1], [2.38, "fall", 2], [4.2, "quack", null]]);
  });
  it("never falls for a duck out of time, every lane out of time included", () => {
    expect(heistCues([], [{ trace: walk(3000, 2), caught: null }, { trace: walk(3000, 0.01), caught: null }], 6, 60)).toEqual([]);
  });
  it("counts a clip lane's frames after its lead-in", () => {
    expect(at2(heistCues([], [{ trace: walk(145, 1.5), caught: null, lead: 25 }], 6, 60))).toEqual([[2.38, "fall", 0]]);
  });
});

const calls = { chirp: (seed, variant) => new Float32Array(4800 + variant) }; // 0.1 s, and a sample more per variant
const settle = () => new Promise((done) => setTimeout(done));

/** A context whose sources log their starts and stops. */
function fakeContext(log) {
  const listeners = [];
  const node = (name) => ({ name, connect() {} });
  return {
    state: "running",
    addEventListener: (type, listener) => listeners.push(listener),
    removeEventListener: (type, listener) => listeners.splice(listeners.indexOf(listener), 1),
    changeState(state) {
      this.state = state;
      for (const listener of [...listeners]) listener();
    },
    destination: { name: "speakers" },
    resume: async () => log.push(["resume"]),
    close: async () => {},
    decodeAudioData: async () => ({ length: 57600 }),
    createGain: () => ({ ...node("gain"), gain: { value: 1 } }),
    createDynamicsCompressor: () => ({ ...node("limiter"), threshold: {}, knee: {}, ratio: {}, attack: {}, release: {} }),
    createWaveShaper: () => node("ceiling"),
    createBuffer: (channels, length) => ({ length, copyToChannel() {} }),
    createBufferSource() {
      const source = {
        ...node("source"),
        buffer: null,
        playbackRate: { value: 1 },
        start: (when, offset) => log.push(["start", source.buffer.length, offset, source.playbackRate.value]),
        stop: () => log.push(["stop"]),
      };
      return source;
    },
  };
}

async function soundWith(cues, { muted = () => false, state = "running" } = {}) {
  const log = [];
  const loaded = [];
  const context = fakeContext(log);
  context.state = state;
  const sound = createHeistSound(async () => calls, {
    makeContext: () => context,
    muted,
    load: async (file) => { loaded.push(file); return new ArrayBuffer(8); },
  });
  sound.set(cues);
  await settle();
  return { sound, log, loaded, context };
}

describe("createHeistSound", () => {
  it("quacks as the clock crosses a red's onset, once, slowed to the giant's rate", async () => {
    const { sound, log } = await soundWith([{ at: 0.6, kind: "quack", lane: null, ...quackOf(3, 0) }]);
    [0.58, 0.6, 0.62].forEach((s) => sound.follow(s));
    expect(log.filter(([what]) => what === "start")).toEqual([["start", 4800 + quackOf(3, 0).variant, 0, quackOf(3, 0).rate]]);
  });
  it("gives each red's quack its own chirp and rate", async () => {
    const [a, b] = [quackOf(3, 0), quackOf(3, 1)];
    expect(a.variant).not.toBe(b.variant);
    const { sound, log } = await soundWith([{ at: 0.6, kind: "quack", lane: null, ...a }, { at: 4.2, kind: "quack", lane: null, ...b }]);
    [0.6, 4.2].forEach((s) => sound.follow(s));
    expect(log.filter(([what]) => what === "start")).toEqual([["start", 4800 + a.variant, 0, a.rate], ["start", 4800 + b.variant, 0, b.rate]]);
  });
  it("plays the fall's recording where a duck goes out", async () => {
    const { sound, log, loaded } = await soundWith([{ at: 1, kind: "fall", lane: 1 }]);
    expect(loaded).toEqual(["microduck-fall.wav"]);
    [0.98, 1].forEach((s) => sound.follow(s));
    expect(log[0]).toEqual(["start", 57600, 0, 1]);
  });
  it("is silent while the Arena is muted or the page hushed", async () => {
    const { sound, log } = await soundWith([{ at: 0.6, kind: "quack", lane: null }], { muted: () => true });
    [0.6, 0.62].forEach((s) => sound.follow(s));
    expect(log).toEqual([]);
  });
  it("waits for a gesture while the browser keeps its context suspended, then plays from where the clock is", async () => {
    const { sound, log, context } = await soundWith([{ at: 0.6, kind: "quack", lane: null, ...quackOf(3, 0) }], { state: "suspended" });
    sound.follow(0.6);
    expect(log).toEqual([]);
    window.dispatchEvent(new Event("pointerdown"));
    expect(log).toEqual([["resume"]]);
    context.changeState("running");
    sound.follow(0.64);
    expect(log.at(-1)).toEqual(["start", 4800 + quackOf(3, 0).variant, expect.closeTo(0.04 * quackOf(3, 0).rate, 5), quackOf(3, 0).rate]);
  });
  it("starts again from where the clock lands when the replay jumps back", async () => {
    const { rate } = quackOf(3, 0);
    const { sound, log } = await soundWith([{ at: 0.6, kind: "quack", lane: null, ...quackOf(3, 0) }]);
    [0.6, 3, 0.65].forEach((s) => sound.follow(s));
    expect(log.filter(([what]) => what === "start").map(([, , offset]) => offset)).toEqual([0, expect.closeTo(0.05 * rate, 5)]);
  });
  it("makes no context and loads nothing for a replay without cues", async () => {
    const asked = [];
    const spy = (name) => () => { asked.push(name); };
    const sound = createHeistSound(spy("loadCalls"), { makeContext: spy("makeContext"), muted: () => false, load: spy("load") });
    sound.set([]);
    await settle();
    sound.follow(1);
    sound.dispose();
    expect(asked).toEqual([]);
  });
});
