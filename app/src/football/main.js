// The football page: the match `arena football A B --watch` has just played
// (arena/football_watch.py), play by play, in the Arena's own stadium — the
// hall, the stands and their crowd, the jury on its table — round the pitch,
// its goals and their keepers (football-venue.js). The page reads the match
// once, fetches each play's frames as it comes to it, and plays the plays in
// their order, the next a moment after the last has ended, until the visitor
// picks one or pauses.

import { MIN } from "../brightness.js";
import { followKeyFor, offerOrbit, wireDeck } from "../deck.js";
import { PROP_WIDTH } from "../football-venue.js";
import { splitDucks } from "../replay.js";
import { footer } from "../signage.js";
import { createViewer, PLATE_HEIGHT, PLATE_LIFT } from "../viewer.js";
import { el } from "../workshop/dom.js";
import { flipTo, footballHall, strip } from "./hall.js";
import { eventCaption, playClock, playEvent, playLanes, playTimes, scoreAt, verdict } from "./plays.js";

// How long a finished play's last frame holds before the next play.
const NEXT_MS = 2500;
// The stamp over the scorer: clear of its plate (viewer.js spot), inside the
// picture, and under the clock and the verdict's line.
const STAMP_INSET = 0.2;
const STAMP_LIFT = PLATE_LIFT + PLATE_HEIGHT / 2 + 0.04;
const STAMP_FOOT = [0.25, 0.7];
const STAMP_CLEAR = 6;

const clamp = (value, [low, high]) => Math.min(high, Math.max(low, value));

async function failed(response) {
  return new Error((await response.text()).trim() || `${response.status} ${response.statusText}`);
}

async function json(path) {
  const response = await fetch(path);
  if (!response.ok) throw await failed(response);
  return response.json();
}

/** A play's settle or trace, one per end: little-endian float32, end 0's frames, then end 1's. */
async function frames(path) {
  const response = await fetch(path);
  if (!response.ok) throw await failed(response);
  return splitDucks(new Float32Array(await response.arrayBuffer()), Number(response.headers.get("X-Duck-Count")));
}

/** A play's props: little-endian float32, PROP_WIDTH a frame. */
async function props(path) {
  const response = await fetch(path);
  if (!response.ok) throw await failed(response);
  const width = Number(response.headers.get("X-Prop-Width"));
  if (width !== PROP_WIDTH) throw new Error(`props ${width} wide, where the page reads ${PROP_WIDTH}`);
  return new Float32Array(await response.arrayBuffer());
}

