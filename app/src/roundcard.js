// One event as a trading card: its number in the programme, what kind of
// event it is, its name over its illustration, its course in three cells, who
// holds it, and the button in.
//
// Its own module because three views deal it — the front page's wall, the
// strip of other rounds under a race, and the workshop's wall. A race page
// importing a page to get at one component is how a view ends up dragging a
// whole other view's imports behind it.

import { formatRate, formatScore, isTug } from "./format.js";
import { raceHref, voteHref } from "./router.js";
import { symbol } from "./symbols.js";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/** What a manifest does not say about its card: the colour it wears, the word
 * on its button, and a shorter name where the event's own would not hold one
 * line. An event missing here still deals, in paper with a plain "Go!". */
const CARDS = {
  "sprint-2m": { accent: "var(--yellow)", cta: "Let's go!" },
  "got-a-talent": { accent: "var(--lavender)", cta: "Vote", title: "Got a Talent" },
  "roller-sprint-2m": { accent: "var(--orange)", cta: "Let's roll!" },
  "hill-climb-1m5": { accent: "var(--cyan)", cta: "Climb!" },
  "tug-of-war": { accent: "var(--lime)", cta: "Pull!" },
  "sock-heist-6m": { accent: "var(--magenta)", cta: "Sneak in!", title: "Sock Heist" },
};
const PLAIN = { accent: "var(--paper)", cta: "Go!" };

const CATEGORY_SYMBOLS = { race: "sports_score", showcase: "how_to_vote", versus: "emoji_events" };

const compact = new Intl.NumberFormat("en", { notation: "compact" });

function stat(name, label) {
  const cell = el("div", "round-card__stat");
  cell.append(symbol(name), el("span", null, label));
  return cell;
}

/** The course in three cells; on a voted event, the week's votes in one. A
 * voted event with no rows (the workshop's wall) has nothing to count. */
function stats(event, rows) {
  const box = el("div", "round-card__stats");
  if (event.vote) {
    if (rows === null) return null;
    const cell = stat("bar_chart", "Votes");
    cell.classList.add("round-card__stat--wide");
    const total = rows.reduce((sum, row) => sum + (row.votes || 0), 0);
    cell.append(el("b", null, compact.format(total)));
    box.append(cell);
    return box;
  }
  const rig = event.rig === "rollers" ? stat("roller_skating", "Rollers") : stat("directions_walk", "Legs");
  if (isTug(event)) {
    box.append(stat("straighten", `${event.pit_m} m pit`), stat("sports_score", `${event.bout.time_limit_s} s bouts`), rig);
    return box;
  }
  box.append(
    stat("straighten", `${event.length_m} m`),
    event.slope_deg ? stat("signal_cellular_0_bar", `${event.slope_deg}°`) : stat("texture", "Flat"),
    rig,
  );
  return box;
}

/** Who holds this event, on one line under the cells. */
function leaderLine(event, rows) {
  const line = el("p", "round-card__score");
  line.append(symbol("emoji_events"));
  const leader = rows.find((row) => row.seeds_finished > 0);
  if (!leader) {
    line.append(el("b", null, rows.length ? "no finisher yet" : "be the first"));
    return line;
  }
  // A voted event is held by whoever wins its ballots most often THIS WEEK, so
  // the line says that rating. A time would be the wrong fact about it.
  const held = event.vote
    ? (leader.votes ? `rated ${formatRate(leader.rate)}` : "no votes yet")
    : formatScore(leader.score, { finished: leader.seeds_finished, metric: event.metric });
  line.append(el("b", null, held), el("i", "round-card__holder", `@${leader.user}`));
  return line;
}

/** The pointer tilts the card toward itself and drags the sheen along. The
 * sheet only reads these under no-preference, so reduced motion keeps a flat
 * card whatever is written here. */
function follow(card) {
  card.addEventListener("pointermove", (e) => {
    const box = card.getBoundingClientRect();
    const x = (e.clientX - box.left) / box.width;
    const y = (e.clientY - box.top) / box.height;
    card.style.setProperty("--mx", `${x * 100}%`);
    card.style.setProperty("--my", `${y * 100}%`);
    card.style.setProperty("--ry", `${(x - 0.5) * 14}deg`);
    card.style.setProperty("--rx", `${(0.5 - y) * 14}deg`);
  });
  card.addEventListener("pointerleave", () => {
    for (const name of ["--mx", "--my", "--rx", "--ry"]) card.style.removeProperty(name);
  });
}

/**
 * One event on the wall, dealt as card `number` of the programme.
 *
 * The title is the link and covers the whole card, so every part of it leads
 * to the event. A voted event's button is a link of its own on top, into the
 * booth: the card is the event, its button is the vote.
 *
 * The workshop deals the same card: there `rows` is null (the card is about
 * training, not results: no leader line), `href` leads to the challenge's
 * workshop page, `cta` is its own word on a plain button, and `corner` is
 * what it pins in the top corner (null: nothing).
 */
export function roundCard(event, rows, { number, href = raceHref(event.id), corner = null, cta } = {}) {
  const look = CARDS[event.id] ?? PLAIN;
  const card = el("article", "round-card");
  card.style.setProperty("--c", look.accent);

  const head = el("div", "round-card__head");
  head.append(el("span", "round-card__num", `#${String(number).padStart(2, "0")}`));
  const kind = CATEGORY_SYMBOLS[event.category];
  // An unrecognised category says nothing rather than borrowing another's
  // word: one malformed manifest must not take the wall down or lie on it.
  if (kind) {
    const icon = el("span", "round-card__ico");
    icon.append(symbol(kind));
    head.append(el("span", "round-card__cat", event.category), icon);
  }

  const link = el("a", "round-card__link");
  link.href = href;
  link.append(el("h4", "round-card__title", look.title ?? event.title));

  const art = el("div", "round-card__art");
  const img = el("img");
  img.src = `/cards/${event.id}.webp`;
  img.alt = "";
  art.append(img);

  const ballot = event.vote && !cta;
  const go = el(ballot ? "a" : "span", "round-card__cta");
  if (ballot) go.href = voteHref(event.id);
  go.append(el("span", null, cta ?? look.cta), symbol("arrow_forward"));

  const frame = el("div", "round-card__frame");
  frame.append(head, link, art);
  const course = stats(event, rows);
  if (course) frame.append(course);
  if (rows !== null) frame.append(leaderLine(event, rows));
  frame.append(go);

  card.append(frame);
  if (corner) card.append(corner);
  card.append(el("span", "round-card__holo"));
  follow(card);
  return card;
}
