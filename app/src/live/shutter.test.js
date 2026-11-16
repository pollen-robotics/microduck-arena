import { describe, expect, it } from "vitest";
import { TRANSITION_MS, createShutter, shutterAt } from "./shutter.js";

describe("shutterAt", () => {
  it("sweeps in over 400 ms, holds to 1200, sweeps out to the right by 1600", () => {
    expect(shutterAt(0)).toEqual({ x: -1, destination: false });
    expect(shutterAt(200).x).toBeCloseTo(-0.5);
    expect(shutterAt(400)).toEqual({ x: 0, destination: false });
    expect(shutterAt(799).destination).toBe(false);
    expect(shutterAt(800)).toEqual({ x: 0, destination: true });
    expect(shutterAt(1400).x).toBeCloseTo(0.5);
    expect(shutterAt(TRANSITION_MS)).toEqual({ x: 1, destination: true });
  });
});

describe("createShutter", () => {
  it("shows the card with the next replay only on the way out, and hides at the ends", () => {
    const container = document.createElement("div");
    const shutter = createShutter(container);
    const panel = container.querySelector(".live-shutter");
    const card = panel.querySelector(".live-upnext");
    shutter.draw(600, { event: "2 m Sprint", user: "carol" });
    expect(panel.hidden).toBe(false);
    expect(card.hidden).toBe(true);
    shutter.draw(900, { event: "2 m Sprint", user: "carol" });
    expect(card.hidden).toBe(false);
    expect(card.querySelector(".live-upnext-event").textContent).toBe("2 m Sprint");
    expect(card.querySelector(".live-upnext-user").textContent).toBe("@carol");
    shutter.draw(900, null);
    expect(card.hidden).toBe(true);
    expect(panel.style.getPropertyValue("--shutter-x")).toBe("0");
    shutter.draw(1600, null);
    expect(panel.hidden).toBe(true);
    shutter.hide();
    expect(panel.hidden).toBe(true);
  });

  it("announces a cup match by its title, over its billing when it has one", () => {
    const container = document.createElement("div"), shutter = createShutter(container);
    shutter.draw(900, { match_id: "m", title: "Cup #1 · Final", billing: "Tank (@ana) vs Lean (@bo)" });
    expect(container.querySelector(".live-upnext-event").textContent).toBe("Cup #1 · Final");
    expect(container.querySelector(".live-upnext-user").hidden).toBe(false);
    expect(container.querySelector(".live-upnext-user").textContent).toBe("Tank (@ana) vs Lean (@bo)");
    shutter.draw(900, { match_id: "m", title: "Final" });
    expect(container.querySelector(".live-upnext-event").textContent).toBe("Final");
    expect(container.querySelector(".live-upnext-user").hidden).toBe(true);
    expect(container.querySelector(".live-upnext-user").textContent).toBe("");
    shutter.draw(900, { event: "2 m Sprint", user: "carol" });
    expect(container.querySelector(".live-upnext-user").hidden).toBe(false);
    expect(container.querySelector(".live-upnext-user").textContent).toBe("@carol");
  });
});
