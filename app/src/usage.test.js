import { beforeEach, describe, expect, it, vi } from "vitest";
import { trackUsage } from "./usage.js";

function memoryStorage() {
  const kept = new Map();
  return { getItem: (k) => kept.get(k) ?? null, setItem: (k, v) => kept.set(k, String(v)) };
}

beforeEach(() => {
  vi.stubGlobal("localStorage", memoryStorage());
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  location.hash = "#/e/sprint-2m";
});

function hide() {
  Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
  document.dispatchEvent(new Event("visibilitychange"));
}

describe("trackUsage", () => {
  it("opens a visit with a view of the page it landed on, saying how it came", () => {
    const send = vi.fn();
    trackUsage(send);
    const [[hit]] = send.mock.calls;
    expect(hit).toMatchObject({ kind: "view", page: "/e/sprint-2m", embedded: false, mobile: false });
    expect(hit.visitor).toMatch(/^[A-Za-z0-9-]{8,40}$/);
    expect(hit.visit).not.toBe(hit.visitor);
  });

  it("keeps the visitor across visits, and a new visit each time", () => {
    const first = vi.fn();
    const second = vi.fn();
    trackUsage(first);
    trackUsage(second);
    expect(second.mock.calls[0][0].visitor).toBe(first.mock.calls[0][0].visitor);
    expect(second.mock.calls[0][0].visit).not.toBe(first.mock.calls[0][0].visit);
  });

  it("counts a view for every page the visit moves to", async () => {
    const send = vi.fn();
    trackUsage(send);
    location.hash = "#/live";
    await new Promise((resolve) => addEventListener("hashchange", resolve, { once: true }));
    const view = send.mock.calls.at(-1)[0];
    expect(view).toMatchObject({ kind: "view", page: "/live" });
    expect(view).not.toHaveProperty("embedded");
  });

  it("reports a link that leaves the site, not one that stays", () => {
    const send = vi.fn();
    trackUsage(send);
    const out = Object.assign(document.createElement("a"), { href: "https://store.pollen-robotics.com/products/microduck" });
    const inside = Object.assign(document.createElement("a"), { href: "#/live" });
    const label = document.createElement("span");
    out.append(label);
    document.body.append(out, inside);
    out.addEventListener("click", (event) => event.preventDefault());
    inside.addEventListener("click", (event) => event.preventDefault());
    label.click();
    inside.click();
    const outs = send.mock.calls.map(([hit]) => hit).filter((hit) => hit.kind === "out");
    expect(outs).toEqual([expect.objectContaining({ href: "https://store.pollen-robotics.com/products/microduck" })]);
  });

  it("reports how long the page was looked at when it is hidden", () => {
    vi.useFakeTimers();
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    const send = vi.fn();
    trackUsage(send);
    vi.advanceTimersByTime(42_000);
    hide();
    vi.useRealTimers();
    expect(send.mock.calls.at(-1)[0]).toMatchObject({ kind: "time", seconds: 42 });
  });
});
