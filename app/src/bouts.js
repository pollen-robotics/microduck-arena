// A cup's match on the tug's rope: which of its two entrants pulls from which end in each bout, and
// in which livery.

import { VARIANT_NAMES } from "./liveries.js";
import { SIDES } from "./tug.js";

/** The liveries entrants `a` and `b` wear in their match: their own, except b in a's, which then wears
 * the first other one, as the reference duck does in an entry's charcoal. */
export function matchLiveries(a, b) {
  return [a.livery, b.livery === a.livery ? VARIANT_NAMES.find((name) => name !== a.livery) : b.livery];
}

/**
 * Bout `k` of `match` as a lane of the viewer, from its two traces and settles (west first) and its
 * string: each entrant on the end of the string the bout gave it, in its match livery, under its
 * on-air name.
 */
export function boutLane(match, k, traces, settles, string) {
  const [liveryA, liveryB] = matchLiveries(match.a, match.b);
  const a = { livery: liveryA, name: match.a.name };
  const b = { livery: liveryB, name: match.b.name };
  const [west, east] = match.bouts[k].a_side === SIDES[0] ? [a, b] : [b, a];
  return { tug: "bout", ducks: [west, east].map((duck, side) => ({ trace: traces[side], settle: settles[side], ...duck })), string };
}

/** Who won a match, by its on-air name or the `name` given: by rating when its bouts tied. */
export function winLine(match, name = match[match.winner].name) {
  return `${name} wins${match.decided_by === "rating" ? " on rating" : ""}`;
}
