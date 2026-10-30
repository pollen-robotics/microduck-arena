import { describe, expect, it } from "vitest";
import { credit, featured, pageCamera, replayLane, replaySeed, stageDucks } from "./cast.js";
import { TRACE_WIDTH, frameCount } from "./replay.js";

const STAGE = { id: "got-a-talent", course: "stage", rig: "legs" };
const SPRINT = { id: "sprint-2m", course: "lane", rig: "legs" };
const HEIST = { id: "sock-heist-6m", course: "lane", rig: "legs", lights: { turn_s: 0.4, tolerance_m: 0.03, timetables: {} },
  clip: { camera: { kind: "chase", back: 2.1, track: true, hold: 0.8 } } };
const TUG = { id: "tug-of-war", course: "tug", rig: "legs" };
/** A borrowed policy as arena/cast.py borrowed_source records it. */
const borrowed = (user, name) => ({
  repo_id: `${user}/microduck-${name}`, filename: "policy.onnx", revision: "a".repeat(40),
  url: `https://huggingface.co/${user}/microduck-${name}/resolve/${"a".repeat(40)}/policy.onnx`,
  model_sha256: "f".repeat(64), user, policy_name: name,
});
const walker = borrowed("bob", "walker");
const frames = (count, value) => new Float32Array(count * TRACE_WIDTH).fill(value);
const SINGS = { song: [[0, 1, 69, 0.7, 0.9, 0]] };

describe("stageDucks", () => {
  const cast = [
    { policy: "self", rig: null, start: { x: 0, y: 0, yaw: 0 }, sound: SINGS },
    { policy: walker, rig: "rollers", start: { x: 0.4, y: -0.6, yaw: 90 }, sound: null },
    { policy: "self", rig: null, start: { x: -0.4, y: 0.6, yaw: 0 }, sound: null },
  ];
  const traces = [frames(3, 0), frames(3, 1), frames(3, 2)];

  it("draws every duck in duck order, the star first, each on its own trace, rig and place, singing its own sound", () => {
    expect(stageDucks(cast, traces, null, { livery: "purple", eventRig: "legs" })).toEqual([
      { trace: traces[0], lead: 0, sound: SINGS, rig: "legs", livery: "purple", start: cast[0].start, star: true },
      { trace: traces[1], lead: 0, sound: null, rig: "rollers", livery: "classic", start: cast[1].start, star: false },
      { trace: traces[2], lead: 0, sound: null, rig: "legs", livery: "purple", start: cast[2].start, star: false },
    ]);
  });

  it("dresses the author's own ducks in the entry's livery on an anonymous ballot too", () => {
    const ballot = cast.map((duck) => ({ ...duck, policy: duck.policy === "self" ? "self" : "borrowed" }));
    expect(stageDucks(ballot, traces, null, { livery: "classic", eventRig: "legs" }).map((duck) => duck.livery))
      .toEqual(["classic", "classic", "classic"]);
  });

  it("keeps a run recorded before troupes as it was: one duck, on the event's rig, with no place of its own", () => {
    const [star] = stageDucks([{ policy: "self", rig: null, start: null, sound: null }], [frames(2, 0)], null, { livery: "purple", eventRig: "legs" });
    expect(star).toMatchObject({ rig: "legs", livery: "purple", start: null, star: true });
  });

  it("plays each duck's settle first, every duck in step", () => {
    const settles = [frames(2, 10), frames(2, 11), frames(2, 12)];
    const ducks = stageDucks(cast, traces, settles, { livery: "purple", eventRig: "legs", lead: 2 });
    for (const [k, duck] of ducks.entries()) {
      expect(frameCount(duck.trace)).toBe(5);
      expect(duck.trace[0]).toBe(10 + k);
      expect(duck.trace[2 * TRACE_WIDTH]).toBe(k);
      expect(duck.lead).toBe(2);
    }
  });
});

