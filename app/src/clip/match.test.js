import { describe, expect, it } from "vitest";
import { BOUT_HOLD_S, boutAt, matchPlan, matchWords, scoreAt } from "./match.js";
import { actAt } from "./plan.js";

describe("matchPlan", () => {
  const full = { settle: 26, steps: 2250 };
  it("chains three 45 s bouts between the title and the outro, each held 6 s once it ends: a 160 s clip", () => {
    const plan = matchPlan([0, 1, 2].map((k) => ({ k, ...full })));
    expect(plan.frames).toBe(4002);
    expect(plan.seconds).toBeCloseTo(160.08);
    expect(plan.bouts).toEqual([{ k: 0, tape_start_s: 3.52, tape_end_s: 48.52, hold_end_s: 54.52 },
      { k: 1, tape_start_s: 55.04, tape_end_s: 100.04, hold_end_s: 106.04 },
      { k: 2, tape_start_s: 106.56, tape_end_s: 151.56, hold_end_s: 157.56 }]);
  });
  it("makes the longest match, five full bouts, 263 s long", () => {
    expect(matchPlan([0, 1, 2, 3, 4].map((k) => ({ k, ...full }))).seconds).toBeCloseTo(263.12);
  });
  // Tape frames 75-77, held to 227; then 228-231, held to 381; the outro from 382.
  const small = () => matchPlan([{ k: 0, settle: 2, steps: 4 }, { k: 1, settle: 2, steps: 6 }]);
  it("finds the bout and its step for every frame, a bout's last step held until the next bout or the outro", () => {
    const plan = small();
    expect(BOUT_HOLD_S).toBe(6);
    expect([0, 76, 78, 227, 228, 231, 381, plan.frames - 1].map((i) => boutAt(plan, i))).toEqual([
      { bout: 0, step: 0 }, { bout: 0, step: 2 }, { bout: 0, step: 5 }, { bout: 0, step: 5 }, { bout: 1, step: 0 },
      { bout: 1, step: 6 }, { bout: 1, step: 7 }, { bout: 1, step: 7 }]);
    expect([381, 382].map((i) => actAt(plan, i))).toEqual(["tape", "outro"]);
    expect(plan.frames).toBe(382 + 63);
  });
  it("counts a bout on the bug as soon as its tape ends, so its result shows through the hold", () => {
    const plan = small(), match = { bouts: [{ winner: "a" }, { winner: "b" }] };
    expect([77, 78, 227, 231, 232, plan.frames - 1].map((i) => scoreAt(plan, match, i))).toEqual(
      [[0, 0], [1, 0], [1, 0], [1, 0], [1, 1], [1, 1]]);
  });
  it("says who meets whom, the players on the tape, and who won over its player's handle", () => {
    const match = { cup: 3, round: "final", group: null, title: "Final · Tank (@ana) vs Lean (@bo)",
      event: { title: "Tug of War" }, a: { name: "Tank", policy_name: "Tank", user: "ana" },
      b: { name: "Lean", policy_name: "Lean", user: "bo" }, winner: "a", wins: [2, 1] };
    expect(matchWords(match)).toEqual({ title: "Tug of War · Cup #3", line: "Final · Tank (@ana) vs Lean (@bo)",
      players: "Final · @ana vs @bo", outro: "Tank wins 2–1", by: "@ana" });
  });
  it("says a tie went to the rating, not a score nobody won by", () => {
    const match = { cup: 3, round: "group", group: "A", title: "Group A · Tank (@ana) vs Lean (@bo)",
      event: { title: "Tug of War" }, a: { name: "Tank", policy_name: "Tank", user: "ana" },
      b: { name: "Lean", policy_name: "Lean", user: "bo" }, winner: "b", wins: [1, 1], decided_by: "rating" };
    expect(matchWords(match)).toMatchObject({ players: "Group A · @ana vs @bo", outro: "Lean wins on rating", by: "@bo" });
  });
  it("stamps a winner whose name carries its handle, as two ducks of one name do, with the handle once", () => {
    const match = { cup: 3, round: "semi-final", group: null, title: "Semi-final · v11 (@ana) vs v11 (@bo)",
      event: { title: "Tug of War" }, a: { name: "v11 (@ana)", policy_name: "v11", user: "ana" },
      b: { name: "v11 (@bo)", policy_name: "v11", user: "bo" }, winner: "b", wins: [0, 2] };
    expect(matchWords(match)).toMatchObject({ players: "Semi-final · @ana vs @bo", outro: "v11 wins 2–0", by: "@bo" });
  });
});
