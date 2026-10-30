import { describe, expect, it } from "vitest";
import { matchPlan } from "./match.js";
import { clipPlan } from "./plan.js";
import { quackOf } from "../heist-sound.js";
import { clipScore, clipVerdict, matchScore } from "./score.js";

/** A trace of `frames` frames, the trunk going from x 0 to `to`. */
function walk(frames, to) {
  const lane = new Float32Array(frames * 21);
  for (let i = 0; i < frames; i++) lane[i * 21] = (to * i) / (frames - 1);
  return lane;
}

const event = { id: "sprint-2m", length_m: 2, clip: { sounds: ["crowd", "horn", "verdict"] } };
const trace = new Float32Array(200 * 21);
for (let i = 0; i < 200; i++) trace[i * 21] = i / 100; // x from 0 to 2 m
const TUG = {
  id: "tug-of-war", title: "Tug of War", course: "tug", metric: "mean_ground_cm", ring_m: 3,
  clip: { sounds: ["crowd", "verdict"], tape_max_s: 30 },
};
const tugRun = {
  run_id: "R1", user: "nico", policy_name: "puller", event: TUG, score: 4.2134, seeds_finished: 5, seeds_total: 5,
  trace_seed: 3, rank: 2, on_board: true, withdrawn: false, receipts: [{ act: "run", points: 10 }],
  per_seed: [{ seed: 3, status: "won", time_s: 45, score_cm: 1 }], cast: [{ policy: "self" }],
};
const traced = (status) => ({ ...tugRun, per_seed: [{ seed: 1, status: "lost", time_s: 45, score_cm: -3 }, { seed: 3, status, time_s: 45, score_cm: 1 }] });

describe("clipVerdict", () => {
  it("stamps a rated run with how its replayed bout ended, a pass for a win", () => {
    expect(["won", "lost", "draw", "pit_won", "pit_lost", "fault"].map((s) => clipVerdict(traced(s)))).toEqual([
      { stamp: "WON THE PULL", pass: true }, { stamp: "LOST THE PULL", pass: false }, { stamp: "DRAW", pass: false },
      { stamp: "PULLED IT IN", pass: true }, { stamp: "DRAGGED IN", pass: false }, { stamp: "FAULTED", pass: false }]);
  });
  it("stamps a race and a performance as it always has", () => {
    const race = { event, seeds_finished: 5 };
    expect(clipVerdict(race)).toEqual({ stamp: "VICTORY", pass: true });
    expect(clipVerdict({ ...race, seeds_finished: 0 })).toEqual({ stamp: "DNF", pass: false });
    const stage = { event: { id: "got-a-talent", course: "stage" }, seeds_finished: 1 };
    expect(clipVerdict(stage)).toEqual({ stamp: "WELL DONE", pass: true });
    expect(clipVerdict({ ...stage, seeds_finished: 0 })).toEqual({ stamp: "CUT SHORT", pass: false });
  });
});

