import { describe, expect, it } from "vitest";
import { clipStatus, intentUrl, postText, shareStrip, wireShare } from "./share.js";

/** X's count: every link is 23 characters, whatever its length. Test-only —
 * nothing in share.js needs its own count of what X will display. */
const xLength = (text) => text.replace(/(https?:\/\/)?[\w.-]+\.\w+\/\S*/g, "x".repeat(23)).length;

const run = {
  run_id: "01M2X", user: "alice", policy_name: "walker v2", score: 2.314,
  seeds_finished: 5, seeds_total: 5, per_seed: [], on_board: true, withdrawn: false, rank: 3,
  receipts: [{ act: "run", points: 10 }, { act: "own_best", points: 25 }],
  policy_url: "https://huggingface.co/alice/microduck-walker-v2",
  event: { id: "sprint-2m", title: "2 m Sprint" },
};
const origin = "https://arena.hf.space";

describe("postText", () => {
  it("says the result, links the run, names the weights, and mentions only on X", () => {
    expect(postText(run, { origin, network: "x" })).toBe(
      "I coded a robot duck to walk. On 2 m Sprint it finished 5/5 seeds in 2.314 s, #3 on the board (+35 pts).\n" +
      "Beat it: https://arena.hf.space/r/01M2X\n" +
      "Weights: huggingface.co/alice/microduck-walker-v2\n" +
      "#MicroduckArena @pollenrobotics @huggingface",
    );
    expect(postText(run, { origin, network: "linkedin" }).split("\n").at(-1)).toBe("#MicroduckArena");
  });

  it("leaves out the place off the board, the points at zero, and the weights without a repo", () => {
    const plain = { ...run, on_board: false, receipts: [], policy_url: null };
    const text = postText(plain, { origin, network: "x" });
    expect(text).toContain("finished 5/5 seeds in 2.314 s.\n");
    expect(text).not.toContain("Weights");
  });

  it("tells a DNF how it ended", () => {
    const fell = { ...run, seeds_finished: 0, per_seed: [{ seed: 1, status: "fall", time_s: null }] };
    expect(postText(fell, { origin, network: "x" })).toContain("finished 0/5 seeds on its feet — it ate the floor.");
    const late = { ...fell, per_seed: [{ seed: 1, status: "timeout", time_s: null }] };
    expect(postText(late, { origin, network: "x" })).toContain("it ran out of time.");
    const caught = { ...fell, per_seed: [{ seed: 1, status: "caught", time_s: null }, { seed: 2, status: "timeout", time_s: null }] };
    expect(postText(caught, { origin, network: "x" })).toContain("it got caught moving while the giant looked.");
  });

  it("fits X with a long policy name, links counted as 23", () => {
    const long = { ...run, policy_name: "x".repeat(60), policy_url: `https://huggingface.co/alice/microduck-${"x".repeat(60)}` };
    expect(xLength(postText(long, { origin, network: "x" }))).toBeLessThanOrEqual(280);
  });
});

describe("postText for a performance", () => {
  const duck = { policy: "self", rig: null, start: null, sound: null };
  const stageRun = { event: { title: "MicroDuck Got a Talent", course: "stage" }, seeds_total: 1, seeds_finished: 1,
    score: 20, receipts: [{ points: 100 }], per_seed: [], run_id: "r1", rank: 1, on_board: true, policy_url: null, cast: [duck] };

  it("shares a performance as one", () => {
    const text = postText(stageRun, { origin: "https://arena.test", network: "linkedin" });
    expect(text).toContain("I coded a robot duck to perform. On MicroDuck Got a Talent it gave a 20.00 s performance (+100 pts).");
    expect(text).toContain("Watch it: https://arena.test/r/r1");
    expect(postText({ ...stageRun, seeds_finished: 0, receipts: [] }, { origin: "https://arena.test", network: "linkedin" }))
      .toContain("Its performance on MicroDuck Got a Talent was cut short.");
  });

  it("shares a troupe as robot ducks", () => {
    const troupe = { ...stageRun, cast: [duck, duck, duck] };
    const text = postText(troupe, { origin: "https://arena.test", network: "linkedin" });
    expect(text).toContain("I coded robot ducks to perform. On MicroDuck Got a Talent they gave a 20.00 s performance (+100 pts).");
    expect(text).toContain("Watch them: https://arena.test/r/r1");
    expect(postText({ ...troupe, seeds_finished: 0, receipts: [] }, { origin: "https://arena.test", network: "linkedin" }))
      .toContain("Their performance on MicroDuck Got a Talent was cut short.");
  });
});

