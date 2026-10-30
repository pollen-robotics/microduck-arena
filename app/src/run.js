// One publication: the replay of the run against the ducks ranked just under
// it, the time it set, where it stands on the event's board, what it earned.
//
// Two modes. Plain shows all of it at once and loops the replay. Reveal — the
// author's first look — hides the result and plays it in beats (reveal.js).

import { getClip, getMe, getRun, getString, getTrace, markSeen } from "./api.js";
import { flipTiles } from "./animation.js";
import { boardsheetMarkup, wireBoardsheet } from "./boardsheet.js";
import { featured, pageCamera, replayLane, replaySeed } from "./cast.js";
import { deckMarkup, followKeyFor, offerOrbit, wireDeck } from "./deck.js";
import { formatSpeed, isStage, isTug } from "./format.js";
import { colourLanes, lanesFor } from "./lanes.js";
import { onDuckPanel, onWheels, popFrom } from "./onduck.js";
import { climbPlan, reveal, revealFor, setRanks } from "./reveal.js";
import { dress, guideHref, playerHref, raceHref } from "./router.js";
import { shareStrip, wireShare } from "./share.js";
import { footer, signage } from "./signage.js";
import { load as loadSounds } from "./sound.js";
import { BOUT_WORDS, SIDES, entrySide } from "./tug.js";
import { createViewer } from "./viewer.js";

