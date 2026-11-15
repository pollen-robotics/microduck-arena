// The wipe between two segments: a 400 ms sweep in
// from the left, 800 ms fully covering, a 400 ms sweep out to the right. The
// slot underneath switches at 800 ms, while nothing shows through. On the way
// out to a replay the panel carries the UP NEXT card, which is how the next
// replay is announced: a run by its event and its player, a cup match by its
// title.

import { wordmark } from "../wordmark.js";

export const TRANSITION_MS = 1600;
const smooth = (t) => t * t * (3 - 2 * t);

export function shutterAt(ms) {
  const x = ms < 400 ? smooth(Math.max(0, ms) / 400) - 1
    : ms <= 1200 ? 0
    : smooth(Math.min(1, (ms - 1200) / 400));
  return { x, destination: ms >= 800 };
}

export function createShutter(container) {
  const panel = document.createElement("div");
  panel.className = "live-shutter";
  panel.hidden = true;
  const mark = wordmark();
  const card = document.createElement("div");
  card.className = "live-upnext";
  card.hidden = true;
  const label = document.createElement("span");
  label.className = "eyebrow";
  label.textContent = "Up next";
  const event = document.createElement("span");
  event.className = "live-upnext-event";
  const user = document.createElement("span");
  user.className = "live-upnext-user mono-label";
  card.append(label, event, user);
  panel.append(mark, card);
  container.append(panel);
  return {
    draw(ms, next) {
      const { x, destination } = shutterAt(ms);
      if (Math.abs(x) >= 1) {
        panel.hidden = true;
        return;
      }
      panel.hidden = false;
      panel.style.setProperty("--shutter-x", String(x));
      panel.classList.toggle("live-shutter-out", destination);
      const announce = destination && next;
      card.hidden = !announce;
      if (announce) {
        // A cup match is announced by its title alone, which bills both its players, never by one of them.
        const match = Boolean(next.title);
        event.textContent = match ? next.title : next.event;
        user.hidden = match;
        user.textContent = match ? "" : `@${next.user}`;
      }
    },
    hide() {
      panel.hidden = true;
    },
  };
}
