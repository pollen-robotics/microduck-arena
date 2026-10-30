import { afterEach, describe, expect, it } from "vitest";
import { renderGuides } from "./guides.js";
import { raceHall } from "./race.js";

afterEach(() => document.body.replaceChildren());

function show(guideId = "index", section = null, event = null) {
  const root = document.createElement("div");
  document.body.replaceChildren(root);
  renderGuides(root, event ? { eventId: event.id, event, section } : { guideId, section });
  return root;
}

describe("public guides", () => {
  it("opens a readable guide and focuses its heading without fetching an identity", () => {
    const root = show("train-a-policy");
    expect(document.activeElement).toBe(root.querySelector("article h1"));
    expect(document.title).toBe("Train your first policy · Microduck Arena");
    expect([...root.querySelectorAll("pre code")].map(node => node.textContent).join("\n")).toContain("uv run train");
    expect(root.querySelector('a[href*="roller-sprint"]')).toBeNull();
  });

  it("tells someone who already has an .onnx how to race it here and how to enter it", () => {
    const root = show("train-a-policy");
    const commands = [...root.querySelectorAll("pre code")].map(node => node.textContent).join("\n");
    expect(commands).toContain("uv run --group workshop arena score policy.onnx --event sprint-2m");
    expect(commands).toContain(
      "uv run publish --onnx policy.onnx --repo <you>/microduck-<name> --kind perpetual --no-private --enter --event sprint-2m");
    expect(root.textContent).not.toMatch(/on a challenge's page/);
  });

  it("enters from the shell with publish --enter", () => {
    const commands = [...show("train-a-policy").querySelectorAll("pre code")].map(node => node.textContent).join("\n");
    expect(commands).toContain("uv run publish --run logs/rsl_rl/sprint_2m/<the run> --repo <you>/microduck-first --no-private --enter");
  });

  it("gives general help no navigation of its own: the strip's mark is the way back", () => {
    for (const id of ["index", "train-a-policy", "points"]) {
      const root = show(id);
      expect(root.querySelector(".guide-breadcrumbs")).toBeNull();
      expect(root.querySelector('header.signage .wordmark a[href="#/"]')).not.toBeNull();
    }
  });

  it("keeps challenge guidance out of general help and points", () => {
    for (const id of ["index", "train-a-policy", "points"]) {
      const root = show(id);
      expect(root.querySelector('a[href^="#/e/"]')).toBeNull();
      expect(root.querySelector('a[href="#/guides/sprint-2m"]')).toBeNull();
      if (id !== "points") expect(root.querySelector('a[href="#/guides/points"]')).toBeNull();
    }
  });

  it("keeps each challenge's help within its own context", () => {
    const ids = ["sprint-2m", "roller-sprint-2m", "hill-climb-1m5", "got-a-talent", "tug-of-war", "sock-heist-6m"];
    for (const id of ids) {
      const root = show(null, null, { id });
      expect(root.querySelector("article h1").textContent).not.toBe("Guide not found");
      expect(root.querySelector(`a[href="#/e/${id}"]`)).not.toBeNull();
      const links = [...root.querySelectorAll("article a")].map(a => a.getAttribute("href"));
      expect(links.filter(href => href.startsWith("#/"))).toEqual(["#/guides/train-a-policy"]);
    }
  });

  it("recovers from an unknown guide or stale section with a usable heading and navigation", () => {
    for (const id of ["missing", "constructor", "__proto__"]) {
      const unknown = show(id);
      expect(unknown.querySelector('a[href="#/guides"]')).not.toBeNull();
      expect(document.activeElement).toBe(unknown.querySelector("article h1"));
    }
    const stale = show("points", "missing-section");
    expect(document.activeElement).toBe(stale.querySelector("article h1"));
  });

  it("makes wide tables and commands keyboard-scrollable", () => {
    const training = show("train-a-policy");
    expect(training.querySelector("pre").tabIndex).toBe(0);
    const root = show("points");
    expect(root.querySelector("table").parentElement.tabIndex).toBe(0);
    expect(root.querySelector("table").parentElement.getAttribute("role")).toBe("region");
  });

  it("lets anyone learn the rules from the race page, signed in or not", () => {
    const hall = raceHall({ id: "sprint-2m", title: "2 m Sprint" });
    expect(hall.querySelector('.entry-col a.help-link[href="#/e/sprint-2m/guide"]')).not.toBeNull();
    expect(hall.querySelector("#publish, #try, #dropzone")).toBeNull();
  });

  it("sends a stale link to a removed challenge's guide back to the rounds", () => {
    const root = document.createElement("div");
    renderGuides(root, { eventId: "highest-jump", event: undefined });
    expect(root.querySelector("article h1").textContent).toBe("Guide not found");
    expect(root.querySelector('.guide-breadcrumbs a[href="#/"]')).not.toBeNull();
    expect(root.querySelector('a[href^="#/e/"]')).toBeNull();
  });
});