// The colour each kind of receipt wears on its edge.
const TONES = {
  first_event: "receipt-lime",
  run: "receipt-cyan",
  own_best: "receipt-lavender",
  podium: "receipt-magenta",
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/** Which seed the stored replay is, and why that one; a performance is played once, a rated
 * tug run replays the bout whose ground is its median. */
export function replayLine(run) {
  if (isStage(run.event)) return "replay: the whole performance";
  if (isTug(run.event)) return `replay: seed ${run.trace_seed}, the median bout`;
  const finishers = run.per_seed.filter((s) => s.status === "finish").length;
  const which =
    finishers > 1 ? "median finisher" : finishers === 1 ? "the one finisher" : "first seed";
  return `${formatSpeed(run.command_vx, { finished: run.seeds_finished })} m/s · replay: seed ${run.trace_seed}, ${which}`;
}

/** What the scoreboard says over its number, and the stamp it lands. A stage has no time and no
 * finish: its number is the performance's length, and it was performed or cut short. A tug run's
 * number is its rating, in centimetres won from the reference duck. */
export function verdict(run) {
  const dnf = run.seeds_finished === 0;
  if (isStage(run.event)) return { label: "length", stamp: dnf ? "CUT SHORT" : "PERFORMED" };
  if (isTug(run.event)) return { label: "rating · cm", stamp: "RATED" };
  return { label: "time", stamp: dnf ? "DNF" : `FINISHED ${run.seeds_finished}/${run.seeds_total}` };
}

/**
 * The number the scoreboard flips: a tug's rating to the tenth of a centimetre (the label says
 * the unit), a time to the millisecond, or DNF. Veiled, zeros of the number's own shape whatever
 * the run did: a DNF's three tiles beside a time's six would give the verdict away before the stamp.
 */
export function flipScore(run, { veiled = false } = {}) {
  const tug = isTug(run.event);
  if (veiled) return tug ? "00.0" : "00.000";
  if (run.seeds_finished === 0) return "DNF";
  return run.score.toFixed(tug ? 1 : 3);
}

/** One seed's line: in a tug the ground the bout won, the entry's side and how it ended; in a race
 * its time, or how it ended. */
export function seedText(seed) {
  if (seed.score_cm != null) {
    return `${seed.score_cm >= 0 ? "+" : ""}${seed.score_cm.toFixed(1)} cm · ${SIDES[entrySide(seed.seed)]} · ${BOUT_WORDS[seed.status]}`;
  }
  return seed.time_s == null ? seed.status : `${seed.time_s.toFixed(3)}s`;
}

/**
 * One receipt: a banknote, the denomination at one end and what it paid for
 * across the face. A note and not a sticker — a sticker is something you
 * press, and these do nothing. "first entry" names no event: the page's
 * title already does, and with it the three notes no longer fit on one row
 * of the column.
 */
export function receiptCard(receipt) {
  const what = {
    first_event: "first entry",
    run: "run",
    own_best: "personal best",
    podium: "podium · held",
  }[receipt.act];
  const card = el("span", `receipt ${TONES[receipt.act]}`);
  card.append(el("strong", "receipt-points", `+${receipt.points}`), el("span", "mono-label", what));
  return card;
}

/**
 * The policies a troupe borrowed, each credited to its author and linked to its repo at the commit
 * that performed: they earn nothing from it, but they are named. Null when every duck is the
 * author's own.
 */
export function featuring(cast) {
  const policies = featured(cast);
  if (!policies.length) return null;
  const line = el("span", null, "featuring ");
  policies.forEach((policy, i) => {
    const link = el("a", null, `@${policy.user} · ${policy.policy_name}`);
    link.href = `https://huggingface.co/${policy.repo_id}/tree/${policy.revision}`;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    if (i) line.append(", ");
    line.append(link);
  });
  return line;
}

/**
 * The page's frame, as a detached element — DOM a test can exercise rather
 * than code it can only read, as raceHall is.
 *
 * Four rows, and only the stage gives: the page is exactly one window tall,
 * so everything the reveal animates is on screen at once. race.css does the
 * arithmetic; this is the order. The stage is the challenge page's deck and
 * the board its sheet, so a row ticked here means what it means there.
 */
export function runHall() {
  const page = el("main", "hall run");
  page.innerHTML = `
    <header class="run-head">
      <p class="eyebrow">Publication</p>
      <h2 class="racetitle"><a id="title"></a></h2>
      <p class="run-byline mono-label" id="byline"></p>
    </header>
    <div class="run-top">
      ${deckMarkup}
      <section class="run-score">
        <div class="scoreboard" id="scoreboard">
          <span class="mono-label" id="score-label">time</span>
          <div class="flip" id="flip"></div>
          <span class="stamp" id="stamp"></span>
        </div>
        <section class="run-receipts" id="points"></section>
      </section>
      <p class="mono-label run-facts" id="facts"></p>
    </div>
    <section class="run-board">${boardsheetMarkup}</section>
    <details class="run-seedlist" id="seedlist">
      <summary class="eyebrow">Seeds</summary>
      <ol id="seeds"></ol>
    </details>
  `;
  return page;
}

export async function renderRun(root, runId, state) {
  // Both are needed before anything can be drawn: whether the reveal plays at
  // all is a fact about this run AND about who is looking at it.
  const [run, me] = await Promise.all([getRun(runId), getMe()]);
  // The sheet goes on with the first element, not on the way in: until here
  // the previous page is still on screen and keeps its own.
  dress("run");
  root.replaceChildren(signage(me));
  const revealing = revealFor(run, me, matchMedia("(prefers-reduced-motion: reduce)").matches);
  const earned = run.receipts.reduce((sum, r) => sum + r.points, 0);
  const plan = climbPlan(run.board);
  const dnf = run.seeds_finished === 0;

  const page = runHall();
  // Which beat the page is in. Read by nothing yet: it is the hook a screenshot
  // or a test waits on. A reveal's first beat waits on the stage.
  page.dataset.act = revealing ? "load" : "rest";
  root.append(page, footer());
  const $ = (id) => page.querySelector(`#${id}`);

  // The title is the way back to the event, which is why the page carries no
  // back link of its own.
  $("title").textContent = run.event.title;
  $("title").href = raceHref(run.event.id);
  const who = el("a", null, `@${run.user}`);
  who.href = playerHref(run.user);
  $("byline").append(who, ` · ${run.policy_name}`);
  const credits = featuring(run.cast);
  if (credits) $("byline").append(" · ", credits);
  $("byline").append(` · ${run.submitted_at.slice(0, 10)}`);
  const scoringHelp = el("a", null, "How points work");
  scoringHelp.href = guideHref("points");
  $("byline").append(" · ", scoringHelp);
  if (run.withdrawn) $("byline").append(" · ", el("span", "sticker sticker-magenta", "withdrawn"));
  else if (!run.on_board) $("byline").append(" · ", el("span", "sticker", "not on the board"));
  // What you can take away sits with who made it: one line, no section of its own.
  if (run.offers_download) {
    const grab = el("a", null, "Download .onnx");
    grab.href = run.policy_url || `/api/runs/${run.run_id}/policy`;
    grab.setAttribute("download", "");
    $("byline").append(" · ", grab);
  }
  if (run.robot_command) {
    const open = el("button", "onduck-open", "Run it on my microduck");
    open.type = "button";
    const panel = onDuckPanel({ command: run.robot_command, wheels: onWheels(run.cast, run.event), event: run.event });
    popFrom(open, panel);
    $("byline").append(" · ", open);
    page.append(panel);
  }
  if (run.env_url) {
    const env = el("a", null, "Training environment");
    env.href = run.env_url;
    env.target = "_blank";
    env.rel = "noopener noreferrer";
    $("byline").append(" · ", env);
  }

  // `rollCounter` rolls each tile to the digit it already shows, so the number
  // is in the DOM before any theatre. A reveal starts on constant zeros
  // instead (flipScore), and the time beat swaps the real number in. The tile
  // count changes with it, but a width in this column costs no height.
  const score = flipScore(run);
  $("flip").append(...flipTiles(flipScore(run, { veiled: revealing })));
  const said = verdict(run);
  $("score-label").textContent = said.label;
  const stamp = $("stamp");
  stamp.textContent = said.stamp;
  stamp.classList.add(dnf ? "stamp-fail" : "stamp-pass");
  stamp.classList.toggle("veiled", revealing);
  // "median finisher" says the run finished, so the caption waits for the stamp.
  // Veiled, not hidden: on a page of fixed height a box that leaves the flow
  // hands its height to the stage, and the picture jumps mid-beat.
  $("facts").textContent = replayLine(run);
  $("facts").classList.toggle("veiled", revealing);

  const cards = run.receipts.map(receiptCard);
  for (const card of cards) card.classList.toggle("veiled", revealing);
  $("points").append(...cards);
  if (!cards.length) $("points").append(el("p", "mono-label", "no points from this run"));

  // Sharing, under the points: the networks on one row, the clips on the
  // next, standing there from the first frame and veiled through a reveal like
  // everything else in this column; the clip stickers follow the render while
  // it is owed.
  const strip = shareStrip(run, { origin: location.origin });
  strip.root.classList.toggle("veiled", revealing);
  $("points").after(strip.root);
  wireShare(strip, run, { origin: location.origin });
  // Queued is the honest first state: nobody has answered for the clip yet, so
  // the row wears the face of a render nobody has started — present, disabled
  // and turning — not a live-looking link that goes stale a beat later.
  strip.setClip({ state: "queued", ahead: null });
  const leaving = new AbortController();
  let timer = null;
  async function followClip() {
    const clip = await getClip(run.run_id).catch(() => null);
    if (leaving.signal.aborted) return;
    if (clip) strip.setClip(clip);
    // A render moves frame by frame and is worth watching closely; a queue only
    // moves when something ahead of it finishes, which is minutes away. Ready,
    // failed and none are final — nothing to come back for.
    const again = clip ? { rendering: 2000, queued: 5000 }[clip.state] : 5000;
    if (again) timer = setTimeout(followClip, again);
  }
  followClip();

  // One line per seed: the time or the pull, or how it ended. Folded away by
  // default — it is a detail you go and look up, not a step of the show. A
  // performance is played once: there is no seed list to open.
  if (isStage(run.event)) {
    $("seedlist").remove();
  } else {
    for (const s of run.per_seed) {
      const row = el("li", s.seed === run.trace_seed ? "seed replayed" : "seed");
      row.append(
        el("span", "mono-label", `seed ${s.seed}`),
        el("strong", null, seedText(s)),
      );
      $("seeds").append(row);
    }
  }

  // The reveal's lifetime opens before the loads it must survive leaving
  // during: a first visit's GLB fetch and the trace downloads are both slow
  // enough that navigating away mid-load must not fall through to the
  // theatre and spend the one-shot reveal on a page nobody watched.
  let theatre, lifetime;
  if (revealing) {
    theatre = new AbortController();
    lifetime = new AbortController();
  }
  state.teardown = () => {
    leaving.abort();
    clearTimeout(timer);
    lifetime?.abort();
    theatre?.abort("leave");
  };

  // The board under the picture: the event's whole field as this run sees it,
  // on the challenge page's sheet, opening on this run and the three ranked
  // under it. Any row can go on the stage or come off it, and the colours
  // follow the table, as they do there. Drawn now; raced once the stage is up,
  // which on a first visit is a model download away.
  const byId = new Map(run.board.map((row) => [row.run_id, row]));
  const traces = new Map();
  const replayed = replaySeed(run.event, run); // a lights event: every lane plays this run's own trace seed
  const traceFor = async (id) => {
    if (!traces.has(id)) traces.set(id, await getTrace(id, replayed));
    return traces.get(id);
  };
  // A rated run's string beside its ducks: the page plays no settle, so its timed frames only.
  const strings = new Map();
  const stringFor = async (id) => {
    if (!strings.has(id)) strings.set(id, { trace: (await getString(id)).trace });
    return strings.get(id);
  };
  let viewer = null;
  let parked = null;
  async function race(runIds, tiers) {
    if (!viewer) {
      parked = [runIds, tiers];
      return;
    }
    const [fetched, strung] = await Promise.all([
      Promise.all(runIds.map(traceFor)),
      Promise.all(isTug(run.event) ? runIds.map(stringFor) : []),
    ]);
    if (leaving.signal.aborted) return;
    const lanes = runIds.map((id, i) => replayLane(run.event, byId.get(id).cast, fetched[i], {
      runId: id,
      tier: tiers.get(id) ?? "ghost",
      livery: byId.get(id).livery,
      // The plate over the duck.
      name: byId.get(id).user,
      // The seed its bout replays, which says which end of the string the entry holds.
      traceSeed: replayed ?? byId.get(id).trace_seed,
    }, strung[i]));
    viewer.setLanes(colourLanes($("board"), lanes), run.event);
  }
  const sheet = wireBoardsheet(page, {
    event: run.event,
    me: me?.user ?? null,
    rows: () => run.board,
    opening: (rows) => lanesFor({ board: rows, event: run.event }).map((row) => row.run_id),
    onRace: race,
    // Everything: the row this page is about has to be on the table, whatever
    // its rank.
    filters: { mine: false, top: false },
  });
  await sheet.paint();

  // The rows by run: what the reveal renumbers, reorders and climbs. This
  // run's own is in lime, and in view — a few rows show, the rest scroll.
  const tbody = $("board").querySelector("tbody");
  const pegRows = new Map(
    [...tbody.rows].map((row) => [row.querySelector("input[data-run-id]").dataset.runId, row]),
  );
  const yourRow = pegRows.get(run.run_id);
  yourRow.classList.add("you");
  const showYourRow = () => {
    const box = $("board");
    box.scrollTop = yourRow.offsetTop - (box.clientHeight - yourRow.offsetHeight) / 2;
  };
  // Your own time only goes up on the board once the split-flap has rolled it.
  // A voted table has no `.time` cell.
  const yourScore = yourRow.querySelector(".time, .rate");
  yourScore.classList.toggle("veiled", revealing);
  if (revealing) {
    // The board as it was before this run — you at the bottom, the rows under
    // you a place higher — until the climb. Held still until the theatre ends:
    // a filter redraws the table, and the climb moves these very rows.
    setRanks(pegRows, plan.start);
    tbody.replaceChildren(...plan.start.map((row) => pegRows.get(row.run_id)));
    sheet.setInert(true);
  }
  showYourRow();

  // The stage.
  const created = await createViewer($("stage"), {
    rig: run.event.rig,
    lights: Boolean(run.event.lights),
    camera: pageCamera(run.event),
    onChaseChange: followKeyFor(page),
    hushed: () => !strip.player.paused,
  });
  if (leaving.signal.aborted) {
    created.dispose();
    return;
  }
  state.viewer = created;
  viewer = created;
  wireDeck(page, viewer);
  await race(...parked);
  if (leaving.signal.aborted) return;
  if (!revealing) {
    offerOrbit(page, viewer);
    // No theatre — but the author has still seen their result.
    if (me?.user === run.user && !run.seen) {
      markSeen(run.run_id).catch(() => {});
      if (me.unseen <= 1) root.querySelector(".profile-chip")?.classList.remove("unread");
    }
    return;
  }
  // The chip stays on screen so the stars have somewhere to fly to.
  root.querySelector(".signage").classList.add("signage--pinned");
  const startPoints = me.points - earned;

  // The reveal. The chip starts at the total BEFORE this run, since /api/me
  // already counts it; Space skips; leaving the page abandons without marking.
  loadSounds();
  const chip = root.querySelector(".profile-chip");
  const chipFlip = chip.querySelector(".flip");
  chipFlip.replaceChildren(...flipTiles(startPoints));
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.code !== "Space" || event.target.closest("button, a, input, select, textarea")) {
        return;
      }
      event.preventDefault();
      theatre.abort("skip");
    },
    { signal: lifetime.signal },
  );
  await reveal(
    {
      page,
      chip,
      chipFlip,
      facts: $("facts"),
      scoreboard: $("scoreboard"),
      stamp,
      flip: $("flip"),
      yourScore,
      pegboard: tbody,
      pegRows,
      cards,
      share: strip.root,
    },
    {
      run,
      plan,
      receipts: run.receipts,
      startPoints,
      score,
      onSeen: () => {
        markSeen(run.run_id).catch(() => {});
        if (me.unseen <= 1) chip.classList.remove("unread");
        sheet.setInert(false);
        showYourRow();
      },
    },
    theatre.signal,
  );
  // The theatre is over: Space should scroll the page again, not skip it.
  lifetime.abort();
  // The hint never plays over the theatre: it would draw the eye off the result.
  offerOrbit(page, viewer);
}
