// One race: the stage, the entry column beside it, the standing beneath.

import {
  getCups,
  getEvents,
  getLeaderboard,
  getMe,
  getString,
  getTrace,
  withdrawRun,
} from "./api.js";
import { boardsheetMarkup, podium, wireBoardsheet } from "./boardsheet.js";
import { pageCamera, replayLane, replaySeed } from "./cast.js";
import { cupDaysLeft } from "./cup.js";
import { deckMarkup, followKeyFor, offerOrbit, wireDeck } from "./deck.js";
import { colourLanes } from "./lanes.js";
import { MIN } from "./brightness.js";
import { formatEventFacts, isStage, isTug } from "./format.js";
import { roundCard } from "./roundcard.js";
import { dress, eventGuideHref, menuHref } from "./router.js";
import { footer, settleIdentity, signage } from "./signage.js";
import { renderTrainPanel } from "./trainpanel.js";
import { createViewer } from "./viewer.js";
import { voteButton } from "./votebutton.js";

// Colours belong to leaderboard entries; lane positions are shuffled afterwards.
export function arrangeLanes(board, lanes, random = Math.random) {
  colourLanes(board, lanes);
  for (let i = lanes.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [lanes[i], lanes[j]] = [lanes[j], lanes[i]];
  }
  return lanes;
}

/**
 * The event facts, and the caveat that belongs right under them.
 *
 * Split out from `renderRace` so it can be exercised without a WebGL viewer
 * or an API round-trip: give it a container with a `#facts` node and an
 * event, and check what lands in the DOM.
 *
 * The caveat is earned, not decorative: a policy tuned on a different course,
 * friction or physics build can score worse here without being worse, and
 * saying so plainly is the difference between a board people trust and one
 * they think is broken.
 */
export function renderEventFacts(root, event) {
  const facts = root.querySelector("#facts");
  for (const fact of formatEventFacts(event)) {
    const pair = document.createElement("div");
    const dt = document.createElement("dt");
    dt.textContent = fact.label;
    const dd = document.createElement("dd");
    dd.textContent = fact.value;
    pair.append(dt, dd);
    facts.append(pair);
  }

  const caveat = document.createElement("p");
  caveat.className = "racecaveat";
  caveat.textContent = isStage(event)
    ? "Performances play on this stage, with this friction and this physics build. A " +
      "policy tuned elsewhere can perform differently here."
    : isTug(event)
      ? "Ratings are measured in bouts against the reference duck, with this friction and this physics build. A " +
        "policy tuned elsewhere can pull less here without being weaker."
      : "Times are measured on this course, with this friction and this " +
        "physics build. A policy tuned elsewhere can do worse here without " +
        "being worse.";
  facts.after(caveat);
  return caveat;
}

/**
 * The way into the booth, when this event takes votes.
 *
 * At the top of the entry column, not beside the title -- "set apart and more
 * visible" was the owner's ask, and a button sharing a line with a heading
 * reads as a menu item, not a call to action. Its own function so the
 * placement is testable without a WebGL viewer or a leaderboard fetch: give
 * it a root with an `.entry-col` node and an event, and check what lands
 * first in it.
 */
export function renderVoteButton(root, event) {
  if (!event.vote) return;
  root.querySelector(".entry-col").prepend(voteButton(event));
}

/**
 * A versus event's days left before its cup, atop the entry column, above training: the date a player trains
 * for, and the way to the cup's page. Given the cups the page fetched, so the placement is testable without one.
 */
export function renderCupDaysLeft(root, event, cups, nowMs = Date.now()) {
  const { cup, left, href } = cupDaysLeft(event.id, cups, nowMs);
  const link = document.createElement("a");
  link.className = "cup-left";
  link.href = href;
  const name = document.createElement("span");
  name.className = "cup-left__cup";
  name.textContent = cup;
  const days = document.createElement("strong");
  days.className = "cup-left__days";
  days.textContent = left;
  link.append(name, days);
  root.querySelector(".entry-col").prepend(link);
}

