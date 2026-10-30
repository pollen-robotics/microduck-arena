import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { roundCard } from "./roundcard.js";

const SPRINT = {
  id: "sprint-2m", title: "2 m Sprint", category: "race", vote: null,
  length_m: 2, slope_deg: 0, rig: "legs", sweep_lo: 0.2, sweep_hi: 1.2, sweep_count: 21,
};
const HILL = { ...SPRINT, id: "hill-climb-1m5", title: "1.5 m Hill Climb", length_m: 1.5, slope_deg: 8 };
const ROLLER = { ...SPRINT, id: "roller-sprint-2m", title: "2 m Roller Sprint", rig: "rollers" };
const HEIST = { ...SPRINT, id: "sock-heist-6m", title: "6 m Sock Heist", length_m: 6 };
const TALENT = { id: "got-a-talent", title: "MicroDuck Got a Talent", category: "showcase", course: "stage",
  rig: "legs", time_limit_s: 20, metric: "votes", vote: { ballot_min: 2 } };
const HELD = [{ user: "cdeplanne", policy_name: "Walk rough", score: 9.456, seeds_finished: 5 }];

const TUG = {
  id: "tug-of-war", title: "Tug of War", category: "versus", course: "tug", metric: "mean_ground_cm", rig: "legs", vote: null,
  ring_m: 3, pit_m: 0.3, bout: { time_limit_s: 45 },
};

const cells = (card) => [...card.querySelectorAll(".round-card__stat")].map((cell) => cell.textContent);

describe("a round card", () => {
  it("is numbered in the programme and named by its link, which leads to the race", () => {
    const card = roundCard(SPRINT, HELD, { number: 1 });
    expect(card.querySelector(".round-card__num").textContent).toBe("#01");
    const link = card.querySelector("a.round-card__link");
    expect(link.getAttribute("href")).toBe("#/e/sprint-2m");
    expect(link.textContent).toBe("2 m Sprint");
  });

  it("says what kind of event it is, and nothing for a kind it does not know", () => {
    expect(roundCard(SPRINT, [], { number: 1 }).querySelector(".round-card__cat").textContent).toBe("race");
    expect(roundCard(TALENT, [], { number: 2 }).querySelector(".round-card__cat").textContent).toBe("showcase");
    // One malformed manifest must not take the wall down, nor borrow a word.
    const odd = roundCard({ ...SPRINT, category: "parade" }, [], { number: 1 });
    expect(odd.querySelector(".round-card__cat")).toBeNull();
    expect(odd.querySelector(".round-card__num")).not.toBeNull();
  });

  it("shows the event's own illustration", () => {
    expect(roundCard(HILL, [], { number: 4 }).querySelector(".round-card__art img").getAttribute("src"))
      .toBe("/cards/hill-climb-1m5.webp");
  });

  it("states the course in three cells", () => {
    expect(cells(roundCard(SPRINT, [], { number: 1 }))).toEqual(["2 m", "Flat", "Legs"]);
    expect(cells(roundCard(HILL, [], { number: 4 }))).toEqual(["1.5 m", "8°", "Legs"]);
    expect(cells(roundCard(ROLLER, [], { number: 3 }))).toEqual(["2 m", "Flat", "Rollers"]);
  });

  it("shows who holds it and in what time", () => {
    const line = roundCard(SPRINT, HELD, { number: 1 }).querySelector(".round-card__score");
    expect(line.textContent).toBe("9.456s@cdeplanne");
  });

  it("invites an entry when nobody has finished", () => {
    expect(roundCard(SPRINT, [], { number: 1 }).querySelector(".round-card__score").textContent).toBe("be the first");
    const dnf = [{ user: "a", policy_name: "p", score: 50, seeds_finished: 0 }];
    expect(roundCard(SPRINT, dnf, { number: 1 }).querySelector(".round-card__score").textContent).toBe("no finisher yet");
  });

  it("wears its own accent and button word", () => {
    const card = roundCard(ROLLER, [], { number: 3 });
    expect(card.style.getPropertyValue("--c")).toBe("var(--orange)");
    expect(card.querySelector(".round-card__cta").textContent).toBe("Let's roll!");
    // The button is the card's own on a timed event: the link's cover takes the click.
    expect(card.querySelector("span.round-card__cta")).not.toBeNull();
  });

  it("names the heist in a word that holds one line, and its button sneaks in", () => {
    const card = roundCard(HEIST, [], { number: 6 });
    expect(card.querySelector(".round-card__title").textContent).toBe("Sock Heist");
    expect(card.querySelector(".round-card__cta").textContent).toBe("Sneak in!");
    expect(card.style.getPropertyValue("--c")).toBe("var(--magenta)");
    expect(cells(card)).toEqual(["6 m", "Flat", "Legs"]);
    expect(card.querySelector(".round-card__art img").getAttribute("src")).toBe("/cards/sock-heist-6m.webp");
  });

  it("still deals an event it has no look for, in paper with a plain button", () => {
    const card = roundCard({ ...SPRINT, id: "new-round" }, [], { number: 5 });
    expect(card.style.getPropertyValue("--c")).toBe("var(--paper)");
    expect(card.querySelector(".round-card__cta").textContent).toBe("Go!");
  });
});

