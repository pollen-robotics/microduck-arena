import { describe, expect, it } from "vitest";
import { SCREEN_PX, screenLayout } from "./screen.js";

// Views in the shape of the desk segment's `screen` (arena/commentary/cup.py
// screen_view), which names a group's rows by handle and bills every other duck
// "<policy> (@<user>)": short names stand in for the ducks that fit.
const [WIDTH, HEIGHT] = SCREEN_PX;
const TITLE = "Tug of War · Cup #1";
const row = (name, won, played) => ({ name, won, played });
const open = (count) => Array.from({ length: count }, () => ({ a: null, b: null, winner: null, next: false }));
const group = (name, names, won = [0, 0, 0], played = [0, 0, 0]) => ({
  name,
  rows: names.map((duck, i) => row(duck, won[i], played[i])),
});

// Four groups of three, round 2 about to start in Group C.
const GROUPS = {
  title: TITLE,
  stage: "Groups · round 2 of 3",
  groups: [
    group("A", ["puller 1", "puller 9", "puller 5"], [2, 0, 0], [2, 1, 1]),
    group("B", ["puller 4", "puller 8", "puller 11"], [1, 1, 0], [1, 2, 1]),
    group("C", ["puller 3", "puller 0", "puller 2"], [1, 0, 0], [1, 0, 1]),
    group("D", ["puller 6", "puller 7", "puller 10"], [1, 0, 0], [1, 1, 0]),
  ],
  knockout: [
    { round: "quarter-final", matches: open(4) },
    { round: "semi-final", matches: open(2) },
    { round: "final", matches: open(1) },
  ],
  next: { a: "puller 0", b: "puller 2", group: "C", round: "group" },
  champion: null,
};

// Eight groups of three before the first match.
const EIGHT = {
  title: TITLE,
  stage: "Groups · round 1 of 3",
  groups: [..."ABCDEFGH"].map((name, g) => group(name, [0, 8, 16].map((k) => `puller ${g + k}`))),
  knockout: [
    { round: "round of 16", matches: open(8) },
    { round: "quarter-final", matches: open(4) },
    { round: "semi-final", matches: open(2) },
    { round: "final", matches: open(1) },
  ],
  next: { a: "puller 0", b: "puller 8", group: "A", round: "group" },
  champion: null,
};

// Six ducks: the first semi-final aired, the second next, the final unknown.
const BRACKET = {
  title: TITLE,
  stage: "Semi-final",
  groups: [
    group("A", ["puller 0", "puller 2", "puller 4"], [2, 1, 0], [2, 2, 2]),
    group("B", ["puller 1", "puller 3", "puller 5"], [2, 1, 0], [2, 2, 2]),
  ],
  knockout: [
    {
      round: "semi-final",
      matches: [
        { a: "puller 0", b: "puller 3", winner: "a", next: false },
        { a: "puller 1", b: "puller 2", winner: null, next: true },
      ],
    },
    { round: "final", matches: open(1) },
  ],
  next: { a: "puller 1", b: "puller 2", group: null, round: "semi-final" },
  champion: null,
};

const CHAMPION = {
  ...BRACKET,
  stage: "Champion",
  knockout: [
    {
      round: "semi-final",
      matches: [
        { a: "puller 0", b: "puller 3", winner: "a", next: false },
        { a: "puller 1", b: "puller 2", winner: "a", next: false },
      ],
    },
    { round: "final", matches: [{ a: "puller 0", b: "puller 1", winner: "a", next: false }] },
  ],
  next: null,
  champion: "puller 0",
};

const texts = (ops) => ops.filter((op) => op.kind === "text");
const words = (ops) => texts(ops).map((op) => op.text);
const said = (ops, text) => texts(ops).find((op) => op.text === text);
const framed = (ops) => ops.filter((op) => op.kind === "rect" && op.stroke === "yellow");
const holds = (rect, op) => rect.x <= op.x && op.x <= rect.x + rect.w && rect.y <= op.y && op.y <= rect.y + rect.h;
// The layout's own estimate of a text's width: it measures no text.
const right = (op) => op.x + 0.55 * op.size * op.text.length;