describe("clipScore", () => {
  const plan = clipPlan(200, 12, 0);

  it("sounds the horn at the start, the stamp at the tape end and the victory after it", () => {
    const score = clipScore({ run: { run_id: "R1", event, seeds_finished: 5 }, plan, trace, ducks: [] });
    expect(score.cues.map((c) => [c.at, c.file])).toEqual([
      [3, "air-horn.mp3"],
      [7, "stamp.wav"],
      [7.16, "microduck-victory-echo.mp3"],
    ]);
    expect(score.crowd).toMatchObject({ start: 3, end: 7, verdict: "pass" });
    expect(score.crowd.progress[0]).toEqual({ second: 3, value: 0 });
    expect(score.crowd.progress.at(-1).value).toBeGreaterThan(0.9);
  });

  it("follows the author's progress through a tape that runs on past its lane, holding its last frame", () => {
    const plan = clipPlan(400, 60, 0); // a rival's 400 frames; the author's trace has 200
    const { crowd } = clipScore({ run: { run_id: "R6", event, seeds_finished: 5 }, plan, trace, ducks: [] });
    expect(crowd.progress.every((sample) => Number.isFinite(sample.value))).toBe(true);
    expect(crowd.progress.at(-1).second).toBeCloseTo(3 + 8);
    expect(crowd.progress.at(-1).value).toBeCloseTo(0.995);
  });

  it("falls after a DNF, and only plays the sources the event lists", () => {
    const dnf = clipScore({ run: { run_id: "R2", event, seeds_finished: 0 }, plan, trace, ducks: [] });
    expect(dnf.cues.at(-1).file).toBe("microduck-fall.wav");
    expect(dnf.crowd.verdict).toBe("fail");
    const quiet = clipScore({
      run: { run_id: "R3", event: { ...event, clip: { sounds: ["crowd"] } }, seeds_finished: 5 },
      plan, trace, ducks: [],
    });
    expect(quiet.cues).toEqual([]);
  });

  it("a stage's crowd answers the verdict alone: a performance goes down no course", () => {
    const event = { id: "got-a-talent", course: "stage", clip: { tape_max_s: 20, sounds: ["crowd", "verdict"] } };
    const run = { run_id: "r1", seeds_finished: 1, event };
    const plan = clipPlan(1000, 20, 26);
    const trace = new Float32Array(21 * 1026);
    const score = clipScore({ run, plan, trace, ducks: [{ sound: null }] });
    expect(score.crowd.progress).toEqual([]);
    expect(score.cues.map((cue) => cue.file)).not.toContain("air-horn.mp3");
  });

  it("a tug's crowd answers the verdict alone: a bout goes down no course", () => {
    const score = clipScore({ run: tugRun, plan: clipPlan(100, 30, 26), trace, ducks: [] });
    expect(score.crowd.progress).toEqual([]);
    expect(score.crowd.verdict).toBe("pass");
  });

  it("puts the duck's quack and wheee on the tape after the settle, cut where the performance ends", () => {
    const event = { id: "got-a-talent", course: "stage", clip: { tape_max_s: 20, sounds: ["crowd", "verdict"] } };
    const plan = clipPlan(250, 20, 26); // a 5 s performance after 26 frames of settle
    const sound = { triggers: [[0, 0, 0], [1, 1, 0], [1.2, 0, 0], [4, 0, 1]] };
    const run = { run_id: "r1", seeds_finished: 1, event };
    const voice = clipScore({ run, plan, trace: new Float32Array(21 * 276), ducks: [{ sound }] }).cues.filter((cue) => cue.call);
    expect(voice.map((cue) => cue.call)).toEqual([
      { tag: "chirp", variant: 0, start: 1, end: 4 },
      { tag: "wheee", variant: 0, start: 4, end: 5 },
    ]);
    expect(voice[0].at).toBeCloseTo(3 + 0.52 + 1);
    expect(voice[1].at).toBeCloseTo(3 + 0.52 + 4);
  });

  it("a performance that makes no sound adds no voice", () => {
    const event = { id: "got-a-talent", course: "stage", clip: { tape_max_s: 20, sounds: ["crowd", "verdict"] } };
    const run = { run_id: "r1", seeds_finished: 1, event };
    const score = clipScore({ run, plan: clipPlan(250, 20, 26), trace: new Float32Array(21 * 276), ducks: [{ sound: null }] });
    expect(score.cues.some((cue) => cue.call)).toBe(false);
  });

  it("puts the duck's song on the tape at the performance's start, and its calls in its voice", () => {
    const event = { id: "got-a-talent", course: "stage", clip: { tape_max_s: 20, sounds: ["crowd", "verdict"] } };
    const plan = clipPlan(250, 20, 26); // a 5 s performance after 26 frames of settle
    const sound = { voice: { pitch: 1 }, song: [[0.5, 1, 69, 0.7, 0.9, 0]], triggers: [[0, 0, 0], [2, 1, 0]] };
    const run = { run_id: "r1", seeds_finished: 1, event };
    const cues = clipScore({ run, plan, trace: new Float32Array(21 * 276), ducks: [{ sound }] }).cues;
    const sung = cues.find((cue) => cue.song);
    expect(sung.at).toBeCloseTo(3 + 0.52);
    expect(sung.song).toEqual({ sound, duration: expect.closeTo(5), part: { choral: false, variant: 0 } });
    expect(cues.find((cue) => cue.call).voice).toEqual({ pitch: 1 });
  });

  it("puts every duck of a troupe on the tape, each its calls in its own voice, two singers as a chorus", () => {
    const event = { id: "got-a-talent", course: "stage", clip: { tape_max_s: 20, sounds: ["crowd", "verdict"] } };
    const plan = clipPlan(250, 20, 26); // a 5 s performance after 26 frames of settle
    const singer = { sound: { song: [[0.5, 1, 69, 0.7, 0.9, 0]] } };
    const caller = { sound: { voice: { pitch: 0 }, triggers: [[0, 0, 0], [2, 1, 0]] } };
    const run = { run_id: "r1", seeds_finished: 1, event };
    const cues = clipScore({ run, plan, trace: new Float32Array(21 * 276), ducks: [singer, caller, singer] }).cues;
    expect(cues.filter((cue) => cue.song).map((cue) => [cue.at, cue.song.part])).toEqual([
      [expect.closeTo(3 + 0.52), { choral: true, variant: 0 }],
      [expect.closeTo(3 + 0.52), { choral: true, variant: 2 }],
    ]);
    expect(cues.filter((cue) => cue.call).map((cue) => [cue.at, cue.voice])).toEqual([[expect.closeTo(3 + 0.52 + 2), { pitch: 0 }]]);
  });

  it("leaves a troupe's lone singer solo", () => {
    const event = { id: "got-a-talent", course: "stage", clip: { tape_max_s: 20, sounds: ["crowd", "verdict"] } };
    const singer = { sound: { song: [[0.5, 1, 69, 0.7, 0.9, 0]] } };
    const run = { run_id: "r1", seeds_finished: 1, event };
    const cues = clipScore({ run, plan: clipPlan(250, 20, 26), trace: new Float32Array(21 * 276), ducks: [{ sound: null }, singer] }).cues;
    expect(cues.filter((cue) => cue.song).map((cue) => cue.song.part)).toEqual([{ choral: false, variant: 1 }]);
  });
});

