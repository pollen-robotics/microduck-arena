import { describe, expect, it } from "vitest";
import { LANE_COLORS, LANE_CSS } from "../course.js";
import { TRACE_WIDTH, frameCount } from "../replay.js";
import {
  CAPTION_S, LETTERS, eventCaption, keeperColour, playClock, playEvent, playLanes, playLine, playTimes,
  policyColour, policyOn, scoreAt, verdict,
} from "./plays.js";

// A match as arena/football_watch.py football_summary answers it, the pitch's
// measures arena/football.toml's: A kicks off from end 0 in `play`, and
// from end 1 in `swapped`, as the policies swap ends from one play to the next.
const pitch = { length_m: 2.2, width_m: 1.5, corner_m: 0.25, board_height_m: 0.2, board_thickness_m: 0.05, boards: [], nets: [] };
const goal = { width_m: 0.6, height_m: 0.3, depth_m: 0.2 };
const ball = { radius_m: 0.035 };
const keeper = { diameter_m: 0.16, height_m: 0.26, x_m: 1.08, rail_m: 0.14 };

function match(plays) {
  return {
    id: "football", title: "Football", rig: "legs", names: ["alpha", "beta"], ctrl_dt: 0.02,
    time_limit_s: 20, pitch, goal, ball, keeper, start_x_m: 0.45, fall_hold_s: 0.3, plays,
  };
}

const play = (fields) => ({
  seed: 1, on_end: ["alpha", "beta"], scorer: null, end: "whistle", time_s: 20, events: [],
  kickoff: [0, 0, 0.035, 1, 0, 0, 0, 0, 0], settle_frames: 51, frames: 1001, ...fields,
});
const swapped = (fields) => play({ on_end: ["beta", "alpha"], ...fields });

const frames = (count, value) => new Float32Array(count * TRACE_WIDTH).fill(value);

describe("policyOn, policyColour and keeperColour: who kicked off where, in whose colour", () => {
  it("finds an end's policy by its name, whichever way round the ends are", () => {
    const summary = match([swapped({})]);
    expect(policyOn(summary, summary.plays[0], 0)).toBe(1);
    expect(policyOn(summary, summary.plays[0], 1)).toBe(0);
  });

  it("gives A and B the Arena's first two lane colours, and each keeper its shell's", () => {
    expect(LETTERS).toEqual(["A", "B"]);
    expect([policyColour(0), policyColour(1)]).toEqual([LANE_CSS[0], LANE_CSS[1]]);
    expect([keeperColour(0), keeperColour(1)]).toEqual(["#c8ff2e", "#ff2fa8"]);
  });
});

describe("playTimes: the kick-off and the decision in the replay's seconds", () => {
  it("kicks off on the settle's last frame, and decides time_s later", () => {
    const { horn_s, decided_s } = playTimes(match([]), play({ settle_frames: 51, time_s: 8.42 }));
    expect(horn_s).toBeCloseTo(1.0, 10);
    expect(decided_s).toBeCloseTo(9.42, 10);
  });

  it("never puts either before the replay's start", () => {
    expect(playTimes(match([]), play({ settle_frames: 0, time_s: 0 }))).toEqual({ horn_s: 0, decided_s: 0 });
  });
});

describe("playEvent: a play as the viewer's event", () => {
  it("builds the pitch from the match's measures, with the play's kick-off, decision and result", () => {
    const summary = match([play({}), swapped({ scorer: 1, end: "goal", time_s: 6.5 })]);
    const props = new Float32Array(9 * 4);
    const event = playEvent(summary, 1, props);
    expect(event).toMatchObject({
      course: "football", id: "football", title: "Football", rig: "legs", ctrl_dt: 0.02, scorer: 1, end: "goal",
      settle_frames: 51,
    });
    expect(event.football).toEqual({ pitch, goal, ball, keeper });
    expect(event.horn_s).toBeCloseTo(1.0, 10);
    expect(event.decided_s).toBeCloseTo(7.5, 10);
    expect(event.kickoff).toBe(summary.plays[1].kickoff);
    expect(event.props).toBe(props);
  });

  it("has no props till the server has sent them", () => {
    expect(playEvent(match([play({})]), 0).props).toBeNull();
  });
});

describe("playLanes: a play's two ducks, end 0's first", () => {
  it("dresses each policy in its own livery and colour, whichever end it kicked off from", () => {
    const summary = match([play({}), swapped({})]);
    const [left, right] = playLanes(summary, 1, [frames(51, 0), frames(51, 1)], [frames(10, 2), frames(10, 3)]);
    expect(left).toMatchObject({ name: "beta", livery: "blue", colour: LANE_COLORS[1], opacity: 1 });
    expect(right).toMatchObject({ name: "alpha", livery: "classic", colour: LANE_COLORS[0], opacity: 1 });
  });

  it("leads each lane in on its own end's settle, so the trace starts at the kick-off", () => {
    const summary = match([play({ settle_frames: 51 })]);
    const [left, right] = playLanes(summary, 0, [frames(51, 0), frames(51, 1)], [frames(10, 2), frames(10, 3)]);
    expect(frameCount(left.trace)).toBe(61);
    expect(left.trace[50 * TRACE_WIDTH]).toBe(0);
    expect(left.trace[51 * TRACE_WIDTH]).toBe(2);
    expect(right.trace[50 * TRACE_WIDTH]).toBe(1);
    expect(right.trace[51 * TRACE_WIDTH]).toBe(3);
  });
});

