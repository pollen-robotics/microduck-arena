import { describe, expect, it } from "vitest";
import { featuring, flipScore, offBoard, receiptCard, replayLine, runHall, seedText, verdict } from "./run.js";

const STAGE = { title: "MicroDuck Got a Talent", course: "stage", metric: "votes" };
const TUG = { id: "tug-of-war", title: "Tug of War", course: "tug", metric: "mean_ground_cm", bout: { time_limit_s: 45 } };
const tugRun = {
  run_id: "R1", user: "nico", policy_name: "puller", event: TUG, score: 12.34, seeds_finished: 5, seeds_total: 5,
  trace_seed: 3, rank: 2, on_board: true, withdrawn: false, receipts: [{ act: "run", points: 10 }],
  per_seed: [{ seed: 3, status: "won", time_s: 45, score_cm: 10.1 }], cast: [{ policy: "self" }],
};

describe("a receipt", () => {
  it("is a small card, not a sticker to press: the points over what they were for", () => {
    const card = receiptCard({ act: "first_event", points: 100 });
    expect(card.tagName).not.toBe("BUTTON");
    expect(card.classList.contains("receipt")).toBe(true);
    expect(card.classList.contains("sticker")).toBe(false);
    expect(card.querySelector(".receipt-points").textContent).toBe("+100");
    expect(card.querySelector(".mono-label").textContent).toBe("first entry");
  });

  it("wears its act's colour on its edge", () => {
    expect(receiptCard({ act: "podium", points: 250 }).classList.contains("receipt-magenta")).toBe(true);
    expect(receiptCard({ act: "run", points: 10 }).classList.contains("receipt-cyan")).toBe(true);
  });
});

describe("a publication's frame", () => {
  it("puts the stage in the same deck as the challenge page", () => {
    const page = runHall();
    expect(page.querySelector(".run-top > .deck > canvas#stage")).not.toBeNull();
    expect([...page.querySelectorAll(".deck button")].map((b) => b.id)).toEqual(["follow"]);
  });

  it("hangs the challenge page's board sheet under the picture, and no legend", () => {
    const page = runHall();
    expect(page.querySelector(".run-board > .boardsheet > .boardtop")).not.toBeNull();
    expect(page.querySelector(".run-board > .boardsheet > #board")).not.toBeNull();
    expect(page.querySelector(".pegboard")).toBeNull();
    expect(page.querySelector(".key")).toBeNull();
    expect(page.querySelector(".run-top > #facts")).not.toBeNull();
  });
});

describe("a performance's scoreboard", () => {
  it("says its length and that it was performed, or cut short", () => {
    expect(verdict({ event: STAGE, seeds_finished: 1, seeds_total: 1 })).toEqual({ label: "length", stamp: "PERFORMED" });
    expect(verdict({ event: STAGE, seeds_finished: 0, seeds_total: 1 })).toEqual({ label: "length", stamp: "CUT SHORT" });
  });
  it("keeps a race's time and seeds", () => {
    expect(verdict({ event: { course: "lane" }, seeds_finished: 4, seeds_total: 5 })).toEqual({ label: "time", stamp: "FINISHED 4/5" });
  });
  it("replays the whole performance, at no speed and no seed", () => {
    expect(replayLine({ event: STAGE, command_vx: 0, seeds_finished: 1, per_seed: [], trace_seed: 1 })).toBe("replay: the whole performance");
  });
});

describe("a rated tug run's scoreboard", () => {
  it("is rated in centimetres and stamped rated", () => {
    expect(verdict(tugRun)).toEqual({ label: "rating · cm", stamp: "RATED" });
  });
  it("replays the median bout", () => {
    expect(replayLine(tugRun)).toBe("replay: seed 3, the median bout");
  });
});

describe("the number the scoreboard flips", () => {
  const race = { event: { course: "lane", metric: "mean_finish_time" }, score: 12.3456, seeds_finished: 5 };

  it("rolls a rating to the tenth of a centimetre, from zeros of its own shape", () => {
    expect(flipScore(tugRun)).toBe("12.3");
    expect(flipScore(tugRun, { veiled: true })).toBe("00.0");
  });
  it("keeps a race's time to the millisecond, from the same zeros as ever, and a DNF", () => {
    expect(flipScore(race)).toBe("12.346");
    expect(flipScore(race, { veiled: true })).toBe("00.000");
    expect(flipScore({ ...race, seeds_finished: 0 })).toBe("DNF");
  });
});

describe("a seed's line", () => {
  it("says the ground a bout won in centimetres, the entry's side and how it ended", () => {
    expect(seedText({ seed: 3, status: "won", time_s: 45, score_cm: 10.14 })).toBe("+10.1 cm · west · won the pull");
    expect(seedText({ seed: 2, status: "pit_lost", time_s: 4.5, score_cm: -143.42 })).toBe("-143.4 cm · east · dragged in");
    expect(seedText({ seed: 5, status: "fault", time_s: 0.02, score_cm: -200 })).toBe("-200.0 cm · west · faulted");
  });
  it("keeps a race's time, or how it ended", () => {
    expect(seedText({ seed: 1, status: "finish", time_s: 12.3456 })).toBe("12.346s");
    expect(seedText({ seed: 2, status: "fall", time_s: null })).toBe("fall");
  });
});

describe("a troupe's credits", () => {
  const walker = { repo_id: "bob/microduck-walker", filename: "policy.onnx", revision: "a".repeat(40), user: "bob", policy_name: "walker" };
  const roller = { ...walker, repo_id: "carol/microduck-roller", user: "carol", policy_name: "roller" };

  it("features each borrowed policy once, linked to its repo at the commit that performed", () => {
    const credits = featuring([{ policy: "self" }, { policy: walker }, { policy: roller }, { policy: walker }]);
    expect(credits.textContent).toBe("featuring @bob · walker, @carol · roller");
    expect([...credits.querySelectorAll("a")].map((a) => a.href)).toEqual([
      `https://huggingface.co/bob/microduck-walker/tree/${"a".repeat(40)}`,
      `https://huggingface.co/carol/microduck-roller/tree/${"a".repeat(40)}`,
    ]);
  });

  it("credits nobody when every duck is the author's own", () => {
    expect(featuring([{ policy: "self" }, { policy: "self" }])).toBeNull();
  });
});

describe("a run off the board", () => {
  it("names the run a copy races exactly like, and leads to it", () => {
    const sticker = offBoard({ on_board: false, withdrawn: false, copy_of: { user: "rumezhak", run_id: "R0" } });
    expect(sticker.textContent).toBe("copy of @rumezhak");
    expect(sticker.getAttribute("href")).toBe("#/r/R0");
    expect(sticker.classList.contains("sticker")).toBe(true);
  });
  it("says withdrawn, or not on the board, and nothing for a run on it", () => {
    expect(offBoard({ on_board: false, withdrawn: true, copy_of: null }).textContent).toBe("withdrawn");
    expect(offBoard({ on_board: false, withdrawn: false, copy_of: null }).textContent).toBe("not on the board");
    expect(offBoard({ on_board: true, withdrawn: false, copy_of: null })).toBeNull();
  });
});
