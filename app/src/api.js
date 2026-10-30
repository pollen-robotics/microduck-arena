// Every call the page makes. Errors surface the server's own message, which for
// a rejected policy is the same sentence the robot's daemon would give.

import { splitDucks } from "./replay.js";

export async function detailFrom(response) {
  try {
    const body = await response.json();
    if (body.detail) {
      // FastAPI's own validation errors put an ARRAY here, not a string;
      // stringify rather than letting it become "[object Object]".
      return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    }
  } catch {
    // Not a JSON body; the status line is the best we have.
  }
  return `${response.status} ${response.statusText}`;
}

async function json(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(await detailFrom(response));
  return response.json();
}

export const getEvents = () => json("/api/events").then((b) => b.events);
export const getLeaderboard = (eventId) => json(`/api/events/${eventId}/leaderboard`);
export const getRun = (runId) => json(`/api/runs/${runId}`);

export const getStandings = () => json("/api/standings").then((b) => b.rows);

/** One player's page, or null when nobody by that name has published. */
export async function getPlayer(user) {
  const response = await fetch(`/api/players/${encodeURIComponent(user)}`);
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await detailFrom(response));
  return response.json();
}

/**
 * Drop the session, server side and in the cookie.
 *
 * Only ever offered where OAuth is what signed you in: the local path hands
 * out a session from ARENA_DEV_USER on every request and would sign you
 * straight back in, so a button there would do nothing and say it had.
 */
export const signOut = () => json("/logout", { method: "POST" });

/** Who the server thinks you are. Never throws: a failure means signed out. */
export async function getMe() {
  try {
    return await json("/api/me");
  } catch {
    return null;
  }
}

const POINT_FLOATS = 17 * 3;

async function frames(path) {
  const response = await fetch(path);
  // Same contract as every other call: the server's own sentence, not a status.
  if (!response.ok) throw new Error(await detailFrom(response));
  // Raw little-endian float32 from the server, 21 values per frame, one duck after the other: a
  // stage sends every duck of its troupe (X-Duck-Count), a lane its one duck.
  const ducks = Number(response.headers.get("X-Duck-Count") ?? 1);
  const caught = response.headers.get("X-Caught-Frame");
  // `caught`: the frame a Sock Heist seed's duck was caught on, null when it was not (and on every other event).
  return Object.assign(splitDucks(new Float32Array(await response.arrayBuffer()), ducks), {
    caught: caught === null ? null : Number(caught),
  });
}

/** A tug's string, 17 points a frame: the untimed settle's frames, then the timed ones. */
async function points(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(await detailFrom(response));
  const all = new Float32Array(await response.arrayBuffer());
  const settled = Number(response.headers.get("X-Settle-Frame-Count")) * POINT_FLOATS;
  return { settle: all.slice(0, settled), trace: all.slice(settled) };
}

const seeded = (path, seed) => (seed == null ? path : `${path}?seed=${seed}`);

/** A run's trace, one per duck, in duck order: a lane's is its one duck. A Sock Heist run plays one `seed` of its five. */
export function getTrace(runId, seed) {
  return frames(seeded(`/api/runs/${runId}/trace`, seed));
}

export const getString = (runId) => points(`/api/runs/${runId}/string`);

/** The untimed settle before a run's trace, from the reset pose, one per duck; empty for a run stored before settles were recorded. */
export function getSettle(runId, seed) {
  return frames(seeded(`/api/runs/${runId}/settle`, seed));
}

/** Take one of your own entries off the board. Not a delete — see the server. */
export const withdrawRun = (runId) =>
  json(`/api/runs/${runId}/withdraw`, { method: "POST" });

/**
 * A field to judge, or the reason there is none.
 *
 * Every answer is a STATE, never a thrown error: "you are signed out", "there
 * are not enough ducks yet" and "that is your votes for today" are all things
 * the page draws as a panel, not failures.
 */
export async function getBallot(eventId) {
  const response = await fetch(`/api/events/${encodeURIComponent(eventId)}/ballot`);
  if (response.status === 401) return { state: "signed-out" };
  if (!response.ok) throw new Error(await detailFrom(response));
  return response.json();
}

/** One lane's replay, one trace per duck. Addressed through the ballot, so no run id is exposed. */
export const ballotTraceUrl = (ballot, lane) => `/api/ballots/${ballot}/lanes/${lane}/trace`;

export const getBallotTrace = (ballot, lane) => frames(ballotTraceUrl(ballot, lane));

export const castVote = (eventId, ballot, lane) =>
  json(`/api/events/${encodeURIComponent(eventId)}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ballot, lane }),
  });

/** Tell the server its author has seen this run's page. The server refuses anyone else. */
export const markSeen = (runId) => json(`/api/runs/${runId}/seen`, { method: "POST" });

/** Where a run's clip stands: none, pending, failed, or ready with its files. */
export const getClip = (runId) => json(`/api/runs/${runId}/clip`);

/** The channel's grid and the server's clock. Never cached: the clock is in it. */
export const getLive = () => json("/api/live", { cache: "no-store" });

/** What a live slot plays, never cached: null when it is gone, or not served yet. */
async function onAir(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await detailFrom(response));
  return response.json();
}

/** A booth's dialogue and the plan that plays it, or null when it is gone. */
export const getBroadcast = (id) => onAir(`/api/live/broadcast/${id}`);

/** A desk segment of a cup's show: its dialogue, its plan and the cup screen's view, served from shortly before it airs. */
export const getShow = (eventId, number, segment) => onAir(`/api/live/show/${eventId}/${number}/${segment}`);

/** A called match's lines and the plan that voices them over its clip, served with the clip's media. */
export const getCall = (matchId) => onAir(`/api/live/call/${matchId}`);

// `version` is the render the file belongs to (a slot's `clip`): the files are
// cached for a year as immutable, so a clip rendered again is a new URL.
export const clipUrl = (runId, name, version) => `/api/runs/${runId}/clip/${name}?v=${version}`;

/** An event's cups, newest first, and the next one: when it closes, when it premieres, who has entered. */
export const getCups = (eventId) => json(`/api/events/${eventId}/cups`);

/** One cup as far as it has aired: the field before the show, then its groups and bracket match by match. */
export const getCup = (eventId, number) => json(`/api/events/${eventId}/cups/${number}`);

/** A cup's match: its two entrants, its bouts and how it ended. */
export const getMatch = (matchId) => json(`/api/matches/${matchId}`);

/** Bout `k` of a match, both ducks, west first; and the untimed settle before it. */
export const getBoutTrace = (matchId, k) => frames(`/api/matches/${matchId}/bouts/${k}/trace`);
export const getBoutSettle = (matchId, k) => frames(`/api/matches/${matchId}/bouts/${k}/settle`);
export const getBoutString = (matchId, k) => points(`/api/matches/${matchId}/bouts/${k}/string`);

// Versioned by its render, as a run's clip files are (clipUrl).
export const matchClipUrl = (matchId, name, version) => `/api/matches/${matchId}/clip/${name}?v=${version}`;
