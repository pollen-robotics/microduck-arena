import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { avatar, chequer, chip, footer, pendingIdentity, settleIdentity, signOutButton, signage } from "./signage.js";
import { duckHead, wordmark } from "./wordmark.js";

describe("avatar", () => {
  it("asks the Hub for the user's picture", () => {
    const img = avatar("cdeplanne").querySelector("img");
    expect(img.getAttribute("src")).toBe("https://huggingface.co/api/avatars/cdeplanne");
    expect(img.getAttribute("referrerpolicy")).toBe("no-referrer");
    expect(img.getAttribute("alt")).toBe("");
  });

  it("falls back to a duck when the Hub has no picture", () => {
    const el = avatar("local");
    el.querySelector("img").dispatchEvent(new Event("error"));
    expect(el.querySelector("img")).toBeNull();
    expect(el.textContent).toBe("🦆");
  });

  it("escapes the handle in the URL", () => {
    expect(avatar("a b").querySelector("img").getAttribute("src")).toContain("a%20b");
  });
});

describe("chip", () => {
  it("links a signed-in player to their page, with picture, name and points", () => {
    const el = chip({ signed_in: true, user: "cdeplanne", oauth_enabled: true, points: 385, unseen: 0 });
    expect(el.matches("a.profile-chip")).toBe(true);
    expect(el.getAttribute("href")).toBe("#/p/cdeplanne");
    expect(el.querySelector(".avatar img")).not.toBeNull();
    expect(el.textContent).toContain("cdeplanne");
    expect([...el.querySelectorAll(".chip-points .flip-digit")].map((t) => t.textContent)).toEqual(["3", "8", "5"]);
    expect(el.classList.contains("unread")).toBe(false);
  });

  it("wears a dot while a result waits to be opened", () => {
    const el = chip({ signed_in: true, user: "cdeplanne", oauth_enabled: true, points: 10, unseen: 2 });
    expect(el.classList.contains("unread")).toBe(true);
  });

  it("offers sign-in when signed out", () => {
    const el = chip({ signed_in: false, user: null, oauth_enabled: true });
    expect(el.matches("a.sticker")).toBe(true);
    expect(el.textContent).toBe("Sign in with Hugging Face");
    expect(el.getAttribute("href")).toMatch(/^\/login/);
  });

  it("renders nothing when the server could not be reached", () => {
    const el = chip(null);
    expect(el.textContent).toBe("");
    expect(el.querySelector("a")).toBeNull();
  });
});

describe("signage", () => {
  it("carries the mark, links home from it, and seats the chip top-right", () => {
    const el = signage({ signed_in: true, user: "ann", oauth_enabled: false });
    expect(el.matches("header.signage")).toBe(true);
    expect(el.querySelector(".club-brand img.duckhead")).not.toBeNull();
    expect(el.querySelector("nav.site-nav .profile-chip")).not.toBeNull();
  });

  it("puts the link inside the heading, so the heading stays one", () => {
    // An <a> wrapped AROUND the <h1> is not announced as a heading.
    const el = signage({ signed_in: false, user: null, oauth_enabled: true });
    const home = el.querySelector("h1.wordmark > a");
    expect(home.getAttribute("href")).toBe("#/");
    expect(home.querySelector(".wordmark__solid").textContent).toBe("Microduck");
    expect(home.querySelector(".wordmark__arena").textContent).toBe("Arena");
  });
});

describe("the mark's two variants", () => {
  it("leaves the strip's mark flat", () => {
    // Two ghosts beside a handle and a picture read as a printing fault.
    expect(wordmark().className).toBe("wordmark");
  });

  it("gives the cover's mark the charter's aberration", () => {
    const mark = wordmark({ variant: "cover" });
    expect(mark.className).toContain("wordmark--cover");
    expect(mark.className).toContain("fx-aberration");
  });
});

