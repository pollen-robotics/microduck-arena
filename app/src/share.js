// Sharing a run: the post, the two composers that take a text, the two
// networks that take uploads only, and the clip downloads. The row is
// markup: every link works with no script at all.

import { isStage, isTug } from "./format.js";

export const HASHTAG = "#MicroduckArena";
const MENTIONS = { x: "@pollenrobotics @huggingface" };
// The only two addresses that open a composer with a text in it.
const INTENTS = {
  x: (text) => `https://x.com/intent/post?text=${encodeURIComponent(text)}`,
  linkedin: (text) => `https://www.linkedin.com/feed/?shareActive=true&text=${encodeURIComponent(text)}`,
};
const NETWORKS = ["x", "linkedin"];
const UPLOADS = ["instagram", "tiktok"];
const LABELS = {
  x: "X", linkedin: "LinkedIn", instagram: "Instagram", tiktok: "TikTok", link: "Copy link",
};
const LAYOUTS = ["landscape", "vertical"];
/** The tilt magnitudes the stickers take in turn; the row alternates the sign. */
const TILTS = ["2-5", "1-5", "3-0", "1-0"];
/** What the recorder is doing, in the order it does it (arena/recorder.py). */
const STAGES = {
  opening: "Opening the stage",
  soundtrack: "Mixing the soundtrack",
  frames: "Photographing the arena",
};

/** The post, the same on every network but for the mentions X gets. */
export function postText(run, { origin, network }) {
  const total = run.seeds_total;
  const earned = run.receipts.reduce((sum, r) => sum + r.points, 0);
  const points = earned > 0 ? ` (+${earned} pts)` : "";
  const place = run.on_board && !run.withdrawn ? `, #${run.rank} on the board` : "";
  const stage = isStage(run.event);
  const tug = isTug(run.event);
  // A troupe is shared as the robot ducks it is.
  const troupe = stage && run.cast.length > 1;
  let result;
  if (stage) {
    result = run.seeds_finished === 0
      ? `${troupe ? "Their" : "Its"} performance on ${run.event.title} was cut short.`
      : `On ${run.event.title} ${troupe ? "they" : "it"} gave a ${run.score.toFixed(2)} s performance${points}.`;
  } else if (tug) {
    result = `On ${run.event.title} its rating is ${run.score.toFixed(1)} cm against the reference duck${place}${points}.`;
  } else if (run.seeds_finished === 0) {
    const fell = run.per_seed.some((s) => s.status === "fall");
    // Sock Heist ends a duck caught moving while the giant looks: standing, so no fall, and early, so no clock.
    const caught = run.per_seed.some((s) => s.status === "caught");
    const why = fell ? "it ate the floor" : caught ? "it got caught moving while the giant looked" : "it ran out of time";
    result = `On ${run.event.title} it finished 0/${total} seeds on its feet — ${why}.`;
  } else {
    result = `On ${run.event.title} it finished ${run.seeds_finished}/${total} seeds in ${run.score.toFixed(3)} s${place}${points}.`;
  }
  const lines = [
    `I coded ${troupe ? "robot ducks" : "a robot duck"} to ${stage ? "perform" : tug ? "pull" : "walk"}. ${result}`,
    `${troupe ? "Watch them" : stage ? "Watch it" : "Beat it"}: ${origin}/r/${run.run_id}`,
  ];
  if (run.policy_url) lines.push(`Weights: ${run.policy_url.replace(/^https?:\/\//, "")}`);
  lines.push([HASHTAG, MENTIONS[network]].filter(Boolean).join(" "));
  return lines.join("\n");
}

export const intentUrl = (network, text) => INTENTS[network](text);