/**
 * The page's frame, as a detached element.
 *
 * Its own function for the reason `renderVoteButton` is: everything below
 * needs a WebGL viewer and a leaderboard fetch, so the layout could only be
 * read as code rather than exercised as DOM. The structure matters — the
 * entry column starts level with the title because the title is INSIDE the
 * stage's column, and nothing but a test keeps it there.
 */
export function raceHall(event) {
  const hall = document.createElement("main");
  hall.className = "hall";
  hall.innerHTML = `
    <a class="raceback" href="${menuHref}">Back to the rounds</a>
    <div class="racegrid">
      <div>
        ${event.category ? `<p class="raceeyebrow">${event.category.toUpperCase()}</p>` : ""}
        <h2 class="racetitle">${event.title}</h2>
        <dl class="facts" id="facts"></dl>
        ${deckMarkup}
      </div>
      <div class="entry-col">
        <a class="help-link" href="${eventGuideHref(event.id)}">Training & rules ?</a>
      </div>
    </div>
    ${boardsheetMarkup}
    <p class="board-note" id="board-note" role="status"></p>
  `;
  return hall;
}


/**
 * The way on, under the board: every other round, as the same cards the
 * front page deals on its wall.
 *
 * All of them, wrapping onto a second row rather than a chosen four with a
 * button to the rest — with the whole programme already here, that button
 * would only send you to a page showing the same thing. The current event is
 * left out: a card back to the page you are already on is a dead end dressed
 * as a way forward.
 */
export function otherRounds(events, event, boards) {
  const others = events.filter((e) => e.id !== event.id);
  const strip = document.createElement("section");
  strip.className = "rounds-on";
  const head = document.createElement("div");
  head.className = "rounds-on__head";
  const titles = document.createElement("div");
  const eyebrow = document.createElement("p");
  eyebrow.className = "eyebrow";
  eyebrow.textContent = "Keep racing";
  const heading = document.createElement("h2");
  heading.className = "rounds-on__title";
  heading.textContent = "Watch the other rounds.";
  titles.append(eyebrow, heading);
  head.append(titles);
  const wall = document.createElement("div");
  wall.className = "round-cards";
  // Numbered by the whole programme, so a card keeps its number on every wall.
  wall.append(...others.map((e) => roundCard(e, boards.get(e.id) ?? [], { number: events.indexOf(e) + 1 })));
  strip.append(head, wall);
  return strip;
}

/**
 * Fill and hang the strip of other rounds, once the race above it is up.
 *
 * Separate from otherRounds so that the shape is testable without a network:
 * this is the part that fetches, and it asks for a leaderboard per card.
 */
export async function keepRacing(root, event) {
  const events = await getEvents();
  const others = events.filter((e) => e.id !== event.id);
  const boards = new Map();
  await Promise.all(others.map(async (e) => {
    boards.set(e.id, (await getLeaderboard(e.id).catch(() => ({ rows: [] }))).rows);
  }));
  const strip = otherRounds(events, event, boards);
  const foot = root.querySelector("footer");
  if (foot) foot.before(strip); else root.append(strip);
}

