// Views chosen by the hash. Everything else lives in its view.

import { getEvents } from "./api.js";
import { renderCup } from "./cup.js";
import { renderHome } from "./home.js";
import { renderLive } from "./live.js";
import { renderMatch } from "./match.js";
import { renderPlayer } from "./player.js";
import { renderRace } from "./race.js";
import { renderRun } from "./run.js";
import { parseRoute } from "./router.js";
import { renderVote } from "./vote.js";
import { renderGuides } from "./guides.js";
import { HALLOWEEN, decoratePage } from "./halloween.js";

const root = document.querySelector("#app");
const state = { events: null, viewer: null, teardown: null };

async function events() {
  if (!state.events) state.events = await getEvents();
  return state.events;
}


async function show() {
  // Tear the old view's render loop down before building the next one, or two
  // viewers keep animating against the same canvas.
  state.viewer?.dispose();
  state.viewer = null;
  // A reveal in progress is abandoned, not finished, when the page is left.
  state.teardown?.();
  state.teardown = null;

  const route = parseRoute(location.hash);
  document.title = "Microduck Arena";
  try {
    if (route.view === "guides") {
      const event = route.eventId ? (await events()).find(e => e.id === route.eventId) : null;
      renderGuides(root, { ...route, event });
    } else if (route.view === "race") {
      const event = (await events()).find((e) => e.id === route.eventId);
      if (!event) {
        // A stale link should land on something useful, not an error.
        location.hash = "#/";
        return;
      }
      await renderRace(root, { event, state });
    } else if (route.view === "vote") {
      const event = (await events()).find((e) => e.id === route.eventId);
      if (!event || !event.vote) {
        location.hash = "#/";
        return;
      }
      await renderVote(root, { event, state });
    } else if (route.view === "run") {
      await renderRun(root, route.runId, state);
    } else if (route.view === "cup") {
      if (!(await events()).some((e) => e.id === route.eventId)) {
        location.hash = "#/";
        return;
      }
      await renderCup(root, route.eventId, route.number, state);
    } else if (route.view === "match") {
      await renderMatch(root, route.matchId, state);
    } else if (route.view === "live") {
      await renderLive(root, state);
    } else if (route.view === "player") {
      await renderPlayer(root, route.user);
    } else {
      await renderHome(root, state);
    }
  } catch (error) {
    const failed = document.createElement("p");
    failed.className = "failed";
    failed.textContent = `Could not reach the API: ${error.message}`;
    root.replaceChildren(failed);
  }
}

if (HALLOWEEN) decoratePage();
addEventListener("hashchange", show);
show();
