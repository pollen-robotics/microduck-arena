// A cup's match on tape: a title over the waiting ducks, its bouts one after the other at speed, each
// from its settle and held on its end, and an outro on the winner. Pure, as plan.js, whose actAt and
// travelAt read this plan as they read a run's.

import { winLine } from "../bouts.js";
import { capitalised } from "../format.js";
import { CTRL_DT } from "../replay.js";
import { FPS, INTRO_S, OUTRO_S, STRIDE, TRAVEL_S } from "./plan.js";

/** How long a bout's last pose holds, its result on the bug, before the next bout or the outro: the
 * booth says the result as it is seen, never before. */
export const BOUT_HOLD_S = 6;

const round3 = (seconds) => Math.round(seconds * 1000) / 1000;

/**
 * `bouts` are the match's bouts in order, each `{k, settle, steps}`: the frames of its settle and of
 * its trace. Each `span` is a bout's clip frames, `from` up to `to`, its tape up to `held` and its
 * last pose held from there; each of `bouts` says where its trace starts and ends on the tape, in
 * seconds, after its settle, and where its hold ends.
 */
export function matchPlan(bouts) {
  const intro = FPS * INTRO_S;
  const spans = [];
  let from = intro;
  for (const { k, settle, steps } of bouts) {
    const held = from + Math.ceil((settle + steps) / STRIDE);
    const to = held + FPS * BOUT_HOLD_S;
    spans.push({ k, from, held, to, settle, steps });
    from = to;
  }
  const tapeEnd = from;
  const outro = Math.round(FPS * OUTRO_S);
  const frames = tapeEnd + outro;
  return {
    fps: FPS,
    stride: STRIDE,
    intro,
    travel: FPS * TRAVEL_S,
    outro,
    frames,
    seconds: frames / FPS,
    tapeEnd,
    poster: intro + Math.floor((tapeEnd - intro) * 0.6),
    spans,
    bouts: spans.map(({ k, from, to, settle, steps }) => {
      const start = round3(from / FPS + settle * CTRL_DT);
      return { k, tape_start_s: start, tape_end_s: round3(start + steps * CTRL_DT), hold_end_s: round3(to / FPS) };
    }),
  };
}

/** The bout clip frame `i` shows and its step, counted from the bout's settle: the first bout's
 * first step under the title, each bout's last step through its hold, the last one's through the
 * outro. */
export function boutAt(plan, i) {
  if (i < plan.intro) return { bout: plan.spans[0].k, step: 0 };
  const span = plan.spans.find((one) => i < one.to) ?? plan.spans.at(-1);
  return { bout: span.k, step: Math.min((i - span.from) * plan.stride, span.settle + span.steps - 1) };
}

/** The bouts each side has won, [a, b], on the tapes ended by clip frame `i`, a bout's from its hold. */
export function scoreAt(plan, match, i) {
  const winners = plan.spans.filter((span) => i >= span.held).map((span) => match.bouts[span.k].winner);
  return ["a", "b"].map((side) => winners.filter((winner) => winner === side).length);
}

/** The words on a match's clip: the cup, who meets whom, the players while the score bug names their
 * policies, and who won by how much, or, on a tie, by the higher rating, the winner by its policy's
 * name over its player's handle. */
export function matchWords(match) {
  const [won, lost] = match.winner === "a" ? match.wins : [...match.wins].reverse();
  const stage = match.round === "group" ? `Group ${match.group}` : capitalised(match.round);
  const winner = match[match.winner];
  const outro = winLine(match, winner.policy_name);
  return {
    title: `${match.event.title} · Cup #${match.cup}`,
    line: match.title,
    players: `${stage} · @${match.a.user} vs @${match.b.user}`,
    outro: match.decided_by === "rating" ? outro : `${outro} ${won}–${lost}`,
    by: `@${winner.user}`,
  };
}