describe("postText for a rated tug run", () => {
  const TUG = { id: "tug-of-war", title: "Tug of War", course: "tug", metric: "mean_ground_cm" };
  const tugRun = {
    run_id: "R1", user: "nico", policy_name: "puller", event: TUG, score: 12.34, seeds_finished: 5, seeds_total: 5,
    trace_seed: 3, rank: 2, on_board: true, withdrawn: false, receipts: [{ act: "run", points: 10 }],
    per_seed: [{ seed: 3, status: "won", time_s: 45, score_cm: 10.1 }], cast: [{ policy: "self" }],
  };

  it("shares its rating in centimetres and dares the next one to beat it", () => {
    expect(postText(tugRun, { origin: "https://x", network: "bluesky" }).split("\n").slice(0, 2)).toEqual([
      "I coded a robot duck to pull. On Tug of War its rating is 12.3 cm against the reference duck, #2 on the board (+10 pts).",
      "Beat it: https://x/r/R1",
    ]);
  });
});

describe("intentUrl", () => {
  it("opens the two composers that take a text", () => {
    expect(intentUrl("x", "a b")).toBe("https://x.com/intent/post?text=a%20b");
    expect(intentUrl("linkedin", "a b")).toBe("https://www.linkedin.com/feed/?shareActive=true&text=a%20b");
  });
});

describe("shareStrip", () => {
  it("is a row of two links and three buttons, then a row of two clip stickers that follow the clip's state", () => {
    const strip = shareStrip(run, { origin });
    expect([...strip.root.children].map((el) => el.tagName)).toEqual(["NAV", "DIV", "P", "DIV"]);
    const marks = [...strip.root.querySelector("nav").children];
    expect(marks.map((el) => el.tagName)).toEqual(["A", "A", "BUTTON", "BUTTON", "BUTTON"]);
    expect(marks[0].href).toMatch(/^https:\/\/x\.com\/intent\/post\?text=/);
    expect(marks[2].dataset.upload).toBe("instagram");
    expect(marks[4].dataset.copy).toBe("link");

    strip.setClip({ state: "queued", ahead: 2 });
    const clips = strip.root.querySelectorAll("[data-clip]");
    expect(clips.length).toBe(2);
    expect(clips[0].textContent).toBe("Clip · queued");
    expect(clips[0].getAttribute("aria-disabled")).toBe("true");
    expect(clips[0].hasAttribute("href")).toBe(false);
    // The reel turns on the sticker itself: the row says the work is alive
    // without the reader having to look anywhere else.
    expect(clips[0].querySelector(".clip-reel")).not.toBe(null);
    expect(clips[0].classList.contains("sticker-working")).toBe(true);

    strip.setClip({ state: "rendering", stage: "frames", done: 310, total: 880 });
    expect(clips[0].textContent).toBe("Clip · 35%");
    expect(clips[0].classList.contains("sticker-working")).toBe(true);

    strip.setClip({ state: "ready", layouts: { landscape: { url: "/l.mp4" }, vertical: { url: "/v.mp4" } } });
    expect(clips[1].getAttribute("href")).toBe("/v.mp4?download=1");
    expect(clips[1].hasAttribute("download")).toBe(true);
    expect(clips[1].textContent).toBe("Clip · vertical");
    expect(clips[1].classList.contains("sticker-working")).toBe(false);

    // A clip that failed says so and stays on the row. Hiding it is what made
    // a jammed render look like a feature that was never there.
    strip.setClip({ state: "failed", reason: "TimeoutError: timed out in 60.0s" });
    expect(clips[0].hidden || clips[1].hidden).toBe(false);
    expect(clips[0].textContent).toBe("Clip · failed");
    expect(clips[0].getAttribute("aria-disabled")).toBe("true");

    strip.setClip({ state: "none" });
    expect(clips[0].hidden && clips[1].hidden).toBe(true);
  });

  it("plays the landscape clip under the stickers once it is ready, fetching nothing before a press", () => {
    const strip = shareStrip(run, { origin });
    const player = strip.root.querySelector("video");
    const screen = player.parentElement;
    strip.setClip({ state: "none" });
    expect(screen.hidden).toBe(true);
    expect(player.hasAttribute("src")).toBe(false);

    strip.setClip({
      state: "ready",
      poster: "/p.png",
      layouts: { landscape: { url: "/l.mp4" }, vertical: { url: "/v.mp4" } },
    });
    expect(screen.hidden).toBe(false);
    expect(player.getAttribute("src")).toBe("/l.mp4");
    expect(player.getAttribute("poster")).toBe("/p.png");
    expect(player.controls).toBe(true);
    expect(player.getAttribute("preload")).toBe("none");
  });

  it("shows the render on the screen the clip will play on, and says why one jammed", () => {
    const strip = shareStrip(run, { origin });
    const player = strip.root.querySelector("video");
    const screen = player.parentElement;
    const panel = screen.querySelector(".clip-render");
    const bar = panel.querySelector(".clip-render-bar");
    const say = () => panel.querySelector(".clip-render-say").textContent;
    const step = () => panel.querySelector(".clip-render-step").textContent;

    // Queued: the screen is already there, so the clip does not appear out of
    // nowhere a quarter of an hour later.
    strip.setClip({ state: "queued", ahead: 2 });
    expect(screen.hidden).toBe(false);
    expect(player.hidden).toBe(true);
    expect(panel.hidden).toBe(false);
    expect(say()).toBe("2 clips ahead");
    expect(bar.classList.contains("clip-render-bar-unknown")).toBe(true);

    strip.setClip({ state: "queued", ahead: 0 });
    expect(say()).toBe("Next on the recorder");
    strip.setClip({ state: "queued", ahead: null });
    expect(say()).toBe("Waiting for the recorder");

    // A stage with no frame count of its own still moves: an indeterminate bar
    // beats a determinate one stuck at nothing for two minutes.
    strip.setClip({ state: "rendering", stage: "soundtrack", done: 0, total: 0 });
    expect(say()).toBe("Mixing the soundtrack");
    expect(bar.classList.contains("clip-render-bar-unknown")).toBe(true);

    strip.setClip({ state: "rendering", stage: "frames", done: 310, total: 880 });
    expect(say()).toBe("Photographing the arena");
    expect(step()).toBe("310 / 880 frames");
    expect(bar.firstElementChild.style.width).toBe("35.2%");
    expect(bar.getAttribute("aria-valuenow")).toBe("35");
    expect(bar.classList.contains("clip-render-bar-unknown")).toBe(false);

    strip.setClip({ state: "failed", reason: "TimeoutError: timed out in 60.0s" });
    expect(screen.hidden).toBe(false);
    expect(panel.hidden).toBe(false);
    expect(say()).toBe("The tape jammed");
    expect(step()).toBe("TimeoutError: timed out in 60.0s");
    expect(bar.hidden).toBe(true);

    strip.setClip({
      state: "ready",
      poster: "/p.png",
      layouts: { landscape: { url: "/l.mp4" }, vertical: { url: "/v.mp4" } },
    });
    expect(player.hidden).toBe(false);
    expect(panel.hidden).toBe(true);
  });
});

