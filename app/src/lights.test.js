// @vitest-environment node
import { describe, expect, it } from "vitest";
import { firstAcross, laneOut, lightAt, outAt, timetableOf } from "./lights.js";
import { TRACE_WIDTH } from "./replay.js";

// A trace whose trunk walks along x from `from` through each of `xs`, one frame each.
const walk = (from, ...xs) => {
  const trace = new Float32Array((xs.length + 1) * TRACE_WIDTH);
  [from, ...xs].forEach((x, i) => { trace[i * TRACE_WIDTH] = x; });
  return trace;
};

function expectLight(timetable, turnS, seconds, { red, facing, watching }) {
  const light = lightAt(timetable, turnS, seconds);
  expect(light.red).toBe(red);
  expect(light.facing).toBeCloseTo(facing);
  expect(light.watching).toBe(watching);
}

const T = [[0.6, 1.6], [4.2, 2.0], [7.8, 1.4]];
const TURN = 0.4;

describe("lightAt", () => {
  it("is green with the head away before the start and through the first green", () => {
    for (const s of [-1, NaN, 0, 0.3, 0.58]) expectLight(T, TURN, s, { red: false, facing: 0, watching: false });
  });
  it("is red on exactly the timetable's steps", () => {
    const red = (s) => lightAt(T, TURN, s).red;
    expect([0.58, 0.6, 2.18, 2.2, 4.18, 4.2, 6.18, 6.2, 7.8, 9.18, 9.2].map(red))
      .toEqual([false, true, true, false, false, true, true, false, true, true, false]);
  });
  it("turns the head round over turn_s, and only then watches", () => {
    expectLight(T, TURN, 0.6, { red: true, facing: 0, watching: false });
    expectLight(T, TURN, 0.8, { red: true, facing: 0.5, watching: false });
    expect(lightAt(T, TURN, 0.98).facing).toBeGreaterThan(0.95);
    expect(lightAt(T, TURN, 0.98).watching).toBe(false);
    expectLight(T, TURN, 1.0, { red: true, facing: 1, watching: true });
    expectLight(T, TURN, 2.18, { red: true, facing: 1, watching: true });
  });
  it("turns the head back away as the red ends, never watching", () => {
    expectLight(T, TURN, 2.2, { red: false, facing: 1, watching: false });
    expectLight(T, TURN, 2.4, { red: false, facing: 0.5, watching: false });
    expectLight(T, TURN, 2.6, { red: false, facing: 0, watching: false });
  });
  it("keeps the head away after the last red, and on a timetable with none", () => {
    expectLight(T, TURN, 20, { red: false, facing: 0, watching: false });
    expectLight([], TURN, 3, { red: false, facing: 0, watching: false });
  });
  it("reads the served seconds on the runner's whole steps", () => {
    const served = [[0.84, 1.62]]; // steps 42 to 122
    expect([0.82, 0.84, 2.44, 2.46].map((s) => lightAt(served, TURN, s).red)).toEqual([false, true, true, false]);
    expect([1.22, 1.24].map((s) => lightAt(served, TURN, s).watching)).toEqual([false, true]);
  });
  it("faces the lanes at once when the head takes no time to turn", () => {
    expectLight(T, 0, 0.6, { red: true, facing: 1, watching: true });
    expectLight(T, 0, 2.2, { red: false, facing: 0, watching: false });
  });
});

describe("outAt", () => {
  it("leaves a duck that reached the line in, wherever it set off", () => {
    expect(outAt(walk(0.01, 3, 6.02), 6, null)).toBeNull();
    expect(outAt(walk(-0.02, 3, 5.99), 6, null)).toBeNull();
  });
  it("puts a duck that fell or ran out of time out from its last frame", () => {
    expect(outAt(walk(0, 2, 3.9), 6, null)).toBe(2);
  });
  it("puts a caught duck out from the frame it was caught on, not where its collapse ends", () => {
    expect(outAt(walk(0, 1, 2, 2.1, 2.15), 6, 2)).toBe(2);
  });
  it("keeps a caught duck out when its collapse carries it over the line", () => {
    expect(outAt(walk(0, 5.9, 5.97, 6.1), 6, 1)).toBe(1);
  });
  it("has nothing to say about an empty trace", () => {
    expect(outAt(new Float32Array(0), 6, null)).toBeNull();
  });
});

describe("laneOut", () => {
  it("counts a lane's caught frame after the settle it leads in with", () => {
    const trace = walk(0, 0, 0, 1, 2, 2.1); // two frames of settle, then the race
    expect(laneOut({ trace, caught: 2, lead: 2 }, 6)).toBe(4);
    expect(laneOut({ trace, caught: 2 }, 6)).toBe(2);
    expect(laneOut({ trace, caught: null, lead: 2 }, 6)).toBe(5);
  });
});

describe("firstAcross", () => {
  const lane = (trace, caught = null) => ({ trace, caught });
  it("is the frame the first duck crossed on, and its lane", () => {
    expect(firstAcross([lane(walk(0, 3, 6.1)), lane(walk(0, 6.05)), lane(walk(0, 1))], 6)).toEqual({ frame: 1, lanes: [1] });
  });
  it("names every lane that crossed on that frame", () => {
    expect(firstAcross([lane(walk(0, 6.1)), lane(walk(0, 3, 6.1)), lane(walk(0, 6.02))], 6)).toEqual({ frame: 1, lanes: [0, 2] });
  });
  it("is none when no duck crossed, a caught duck collapsing over the line included", () => {
    expect(firstAcross([lane(walk(0, 2, 3)), lane(walk(0, 5.9, 6.1), 1)], 6)).toBeNull();
  });
});

describe("timetableOf", () => {
  it("is the served timetable of the replay's seed, and none for a seed it does not serve", () => {
    const event = { lights: { turn_s: 0.4, tolerance_m: 0.03, timetables: { 3: T } } };
    expect(timetableOf(event, 3)).toBe(T);
    expect(timetableOf(event, undefined)).toEqual([]);
  });
});
