import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getJob: vi.fn(),
  getCheckpoint: vi.fn(async (event, id, n) => ({ checkpoint: n, score: 5.62, ducks: 1, traces: [new Float32Array(8)],
    cast: [{ policy: "self", rig: null, start: null, sound: null }] })),
  getCode: vi.fn(),
  publishJob: vi.fn(),
  pushCode: vi.fn(),
  useFork: vi.fn(),
  stopJob: vi.fn(),
  getTimeline: vi.fn(async () => ({ text: "{}" })),
  saveTimeline: vi.fn(async (event, text) => ({ text })),
  getPerformers: vi.fn(async () => []),
}));
vi.mock("./api.js", () => api);
const viewer = vi.hoisted(() => ({ setLanes: vi.fn(), setBrightness: vi.fn(), dispose: vi.fn(), follow() {}, sweep() {} }));
vi.mock("../viewer.js", () => ({ createViewer: vi.fn(async () => viewer) }));

import { createViewer } from "../viewer.js";
import { POLL_MS, futureSlots, mountJob } from "./job.js";

const row = (n, score, finished = 5) => ({ n, status: "evaluated", score, seeds_finished: finished, seeds_total: 5, command_vx: 0.55 });
const JOB = {
  id: "first", name: "first", where: "hf-jobs", state: "running", progress: { done: 1250, total: 3000 },
  started: "2026-09-30T09:15:00+00:00", run_id: "r", dirty: false, job_url: "https://huggingface.co/jobs/alice/j1",
  checkpoints: [row(0, 50, 0), row(250, 8.1), row(500, 5.62), { n: 750, status: "queued" }], best: 500, published: null,
  log: ["$ uv run --no-sync train …"], next: 1, following: true, curve: [[1, 0.1], [2, 0.3]], commit: "abc1234",
  recipe: { num_envs: 4096, max_iterations: 3000, seed: 1 }, params: { forward_reward: 2 }, code_url: null,
};
const CODE = { fork: null, changes: [], identity: true, commit: "abc1234", unpushed: 0 };
const SPRINT = { id: "sprint-2m", title: "2 m Sprint", category: "race", vote: null, metric: "time", rig: "legs",
  length_m: 2, slope_deg: 0, sweep_lo: 0.2, sweep_hi: 1.2, sweep_count: 21 };
const HEIST = { ...SPRINT, id: "sock-heist-6m", length_m: 6, lights: { turn_s: 0.4, tolerance_m: 0.03, timetables: {} },
  clip: { camera: { kind: "chase", back: 2.1, track: true, hold: 0.8 } } };
const TALENT = { id: "got-a-talent", title: "MicroDuck Got a Talent", category: "showcase", course: "stage",
  metric: "votes", rig: "legs", time_limit_s: 20, vote: { ballot_min: 2 },
  size_m: [2.6, 3.8], max_ducks: 4, edge_margin_m: 0.3, min_spacing_m: 0.3 };
const status = (event) => ({ arena: "https://arena.test", gpu: false, challenges: [{ event, folder: "sprint_2m", task: "S", recipe: {}, knobs: [], running: 1 }] });
const account = { get: () => ({ phase: "in", user: "alice", canPay: true }), logIn: vi.fn(), check: vi.fn() };
const settle = async () => { for (let i = 0; i < 5; i += 1) await Promise.resolve(); };
const open = (root, event = SPRINT, job = "first") =>
  mountJob(root, { status: status(event), account, route: { view: "job", event: event.id, job } });

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  api.getJob.mockReset();
  api.getCode.mockResolvedValue(CODE);
  // The polls run the clock past the deck's orbit hint, which jsdom has
  // neither the media queries nor the animations to play.
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  Element.prototype.animate = () => ({ finished: new Promise(() => {}) });
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  delete Element.prototype.animate;
});