describe("replaySeed", () => {
  it("plays every lane of a lights replay on its row's trace seed, and on no seed elsewhere", () => {
    expect(replaySeed(HEIST, { trace_seed: 3 })).toBe(3);
    expect(replaySeed(HEIST, undefined)).toBeUndefined(); // an empty board
    expect(replaySeed(SPRINT, { trace_seed: 3 })).toBeUndefined();
  });
});

describe("pageCamera", () => {
  it("films a sock heist on its pages with its clip's camera, and any other race with the page's own chase", () => {
    expect(pageCamera(HEIST)).toBe(HEIST.clip.camera);
    expect(pageCamera(SPRINT)).toBeNull();
  });
});

describe("replayLane", () => {
  const lane = { runId: "r1", tier: "ghost", livery: "purple", name: "alice" };

  it("puts a stage's whole performance in its lane, every duck of its cast", () => {
    const cast = [{ policy: "self", rig: null, start: null, sound: null }, { policy: walker, rig: "rollers", start: null, sound: null }];
    const traces = [frames(2, 0), frames(2, 1)];
    const made = replayLane(STAGE, cast, traces, lane);
    expect(made).toMatchObject(lane);
    expect(made.ducks.map((duck) => [duck.trace, duck.rig, duck.livery])).toEqual([[traces[0], "legs", "purple"], [traces[1], "rollers", "classic"]]);
    expect(made.trace).toBeUndefined();
  });

  it("races a lane's one duck, as it always has", () => {
    const trace = frames(2, 0);
    expect(replayLane(SPRINT, [{ policy: "self", rig: null, start: null, sound: null }], [trace], lane)).toEqual({ ...lane, trace });
  });

  it("carries a lights lane's caught frame beside its trace", () => {
    const trace = frames(2, 0);
    expect(replayLane(HEIST, [{ policy: "self" }], Object.assign([trace], { caught: 41 }), { ...lane, traceSeed: 3 }))
      .toEqual({ ...lane, traceSeed: 3, trace, caught: 41 });
  });

  it("puts a rated run's entry on its end of the string and the reference duck on the other, the string beside them", () => {
    const [west, east] = [frames(2, 0), frames(2, 1)];
    expect(replayLane(TUG, [{ policy: "self" }], [west, east], { ...lane, traceSeed: 4 }, { trace: "st" })).toEqual({ ...lane, traceSeed: 4, tug: "bout",
      ducks: [{ trace: west, livery: "charcoal", name: "Reference" }, { trace: east, livery: "purple", name: "alice" }], string: { trace: "st" } });
  });
});

describe("featured", () => {
  it("credits each borrowed policy once, in the order the troupe brings them", () => {
    const roller = borrowed("carol", "roller");
    const cast = [{ policy: "self" }, { policy: walker }, { policy: roller }, { policy: { ...walker } }, { policy: "self" }];
    expect(featured(cast)).toEqual([walker, roller]);
  });

  it("credits nobody when every duck is the author's own", () => {
    expect(featured([{ policy: "self" }, { policy: "self" }])).toEqual([]);
  });
});

describe("credit", () => {
  const run = { user: "alice", policy_name: "sitter" };

  it("names the author and the star's policy for a lone duck", () => {
    expect(credit({ ...run, cast: [{ policy: "self" }] })).toBe("@alice · sitter");
  });

  it("counts a troupe's ducks, featuring each borrowed policy once", () => {
    const roller = borrowed("carol", "roller");
    const cast = [{ policy: "self" }, { policy: walker }, { policy: "self" }, { policy: roller }, { policy: walker }];
    expect(credit({ ...run, cast })).toBe("@alice · sitter · 5 ducks, featuring @bob · walker, @carol · roller");
  });

  it("features nobody in a troupe of the author's own", () => {
    expect(credit({ ...run, cast: [{ policy: "self" }, { policy: "self" }, { policy: "self" }] })).toBe("@alice · sitter · 3 ducks");
  });
});