describe("screenLayout", () => {
  it("lays the groups with their tables and picks out the next match's group", () => {
    const ops = screenLayout(GROUPS, WIDTH, HEIGHT);
    expect(ops[0]).toEqual({ kind: "rect", x: 0, y: 0, w: WIDTH, h: HEIGHT, paint: "deep-ink" });
    expect(said(ops, "TUG OF WAR · CUP #1 · GROUPS · ROUND 2 OF 3")).toMatchObject({
      x: 40, y: 64, size: 40, paint: "yellow", weight: 700,
    });
    for (const name of "ABCD") expect(said(ops, `GROUP ${name}`)).toMatchObject({ size: 28, paint: "paper", weight: 700 });
    const groupA = GROUPS.groups[0].rows.map((r) => r.name);
    expect(words(ops).filter((text) => groupA.includes(text))).toEqual(groupA);
    expect(said(ops, "NEXT  puller 0 vs puller 2")).toMatchObject({ y: HEIGHT - 36, size: 32, paint: "yellow" });
    expect(framed(ops)).toHaveLength(1);
    const [frame] = framed(ops);
    const groupC = said(ops, "GROUP C");
    expect(frame.x <= groupC.x && groupC.x <= frame.x + frame.w).toBe(true);
  });

  it("puts eight groups on two rows", () => {
    const ops = screenLayout(EIGHT, WIDTH, HEIGHT);
    expect(said(ops, "GROUP E").y).toBeGreaterThan(said(ops, "GROUP A").y);
    expect(said(ops, "GROUP E").x).toBe(said(ops, "GROUP A").x);
  });

  it("lays the bracket once the knockout has begun", () => {
    const ops = screenLayout(BRACKET, WIDTH, HEIGHT);
    expect(words(ops)).toContain("TUG OF WAR · CUP #1 · SEMI-FINAL");
    expect(words(ops)).toEqual(expect.arrayContaining(["SEMI-FINAL", "FINAL", "?"]));
    expect(words(ops)).not.toContain("GROUP A");
    expect(said(ops, "puller 0").weight).toBe(700);
    expect(said(ops, "puller 3").weight).toBe(400);
    expect(framed(ops)).toHaveLength(1);
    expect(holds(framed(ops)[0], said(ops, "puller 1"))).toBe(true);
    expect(holds(framed(ops)[0], said(ops, "puller 0"))).toBe(false);
  });

  it("names the champion and picks nothing out at the end", () => {
    const ops = screenLayout(CHAMPION, WIDTH, HEIGHT);
    expect(said(ops, "CHAMPION  puller 0")).toMatchObject({ y: HEIGHT - 36, size: 32, paint: "yellow" });
    expect(framed(ops)).toEqual([]);
  });

  it("keeps every text on the screen", () => {
    for (const view of [GROUPS, EIGHT, BRACKET, CHAMPION]) {
      for (const op of texts(screenLayout(view, WIDTH, HEIGHT))) {
        expect(op.x).toBeGreaterThanOrEqual(0);
        expect(op.x).toBeLessThan(WIDTH);
        expect(op.y).toBeGreaterThan(0);
        expect(op.y).toBeLessThan(HEIGHT);
      }
    }
    const long = "a policy name that runs on (@and-on-and)";
    expect(long).toHaveLength(40);

    const groups = structuredClone(GROUPS);
    groups.groups[0].rows[0].name = long;
    const ops = screenLayout(groups, WIDTH, HEIGHT);
    const name = texts(ops).find((op) => op.text.includes("@and-on-and"));
    const won = texts(ops).find((op) => op.y === name.y && op.align === "right");
    expect(right(name)).toBeLessThanOrEqual(won.x - 0.55 * won.size * won.text.length);

    const bracket = structuredClone(BRACKET);
    bracket.knockout[1].matches[0].a = long;
    const lines = screenLayout(bracket, WIDTH, HEIGHT);
    const side = texts(lines).find((op) => op.text.includes("@and-on-and"));
    const panel = lines.find((op) => op.kind === "rect" && op.paint === "ink" && holds(op, side));
    expect(right(side)).toBeLessThanOrEqual(panel.x + panel.w);
  });

  it("cuts the next match's names only when its line has no room for both", () => {
    const long = "a policy name that runs on (@and-on-and)";
    const footer = (a, b) => texts(screenLayout({ ...GROUPS, next: { ...GROUPS.next, a, b } }, WIDTH, HEIGHT)).at(-1);
    expect(footer("puller 0", long).text).toBe(`NEXT  puller 0 vs ${long}`);
    const both = footer(long, "another policy that runs on (@and-on-on)");
    expect(both.text).toBe("NEXT  a policy name… (@and-on-and) vs another policy… (@and-on-on)");
    expect(right(both)).toBeLessThanOrEqual(WIDTH - 40);
  });

  it("cuts a billed duck in its policy's name, its player's handle kept whole, or to its handle alone", () => {
    const cell = (name) => {
      const groups = structuredClone(GROUPS);
      groups.groups[0].rows[0].name = name;
      const all = words(screenLayout(groups, WIDTH, HEIGHT));
      return all[all.indexOf("WON") + 1]; // Group A's first row
    };
    expect(cell("a policy name (@ab)")).toBe("a policy… (@ab)");
    expect(cell("a policy name that runs on (@and-on-and)")).toBe("@and-on-and");
    expect(cell("tug (@a-handle-that-runs-on-and-on)")).toBe("@a-handle-that…");
    expect(cell("a policy name that runs on and on")).toBe("a policy name…");
    const bracket = structuredClone(BRACKET);
    bracket.knockout[1].matches[0].a = "a policy name that runs on (@and-on-and)";
    expect(words(screenLayout(bracket, WIDTH, HEIGHT))).toContain("a policy name that runs… (@and-on-and)");
  });
});