async function main() {
  const root = document.querySelector("#app");
  let summary;
  try {
    summary = await json("/api/football");
  } catch (error) {
    root.replaceChildren(el("p", "failed", `The match's server did not answer (${error.message}). `
      + "This page shows a match that arena football A.onnx B.onnx --watch has played."));
    return;
  }
  document.title = `${summary.names.join(" v ")} · Microduck football`;
  const { hall, parts } = footballHall(summary);
  root.replaceChildren(strip(), hall, footer());

  const viewer = await createViewer(hall.querySelector("#stage"), { rig: summary.rig, onChaseChange: followKeyFor(hall) });
  viewer.setBrightness(MIN); // as the Arena's race page
  wireDeck(hall, viewer);
  offerOrbit(hall, viewer);

  const loads = new Map();
  function load(k) {
    if (!loads.has(k)) {
      const base = `/api/football/plays/${k}`;
      const loading = Promise.all([frames(`${base}/settle`), frames(`${base}/trace`), props(`${base}/props`)]);
      // A load that failed is tried again when the play is next asked for.
      loading.catch(() => loads.delete(k));
      loads.set(k, loading);
    }
    return loads.get(k);
  }

  let current = -1;
  let asked = 0; // the latest show(): an older one that loads late plays nothing
  let next = null; // the timer that plays the next play
  let held = false; // paused by the visitor, who then says when the match goes on
  let decided = null;
  let said = null; // the caption's text, as it stands

  function wait() {
    clearTimeout(next);
    next = null;
  }

  function score(goals) {
    goals.forEach((value, policy) => flipTo(parts.tiles[policy], String(value)));
  }

  async function show(k) {
    const mine = ++asked;
    wait();
    let settles, traces, frame;
    try {
      [settles, traces, frame] = await load(k);
    } catch (error) {
      if (mine === asked) {
        parts.line.textContent = `Play ${k + 1} did not load: ${error.message}`;
        parts.line.hidden = false;
      }
      return;
    }
    if (mine !== asked) return;
    current = k;
    held = false;
    decided = null;
    viewer.setLanes(playLanes(summary, k, settles, traces), playEvent(summary, k, frame), { loop: false });
    const play = summary.plays[k];
    parts.clockLabel.textContent = `Play ${k + 1} of ${summary.plays.length} · seed ${play.seed}`;
    parts.plays.forEach((button, b) => button.setAttribute("aria-current", String(b === k)));
    score(scoreAt(summary, k));
    if (k + 1 < summary.plays.length) load(k + 1).catch(() => {});
  }

  /** The stamp, the verdict and the score, once the referee has decided the play; undone on a seek back. */
  function call(play, now) {
    if (now === decided) return;
    decided = now;
    parts.call.hidden = parts.line.hidden = !now;
    score(scoreAt(summary, current, now));
    if (!now) return;
    const words = verdict(summary, play);
    parts.stamp.textContent = words.stamp;
    parts.stamp.classList.toggle("stamp-fail", play.end === "void");
    parts.stamp.style.color = words.colour ?? "";
    parts.line.textContent = words.line;
    // Over the scorer where it stands now, wherever the camera has been taken; no goal's where football.css puts it.
    if (words.end === null) {
      parts.call.style.left = parts.call.style.top = "";
      return;
    }
    const { x, y } = viewer.spot(words.end, STAMP_LIFT);
    const picture = parts.stage.getBoundingClientRect();
    const tall = parts.call.getBoundingClientRect().height;
    const under = (part) => (part.getBoundingClientRect().bottom - picture.top + STAMP_CLEAR + tall) / picture.height;
    const low = Math.min(Math.max(STAMP_FOOT[0], under(parts.clock), under(parts.line)), STAMP_FOOT[1]);
    parts.call.style.left = `${100 * clamp(x, [STAMP_INSET, 1 - STAMP_INSET])}%`;
    parts.call.style.top = `${100 * clamp(y, [low, STAMP_FOOT[1]])}%`;
  }

  /** What the referee last saw, until the play is decided and the stamp says the rest. */
  function caption(play, t, over) {
    const now = over ? null : eventCaption(summary, play, t);
    const text = now?.text ?? null;
    if (text === said) return;
    said = text;
    parts.caption.hidden = !now;
    parts.caption.textContent = text ?? "";
    parts.caption.style.color = now?.colour ?? "";
  }

  function watch() {
    const play = summary.plays[current];
    if (play) {
      const { player } = viewer;
      const now = player.duration > 0 && player.time >= playTimes(summary, play).decided_s;
      parts.clockTime.textContent = `${playClock(summary, play, player.time).toFixed(2)} s`;
      caption(play, player.time, now);
      call(play, now);
      const over = !player.playing && player.time >= player.duration;
      parts.pause.textContent = player.playing ? "Pause" : over ? "Play again" : "Play";
      if (over && !held && next === null && current + 1 < summary.plays.length) {
        next = setTimeout(() => show(current + 1), NEXT_MS);
      }
    }
    requestAnimationFrame(watch);
  }

  parts.plays.forEach((button, k) => button.addEventListener("click", () => show(k)));
  parts.pause.addEventListener("click", () => {
    const { player } = viewer;
    if (player.playing) {
      player.playing = false;
      held = true;
      wait();
      return;
    }
    if (player.time >= player.duration) player.seek(0);
    held = false;
    player.play();
  });
  parts.replay.addEventListener("click", () => {
    wait();
    held = false;
    viewer.player.seek(0);
    viewer.player.play();
  });

  // For a shell, or a recorder, to take the picture it wants: a play, and a moment of it.
  window.football = {
    summary,
    viewer,
    show,
    get play() {
      return current;
    },
    /** Hold play `current` at the replay's second `t`, the match's progress stopped with it. */
    hold(t) {
      held = true;
      wait();
      viewer.player.playing = false;
      viewer.player.seek(t);
    },
  };
  await show(0);
  requestAnimationFrame(watch);
}

main();