// Each network's mark as one path on its own grid: a row of names all in the
// same sticker face reads as four words, and a player looking for their
// network recognises it. The name stays as the label a screen reader says.
const LOGOS = {
  x: "M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z",
  linkedin: "M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z",
  instagram: "M7.0301.084c-1.2768.0602-2.1487.264-2.911.5634-.7888.3075-1.4575.72-2.1228 1.3877-.6652.6677-1.075 1.3368-1.3802 2.127-.2954.7638-.4956 1.6365-.552 2.914-.0564 1.2775-.0689 1.6882-.0626 4.947.0062 3.2586.0206 3.6671.0825 4.9473.061 1.2765.264 2.1482.5635 2.9107.308.7889.72 1.4573 1.388 2.1228.6679.6655 1.3365 1.0743 2.1285 1.38.7632.2953 1.6361.4961 2.9134.552 1.2773.056 1.6884.069 4.9462.0627 3.2578-.0062 3.668-.0207 4.9478-.0814 1.28-.0607 2.1466-.2652 2.9095-.5633.7889-.3086 1.4578-.72 2.1228-1.3881.665-.6682 1.0745-1.3378 1.3795-2.1284.2957-.7632.4966-1.636.552-2.9124.056-1.2809.0692-1.6898.063-4.9476-.0063-3.2578-.021-3.6668-.0817-4.9466-.0607-1.2798-.264-2.1478-.5633-2.9109-.3084-.7889-.72-1.4568-1.3876-2.1228C21.2982 1.33 20.628.9208 19.8378.6165 19.074.321 18.2017.1197 16.9244.0645 15.6471.0093 15.236-.005 11.977.0014 8.718.0076 8.31.0215 7.0301.0839m.1402 21.6932c-1.17-.0509-1.8053-.2453-2.2287-.408-.5606-.216-.96-.4771-1.3819-.895-.422-.4178-.6811-.8186-.9-1.378-.1644-.4234-.3624-1.058-.4171-2.228-.0595-1.2645-.072-1.6442-.079-4.848-.007-3.2037.0053-3.583.0607-4.848.05-1.169.2456-1.805.408-2.2282.216-.5613.4762-.96.895-1.3816.4188-.4217.8184-.6814 1.3783-.9003.4231-.1651 1.5798-.3611 2.2283-.4171 1.2645-.06 1.6442-.072 4.848-.079 3.2037-.007 3.5834.005 4.849.0608 1.169.0508 1.8053.2445 2.2277.408.5608.216.96.4754 1.3816.895.4217.4194.6816.8176.9005 1.3787.1653.4217.3611 1.5783.4171 2.2273.0602 1.2645.0739 1.6446.0796 4.848.0058 3.2033-.0055 3.5836-.061 4.848-.051 1.17-.245 1.8055-.408 2.2294-.216.5604-.4763.96-.8954 1.3814-.419.4215-.8181.6811-1.3783.9-.4224.1649-1.5797.3613-2.2273.4174-1.2645.0592-1.6442.0719-4.8487.0788-3.2045.007-3.5832-.0066-4.848-.0602m9.6806-16.234a1.44 1.44 0 1 0 1.4373-1.4415 1.44 1.44 0 0 0-1.4373 1.4415M5.8385 12.012c.0067 3.4032 2.7706 6.1557 6.1732 6.1493 3.4026-.0065 6.1573-2.7701 6.1508-6.1733-.0065-3.4032-2.771-6.1565-6.1742-6.1499-3.4032.0067-6.1563 2.7708-6.1498 6.1739M8 12.0077a4 4 0 1 1 4.008 3.9921A4 4 0 0 1 8 12.0077",
  tiktok: "M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.07-.14 1.61.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z",
  link: "M3.9 12c0-1.71 1.39-3.1 3.1-3.1h4V7H7a5 5 0 0 0 0 10h4v-1.9H7c-1.71 0-3.1-1.39-3.1-3.1ZM8 13h8v-2H8Zm9-6h-4v1.9h4c1.71 0 3.1 1.39 3.1 3.1s-1.39 3.1-3.1 3.1h-4V17h4a5 5 0 0 0 0-10Z",
};

/** A film reel, for a clip being made. Turned by race.css, not by a timer. */
const REEL =
  '<svg class="clip-reel" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
  '<path d="M12 1.5a10.5 10.5 0 1 0 0 21 10.5 10.5 0 0 0 0-21Zm0 2.4a8.1 8.1 0 1 1 0 16.2 8.1 8.1 0 0 1 0-16.2Z"></path>' +
  '<circle cx="12" cy="12" r="2.2"></circle><circle cx="12" cy="6.7" r="1.9"></circle>' +
  '<circle cx="16.6" cy="14.7" r="1.9"></circle><circle cx="7.4" cy="14.7" r="1.9"></circle></svg>';

/**
 * What a clip's state says to someone waiting on it: the line, the detail
 * under it, and how far along it is — null where there is nothing honest to
 * measure, which a bar shows as sweeping rather than as zero.
 */
