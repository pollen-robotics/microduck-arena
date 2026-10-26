// What the football page (football/main.js) makes of the match
// `arena football A B --watch` played (arena/football_watch.py
// football_summary): each play as the viewer's event and lanes, its clock, the
// score as it stood, and what the referee saw and said, in words. Pure, so it
// is testable; the page itself needs WebGL.
//
// A play's `scorer` is an end, 0 kicking off from -x and attacking the goal at
// +x, as arena/football.py keeps it, and `on_end[k]` names who kicked off from
// end k; the match's two policies are `names`, A then B, and swap ends from one
// play to the next. End 0 is on the left from where the camera stands
// (football-venue.js footballCamera), and keeper k keeps end k's goal.

import { LANE_COLORS, LANE_CSS } from "../course.js";
import { KEEPER_TINTS } from "../football-venue.js";
import { leadIn } from "../replay.js";

// A's colours and B's, on the ducks and on the page.
const LIVERIES = ["classic", "blue"];
export const LETTERS = ["A", "B"];
// How long the stage's caption says what the referee saw: a shot, a save, a fall.
export const CAPTION_S = 1.4;

/** Which of the match's policies kicked off from end `k` of `play`: 0 for A, 1 for B. */
export const policyOn = (summary, play, k) => summary.names.indexOf(play.on_end[k]);

/** A policy's colour on the page, as a CSS colour: its ducks' lane colour. */
export const policyColour = (policy) => LANE_CSS[policy];

/** Keeper `k`'s colour on the page, as a CSS colour: its shell's. */
export const keeperColour = (k) => `#${KEEPER_TINTS[k].toString(16).padStart(6, "0")}`;

/**
 * Where a play's kick-off and its decision fall in its replay's seconds: the
 * replay opens on the settle, whose last frame is the kick-off, and the play's
 * second `s` is the replay's (settle frames - 1) * ctrl_dt + s.
 */
export function playTimes(summary, play) {
  const start = (play.settle_frames - 1) * summary.ctrl_dt;
  return { horn_s: Math.max(0, start), decided_s: Math.max(0, start + play.time_s) };
}

/**
 * The viewer's event for play `k` (viewer.js setLanes): `football` is what the
 * venue is built from (football-venue.js), `props` the ball's and the keepers'
 * frames as the server sends them, and the kick-off, the decision and how the
 * play ended set the crowd's direction over the replay.
 */
export function playEvent(summary, k, props = null) {
  const play = summary.plays[k];
  return {
    course: "football",
    id: summary.id,
    title: summary.title,
    rig: summary.rig,
    football: { pitch: summary.pitch, goal: summary.goal, ball: summary.ball, keeper: summary.keeper },
    ctrl_dt: summary.ctrl_dt,
    ...playTimes(summary, play),
    scorer: play.scorer,
    end: play.end,
    settle_frames: play.settle_frames,
    kickoff: play.kickoff,
    props,
  };
}

/**
 * Play `k`'s two lanes, end 0's duck first, as the viewer takes them: each from
 * its settle, so both ducks are seen to stand before kick-off. `settles` and
 * `traces` are by end, as the server sends them.
 */
export function playLanes(summary, k, settles, traces) {
  const play = summary.plays[k];
  return [0, 1].map((end) => {
    const policy = policyOn(summary, play, end);
    return {
      trace: leadIn(settles[end], traces[end], play.settle_frames),
      name: play.on_end[end],
      livery: LIVERIES[policy],
      colour: LANE_COLORS[policy],
      opacity: 1,
    };
  });
}

const seconds = (s) => `${s.toFixed(2)} s`;

/**
 * A play in a line of the match's list, its policies by letter: who scored, and
 * when — `fault` when one's action was not a number and the other was given
 * the goal, `down` when both went down, `whistle` at the time limit, and `void`
 * when the simulation diverged.
 */
export function playLine(summary, play) {
  const letter = (k) => LETTERS[policyOn(summary, play, k)];
  const at = seconds(play.time_s);
  const scored = play.scorer === 0 || play.scorer === 1;
  if (play.end === "void") return `Void at ${at}: the simulation diverged`;
  if (play.end === "goal") return `${letter(play.scorer)} scored at ${at}`;
  if (play.end === "fault") {
    return scored
      ? `${letter(play.scorer)} given it at ${at}: ${letter(1 - play.scorer)} faulted`
      : `Both faulted at ${at}: no goal`;
  }
  if (play.end === "down") return `Both down at ${at}: no goal`;
  return "No goal by the whistle";
}

/**
 * What the stage says once the referee has decided a play: a stamp — the
 * scorer's, in its colour, over its duck (`end`), or a goalless play's in the
 * middle — and the verdict in full, with the policies' names.
 */
export function verdict(summary, play) {
  const scored = play.scorer === 0 || play.scorer === 1;
  if (play.end === "void") {
    return { stamp: "Void", colour: null, end: null, line: "Void: the simulation diverged, so it counts for nobody" };
  }
  if (!scored) {
    const lines = {
      fault: "Both faulted, their actions not numbers: no goal",
      down: "Both ducks went down: no goal",
    };
    const stamp = play.end === "down" ? "Both down" : "No goal";
    const line = lines[play.end] ?? `No goal by the whistle, at ${summary.time_limit_s} s`;
    return { stamp, colour: null, end: null, line };
  }
  const [scorer, other] = [play.on_end[play.scorer], play.on_end[1 - play.scorer]];
  const colour = policyColour(policyOn(summary, play, play.scorer));
  if (play.end === "fault") {
    return { stamp: "Given", colour, end: play.scorer, line: `${scorer} is given the goal: ${other} faulted` };
  }
  return { stamp: "Goal!", colour, end: play.scorer, line: `${scorer} scores, ${seconds(play.time_s)} in` };
}

/** The play's clock at the replay's second `t`: nothing before kick-off, stopped at the decision. */
export function playClock(summary, play, t) {
  const { horn_s } = playTimes(summary, play);
  return Math.min(play.time_s, Math.max(0, t - horn_s));
}

/**
 * The score as it stood, A's goals then B's: every play before play `k`, and
 * play `k` itself once it is `decided`. A goal given for a fault counts.
 */
export function scoreAt(summary, k, decided = false) {
  const score = [0, 0];
  summary.plays.slice(0, decided ? k + 1 : k).forEach((play) => {
    if (play.scorer === 0 || play.scorer === 1) score[policyOn(summary, play, play.scorer)] += 1;
  });
  return score;
}

/**
 * What the stage's caption says at the replay's second `t`: the last thing the
 * referee saw — a shot, a save, the ball out or put back, a duck down — for
 * CAPTION_S after it, in its duck's or its keeper's colour; null when there is
 * nothing to say. A touch is the run of play, not news.
 */
export function eventCaption(summary, play, t) {
  const { horn_s } = playTimes(summary, play);
  const letter = (k) => LETTERS[policyOn(summary, play, k)];
  const colour = (k) => policyColour(policyOn(summary, play, k));
  let said = null;
  for (const event of play.events) {
    const at = horn_s + event.time_s;
    if (at > t) break;
    if (event.kind === "touch" || t - at > CAPTION_S) continue;
    const { kind, k } = event;
    if (kind === "shot") said = { text: `${letter(k)} shoots`, colour: colour(k) };
    else if (kind === "save") said = { text: "Saved!", colour: keeperColour(k) };
    else if (kind === "fall") said = { text: `${letter(k)} down`, colour: colour(k) };
    else if (kind === "out") said = { text: "Out", colour: null };
    else if (kind === "stall") said = { text: "Ball back in", colour: null };
  }
  return said;
}
