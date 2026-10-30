import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ballotTraceUrl,
  clipUrl,
  getBallot,
  getBallotTrace,
  getBoutSettle,
  getBoutTrace,
  getBroadcast,
  getCall,
  getCup,
  getCups,
  getLeaderboard,
  getLive,
  getMatch,
  getPlayer,
  getStandings,
  getSettle,
  getShow,
  getString,
  getTrace,
  matchClipUrl,
} from "./api.js";

function respondWith({ ok = true, status = 200, statusText = "OK", body, bytes, headers = {} }) {
  globalThis.fetch = vi.fn(async () => ({
    ok,
    status,
    statusText,
    headers: new Headers(headers),
    json: async () => {
      if (body === undefined) throw new Error("not json");
      return body;
    },
    arrayBuffer: async () => bytes,
  }));
}

afterEach(() => {
  vi.restoreAllMocks();
  delete globalThis.fetch;
});

describe("the error contract", () => {
  it("surfaces the server's sentence, not the status code", async () => {
    respondWith({ ok: false, status: 400, body: { detail: "not a loadable ONNX model: nope" } });
    await expect(getLeaderboard("sprint-2m")).rejects.toThrow("not a loadable ONNX model: nope");
  });

  it("applies the same contract to a trace fetch", async () => {
    // This is the one that used to throw "trace 404" and lose the reason.
    respondWith({ ok: false, status: 404, body: { detail: "no such run: '01NOPE'" } });
    await expect(getTrace("01NOPE")).rejects.toThrow("no such run: '01NOPE'");
  });

  it("stringifies a non-string detail instead of [object Object]", async () => {
    // FastAPI's validation errors put an array here.
    respondWith({ ok: false, status: 422, body: { detail: [{ type: "missing" }] } });
    await expect(getTrace("x")).rejects.toThrow(/"type":"missing"/);
  });

  it("falls back to the status line when the body is not JSON", async () => {
    respondWith({ ok: false, status: 502, statusText: "Bad Gateway" });
    await expect(getTrace("x")).rejects.toThrow("502 Bad Gateway");
  });

  it("returns one duck's Float32Array when the server counts no ducks: a lane's", async () => {
    const source = new Float32Array([1.5, 2.5, 3.5]);
    respondWith({ bytes: source.buffer });
    const ducks = await getTrace("01OK");
    expect(ducks).toHaveLength(1);
    expect(ducks[0]).toBeInstanceOf(Float32Array);
    expect([...ducks[0]]).toEqual([1.5, 2.5, 3.5]);
  });

  it("cuts a troupe's trace into its ducks, in duck order", async () => {
    respondWith({ bytes: new Float32Array([1, 2, 3, 4, 5, 6]).buffer, headers: { "X-Duck-Count": "3" } });
    expect((await getTrace("01OK")).map((duck) => [...duck])).toEqual([[1, 2], [3, 4], [5, 6]]);
  });

  it("fetches a run's settle the way it fetches its trace", async () => {
    respondWith({ bytes: new Float32Array([0.5, 0.25]).buffer, headers: { "X-Duck-Count": "2" } });
    const settles = await getSettle("01OK");
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/runs/01OK/settle");
    expect(settles.map((duck) => [...duck])).toEqual([[0.5], [0.25]]);
  });
});

describe("a tug's string", () => {
  it("is cut into its settle and its timed frames at the settle's count", async () => {
    respondWith({ bytes: new Float32Array(5 * 51).buffer, headers: { "X-Frame-Count": "3", "X-Settle-Frame-Count": "2" } });
    const { settle, trace } = await getString("R1");
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/runs/R1/string");
    expect([settle.length, trace.length]).toEqual([102, 153]);
  });
});