describe("a voted round's card", () => {
  it("goes by its short name", () => {
    expect(roundCard(TALENT, [], { number: 2 }).querySelector(".round-card__title").textContent).toBe("Got a Talent");
  });

  it("leads to the event, and its button into the booth", () => {
    const card = roundCard(TALENT, [], { number: 2 });
    expect(card.querySelector("a.round-card__link").getAttribute("href")).toBe("#/e/got-a-talent");
    const vote = card.querySelector("a.round-card__cta");
    expect(vote.getAttribute("href")).toBe("#/v/got-a-talent");
    expect(vote.textContent).toBe("Vote");
  });

  it("counts the week's votes in one cell, and who is rated best", () => {
    const card = roundCard(TALENT, [
      { user: "cdeplanne", votes: 43, rate: 0.41, seeds_finished: 1 },
      { user: "ann", votes: 1180, rate: 0.33, seeds_finished: 1 },
    ], { number: 2 });
    expect(cells(card)).toEqual(["Votes1.2K"]);
    expect(card.querySelector(".round-card__score").textContent).toBe("rated 41%@cdeplanne");
  });

  it("says so when nothing has been voted for yet", () => {
    const card = roundCard(TALENT, [{ user: "cdeplanne", votes: 0, rate: 0.25, seeds_finished: 1 }], { number: 2 });
    expect(card.querySelector(".round-card__score").textContent).toBe("no votes yet@cdeplanne");
  });
});

describe("the workshop's card", () => {
  it("leads elsewhere, with its own button word, no leader line and its own corner", () => {
    const corner = document.createElement("span");
    corner.className = "mine";
    const card = roundCard(TALENT, null, { number: 2, href: "#/c/got-a-talent", cta: "Train", corner });
    expect(card.querySelector("a.round-card__link").getAttribute("href")).toBe("#/c/got-a-talent");
    expect(card.querySelector(".round-card__score")).toBeNull();
    // Training is not voting: the button is the card's, not the booth's.
    expect(card.querySelector("a.round-card__cta")).toBeNull();
    expect(card.querySelector(".round-card__cta").textContent).toBe("Train");
    // Nothing to count without the week's rows.
    expect(card.querySelector(".round-card__stats")).toBeNull();
    expect(card.querySelector(".mine")).not.toBeNull();
  });

  it("keeps a race's course cells", () => {
    expect(cells(roundCard(SPRINT, null, { number: 1, cta: "Train" }))).toEqual(["2 m", "Flat", "Legs"]);
  });
});

describe("the card's sheet", () => {
  const css = readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), "../public/cards.css"),
    "utf8",
  ).replace(/\/\*[\s\S]*?\*\//g, "");
  const guard = /@media \(prefers-reduced-motion: no-preference\) \{\n[\s\S]*?\n\}/g;

  it("tilts, shines and moves only where motion is wanted", () => {
    const unguarded = css.replace(guard, "");
    expect(unguarded, "the tilt escapes the media query").not.toMatch(/rotateX|rotateY/);
    expect(unguarded, "a transition escapes the media query").not.toMatch(/transition\s*:/);
    expect(unguarded, "the sheen is drawn where motion was refused").not.toMatch(/color-dodge/);
    expect([...css.matchAll(guard)].join("\n")).toMatch(/rotateX\(var\(--rx\)\) rotateY\(var\(--ry\)\)/);
  });

  it("lets the link's cover reach the card's own edge", () => {
    // A positioned frame would stop the cover at the frame, and the card's
    // paper rim would take clicks that lead nowhere.
    const frame = css.match(/\.round-card__frame \{([^}]*)\}/);
    expect(frame[1]).not.toMatch(/position\s*:/);
    expect(css).toMatch(/\.round-card__link::after \{[^}]*position: absolute;[^}]*inset: 0;/);
  });
});

describe("the tug's round card", () => {
  it("is lime, says Pull!, and counts in centimetres", () => {
    const card = roundCard(TUG, [{ user: "nico", score: 12.34, seeds_finished: 5 }], { number: 5 });
    expect(cells(card).slice(0, 3)).toEqual(["0.3 m pit", "45 s bouts", "Legs"]);
    expect(card.querySelector(".round-card__score").textContent).toBe("12.3 cm@nico");
    expect(card.querySelector(".round-card__cat").textContent).toBe("versus");
    expect(card.querySelector(".round-card__cta").textContent).toBe("Pull!");
  });
});