describe("clipStatus", () => {
  it("reads a state as a line, a detail and a fraction", () => {
    expect(clipStatus({ state: "queued", ahead: 1 })).toEqual({
      say: "1 clip ahead", step: "", fraction: null,
    });
    expect(clipStatus({ state: "rendering", stage: "opening", done: 0, total: 0 }).say)
      .toBe("Opening the stage");
    // A stage this build has never heard of is still progress, not a blank.
    expect(clipStatus({ state: "rendering", stage: "mystery", done: 1, total: 4 })).toEqual({
      say: "Rendering", step: "1 / 4 frames", fraction: 0.25,
    });
    expect(clipStatus({ state: "failed" }).step).toBe("no reason recorded");
  });
});

describe("wireShare", () => {
  it("on a laptop, Instagram copies the post and takes the vertical clip", async () => {
    const strip = shareStrip(run, { origin });
    strip.setClip({ state: "ready", layouts: { landscape: { url: "/l.mp4" }, vertical: { url: "/v.mp4" } } });
    const copied = [];
    const opened = [];
    wireShare(strip, run, {
      origin, handheld: false, share: undefined,
      clipboard: { writeText: async (text) => copied.push(text) }, open: (url) => opened.push(url),
    });
    strip.root.querySelector('[data-upload="instagram"]').click();
    await new Promise((r) => setTimeout(r, 0));
    expect(copied[0]).toBe(postText(run, { origin, network: "instagram" }));
    expect(opened).toEqual(["/v.mp4?download=1"]);
    expect(strip.said.textContent).toMatch(/^Text copied\. Use the clip download/);
  });

  it("copies the run's own address, which is a page the server renders", async () => {
    const strip = shareStrip(run, { origin });
    const copied = [];
    wireShare(strip, run, { origin, clipboard: { writeText: async (t) => copied.push(t) } });
    strip.root.querySelector("[data-copy]").click();
    await new Promise((r) => setTimeout(r, 0));
    expect(copied).toEqual(["https://arena.hf.space/r/01M2X"]);
    expect(strip.said.textContent).toBe("Link copied: https://arena.hf.space/r/01M2X");
  });

  it("hands over the address itself when the clipboard refuses", async () => {
    const strip = shareStrip(run, { origin });
    wireShare(strip, run, {
      origin, clipboard: { writeText: async () => { throw new Error("denied"); } },
    });
    strip.root.querySelector("[data-copy]").click();
    await new Promise((r) => setTimeout(r, 0));
    expect(strip.said.textContent).toBe("Could not copy. The link is https://arena.hf.space/r/01M2X");
  });

  it("on a phone, hands the text to the share sheet", async () => {
    const strip = shareStrip(run, { origin });
    const shared = [];
    wireShare(strip, run, { origin, handheld: true, share: async (data) => shared.push(data) });
    strip.root.querySelector('[data-upload="tiktok"]').click();
    await new Promise((r) => setTimeout(r, 0));
    expect(shared).toEqual([{ text: postText(run, { origin, network: "tiktok" }) }]);
  });
});