export function clipStatus(clip) {
  if (clip.state === "failed") {
    return { say: "The tape jammed", step: clip.reason || "no reason recorded", fraction: null };
  }
  if (clip.state === "queued") {
    const { ahead } = clip;
    if (ahead == null) return { say: "Waiting for the recorder", step: "", fraction: null };
    const say = ahead === 0 ? "Next on the recorder" : `${ahead} clip${ahead > 1 ? "s" : ""} ahead`;
    return { say, step: "", fraction: null };
  }
  const say = STAGES[clip.stage] || "Rendering";
  if (!clip.total) return { say, step: "", fraction: null };
  return { say, step: `${clip.done} / ${clip.total} frames`, fraction: clip.done / clip.total };
}

/** What a clip sticker reads while it cannot be pressed. */
function clipLabel(clip, layout) {
  if (clip.state === "ready") return `Clip · ${layout}`;
  if (clip.state === "failed") return "Clip · failed";
  if (clip.state === "queued") return "Clip · queued";
  const { fraction } = clipStatus(clip);
  return fraction === null ? "Clip · rendering…" : `Clip · ${Math.floor(fraction * 100)}%`;
}

const logo = (id) =>
  `<svg class="sticker-logo" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="${LOGOS[id]}"></path></svg>`;

function mark(tag, id, tilt) {
  const node = document.createElement(tag);
  node.className = `sticker sticker-mark fx-tilt-${tilt}`;
  node.setAttribute("aria-label", LABELS[id]);
  node.title = LABELS[id];
  node.innerHTML = logo(id);
  return node;
}

/**
 * Under the points: a row of the networks — X and LinkedIn as links, Instagram
 * and TikTok as buttons — then a row of one cyan sticker per clip, the line
 * that says what a press did, and a small player for the landscape clip, to
 * watch it here without downloading it. `setClip` takes the `/clip` body and
 * dresses the clip stickers and the player for its state.
 */
export function shareStrip(run, { origin }) {
  const root = document.createElement("section");
  root.className = "run-share";
  const nav = document.createElement("nav");
  nav.className = "run-share-networks fx-tilt-alternate";
  nav.setAttribute("aria-label", "Share this run");
  let i = 0;
  const tilt = () => TILTS[i++ % TILTS.length];
  for (const id of NETWORKS) {
    const link = mark("a", id, tilt());
    link.href = intentUrl(id, postText(run, { origin, network: id }));
    link.target = "_blank";
    link.rel = "noopener";
    link.dataset.network = id;
    nav.append(link);
  }
  for (const id of UPLOADS) {
    const button = mark("button", id, tilt());
    button.type = "button";
    button.dataset.upload = id;
    nav.append(button);
  }
  // The run's own address. `/r/<id>` is a page the server renders — Open Graph
  // tags and all — so the link is worth handing over on its own, not only
  // buried inside a post someone has to open a composer to read.
  const copy = mark("button", "link", tilt());
  copy.type = "button";
  copy.dataset.copy = "link";
  nav.append(copy);

  const clips = document.createElement("div");
  clips.className = "run-share-clips fx-tilt-alternate";
  for (const layout of LAYOUTS) {
    const sticker = document.createElement("a");
    sticker.className = `sticker sticker-cyan fx-tilt-${tilt()}`;
    sticker.dataset.clip = layout;
    sticker.innerHTML = `${REEL}<span class="sticker-say"></span>`;
    clips.append(sticker);
  }
  const said = document.createElement("p");
  said.className = "mono-label run-share-said";
  said.hidden = true;
  // The screen takes whatever room the column has left: race.css sizes it, and
  // drops it where there is too little. It holds two things at the same size —
  // the player, and the panel that stands in for it while the clip is made, so
  // a render is something you watch happen rather than a row that vanishes.
  const screen = document.createElement("div");
  screen.className = "run-share-screen";
  screen.hidden = true;
  const player = document.createElement("video");
  player.controls = true;
  // Nothing crosses the wire until a press: the poster stands in until then.
  player.preload = "none";
  player.playsInline = true;
  const panel = document.createElement("div");
  panel.className = "clip-render";
  panel.innerHTML =
    `${REEL}<p class="clip-render-say"></p>` +
    '<div class="clip-render-bar" role="progressbar" aria-valuemin="0" aria-valuemax="100">' +
    "<span></span></div><p class=\"mono-label clip-render-step\"></p>";
  screen.append(player, panel);
  root.append(nav, clips, said, screen);

  function setClip(clip) {
    const working = ["queued", "rendering"].includes(clip.state);
    for (const sticker of clips.querySelectorAll("[data-clip]")) {
      const layout = sticker.dataset.clip;
      // Only a run that owes no clip at all loses the row. A render in flight
      // and a render that jammed both have something to say.
      sticker.hidden = clip.state === "none";
      sticker.classList.toggle("sticker-working", working);
      sticker.querySelector(".sticker-say").textContent = clipLabel(clip, layout);
      if (clip.state === "ready") {
        sticker.href = `${clip.layouts[layout].url}?download=1`;
        sticker.setAttribute("download", "");
        sticker.removeAttribute("aria-disabled");
      } else {
        sticker.removeAttribute("href");
        sticker.removeAttribute("download");
        sticker.setAttribute("aria-disabled", "true");
      }
    }
    screen.hidden = clip.state === "none";
    player.hidden = clip.state !== "ready";
    panel.hidden = clip.state === "ready";
    if (clip.state === "ready") {
      player.poster = clip.poster;
      player.src = clip.layouts.landscape.url;
      return;
    }
    const { say, step, fraction } = clipStatus(clip);
    panel.querySelector(".clip-render-say").textContent = say;
    panel.querySelector(".clip-render-step").textContent = step;
    panel.classList.toggle("clip-render-jammed", clip.state === "failed");
    const bar = panel.querySelector(".clip-render-bar");
    bar.hidden = clip.state === "failed";
    bar.classList.toggle("clip-render-bar-unknown", fraction === null);
    if (fraction === null) {
      bar.firstElementChild.style.width = "";
      bar.removeAttribute("aria-valuenow");
    } else {
      bar.firstElementChild.style.width = `${(fraction * 100).toFixed(1)}%`;
      bar.setAttribute("aria-valuenow", String(Math.floor(fraction * 100)));
    }
  }
  return { root, said, player, setClip };
}

