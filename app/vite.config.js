import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const page = (name) => fileURLToPath(new URL(`./${name}`, import.meta.url));

/**
 * Stamp every stylesheet link with a hash of the file behind it.
 *
 * The bundle Vite builds is hashed into its own filename, so a deploy always
 * hands the browser a URL it has never seen. The stylesheets are not: they
 * live in public/ and are served at fixed paths, so a deploy ships new markup
 * against whatever copy of `/race.css` the browser or the CDN already had.
 * That shipped once — the race page's strip of other rounds came out with no
 * styling at all while everything above it was fine.
 *
 * A content hash and not a build id, so a sheet that did not change keeps its
 * URL and stays cached.
 */
function stampStylesheets() {
  const stamp = (file) => {
    const bytes = readFileSync(fileURLToPath(new URL(`./public/${file}`, import.meta.url)));
    return createHash("sha256").update(bytes).digest("hex").slice(0, 8);
  };
  return {
    name: "stamp-stylesheets",
    apply: "build",
    transformIndexHtml(html) {
      return html.replace(/href="\/([\w/.-]+\.css)"/g, (whole, file) => {
        try {
          return `href="/${file}?v=${stamp(file)}"`;
        } catch {
          // A sheet that is not in public/ is not ours to stamp; leave it be
          // rather than failing the build over a path we do not own.
          return whole;
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [stampStylesheets()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    // Five pages: the app, the clip the recorder photographs, the plan the
    // booth's dialogue is timed by, the workshop (served by `workshop`, never
    // by the Space's API) and the football match (served by `arena football
    // --watch`, never by the Space's API either).
    rollupOptions: {
      input: {
        main: page("index.html"),
        clip: page("clip.html"),
        plan: page("plan.html"),
        workshop: page("workshop.html"),
        football: page("football.html"),
      },
    },
  },
  // `npm run dev` serves the UI on 5173 with hot reload and forwards the API to
  // `arena serve` on 8000, so the frontend can be iterated on without a rebuild.
  server: {
    fs: { allow: [fileURLToPath(new URL("..", import.meta.url))] },
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  // jsdom so the rendered leaderboard table is testable, not just the pure
  // row-building rules behind it.
  test: { environment: "jsdom" },
});