describe("a training's page", () => {
  it("counts the checkpoints still to come from the spacing of those saved", () => {
    expect(futureSlots(JOB)).toEqual([1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750, 2999]);
    expect(futureSlots({ ...JOB, state: "done" })).toEqual([]);
  });

  it("opens a race on its best checkpoint and replays it", async () => {
    api.getJob.mockResolvedValue(JOB);
    const root = document.createElement("div");
    await mountJob(root, { status: status(SPRINT), account, route: { view: "job", event: "sprint-2m", job: "first" } });
    await settle();
    expect(root.querySelector(".racetitle").textContent).toBe("first");
    expect(root.querySelector(".raceeyebrow").textContent).toBe("Training · Hugging Face Jobs · L4");
    expect(root.querySelector(".score__label").textContent).toBe("Checkpoint 500 · ★ best");
    expect(root.querySelector(".score__value").textContent).toBe("5.62 s");
    expect(api.getCheckpoint).toHaveBeenCalledWith("sprint-2m", "first", 500);
    expect(createViewer).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ camera: null }));
    expect(viewer.setLanes).toHaveBeenLastCalledWith([expect.objectContaining({ name: "checkpoint 500", tier: "trial" })], SPRINT);
    expect(root.querySelector(".output pre").textContent).toContain("uv run --no-sync train");
    expect(viewer.setLanes.mock.lastCall[0][0]).not.toHaveProperty("caught");
  });

  it("replays a sock heist checkpoint on its trace seed, caught where it was caught", async () => {
    api.getJob.mockResolvedValue(JOB);
    api.getCheckpoint.mockResolvedValueOnce({ checkpoint: 500, score: 30, ducks: 1, traces: [new Float32Array(21)],
      trace_seed: 4, caught_frame: 120, cast: [{ policy: "self", rig: null, start: null, sound: null }] });
    const root = document.createElement("div");
    await open(root, HEIST);
    await settle();
    expect(createViewer).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ camera: HEIST.clip.camera }));
    expect(viewer.setLanes).toHaveBeenLastCalledWith([expect.objectContaining({ traceSeed: 4, caught: 120 })], HEIST);
  });

  it("a tug's training rates its checkpoints in centimetres and replays the bout against the reference", async () => {
    const TUG = { id: "tug-of-war", title: "Tug of War", category: "versus", course: "tug", metric: "mean_ground_cm", rig: "legs", vote: null };
    api.getJob.mockResolvedValue({ ...JOB, checkpoints: [row(0, 2), row(250, 10.1)], best: 250 });
    const [w, e, string] = [new Float32Array(21), new Float32Array(21), new Float32Array(51)];
    api.getCheckpoint.mockResolvedValueOnce({ checkpoint: 250, score: 10.1, ducks: 2, traces: [w, e], string, trace_seed: 2, cast: null });
    const root = document.createElement("div");
    await open(root, TUG);
    await settle();
    expect(root.querySelector(".ckpts .hint").textContent).toBe("The higher, the stronger. Click one to watch it.");
    expect(root.querySelector(".score__value").textContent).toBe("10.1 cm");
    expect(viewer.setLanes).toHaveBeenLastCalledWith([{ tug: "bout", ducks: [{ trace: w, livery: "charcoal", name: "Reference" },
      { trace: e, livery: "classic", name: "checkpoint 250" }], string: { trace: string } }], TUG);
  });

  it("a click on a bar replays that checkpoint", async () => {
    api.getJob.mockResolvedValue(JOB);
    const root = document.createElement("div");
    await mountJob(root, { status: status(SPRINT), account, route: { view: "job", event: "sprint-2m", job: "first" } });
    await settle();
    root.querySelectorAll(".ckpts .bars i")[1].click();
    await settle();
    expect(root.querySelector(".score__value").textContent).toBe("8.10 s");
    expect(api.getCheckpoint).toHaveBeenLastCalledWith("sprint-2m", "first", 250);
  });

  it("a voted event opens on no checkpoint", async () => {
    api.getJob.mockResolvedValue({ ...JOB, best: null });
    const root = document.createElement("div");
    await mountJob(root, { status: status(TALENT), account, route: { view: "job", event: "got-a-talent", job: "first" } });
    await settle();
    expect(root.querySelector(".score__label").textContent).toBe("No checkpoint chosen");
    expect(root.querySelector(".publish__go").textContent).toBe("Pick a checkpoint");
  });

  it("a stage's training page edits its performance and says what the checkpoint did", async () => {
    const stageRow = { n: 500, status: "evaluated", score: 20, seeds_finished: 1, seeds_total: 1, command_vx: 0,
      stage: [{ fell_at: null, seated_s: 7.9, standing_s: 11.5 }] };
    api.getJob.mockResolvedValue({ ...JOB, checkpoints: [stageRow], best: null });
    const root = document.createElement("div");
    await open(root, TALENT);
    await settle();
    expect(root.querySelector(".performance textarea")).not.toBeNull();
    expect(api.getTimeline).toHaveBeenCalledWith("got-a-talent");
    expect(root.querySelector(".performance .placement")).not.toBeNull();
    expect(api.getPerformers).toHaveBeenCalledWith("got-a-talent");
    root.querySelector(".ckpts .bars i").click();
    await settle();
    expect(root.querySelector(".score__value").textContent).toBe("No fall");
    expect(root.querySelector(".score__seeds").textContent).toBe("seated 7.90 s · standing 11.50 s");
  });

  it("a Save and play's fresh evaluation counts even while the ticket row still says queued", async () => {
    const stageEvent = { ...TALENT, metric: "time" }; // so the best checkpoint is picked at once, as on a race
    api.getJob.mockResolvedValue({ ...JOB, checkpoints: [{ n: 500, status: "queued" }], best: 500 });
    api.getCheckpoint.mockResolvedValue({ checkpoint: 500, ducks: 1, traces: [new Float32Array(8)],
      cast: [{ policy: "self", rig: "legs", start: { x: 0, y: 0, yaw: 0 }, sound: null }],
      stage: [{ fell_at: 3.2, seated_s: 1, standing_s: 2 }] });
    const root = document.createElement("div");
    await open(root, stageEvent);
    await settle();
    expect(root.querySelector(".score__value").textContent).toBe("Fell at 3.20 s");
    expect(root.querySelector(".score__seeds").textContent).toBe("seated 1.00 s · standing 2.00 s");
  });

  it("a race has no performance to edit", async () => {
    api.getJob.mockResolvedValue(JOB);
    const root = document.createElement("div");
    await open(root, SPRINT);
    await settle();
    expect(root.querySelector(".performance")).toBeNull();
    expect(api.getTimeline).not.toHaveBeenCalled();
  });

  it("plays a troupe's every duck on its own rig, and says what each did", async () => {
    api.getJob.mockResolvedValue({ ...JOB, best: null,
      checkpoints: [{ n: 500, status: "evaluated", score: 2, seeds_finished: 1, seeds_total: 1, command_vx: 0 }] });
    api.getCheckpoint.mockResolvedValueOnce({
      checkpoint: 500, ducks: 2, traces: [new Float32Array(21), new Float32Array(21)],
      cast: [
        { policy: "self", rig: "legs", start: { x: 0, y: 0, yaw: 0 }, sound: null },
        { policy: `pollen-robotics/microduck-roller@${"c".repeat(40)}`, rig: "rollers", start: { x: 0.5, y: 0, yaw: 180 }, sound: null },
      ],
      stage: [{ fell_at: null, seated_s: 1, standing_s: 0.5 }, { fell_at: 0.8, seated_s: 0, standing_s: 0.2 }],
    });
    const root = document.createElement("div");
    await open(root, TALENT);
    await settle();
    root.querySelector(".ckpts .bars i").click();
    await settle();
    const [[lane]] = viewer.setLanes.mock.lastCall;
    expect(lane.name).toBe("checkpoint 500");
    expect(lane.ducks.map((duck) => duck.rig)).toEqual(["legs", "rollers"]);
    expect(root.querySelector(".score__value").textContent).toBe("1 of 2 fell");
    expect(root.querySelector(".score__seeds").textContent).toBe(
      "★ · no fall · seated 1.00 s · standing 0.50 s\n1 · fell at 0.80 s · seated 0.00 s · standing 0.20 s");
  });

  it("says why a checkpoint cannot play: the last line of what failed", async () => {
    api.getJob.mockResolvedValue({ ...JOB, best: null, checkpoints: [{ n: 500, status: "failed" }] });
    api.getCheckpoint.mockResolvedValueOnce({ checkpoint: 500,
      error: "[publish] exporting checkpoint 500\nTimelineError: 'local:sprint_2m/2026-09-25_10-00-00_first@7': this checkout has no such checkpoint\n" });
    const root = document.createElement("div");
    await open(root, TALENT);
    await settle();
    root.querySelector(".ckpts .bars i").click();
    await settle();
    expect(root.querySelector(".score__value").textContent).toBe("Failed");
    expect(root.querySelector(".score__seeds").textContent).toBe(
      "TimelineError: 'local:sprint_2m/2026-09-25_10-00-00_first@7': this checkout has no such checkpoint");
  });

  it("keeps what is typed while the page redraws every few seconds", async () => {
    // Review focus: the job page polls; the name and the words for the commentators must stay.
    api.getJob.mockResolvedValue(JOB);
    const root = document.createElement("div");
    const page = await mountJob(root, { status: status(SPRINT), account, route: { view: "job", event: "sprint-2m", job: "first" } });
    await settle();
    root.querySelector("input[name=policy]").value = "my-walker";
    root.querySelector("textarea").value = "It leans into every step.";
    api.getJob.mockResolvedValue({ ...JOB, log: ["Learning iteration 1300/3000"], next: 2 });
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(root.querySelector("input[name=policy]").value).toBe("my-walker");
    expect(root.querySelector("textarea").value).toBe("It leans into every step.");
    expect(root.querySelector(".output pre").textContent).toContain("Learning iteration 1300/3000");
    page.leave();
    expect(viewer.dispose).toHaveBeenCalled();
  });

  it("publishes a troupe call by call until the star is entered", async () => {
    api.getJob.mockResolvedValue(JOB);
    api.publishJob
      .mockResolvedValueOnce({ publishing: { done: 1, of: 2 } })
      .mockResolvedValueOnce({ repo: "alice/microduck-first", revision: "a".repeat(40), env: null,
        entered: "entered on sprint-2m: 4.892 s (5/5 seeds) at 0.55 m/s", page_url: "http://arena.test/#/r/x" });
    const root = document.createElement("div");
    const page = await open(root);
    await settle();
    const words = root.querySelector(".publish textarea");
    words.value = "It leans into every step.";
    words.dispatchEvent(new Event("input"));
    root.querySelector(".publish__go").click();
    // vi.waitFor steps the fake clock 50 ms at a time: well before the next poll.
    await vi.waitFor(() => expect(root.querySelector(".publish .result").hidden).toBe(false));
    expect(api.publishJob).toHaveBeenCalledTimes(2);
    expect(api.publishJob.mock.calls[1]).toEqual(api.publishJob.mock.calls[0]);
    page.leave();
  });

  it("keeps its bars through a poll, and a bar picked from the keyboard keeps the focus", async () => {
    api.getJob.mockResolvedValue(JOB);
    const root = document.createElement("div");
    document.body.append(root);
    const page = await open(root);
    await settle();
    const bar = root.querySelectorAll(".ckpts .bars i")[1];
    bar.focus();
    bar.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    await settle();
    expect(root.querySelectorAll(".ckpts .bars i")[1]).toBe(bar);
    expect(bar.classList.contains("sel")).toBe(true);
    expect(document.activeElement).toBe(bar);
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(root.querySelectorAll(".ckpts .bars i")[1]).toBe(bar);
    expect(root.querySelector(".ticks .sel").textContent).toBe("250");
    page.leave();
    root.remove();
  });

  it("says in the score why a checkpoint cannot play, until another is picked", async () => {
    api.getJob.mockResolvedValue(JOB);
    const root = document.createElement("div");
    const page = await open(root);
    await settle();
    api.getCheckpoint.mockRejectedValueOnce(new Error("Checkpoint 250 is not evaluated yet."));
    root.querySelectorAll(".ckpts .bars i")[1].click();
    await settle();
    await vi.advanceTimersByTimeAsync(POLL_MS);
    expect(root.querySelector(".score__seeds").textContent).toBe("Checkpoint 250 is not evaluated yet.");
    root.querySelectorAll(".ckpts .bars i")[2].click();
    await settle();
    expect(root.querySelector(".score__seeds").textContent).toBe("5/5 seeds · at 0.55 m/s");
    page.leave();
  });

  it("a checkpoint that fails to load late never paints over the one picked since", async () => {
    api.getJob.mockResolvedValue(JOB);
    const root = document.createElement("div");
    const page = await open(root);
    await settle();
    let fail;
    api.getCheckpoint.mockImplementationOnce(() => new Promise((resolve, reject) => { fail = reject; }));
    root.querySelectorAll(".ckpts .bars i")[1].click(); // 250, still loading
    root.querySelectorAll(".ckpts .bars i")[2].click(); // 500, loaded already
    await settle();
    fail(new Error("Checkpoint 250 is not evaluated yet."));
    await settle();
    expect(root.querySelector(".score__seeds").textContent).toBe("5/5 seeds · at 0.55 m/s");
    page.leave();
  });

  it("stops a training once confirmed, saying what is lost, and asks once while it stops", async () => {
    api.getJob.mockResolvedValue(JOB);
    let stopped;
    api.stopJob.mockImplementation(() => new Promise((resolve) => { stopped = resolve; }));
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const root = document.createElement("div");
    const page = await open(root);
    await settle();
    const stop = root.querySelector(".job-stop");
    expect(stop.hidden).toBe(false);
    stop.click();
    stop.click();
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(confirm).toHaveBeenCalledWith("Stop first? A stopped Hugging Face job cannot be resumed.");
    expect(api.stopJob).toHaveBeenCalledTimes(1);
    api.getJob.mockResolvedValue({ ...JOB, state: "stopped" });
    stopped({});
    await settle();
    expect(stop.hidden).toBe(true);
    expect(root.querySelector(".raceeyebrow").textContent).toBe("Stopped · Hugging Face Jobs · L4");
    confirm.mockRestore();
    page.leave();
  });

  it("drops a poll's answer that a newer look overtook", async () => {
    api.getCode.mockResolvedValue({ ...CODE, fork: "alice/microduck-challenges", unpushed: 2 });
    api.getJob.mockResolvedValue(JOB);
    const root = document.createElement("div");
    const page = await open(root);
    await settle();
    let late;
    api.getJob.mockImplementationOnce(() => new Promise((resolve) => { late = resolve; }));
    await vi.advanceTimersByTimeAsync(POLL_MS);
    api.pushCode.mockResolvedValue({});
    api.getJob.mockResolvedValue({ ...JOB, log: ["looked again after the push"], next: 2 });
    root.querySelector(".checks button").click();
    await settle();
    late({ ...JOB, log: ["a stale line"], next: 2 });
    await settle();
    const output = root.querySelector(".output pre").textContent;
    expect(api.pushCode).toHaveBeenCalled();
    expect(output).toContain("looked again after the push");
    expect(output).not.toContain("a stale line");
    page.leave();
  });

  it("once left, asks nothing more and draws no answer still out", async () => {
    api.getJob.mockResolvedValue(JOB);
    const root = document.createElement("div");
    const page = await open(root);
    await settle();
    let late;
    api.getJob.mockImplementationOnce(() => new Promise((resolve) => { late = resolve; }));
    await vi.advanceTimersByTimeAsync(POLL_MS);
    page.leave();
    late({ ...JOB, log: ["after leaving"], next: 2 });
    await vi.advanceTimersByTimeAsync(POLL_MS * 3);
    expect(root.querySelector(".output pre").textContent).not.toContain("after leaving");
    expect(api.getJob).toHaveBeenCalledTimes(2);
  });

  it("after a restart it links the job's whole log on Hugging Face", async () => {
    api.getJob.mockResolvedValue({ ...JOB, following: false, log: [] });
    const root = document.createElement("div");
    await mountJob(root, { status: status(SPRINT), account, route: { view: "job", event: "sprint-2m", job: "first" } });
    await settle();
    expect(root.querySelector(".output a").href).toBe("https://huggingface.co/jobs/alice/j1");
  });

  it("says so for a training that is not there", async () => {
    api.getJob.mockRejectedValue(new Error("No training nope for sprint-2m."));
    const root = document.createElement("div");
    await mountJob(root, { status: status(SPRINT), account, route: { view: "job", event: "sprint-2m", job: "nope" } });
    expect(root.querySelector(".failed").textContent).toContain("nope");
  });
});