describe("standings and players", () => {
  it("returns the ladder rows", async () => {
    respondWith({ body: { rows: [{ rank: 1, user: "ann", points: 360 }] } });
    expect(await getStandings()).toEqual([{ rank: 1, user: "ann", points: 360 }]);
    expect(fetch.mock.calls[0][0]).toBe("/api/standings");
  });

  it("returns a player", async () => {
    respondWith({ body: { user: "ann", points: 360, rank: 1, best: [] } });
    expect(await getPlayer("ann")).toEqual({ user: "ann", points: 360, rank: 1, best: [] });
    expect(fetch.mock.calls[0][0]).toBe("/api/players/ann");
  });

  it("returns null when nobody by that name has published", async () => {
    respondWith({ ok: false, status: 404, body: { detail: "'nobody' has not published yet" } });
    expect(await getPlayer("nobody")).toBeNull();
  });

  it("still surfaces any other failure as the server's sentence", async () => {
    respondWith({ ok: false, status: 500, body: { detail: "store unreadable" } });
    await expect(getPlayer("ann")).rejects.toThrow("store unreadable");
  });
});

describe("the ballot", () => {
  it("reads a field to judge", async () => {
    globalThis.fetch = async () => ({
      ok: true,
      json: async () => ({ state: "ballot", ballot: "tok.mac", lanes: 3, cast_today: 1, per_day: 20 }),
    });
    expect(await getBallot("got-a-talent")).toEqual({
      state: "ballot", ballot: "tok.mac", lanes: 3, cast_today: 1, per_day: 20,
    });
  });

  it("reads being signed out as a state, not a failure", async () => {
    globalThis.fetch = async () => ({ ok: false, status: 401, json: async () => ({}) });
    expect(await getBallot("got-a-talent")).toEqual({ state: "signed-out" });
  });

  it("addresses a lane's replay through the ballot and never a run", () => {
    expect(ballotTraceUrl("tok.mac", 2)).toBe("/api/ballots/tok.mac/lanes/2/trace");
  });

  it("applies the same error contract to a lane's replay", async () => {
    respondWith({ ok: false, status: 404, body: { detail: "no such ballot: 'tok.mac'" } });
    await expect(getBallotTrace("tok.mac", 2)).rejects.toThrow("no such ballot: 'tok.mac'");
  });

  it("stringifies a non-string detail instead of [object Object]", async () => {
    // FastAPI's validation errors put an array here.
    respondWith({ ok: false, status: 422, body: { detail: [{ type: "missing" }] } });
    await expect(getBallotTrace("tok.mac", 2)).rejects.toThrow(/"type":"missing"/);
  });

  it("falls back to the status line when the body is not JSON", async () => {
    respondWith({ ok: false, status: 502, statusText: "Bad Gateway" });
    await expect(getBallotTrace("tok.mac", 2)).rejects.toThrow("502 Bad Gateway");
  });

  it("returns every duck of a lane, fetched over the ballot-scoped url", async () => {
    const source = new Float32Array([1.5, 2.5, 3.5, 4.5]);
    respondWith({ bytes: source.buffer, headers: { "X-Duck-Count": "2" } });
    const ducks = await getBallotTrace("tok.mac", 2);
    expect(ducks.map((duck) => [...duck])).toEqual([[1.5, 2.5], [3.5, 4.5]]);
    expect(fetch.mock.calls[0][0]).toBe("/api/ballots/tok.mac/lanes/2/trace");
  });
});

