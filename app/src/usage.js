// How the Arena is used, for Pollen's private dashboard: every page viewed, every link that
// leaves the site, and how long the page was looked at, each sent to arena/web/routes_usage.py.
// Nothing names anyone: a visitor is a random id this browser keeps, a visit is one page load.

const KEY = "arena.visitor";

function visitorId() {
  try {
    const kept = localStorage.getItem(KEY);
    if (kept) return kept;
    const made = crypto.randomUUID();
    localStorage.setItem(KEY, made);
    return made;
  } catch {
    // Private windows and blocked site data: counted as a new visitor each visit.
    return crypto.randomUUID();
  }
}

function beacon(hit) {
  // A beacon, not a fetch: it still leaves while the page is being closed.
  navigator.sendBeacon("/api/usage", new Blob([JSON.stringify(hit)], { type: "application/json" }));
}

export function trackUsage(send = beacon) {
  const ids = { visitor: visitorId(), visit: crypto.randomUUID() };
  const hit = (kind, fields) =>
    send({ ...ids, kind, page: (location.hash.replace(/^#/, "") || "/").slice(0, 200), ...fields });

  hit("view", {
    referrer: document.referrer ? new URL(document.referrer).host : undefined,
    // Inside huggingface.co's Space page, or on its own address.
    embedded: window.top !== window,
    mobile: matchMedia("(pointer: coarse)").matches,
  });
  addEventListener("hashchange", () => hit("view"));
  // Capturing, so a link whose own handler stops the click is still counted.
  addEventListener("click", (event) => {
    const link = event.target.closest?.("a[href]");
    if (link && link.host !== location.host) hit("out", { href: link.href.slice(0, 300) });
  }, true);

  let shownSince = document.visibilityState === "visible" ? Date.now() : null;
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      shownSince = Date.now();
    } else if (shownSince !== null) {
      hit("time", { seconds: Math.min(86_400, Math.round((Date.now() - shownSince) / 1000)) });
      shownSince = null;
    }
  });
}
