// The football page as a detached element (football/main.js mounts it): the
// Arena's trackside frame (race.css) — the stage on the left under the
// match's name, a column on the right — with what a match needs in
// place of a board: the score, the plays, and the rules in a few words. Its own
// module, so the frame can be exercised as DOM: the rest needs WebGL and the
// server that played the match.

import { deckMarkup } from "../deck.js";
import { duckHead, wordmark } from "../wordmark.js";
import { el } from "../workshop/dom.js";
import { LETTERS, keeperColour, playLine, policyColour, policyOn } from "./plays.js";

/** The strip over the page: the mark, MICRODUCK FOOTBALL. The server answers nothing else, so nothing links on. */
export function strip() {
  const header = el("header", "signage");
  const brand = el("div", "club-brand");
  brand.append(duckHead(), wordmark({ word: "Football" }));
  header.append(brand);
  return header;
}

/** A policy's letter on its colour, as the scoreboard and the plays mark it. */
function swatch(policy) {
  const chip = el("span", "football-swatch", LETTERS[policy]);
  chip.style.background = policyColour(policy);
  return chip;
}

/** Show `text` in the gym scoreboard's flip tiles, a tile a digit, in `row`. */
export function flipTo(row, text) {
  if (row.dataset.shows === text) return;
  row.dataset.shows = text;
  row.replaceChildren(...[...text].map((character) => el("span", /\d/.test(character) ? "flip-digit" : "", character)));
}

function facts(summary) {
  const { length_m: length, width_m: width } = summary.pitch;
  const list = el("dl", "facts");
  for (const [label, value] of [
    ["pitch", `${length} × ${width} m, goals ${Math.round(summary.goal.width_m * 100)} cm wide`],
    ["whistle", `${summary.time_limit_s} s`],
    ["plays", `${summary.plays.length}, every seed from both ends`],
  ]) {
    const pair = el("div");
    pair.append(el("dt", "", label), el("dd", "", value));
    list.append(pair);
  }
  return list;
}

function scoreboard(summary) {
  const board = el("section", "scoreboard football-score");
  board.setAttribute("aria-label", "Goals");
  board.append(el("span", "mono-label", "Goals"));
  const tiles = summary.names.map((name, policy) => {
    const row = el("div", "football-score__row");
    const who = el("span", "football-who");
    who.append(swatch(policy), el("span", "football-who__name", name));
    who.title = name;
    const flip = el("div", "flip");
    flipTo(flip, "0");
    row.append(who, flip);
    board.append(row);
    return flip;
  });
  return { board, tiles };
}

function playList(summary) {
  const list = el("ol", "football-plays");
  summary.plays.forEach((play, k) => {
    const button = el("button", "football-play");
    button.type = "button";
    button.dataset.play = String(k);
    const ends = el("span", "football-play__ends");
    ends.title = `${play.on_end[0]} kicks off from the left, ${play.on_end[1]} from the right`;
    ends.append(swatch(policyOn(summary, play, 0)), el("span", "football-play__vs", "|"), swatch(policyOn(summary, play, 1)));
    button.append(
      el("span", "mono-label football-play__seed", `Play ${k + 1} · seed ${play.seed}`),
      ends,
      el("span", "football-play__how", playLine(summary, play)),
    );
    const item = el("li");
    item.append(button);
    list.append(item);
  });
  return list;
}

/** A keeper's name in its shell's colour, for the note. */
function keeperName(k, word) {
  const name = el("strong", "football-keeper", word);
  name.style.color = keeperColour(k);
  return name;
}

function note(summary) {
  const text = el("p", "football-note");
  text.append(
    "Each duck kicks off from its own end and attacks the far goal, kept by a Reachy Mini on a rail: ",
    keeperName(0, "lime"),
    " on the left, ",
    keeperName(1, "magenta"),
    " on the right. The policies walk; a coach steers each duck to the ball, and a duck on its feet "
      + "with the ball before it strikes it, at the goal once in range and lined up. "
      + "A goal is the ball wholly over the line. "
      + `A duck down ${summary.fall_hold_s} s is out of the play; both down, or the whistle at `
      + `${summary.time_limit_s} s, and nobody scores. A duck whose action is not a number gives the other the goal.`,
  );
  return text;
}

/**
 * The page's frame for `summary` (arena/football_watch.py football_summary),
 * and the parts main.js drives: the stage's clock, caption, stamp and verdict,
 * the score's tiles, the plays' buttons, and the transport.
 */
export function footballHall(summary) {
  const hall = el("main", "hall football");
  const grid = el("div", "racegrid");
  const left = el("div");
  left.append(el("p", "raceeyebrow", "Football"), el("h2", "racetitle", summary.title), facts(summary));
  left.insertAdjacentHTML("beforeend", deckMarkup);
  const stage = left.querySelector(".deck");
  // The camera follows the ball along the touchline, so letting it go and taking it back is a return.
  stage.querySelector("#follow").textContent = "Back to the touchline";

  const clock = el("div", "football-clock");
  const clockLabel = el("span", "mono-label");
  const clockTime = el("span", "football-clock__time", "0.00 s");
  clock.append(clockLabel, clockTime);
  const caption = el("p", "football-caption");
  const call = el("div", "football-verdict");
  const stamp = el("span", "stamp fx-tilt-2-5");
  call.append(stamp);
  const line = el("p", "football-line");
  line.setAttribute("role", "status");
  caption.hidden = call.hidden = line.hidden = true;
  stage.append(clock, caption, call, line);

  const column = el("div", "entry-col");
  const pause = el("button", "sticker", "Pause");
  const replay = el("button", "sticker sticker-cyan", "Replay play");
  pause.type = replay.type = "button";
  const transport = el("div", "football-transport");
  transport.append(pause, replay);
  const plays = playList(summary);
  const { board, tiles } = scoreboard(summary);
  column.append(board, el("p", "eyebrow football-plays__head", "Plays"), plays, transport, note(summary));
  grid.append(left, column);
  hall.append(grid);
  return {
    hall,
    parts: {
      stage,
      clock,
      clockLabel,
      clockTime,
      caption,
      call,
      stamp,
      line,
      tiles,
      plays: [...plays.querySelectorAll(".football-play")],
      pause,
      replay,
    },
  };
}