describe("the channel", () => {
  it("reads the grid uncached, since the clock is in it", async () => {
    respondWith({ body: { version: 1, now_ms: 5000, build: "b", slots: [] } });
    expect(await getLive()).toEqual({ version: 1, now_ms: 5000, build: "b", slots: [] });
    expect(fetch.mock.calls[0]).toEqual(["/api/live", { cache: "no-store" }]);
  });

  it("fetches a broadcast by its id", async () => {
    const calls = [];
    globalThis.fetch = async (url, init) => {
      calls.push([url, init]);
      return { ok: true, json: async () => ({ dialogue: { turns: [] }, plan: { duration_ms: 4000 } }) };
    };
    const body = await getBroadcast("01M2K");
    expect(calls[0][0]).toBe("/api/live/broadcast/01M2K");
    expect(body.plan.duration_ms).toBe(4000);
  });

  it("gives nothing for a broadcast that is gone", async () => {
    globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => ({}) });
    expect(await getBroadcast("gone")).toBe(null);
  });

  it("reads a cup's desk segment and a match's call uncached, and nothing before they are served", async () => {
    respondWith({ body: { plan: { duration_ms: 4000 } } });
    expect(await getShow("tug-of-war", 1, "opening")).toEqual({ plan: { duration_ms: 4000 } });
    await getCall("tug-of-war-0001-003");
    expect(fetch.mock.calls).toEqual([
      ["/api/live/show/tug-of-war/1/opening", { cache: "no-store" }],
      ["/api/live/call/tug-of-war-0001-003", { cache: "no-store" }]]);
    respondWith({ ok: false, status: 404, body: {} });
    expect(await getShow("tug-of-war", 1, "opening")).toBe(null);
    expect(await getCall("tug-of-war-0001-003")).toBe(null);
  });

  it("addresses a clip's files under the run, versioned by the render they belong to", () => {
    // The files are cached for a year as immutable, so a clip rendered again
    // on a new stage has to be a new URL or the old one plays for ever.
    expect(clipUrl("01ABC", "clip.mp4", "20260922T151828Z")).toBe(
      "/api/runs/01ABC/clip/clip.mp4?v=20260922T151828Z",
    );
  });
});

describe("a cup", () => {
  it("reads an event's cups and one cup under the event", async () => {
    respondWith({ body: {} });
    await getCups("tug-of-war");
    await getCup("tug-of-war", 3);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(["/api/events/tug-of-war/cups", "/api/events/tug-of-war/cups/3"]);
  });
});

describe("a match", () => {
  it("reads a bout as two ducks and versions a match clip's files", async () => {
    respondWith({ bytes: new Float32Array(84).buffer, headers: { "X-Duck-Count": "2" } });
    const ducks = await getBoutTrace("tug-of-war-0001-000", 1);
    expect(fetch).toHaveBeenCalledWith("/api/matches/tug-of-war-0001-000/bouts/1/trace");
    expect(ducks.map((d) => d.length)).toEqual([42, 42]);
    expect(matchClipUrl("tug-of-war-0001-000", "landscape.mp4", "v1")).toBe("/api/matches/tug-of-war-0001-000/clip/landscape.mp4?v=v1");
  });

  it("reads a match and its bouts' settles under the match", async () => {
    respondWith({ body: {}, bytes: new Float32Array(84).buffer, headers: { "X-Duck-Count": "2" } });
    await getMatch("tug-of-war-0001-000");
    await getBoutSettle("tug-of-war-0001-000", 2);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(["/api/matches/tug-of-war-0001-000",
      "/api/matches/tug-of-war-0001-000/bouts/2/settle"]);
  });
});

describe("a lights run's seeds", () => {
  it("asks for one seed's trace and settle when given one, and for the stored ones as today when not", async () => {
    respondWith({ bytes: new Float32Array(2).buffer });
    await getTrace("R1", 3);
    expect(globalThis.fetch).toHaveBeenLastCalledWith("/api/runs/R1/trace?seed=3");
    await getSettle("R1", 3);
    expect(globalThis.fetch).toHaveBeenLastCalledWith("/api/runs/R1/settle?seed=3");
    await getTrace("R1");
    expect(globalThis.fetch).toHaveBeenLastCalledWith("/api/runs/R1/trace");
  });
  it("carries the frame a seed's duck was caught on, and null when it was not", async () => {
    respondWith({ bytes: new Float32Array(2).buffer, headers: { "X-Caught-Frame": "412" } });
    expect((await getTrace("R1", 3)).caught).toBe(412);
    respondWith({ bytes: new Float32Array(2).buffer });
    expect((await getTrace("R1", 3)).caught).toBeNull();
  });
});