export async function renderRace(root, { event, state }) {
  // Started, not awaited. /api/me folds the whole run log for two numbers on
  // a chip; the stage, the entry column and the board's own fetch do not need
  // it, and waiting here meant the page drew nothing until it answered.
  const identity = getMe();
  // The sheet goes on with the first element, not on the way in: until
  // here the previous page is still on screen and keeps its own.
  dress("race");
  root.replaceChildren(signage(undefined));

  const hall = raceHall(event);
  root.append(hall, footer());

  // Only now, where the board needs to know whose rows are someone's own.
  const me = await identity;
  settleIdentity(root, me);

  // The strip of other rounds, after the page is up. It costs a leaderboard
  // per card and a WebGL still each; the race above is what the visitor came
  // for, and none of this may hold it up. Every failure leaves the strip off
  // rather than taking the page with it.
  keepRacing(root, event).catch((error) => {
    // Named, not swallowed. This was `catch(() => {})` and it hid a missing
    // import: the strip simply never appeared and nothing said why. A failure
    // here still must not take the page down, but it must be findable.
    console.error("The other-rounds strip did not load:", error);
  });
  renderVoteButton(root, event);
  renderTrainPanel(root, event);
  // Like the strip: the page does not wait for it, and a cup that does not answer leaves it off, named.
  if (event.category === "versus") {
    getCups(event.id)
      .then((cups) => renderCupDaysLeft(root, event, cups))
      .catch((error) => console.error("The cup's days left did not load:", error));
  }

  renderEventFacts(root, event);

  const board = root.querySelector("#board");

  const viewer = await createViewer(root.querySelector("#stage"), {
    // The event declares its rig, and the roller rig is a different kinematic
    // tree with its own blades, rims and tires — not a repaint of the walker.
    rig: event.rig,
    lights: Boolean(event.lights),
    camera: pageCamera(event),
    onChaseChange: followKeyFor(root),
  });
  state.viewer = viewer;
  wireDeck(root, viewer);
  offerOrbit(root, viewer);

  // No slider any more: the stage is pinned at the dimmest the module allows.
  // Worth knowing if this ever looks wrong — brightness.js says in its own
  // comment that the control exists because guessing the exposure from
  // outside cost three rounds. MIN is 0.5 against a 1.25 default.
  viewer.setBrightness(MIN);

  const traces = new Map();
  const liveries = new Map(); // run id -> the colourway it raced in
  const names = new Map(); // run id -> whose run it is, for the plate over its duck
  const casts = new Map(); // run id -> every duck it put on the stage (cast.js)
  const seeds = new Map(); // run id -> the seed its bout replays, which says the entry's end of the string

  // A lights event: the seed every lane plays, the board's leader's, read again with the board.
  let replayed;

  async function traceFor(runId, seed) {
    const key = `${runId}:${seed}`;
    if (!traces.has(key)) traces.set(key, await getTrace(runId, seed));
    return traces.get(key);
  }

  // A rated run's string beside its ducks: the page plays no settle, so its timed frames only.
  const strings = new Map();
  async function stringFor(runId) {
    if (!strings.has(runId)) strings.set(runId, { trace: (await getString(runId)).trace });
    return strings.get(runId);
  }

  async function race(runIds, tiers = new Map()) {
    const [published, strung] = await Promise.all([
      Promise.all(runIds.map((runId) => traceFor(runId, replayed))),
      Promise.all(isTug(event) ? runIds.map(stringFor) : []),
    ]);
    const lanes = runIds.map((runId, i) => replayLane(event, casts.get(runId), published[i], {
      runId,
      tier: tiers.get(runId) ?? "ghost",
      // A published run keeps the colourway it raced in.
      livery: liveries.get(runId) ?? "classic",
      // The plate over the duck: the viewer builds one for a lane with a name.
      name: names.get(runId),
      traceSeed: replayed ?? seeds.get(runId),
    }, strung[i]));
    // A performance plays alone on the stage, a rated run alone against the reference duck.
    const solo = isStage(event) || isTug(event);
    viewer.setLanes(arrangeLanes(board, solo ? lanes.slice(0, 1) : lanes), event);
  }

  // The sheet keeps the lanes and the filters; the page races what is ticked.
  const sheet = wireBoardsheet(hall, {
    event,
    me: me?.user ?? null,
    rows: async () => {
      const { rows } = await getLeaderboard(event.id);
      replayed = replaySeed(event, rows[0]);
      for (const row of rows) {
        liveries.set(row.run_id, row.livery ?? "classic");
        names.set(row.run_id, row.user);
        casts.set(row.run_id, row.cast);
        seeds.set(row.run_id, row.trace_seed);
      }
      return rows;
    },
    opening: podium,
    onRace: race,
    onWithdraw: async (runId, policy) => {
      // Asked before doing, because it is someone's standing and the button
      // sits on every row they own. `confirm` rather than a bespoke dialog:
      // this is a rare, deliberate action, not a flow worth building UI for.
      if (!window.confirm(`Take "${policy}" off the board? The policy stays in your Hub repo.`)) {
        return;
      }
      try {
        hall.querySelector("#board-note").textContent = "";
        await withdrawRun(runId);
        await sheet.paint();
      } catch (error) {
        hall.querySelector("#board-note").textContent = error.message;
      }
    },
  });

  await sheet.paint();
}