describe("playLine and verdict: what the referee said", () => {
  const summary = match([]);

  it("calls a goal for its scorer, by letter and by name, over its duck", () => {
    const scored = swapped({ scorer: 1, end: "goal", time_s: 8.42 });
    expect(playLine(summary, scored)).toBe("A scored at 8.42 s");
    expect(verdict(summary, scored)).toEqual({
      stamp: "Goal!", colour: LANE_CSS[0], end: 1, line: "alpha scores, 8.42 s in",
    });
  });

  it("gives the goal to the duck whose action was a number, or nobody if neither's was", () => {
    const given = play({ scorer: 0, end: "fault", time_s: 0.02 });
    expect(playLine(summary, given)).toBe("A given it at 0.02 s: B faulted");
    expect(verdict(summary, given)).toEqual({
      stamp: "Given", colour: LANE_CSS[0], end: 0, line: "alpha is given the goal: beta faulted",
    });
    const both = play({ end: "fault", time_s: 0.02 });
    expect(playLine(summary, both)).toBe("Both faulted at 0.02 s: no goal");
    expect(verdict(summary, both)).toEqual({
      stamp: "No goal", colour: null, end: null, line: "Both faulted, their actions not numbers: no goal",
    });
  });

  it("calls both ducks down, or the whistle, goalless", () => {
    const down = play({ end: "down", time_s: 12.4 });
    expect(playLine(summary, down)).toBe("Both down at 12.40 s: no goal");
    expect(verdict(summary, down)).toEqual({
      stamp: "Both down", colour: null, end: null, line: "Both ducks went down: no goal",
    });
    expect(playLine(summary, play({}))).toBe("No goal by the whistle");
    expect(verdict(summary, play({}))).toEqual({
      stamp: "No goal", colour: null, end: null, line: "No goal by the whistle, at 20 s",
    });
  });

  it("calls a diverged simulation void, with nobody's colour", () => {
    const diverged = play({ end: "void", time_s: 3.2 });
    expect(playLine(summary, diverged)).toBe("Void at 3.20 s: the simulation diverged");
    expect(verdict(summary, diverged)).toMatchObject({ stamp: "Void", colour: null, end: null });
  });
});

describe("playClock: the seconds since the kick-off", () => {
  const summary = match([]);
  const scored = play({ settle_frames: 51, scorer: 0, end: "goal", time_s: 6.5 });

  it("shows nothing before the kick-off", () => {
    expect(playClock(summary, scored, 0.4)).toBe(0);
  });

  it("counts from the kick-off, and stops where the referee decided", () => {
    expect(playClock(summary, scored, 3.25)).toBeCloseTo(2.25, 10);
    expect(playClock(summary, scored, 9.9)).toBe(6.5);
  });
});

describe("scoreAt: the score as it stood, A's goals then B's", () => {
  const summary = match([
    play({ scorer: 0, end: "goal", time_s: 5 }),
    swapped({ scorer: 0, end: "fault", time_s: 0.02 }),
    play({ end: "down", time_s: 9 }),
    swapped({ scorer: 1, end: "goal", time_s: 7 }),
  ]);

  it("counts the plays before this one, and this one once it is decided", () => {
    expect(scoreAt(summary, 0)).toEqual([0, 0]);
    expect(scoreAt(summary, 0, true)).toEqual([1, 0]);
    expect(scoreAt(summary, 1)).toEqual([1, 0]);
    expect(scoreAt(summary, 3)).toEqual([1, 1]);
    expect(scoreAt(summary, 3, true)).toEqual([2, 1]);
  });

  it("counts a goal given for a fault to the policy it was given to, wherever it kicked off", () => {
    expect(scoreAt(summary, 1, true)).toEqual([1, 1]);
    expect(scoreAt(summary, 2, true)).toEqual([1, 1]);
  });
});

describe("eventCaption: what the stage says the referee saw", () => {
  const summary = match([]);
  // Kicked off 1 s into the replay, so each event is there 1 s after its time_s.
  const busy = swapped({
    scorer: 1, end: "goal", time_s: 9,
    events: [
      { time_s: 1.0, kind: "touch", k: 0 },
      { time_s: 2.0, kind: "shot", k: 0 },
      { time_s: 2.5, kind: "save", k: 1 },
      { time_s: 2.6, kind: "touch", k: 1 },
      { time_s: 5.0, kind: "out", k: null },
      { time_s: 6.0, kind: "fall", k: 0 },
      { time_s: 7.0, kind: "stall", k: null },
    ],
  });

  it("says nothing before there is news, and a touch is none", () => {
    expect(eventCaption(summary, busy, 0.5)).toBeNull();
    expect(eventCaption(summary, busy, 2.5)).toBeNull();
  });

  it("says the last thing the referee saw, in its duck's colour or its keeper's", () => {
    expect(eventCaption(summary, busy, 3.0)).toEqual({ text: "B shoots", colour: LANE_CSS[1] });
    expect(eventCaption(summary, busy, 3.7)).toEqual({ text: "Saved!", colour: "#ff2fa8" });
    expect(eventCaption(summary, busy, 6.2)).toEqual({ text: "Out", colour: null });
    expect(eventCaption(summary, busy, 7.1)).toEqual({ text: "B down", colour: LANE_CSS[1] });
    expect(eventCaption(summary, busy, 8.0)).toEqual({ text: "Ball back in", colour: null });
  });

  it("lets a caption go CAPTION_S after what it says", () => {
    expect(eventCaption(summary, busy, 3.5 + CAPTION_S - 0.05)?.text).toBe("Saved!");
    expect(eventCaption(summary, busy, 3.5 + CAPTION_S + 0.05)).toBeNull();
    expect(eventCaption(summary, busy, 8.0 + CAPTION_S + 0.05)).toBeNull();
  });
});