/**
 * The presses a link cannot make. Instagram and TikTok have no composer: on a
 * phone the system sheet reaches their apps with the post in hand; on a
 * laptop the honest answer is the post in the clipboard and the vertical
 * clip on the disk. The hooks are the browser's by default and plain objects
 * in a test.
 */
export function wireShare(
  strip,
  run,
  {
    origin,
    share = globalThis.navigator?.share?.bind(globalThis.navigator),
    handheld = globalThis.matchMedia?.("(hover: none) and (pointer: coarse)").matches ?? false,
    open = (url) => window.open(url, "_blank", "noopener"),
    clipboard = globalThis.navigator?.clipboard,
  } = {},
) {
  const tell = (line) => {
    strip.said.textContent = line;
    strip.said.hidden = false;
  };
  const link = `${origin}/r/${run.run_id}`;
  strip.root.querySelector("[data-copy]").addEventListener("click", async () => {
    try {
      await clipboard.writeText(link);
      tell(`Link copied: ${link}`);
    } catch {
      // A clipboard that refuses still leaves the address on the page to take.
      tell(`Could not copy. The link is ${link}`);
    }
  });
  for (const button of strip.root.querySelectorAll("[data-upload]")) {
    const text = postText(run, { origin, network: button.dataset.upload });
    button.addEventListener("click", async () => {
      if (handheld && typeof share === "function") {
        // The text ends with the link; a `url` beside it makes some targets drop the text.
        try {
          await share({ text });
        } catch (error) {
          tell(error.name === "AbortError" ? "Sharing cancelled." : "Sharing unavailable. Copy the text instead.");
        }
        return;
      }
      let copied = false;
      try {
        await clipboard.writeText(text);
        copied = true;
      } catch {
        // A clipboard that refuses: the line says so.
      }
      const tape = strip.root.querySelector('[data-clip="vertical"]');
      const ready = Boolean(tape && !tape.hidden && tape.getAttribute("href"));
      if (ready) open(tape.getAttribute("href"));
      tell(
        !copied ? "Could not copy. Select the text and copy it yourself."
        : ready ? "Text copied. Use the clip download to attach your video and publish in your app."
        : "Text copied. The clip is still rendering — come back for the download.",
      );
    });
  }
}