describe("matchScore", () => {
  it("scores a match: the crowd answers the verdict and the stamp lands at the outro", () => {
    const plan = matchPlan([{ k: 0, settle: 26, steps: 1000 }]);
    const score = matchScore({ match: { match_id: "tug-of-war-0001-000", event: { clip: { sounds: ["crowd", "verdict"] } } }, plan });
    expect(score.crowd).toEqual({ start: 3, end: plan.tapeEnd / 25, verdict: "pass", progress: [] });
    expect(score.cues.map((cue) => cue.at)).toEqual([plan.tapeEnd / 25, plan.tapeEnd / 25 + 0.16]);
  });
});

it("quacks at each red and falls where each duck goes out, on the race's clock after the settle", () => {
  const HEIST = { id: "sock-heist-6m", length_m: 6, time_limit_s: 60,
    lights: { turn_s: 0.4, tolerance_m: 0.03, timetables: { 3: [[0.6, 1.6]] } }, clip: { sounds: ["giant"], tape_max_s: 60 } };
  const plan = clipPlan(300, 60, 26); // the race clock starts at 3 + 26 × 0.02 = 3.52 s of tape
  const lanes = [{ trace: walk(300, 6.05), caught: null }, { trace: walk(150, 2), caught: 50 }];
  const { cues } = clipScore({ run: { run_id: "R5", event: HEIST, seeds_finished: 5, trace_seed: 3 }, plan, trace: walk(326, 6.05), ducks: [], lanes });
  expect(cues.map((c) => [Number(c.at.toFixed(2)), c.quack ?? c.file, c.variant, c.rate]))
    .toEqual([[4.12, true, quackOf(3, 0).variant, quackOf(3, 0).rate], [4.52, "microduck-fall.wav", undefined, undefined]]);
});
