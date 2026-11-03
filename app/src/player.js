// One player: their picture and name, what their publications earned, where
// they stand, and every run they published, newest first.

import { getMe, getPlayer } from "./api.js";
import { capitalised, formatRate, formatScore } from "./format.js";
import { cupHref, dress, guideHref, menuHref, raceHref, runHref } from "./router.js";
import { avatar, chequer, footer, settleIdentity, signOutButton, signage } from "./signage.js";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/**
 * A publication's rank counts only if it is still ON the board.
 *
 * A withdrawn run keeps the rank it had when it was pulled, and an entry that
 * never placed carries none. Neither is a standing, and either would make a
 * player look better on their own page than on the board everyone else reads.
 */
function placed(pub) {
  return !pub.withdrawn && pub.on_board && pub.rank != null;
}

/**
 * The publications gathered per event, best first.
 *
 * Pure, and exported, because the ordering is the part worth pinning: groups
 * are sorted by the player's BEST standing in each — what they are good at
 * reads before what they merely tried — and an event where nothing placed
 * sorts last rather than first, which is what a null rank does if it is
 * compared as a number. Ties go to the most recent publication.
 *
 * Within a group the API's own order is kept: newest first.
 */
export function byEvent(publications) {
  const groups = new Map();
  for (const pub of publications) {
    const group = groups.get(pub.event_id) ?? {
      eventId: pub.event_id,
      title: pub.event_title,
      best: null,
      votes: null,
      newest: pub.submitted_at,
      publications: [],
    };
    group.publications.push(pub);
    if (pub.submitted_at > group.newest) group.newest = pub.submitted_at;
    if (placed(pub) && (group.best == null || pub.rank < group.best)) {
      group.best = pub.rank;
      // Carried so the summary can say what the rank was earned by: a voted
      // event ranks on votes, and "#1" beside a time would name the wrong one.
      group.votes = pub.votes;
    }
    groups.set(pub.event_id, group);
  }
  return [...groups.values()].sort((a, b) => {
    if (a.best !== b.best) {
      if (a.best == null) return 1;
      if (b.best == null) return -1;
      return a.best - b.best;
    }
    return a.newest < b.newest ? 1 : -1;
  });
}

export function profile(player, me = null) {
  const box = el("div", "profile");

  const header = el("header", "profile-header");
  const duck = el("span", "profile-duck");
  duck.append(avatar(player.user));
  const words = el("div");
  words.append(el("p", "eyebrow", "Player"), el("h2", "marquee-title", player.user));
  header.append(duck, words);

  // Top right of the header, not under it: they are the two figures a reader
  // comes to this page for, and a line of their own pushed them below the
  // name that is only their label.
  const summary = el("div", "profile-summary");
  summary.append(
    el("span", "sticker", `✦ ${player.points} points`),
    el("span", "sticker sticker-orange", player.rank == null ? "#—" : `#${player.rank}`),
  );
  const pointsHelp = el("a", "help-link", "How points work ?");
  pointsHelp.href = guideHref("points");
  summary.append(pointsHelp);
  // On your own page only, and only where OAuth is what signed you in. It is
  // the page about you; a strip every visitor sees is not the place to offer
  // to sign someone out.
  if (me?.user === player.user) {
    const out = signOutButton(me);
    if (out) summary.append(out);
  }
  header.append(summary);

  // One fold per event, best standing first. The event's name and where this
  // player stands on it are on the outside; the policies are behind the fold,
  // because a page listing thirty runs flat says nothing about any of them.
  const rounds = el("div", "profile-rounds");
  for (const group of byEvent(player.publications)) {
    const fold = document.createElement("details");
    fold.className = "profile-round";
    const head = document.createElement("summary");
    const go = el("a", "profile-round__go fx-shadow-sticker", "Go to the round");
    go.href = raceHref(group.eventId);
    // A summary IS the toggle, so a click anywhere in it opens the fold. This
    // one has to leave instead, and the two must not both happen.
    go.addEventListener("click", (event) => event.stopPropagation());
    head.append(
      el("span", "profile-round__name", group.title),
      el("span", "profile-round__place", group.best == null ? "unplaced" : `#${group.best}`),
      el("span", "profile-round__count",
        group.publications.length === 1 ? "1 policy" : `${group.publications.length} policies`),
      go,
    );
    fold.append(head, results(group.publications, player, me));
    rounds.append(fold);
  }

  box.append(header, el("h3", "eyebrow", "Rounds entered"), rounds);
  if (player.cups?.length) box.append(el("h3", "eyebrow", "Cups"), cupList(player.cups));
  return box;
}

