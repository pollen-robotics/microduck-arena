import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getLeaderboard: vi.fn(),
  getTrace: vi.fn(async () => Object.assign([new Float32Array(21)], { caught: null })),
  getMe: vi.fn(async () => null),
  getEvents: vi.fn(async () => []),
  getCups: vi.fn(async () => []),
  getString: vi.fn(),
  withdrawRun: vi.fn(),
}));
vi.mock("./api.js", () => api);
const viewer = vi.hoisted(() => ({ setLanes: vi.fn(), setBrightness: vi.fn(), follow() {}, sweep() {} }));
vi.mock("./viewer.js", () => ({ createViewer: vi.fn(async () => viewer) }));

import { renderRace } from "./race.js";
import { createViewer } from "./viewer.js";

const SPRINT = {
  id: "sprint-2m", title: "2 m Sprint", category: "race", vote: null, metric: "time", rig: "legs", course: "lane",
  seeds: 5, sweep_count: 5, sweep_lo: 0.2, sweep_hi: 1.2, sweep_step: 0.05, length_m: 2, slope_deg: 0,
};
const HEIST = { ...SPRINT, id: "sock-heist-6m", length_m: 6, lights: { turn_s: 0.4, tolerance_m: 0.03, timetables: {} },
  clip: { camera: { kind: "chase", back: 2.1, track: true, hold: 0.8 } } };
const row = (id, rank, seed) => ({
  run_id: id, rank, trace_seed: seed, user: id.toLowerCase(), policy_name: "walker", score: 5 + rank,
  seeds_finished: 5, seeds_total: 5, command_vx: 0.5, cast: [{ policy: "self", rig: null, start: null, sound: null }],
});

beforeEach(() => {
  vi.clearAllMocks();
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  Element.prototype.animate = () => ({ finished: new Promise(() => {}) });
});

describe("a replay's seed on the event page", () => {
  it("plays every lane on the leader's trace seed, and on the new leader's once the board is read again", async () => {
    api.getLeaderboard
      .mockResolvedValueOnce({ rows: [row("A", 1, 2), row("B", 2, 4), row("C", 3, 1)] })
      .mockResolvedValue({ rows: [row("B", 1, 4), row("C", 2, 1), row("D", 3, 5)] }); // A withdrawn
    const root = document.createElement("div");
    await renderRace(root, { event: HEIST, state: {} });
    expect(createViewer).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ camera: HEIST.clip.camera }));
    expect(api.getTrace.mock.calls).toEqual([["A", 2], ["B", 2], ["C", 2]]);
    expect(viewer.setLanes.mock.lastCall[0].map((lane) => lane.traceSeed)).toEqual([2, 2, 2]);
    root.querySelector('.modes button[data-mode="all"]').click(); // a repaint re-reads the board
    await vi.waitFor(() => expect(api.getTrace).toHaveBeenCalledWith("C", 4));
    expect(api.getTrace.mock.calls.slice(3)).toEqual([["B", 4], ["C", 4]]);
  });

  it("fetches a sprint's lanes as it always has, each its own stored trace", async () => {
    api.getLeaderboard.mockResolvedValue({ rows: [row("A", 1, 2), row("B", 2, 4), row("C", 3, 1)] });
    const root = document.createElement("div");
    await renderRace(root, { event: SPRINT, state: {} });
    expect(createViewer).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ camera: null }));
    expect(api.getTrace.mock.calls).toEqual([["A", undefined], ["B", undefined], ["C", undefined]]);
  });
});
