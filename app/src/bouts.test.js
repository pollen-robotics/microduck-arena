import { describe, expect, it } from "vitest";
import { boutLane, matchLiveries, winLine } from "./bouts.js";

describe("boutLane", () => {
  it("puts each side on its end of the rope, west first, under its on-air name", () => {
    const match = { a: { livery: "blue", name: "Tank" }, b: { livery: "purple", name: "Lean" },
      bouts: [{ a_side: "west" }, { a_side: "east" }] };
    expect(boutLane(match, 1, ["tw", "te"], ["sw", "se"], { trace: "st", settle: "ss" })).toEqual({ tug: "bout", ducks: [
      { trace: "tw", settle: "sw", livery: "purple", name: "Lean" },
      { trace: "te", settle: "se", livery: "blue", name: "Tank" }], string: { trace: "st", settle: "ss" } });
  });
  it("dresses b in another livery when both entrants wear the same, as the reference duck is", () => {
    expect(matchLiveries({ livery: "blue" }, { livery: "purple" })).toEqual(["blue", "purple"]);
    expect(matchLiveries({ livery: "classic" }, { livery: "classic" })).toEqual(["classic", "charcoal"]);
    expect(matchLiveries({ livery: "charcoal" }, { livery: "charcoal" })).toEqual(["charcoal", "classic"]);
    const twins = { a: { livery: "blue", name: "Tank" }, b: { livery: "blue", name: "Lean" }, bouts: [{ a_side: "east" }] };
    expect(boutLane(twins, 0, ["tw", "te"], ["sw", "se"], { trace: "st", settle: "ss" }).ducks.map((duck) => duck.livery)).toEqual(["classic", "blue"]);
  });
});

describe("winLine", () => {
  it("names the winner by its on-air name or the name given, and by rating when the bouts tied", () => {
    const match = { a: { name: "Tank" }, b: { name: "Lean" }, winner: "b", decided_by: "bouts" };
    expect(winLine(match)).toBe("Lean wins");
    expect(winLine({ ...match, decided_by: "rating" })).toBe("Lean wins on rating");
    expect(winLine({ ...match, decided_by: "rating" }, "Lean policy")).toBe("Lean policy wins on rating");
  });
});
