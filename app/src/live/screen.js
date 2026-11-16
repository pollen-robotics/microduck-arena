// The cup screen on the booth's back wall during the cup's show: the groups
// and their tables while the groups play, then the bracket, the next match
// picked out in yellow: the group tables by the players' handles, the bracket
// and the footer every duck billed with its player, "<policy> (@<user>)".
// The layout is a list of paint operations in design tokens; drawCupScreen
// paints them on a canvas. The layout measures no text: a character counts
// CHAR of its size.

import { token } from "./set.js";

export const SCREEN_PX = [1280, 512];
const MARGIN = 40;
const CHAR = 0.55;
const COLUMNS = 4; // groups side by side
const TOP = 88; // the field starts under the header
const BOTTOM = 72; // and ends over the footer
const LINE = 32; // a line's pitch at full size
const BASELINE = 24; // a line's baseline below its top at full size
const INSET = 24; // text from its cell's side
const PAD = 12; // a panel's padding, top and bottom together
const GAP = 8; // between panels
const FOOTER = 32; // the footer's type
const STROKE = 4;
const KEPT = 8; // the fewest characters of a policy's name worth showing, its ellipsis one of them

const ellipsis = (text, chars) => `${text.slice(0, chars - 1).trimEnd()}…`;

/** A name cut with an ellipsis to the room it is given. A billed duck is cut
 * in its policy's name and keeps its player's handle whole, or is its handle
 * alone, cut in turn, when the policy would keep less than KEPT. */
function cut(name, room, size) {
  const chars = Math.floor(room / (CHAR * size));
  if (name.length <= chars) return name;
  const [, policy, handle] = name.match(/^(.+) \((@[^\s()]+)\)$/) ?? [];
  if (!handle) return ellipsis(name, chars);
  const left = chars - ` (${handle})`.length;
  return left < KEPT ? cut(handle, room, size) : `${ellipsis(policy, left)} (${handle})`;
}

export function screenLayout(view, width, height) {
  const ops = [{ kind: "rect", x: 0, y: 0, w: width, h: height, paint: "deep-ink" }];
  const panel = (x, y, w, h, next) =>
    ops.push({ kind: "rect", x, y, w, h, paint: "ink", ...(next && { stroke: "yellow" }) });
  const text = (x, y, value, size, paint, weight = 400, align = "left") =>
    ops.push({ kind: "text", x, y, text: value, size, paint, weight, align });
  // The footer: a label, then the names in what it leaves of the line, each
  // name sure of an equal share and given what the others leave unused.
  const footer = (label, names) => {
    const words = label.length + " vs ".length * (names.length - 1);
    const room = width - 2 * MARGIN - CHAR * FOOTER * words;
    const takes = names.map((name) => Math.min(CHAR * FOOTER * name.length, room / names.length));
    const taken = takes.reduce((sum, take) => sum + take, 0);
    const line = `${label}${names.map((name, i) => cut(name, room - taken + takes[i], FOOTER)).join(" vs ")}`;
    text(MARGIN, height - 36, line, FOOTER, "yellow", 700);
  };
  const field = { top: TOP, height: height - TOP - BOTTOM };
  text(MARGIN, 64, `${view.title} · ${view.stage}`.toUpperCase(), 40, "yellow", 700);

  if (view.next?.round === "group") {
    const columns = Math.min(COLUMNS, view.groups.length);
    const cell = (width - 2 * MARGIN) / columns;
    const tiers = Math.ceil(view.groups.length / columns);
    const lines = 1 + Math.max(...view.groups.map((group) => group.rows.length));
    // A field too tall for the screen shrinks, type and all.
    const scale = Math.min(1, (field.height - (tiers - 1) * GAP) / (tiers * (lines * LINE + PAD)));
    const tall = (lines * LINE + PAD) * scale;
    const first = field.top + (field.height - tiers * tall - (tiers - 1) * GAP) / 2;
    const size = 26 * scale;
    view.groups.forEach((group, g) => {
      const x = MARGIN + (g % columns) * cell;
      const top = first + Math.floor(g / columns) * (tall + GAP);
      const baseline = (line) => top + (PAD / 2 + line * LINE + BASELINE) * scale;
      panel(x + GAP / 2, top, cell - GAP, tall, group.name === view.next.group);
      text(x + INSET, baseline(0), `GROUP ${group.name}`, 28 * scale, "paper", 700);
      text(x + cell - INSET, baseline(0), "WON", 20 * scale, "sky", 700, "right");
      group.rows.forEach((row, i) => {
        const won = String(row.won);
        const room = cell - 2 * INSET - CHAR * size * (won.length + 1);
        text(x + INSET, baseline(i + 1), cut(row.name, room, size), size, "paper");
        text(x + cell - INSET, baseline(i + 1), won, size, "paper", 400, "right");
      });
    });
    footer("NEXT  ", [view.next.a, view.next.b]);
    return ops;
  }

  // The bracket: a column a round under its name, each match centred on the two it follows.
  const column = (width - 2 * MARGIN) / view.knockout.length;
  const head = 40;
  const room = field.height - head;
  const scale = Math.min(1, (room / view.knockout[0].matches.length - GAP) / (2 * LINE + PAD));
  const tall = (2 * LINE + PAD) * scale;
  const size = 26 * scale;
  view.knockout.forEach((round, r) => {
    const x = MARGIN + r * column;
    text(x + INSET, field.top + 28, round.round.toUpperCase(), 28, "paper", 700);
    const each = room / round.matches.length;
    round.matches.forEach((match, i) => {
      const top = field.top + head + (i + 0.5) * each - tall / 2;
      panel(x + GAP / 2, top, column - GAP, tall, match.next);
      ["a", "b"].forEach((side, line) => {
        const name = cut(match[side] ?? "?", column - 2 * INSET, size);
        const baseline = top + (PAD / 2 + line * LINE + BASELINE) * scale;
        text(x + INSET, baseline, name, size, "paper", match.winner === side ? 700 : 400);
      });
    });
  });
  if (view.champion) footer("CHAMPION  ", [view.champion]);
  return ops;
}

/** Paints the cup screen's view on its canvas, in the design tokens and DM Sans. */
export function drawCupScreen(canvas, view) {
  const ctx = canvas.getContext("2d");
  for (const op of screenLayout(view, canvas.width, canvas.height)) {
    ctx.fillStyle = token(op.paint).getStyle();
    if (op.kind === "rect") {
      ctx.fillRect(op.x, op.y, op.w, op.h);
      if (!op.stroke) continue;
      ctx.strokeStyle = token(op.stroke).getStyle();
      ctx.lineWidth = STROKE;
      ctx.strokeRect(op.x + STROKE / 2, op.y + STROKE / 2, op.w - STROKE, op.h - STROKE);
    } else {
      ctx.font = `${op.weight} ${op.size}px "DM Sans", sans-serif`;
      ctx.textAlign = op.align;
      ctx.fillText(op.text, op.x, op.y);
    }
  }
}
