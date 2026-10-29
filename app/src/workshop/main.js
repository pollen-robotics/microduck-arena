// The workshop's page: a home, a page per challenge, a page per training, addressed by hash so the
// browser's back button works. Each page mounts itself and says how to leave it (its polls, its
// viewer) and how to redraw the account when that changes.

import { HALLOWEEN, decoratePage } from "../halloween.js";
import { dress } from "../router.js";
import { createAccount } from "./account.js";
import * as api from "./api.js";
import { mountChallenge } from "./challenge.js";
import { el } from "./dom.js";
import { mountHome } from "./home.js";
import { mountJob } from "./job.js";
import { parseRoute } from "./routes.js";

const MOUNTS = { home: mountHome, challenge: mountChallenge, job: mountJob };
// The Arena's sheet each page wears (router.js's dress): the club's on the home, as on the Arena's
// front; trackside on a challenge's page and a training's, as on the Arena's own.
const SHEETS = { home: "menu", challenge: "race", job: "race" };

const root = document.querySelector("#app");
let page = null;
let shown = 0; // the latest show(): an older one that finishes late shows nothing

const account = createAccount(() => page?.accountChanged());

async function show() {
  const mine = ++shown;
  page?.leave();
  page = null;
  try {
    const status = await api.getStatus();
    const route = parseRoute(location.hash);
    if (mine !== shown) return;
    const view = MOUNTS[route.view] ? route.view : "home";
    // Drawn off the document, then shown only if no newer page was asked for meanwhile: a page
    // that answers late must not paint over, nor dress, the one on screen.
    const box = el("div", "ws-view");
    const next = await MOUNTS[view](box, { status, account, route });
    if (mine !== shown) {
      next.leave();
      return;
    }
    dress(SHEETS[view]);
    root.replaceChildren(box);
    page = next;
    // The account may have answered while the page was being drawn, when there was no page to tell.
    page.accountChanged();
    window.scrollTo(0, 0);
  } catch (error) {
    if (mine === shown) root.replaceChildren(el("p", "failed", `The workshop's server did not answer: ${error.message}`));
  }
}

if (HALLOWEEN) decoratePage();
window.addEventListener("hashchange", show);
account.check(); // not awaited: the Hub may be slow, and no page waits for it
show();