describe("the duck", () => {
  it("is a bare image in the strip", () => {
    expect(duckHead().tagName).toBe("IMG");
  });

  it("carries a quack on the cover, with a beak that opens", () => {
    const duck = duckHead({ quacks: true });
    expect(duck.className).toBe("duck");
    const heads = [...duck.querySelectorAll("img.duckhead")];
    expect(heads.map((h) => h.getAttribute("src"))).toEqual([
      "/duck-head-mark.webp",
      "/duck-head-mark-open.webp",
    ]);
    // The open sprite is 460x333 against the closed one's 454x269 — the extra
    // height is beak. Both are decorative; the wordmark beside them names the
    // page, and "duck head" after "Microduck Arena" is noise in a reader.
    expect(heads.every((h) => h.getAttribute("alt") === "")).toBe(true);
    expect(duck.querySelector(".duck-quack").textContent).toBe("QUACK!");
    expect(duck.querySelector(".duck-quack").getAttribute("aria-hidden")).toBe("true");
  });

  it("keeps the beak and the shout out of the reduced-motion guard", () => {
    // That setting asks for less movement, not for less to look at: with it
    // on, the tilt goes and the mouth still opens.
    const css = readFileSync(
      resolve(dirname(fileURLToPath(import.meta.url)), "../public/club.css"),
      "utf8",
    ).replace(/\/\*[\s\S]*?\*\//g, "");
    const unguarded = css.replace(
      /@media \(prefers-reduced-motion: no-preference\) \{\n[\s\S]*?\n\}/g,
      "",
    );
    expect(unguarded, "the beak only opens when motion is welcome")
      .toMatch(/\.duck:hover \.duckhead--open/);
    expect(unguarded, "the shout only appears when motion is welcome")
      .toMatch(/\.duck:hover \.duck-quack/);
  });
});

describe("footer", () => {
  it("is the strip on deep ink, with the flock and the store as stickers in a new tab", () => {
    const el = footer();
    expect(el.matches("footer.signage.signage-end")).toBe(true);
    const [flock, store] = el.querySelectorAll(".signage-stickers a.sticker");
    expect(flock.textContent).toBe("Join the flock");
    expect(flock.href).toContain("discord.com/invite/pollen-community");
    expect(store.textContent).toBe("Get your real microduck");
    expect(store.href).toBe("https://store.pollen-robotics.com/products/microduck?utm_source=microduck-arena&utm_medium=referral");
    for (const link of el.querySelectorAll("a")) {
      expect(link.target).toBe("_blank");
      expect(link.rel).toBe("noopener");
    }
  });
});

describe("the chequer", () => {
  it("is decorative, and each page dresses it through its own class", () => {
    // Two pages wear one — the front between its chapters, a player's under
    // the strip — and the decision worth keeping in one place is that it says
    // nothing to a reader.
    for (const name of ["chapter-checker", "page-checker"]) {
      const band = chequer(name);
      expect(band.className).toBe(name);
      expect(band.getAttribute("aria-hidden")).toBe("true");
      expect(band.textContent).toBe("");
    }
  });
});

describe("the way out", () => {
  it("is offered only where OAuth is what signed you in", () => {
    // Locally `current_user` answers with ARENA_DEV_USER on every request
    // whatever the cookie says, so signing out would clear a cookie nobody
    // reads and leave you signed in. A control that reports success and
    // changes nothing is worse than no control.
    expect(signOutButton({ signed_in: true, oauth_enabled: false })).toBeNull();
    expect(signOutButton({ signed_in: false, oauth_enabled: true })).toBeNull();
    expect(signOutButton(null)).toBeNull();
    expect(signOutButton({ signed_in: true, oauth_enabled: true })).not.toBeNull();
  });

  it("says what it is in words", () => {
    const out = signOutButton({ signed_in: true, oauth_enabled: true });
    expect(out.textContent).toBe("Sign out");
    expect(out.type).toBe("button");
  });

  it("is not in the strip every visitor sees", () => {
    // It belongs on the page about you, not on the chrome of every page.
    const strip = signage({ signed_in: true, user: "ann", oauth_enabled: true, points: 0 });
    expect(strip.querySelector(".sign-out")).toBeNull();
  });
});

describe("the identity while /api/me is in flight", () => {
  it("holds the space with a duck that names nobody", () => {
    const waiting = pendingIdentity("profile-chip");
    expect(waiting.className).toBe("profile-chip profile-chip--waiting");
    expect(waiting.querySelector("img.duckhead")).not.toBeNull();
    // It names nobody: a reader is told who you are once the answer is in,
    // not that a placeholder is present.
    expect(waiting.getAttribute("aria-hidden")).toBe("true");
  });

  it("is what the strip shows for `undefined`, and not for `null`", () => {
    // undefined is "still coming"; null is "it never will", which is a blank
    // rather than a duck that would sit there for ever.
    expect(signage(undefined).querySelector(".profile-chip--waiting")).not.toBeNull();
    expect(signage(null).querySelector(".profile-chip--waiting")).toBeNull();
  });

  it("is replaced in place when the answer lands", () => {
    const root = document.createElement("div");
    root.append(signage(undefined));
    settleIdentity(root, { signed_in: true, user: "ann", points: 12 });
    expect(root.querySelector(".profile-chip--waiting")).toBeNull();
    expect(root.querySelector("a.profile-chip").getAttribute("href")).toBe("#/p/ann");
  });

  it("settles nothing when the view has already been left", () => {
    // The router replaces the whole root on the way out, so by then the
    // stand-in is in no document and there is nothing to put anything into.
    const gone = document.createElement("div");
    expect(() => settleIdentity(gone, { signed_in: false })).not.toThrow();
    expect(gone.children).toHaveLength(0);
  });
});
