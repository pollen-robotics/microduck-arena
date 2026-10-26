import { describe, expect, it } from "vitest";
import { LANE_CSS } from "../course.js";
import { flipTo, footballHall, strip } from "./hall.js";
import { keeperColour, playLine } from "./plays.js";

// A match as arena/football_watch.py football_summary answers it: two seeds,
// each from both ends, the policies swapping ends from one play to the next.
const play = (fields) => ({ events: [], kickoff: [], settle_frames: 51, frames: 1001, ...fields });
const summary = {
  id: "football",
  title: "Football",
  rig: "legs",
  names: ["alpha", "beta"],
  ctrl_dt: 0.02,
  time_limit_s: 20,
  pitch: { length_m: 2.2, width_m: 1.5, corner_m: 0.25, board_height_m: 0.2, board_thickness_m: 0.05, boards: [], nets: [] },
  goal: { width_m: 0.6, height_m: 0.3, depth_m: 0.2 },
  ball: { radius_m: 0.035 },
  keeper: { diameter_m: 0.16, height_m: 0.26, x_m: 1.08, rail_m: 0.14 },
  start_x_m: 0.45,
  fall_hold_s: 0.3,
  goals: [1, 1],
  plays: [
    play({ seed: 1, on_end: ["alpha", "beta"], scorer: 0, end: "goal", time_s: 8.42 }),
    play({ seed: 1, on_end: ["beta", "alpha"], scorer: null, end: "whistle", time_s: 20 }),
    play({ seed: 2, on_end: ["alpha", "beta"], scorer: 1, end: "fault", time_s: 0.02 }),
    play({ seed: 2, on_end: ["beta", "alpha"], scorer: null, end: "void", time_s: 3.2 }),
  ],
};

// jsdom serialises a colour as rgb(); compare through an element given the hex.
function sameColour(property, actual, hex) {
  const probe = document.createElement("span");
  probe.style[property] = hex;
  expect(actual).toBe(probe.style[property]);
}

describe("strip: the mark over the page", () => {
  it("reads MICRODUCK FOOTBALL, and links nowhere", () => {
    const header = strip();
    expect(header.classList.contains("signage")).toBe(true);
    expect(header.querySelector(".wordmark").textContent).toBe("MicroduckFootball");
    expect(header.querySelector("a")).toBeNull();
  });
});