const REACHED = {
  champion: "Champion",
  final: "Finalist",
  "semi-final": "Semi-finalist",
  "quarter-final": "Quarter-finalist",
  group: "Group stage",
};

/** How far a cup went for a player, from the API's `reached`: a knockout round "round of 16" is the round they went out in. */
export const reachedLabel = (reached) => REACHED[reached] ?? capitalised(reached);

/** The cups a player played, each the way to its page. */
function cupList(cups) {
  const list = el("ul", "profile-results profile-cups");
  for (const cup of cups) {
    const link = el("a");
    link.href = cupHref(cup.event_id, cup.number);
    link.append(
      el("strong", null, `${cup.event_title} Cup #${cup.number}`),
      el("span", "mono-label", reachedLabel(cup.reached)),
      el("span", "profile-date", cup.starts_at.slice(0, 10)),
    );
    const item = el("li");
    item.append(link);
    list.append(item);
  }
  return list;
}

/** A publication's name, and why it holds no row when it was withdrawn or races like someone else's run. */
function note(pub) {
  if (pub.withdrawn) return `${pub.policy_name} · withdrawn`;
  return pub.copy_of ? `${pub.policy_name} · copy of @${pub.copy_of.user}` : pub.policy_name;
}

/** One event's publications, newest first, each the way to its own page. */
function results(publications, player, me) {
  const list = el("ul", "profile-results");
  for (const pub of publications) {
    const item = el("li");
    const link = el("a", pub.withdrawn ? "withdrawn" : null);
    link.href = runHref(pub.run_id);
    // The dot is the owner's alone: it says a result of THEIRS waits to be
    // opened.
    if (me?.user === player.user && !pub.seen) link.classList.add("unread");
    // A voted event's rank is earned by its rating, not by time — "#1 · 18.46s"
    // beside a MicroDuck Got a Talent entry would read as a finish time that placed it,
    // when the finish time never ranked anything there.
    const earned = pub.votes != null
      ? (pub.votes ? `rated ${formatRate(pub.rate)}` : "no votes yet")
      : formatScore(pub.score, { finished: pub.seeds_finished, metric: pub.metric });
    link.append(
      el("strong", null, `#${pub.rank ?? "—"} · ${earned}`),
      el("span", "mono-label", note(pub)),
      el("span", "profile-date", pub.submitted_at.slice(0, 10)),
    );
    item.append(link);
    list.append(item);
  }
  return list;
}

export function noProfile(user) {
  const box = el("div", "profile profile-empty");
  box.append(el("p", "eyebrow", "Player"), el("h2", "marquee-title", user));
  const line = el("p", "lede", `No publication yet. `);
  const back = el("a", null, "Pick a round");
  back.href = menuHref;
  line.append(back, " to put a time up.");
  box.append(line);
  return box;
}

export async function renderPlayer(root, user) {
  const identity = getMe();
  const player = await getPlayer(user);
  // The chequer straight under the strip, where the page begins.
  // The sheet goes on with the first element, not on the way in: until
  // here the previous page is still on screen and keeps its own.
  dress("player");
  root.replaceChildren(signage(undefined), chequer("page-checker"));
  const hall = el("main", "hall hall--warm");
  root.append(hall, footer());

  // The profile itself needs `me` — the way out and the unopened marks are
  // both about whether this page is yours — so it waits, but the strip, the
  // chequer and the page's own ground are up before it does.
  const me = await identity;
  settleIdentity(root, me);
  hall.append(player ? profile(player, me) : noProfile(user));
}