describe("footballHall: the page's frame", () => {
  it("names the match over the stage, with its pitch, goals and whistle", () => {
    const { hall } = footballHall(summary);
    expect([...hall.classList]).toEqual(["hall", "football"]);
    expect(hall.querySelector(".raceeyebrow").textContent).toBe("Football");
    expect(hall.querySelector(".racetitle").textContent).toBe("Football");
    const facts = hall.querySelector(".facts").textContent;
    expect(facts).toContain("2.2 × 1.5 m, goals 60 cm wide");
    expect(facts).toContain("20 s");
    expect(facts).toContain("4, every seed from both ends");
  });

  it("keeps the goals per policy, in its letter and colour, from nil", () => {
    const { hall, parts } = footballHall(summary);
    expect(hall.querySelector(".football-score").getAttribute("aria-label")).toBe("Goals");
    const rows = [...hall.querySelectorAll(".football-score__row")];
    expect(rows).toHaveLength(2);
    rows.forEach((row, policy) => {
      const chip = row.querySelector(".football-swatch");
      expect(chip.textContent).toBe(["A", "B"][policy]);
      sameColour("background", chip.style.background, LANE_CSS[policy]);
      expect(row.querySelector(".football-who__name").textContent).toBe(summary.names[policy]);
      expect(row.querySelector(".flip")).toBe(parts.tiles[policy]);
      expect(parts.tiles[policy].textContent).toBe("0");
    });
  });

  it("lists every play as a button, with its ends and what came of it", () => {
    const { hall, parts } = footballHall(summary);
    expect(parts.plays).toHaveLength(summary.plays.length);
    parts.plays.forEach((button, k) => {
      expect(button.dataset.play).toBe(String(k));
      expect(button.type).toBe("button");
      expect(button.querySelector(".football-play__seed").textContent).toBe(`Play ${k + 1} · seed ${summary.plays[k].seed}`);
      expect(button.querySelector(".football-play__how").textContent).toBe(playLine(summary, summary.plays[k]));
    });
    const letters = (k) => [...parts.plays[k].querySelectorAll(".football-swatch")].map((chip) => chip.textContent);
    expect(letters(0)).toEqual(["A", "B"]);
    expect(letters(1)).toEqual(["B", "A"]);
    expect(parts.plays[1].querySelector(".football-play__ends").title)
      .toBe("beta kicks off from the left, alpha from the right");
    expect(hall.querySelector(".football-plays").tagName).toBe("OL");
  });

  it("puts the clock, the caption, the stamp and the verdict on the stage, all but the clock hidden till wanted", () => {
    const { parts } = footballHall(summary);
    const { stage } = parts;
    expect(stage.classList.contains("stage")).toBe(true);
    for (const part of [parts.clock, parts.clockLabel, parts.clockTime, parts.caption, parts.call, parts.stamp, parts.line]) {
      expect(stage.contains(part)).toBe(true);
    }
    expect(parts.clockTime.textContent).toBe("0.00 s");
    expect([parts.caption.hidden, parts.call.hidden, parts.line.hidden]).toEqual([true, true, true]);
    expect(parts.line.getAttribute("role")).toBe("status");
    expect(parts.stamp.classList.contains("stamp")).toBe(true);
  });

  it("keeps the deck's follow key, as a way back to the touchline", () => {
    const { hall } = footballHall(summary);
    expect(hall.querySelector("#stage").tagName).toBe("CANVAS");
    expect(hall.querySelector("#follow").textContent).toBe("Back to the touchline");
    expect(hall.querySelector(".orbit-hint")).not.toBeNull();
  });

  it("offers a pause and a replay, and states the rules with the match's hold and whistle", () => {
    const { hall, parts } = footballHall(summary);
    expect(parts.pause.textContent).toBe("Pause");
    expect(parts.replay.textContent).toBe("Replay play");
    expect([parts.pause.type, parts.replay.type]).toEqual(["button", "button"]);
    const note = hall.querySelector(".football-note").textContent;
    expect(note).toContain("A duck down 0.3 s is out of the play");
    expect(note).toContain("or the whistle at 20 s, and nobody scores");
    expect(note).toContain("A duck whose action is not a number gives the other the goal");
  });

  it("names each keeper in its shell's colour, lime on the left and magenta on the right", () => {
    const keepers = [...footballHall(summary).hall.querySelectorAll(".football-note .football-keeper")];
    expect(keepers.map((name) => name.textContent)).toEqual(["lime", "magenta"]);
    keepers.forEach((name, k) => sameColour("color", name.style.color, keeperColour(k)));
  });
});

describe("flipTo: the scoreboard's flip tiles", () => {
  it("shows a tile a digit, and anything else as it is", () => {
    const row = document.createElement("div");
    flipTo(row, "10");
    expect([...row.querySelectorAll(".flip-digit")].map((tile) => tile.textContent)).toEqual(["1", "0"]);
    flipTo(row, "–");
    expect(row.textContent).toBe("–");
    expect(row.querySelectorAll(".flip-digit")).toHaveLength(0);
  });

  it("leaves the tiles be when they show the text already, so nothing flips for nothing", () => {
    const row = document.createElement("div");
    flipTo(row, "3");
    const tile = row.firstChild;
    flipTo(row, "3");
    expect(row.firstChild).toBe(tile);
    flipTo(row, "4");
    expect(row.firstChild).not.toBe(tile);
    expect(row.textContent).toBe("4");
  });
});
