import json
import secrets
import tempfile
import threading
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import accumulate
from pathlib import Path

import httpx
import numpy as np

from .constants import NUM_JOINTS, RUNNER_VERSION
from .course import compile_tug
from .cup import (
    GROUP_NAMES,
    Cup,
    Entrant,
    MatchRecord,
    closed_cups,
    cup_times,
    cup_title,
    draw_groups,
    ends_at,
    first_knockout,
    group_fixtures,
    group_table,
    iso,
    match_id,
    match_label,
    parse_iso,
    round_name,
)
from .hub_fetch import PolicyGone, fetch_policy
from .index import copies
from .live import SHUTTER_MS
from .manifest import Manifest, all_events
from .match import bout_seed, play_match
from .policy import Policy, load_policy
from .store import RunRecord, Store
from .trace import encode

# An order fixed late still leaves the live this long to lay the show before it starts.
ORDER_LEAD = timedelta(minutes=10)
# The draw waits this long past the close: an entry is stamped when it is evaluated, and its commit
# lands a few seconds later.
DRAW_GRACE = timedelta(seconds=60)
# How long a policy may fail to load, from this process's first try at a cup's step, before the cup goes on without it.
# One the Hub answers 404 for is not waited for.
LOAD_PATIENCE = timedelta(minutes=10)
# A match clip that failed is launched again this often, as long as it stays failed.
CLIP_RETRY = timedelta(minutes=10)
# A show held by anything but the router (an answer refused every time, a plan page that cannot time one) is written
# again this often: on the next tick it would most likely fail again, after buying its answers again.
SHOW_RETRY = timedelta(minutes=10)
# A show the booth has not written this long past its cup's premiere is given up: the matches air without the desk or
# the calls rather than the live standing by, races and Got a Talent included, for as long as the router is down.
BOOTH_PATIENCE = timedelta(minutes=30)
TICK_S = 30


def load_cup(store: Store, event_id: str, number: int) -> Cup | None:
    draw = store.cup_file(event_id, number, "draw.json")
    if draw is None:
        return None
    return Cup.from_json(draw, store.cup_file(event_id, number, "matches.json"), store.cup_file(event_id, number, "order.json"))


def all_cups(store: Store) -> list[Cup]:
    return [load_cup(store, event.id, number) for event in all_events() if event.cup for number in store.cup_numbers(event.id)]


def entrants_at(records: Iterable[RunRecord], withdrawn: frozenset[str], close_at: datetime,
                runner_version: int = RUNNER_VERSION) -> list[Entrant]:
    """Each player's latest entry at close, not withdrawn, not a copy, on the runner; two ducks of one policy name air
    under their handles."""
    close, latest = iso(close_at), {}
    records = sorted(records, key=lambda r: (r.submitted_at, r.run_id))
    copied = copies(records)
    for record in records:
        if (record.submitted_at <= close and record.run_id not in withdrawn and record.run_id not in copied
                and record.runner_version == runner_version):
            latest[record.user] = record
    names = Counter(record.policy_name for record in latest.values())
    ducks = [Entrant(r.user, r.run_id, r.policy_name, r.livery, r.score, r.model_sha256, r.source,
                     r.policy_name if names[r.policy_name] == 1 else f"{r.policy_name} (@{r.user})")
             for r in latest.values()]
    return sorted(ducks, key=lambda e: (-e.rating, e.user))


def load_entrant(store: Store, entrant: Entrant) -> Policy:
    """From the Hub at its pinned revision, or the store's own copy: the two ways an entry records its policy."""
    source = entrant.source
    if source["kind"] == "hub":
        return load_policy(fetch_policy(f"{source['repo_id']}:{source['filename']}", revision=source["revision"]).path)
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "policy.onnx"
        path.write_bytes(store.model(entrant.model_sha256))
        return load_policy(path)


def compute_matches(manifest: Manifest, cup: Cup, load: Callable[[Entrant], object]) -> tuple[Cup, dict[str, bytes]]:
    """Every match of the cup in playing order: the groups round by round, then each knockout round from the last."""
    model = compile_tug(manifest)  # one model for every bout of the cup
    ratings = [e.rating for e in cup.entrants]
    policies, matches, files = {}, [], {}

    def play(a: int, b: int, round_: str, group: str | None) -> int:
        mid = match_id(cup.event_id, cup.number, len(matches))
        for i in (a, b):
            if i not in policies:
                policies[i] = load(cup.entrants[i])
        seeds = [bout_seed(cup.secret, mid, k) for k in range(manifest.bout.max_bouts)]
        out = play_match(manifest, policies[a], policies[b], seeds, (ratings[a], ratings[b]), model=model)
        for bout, frames in zip(out.bouts, out.traces):
            files[f"bouts/{mid}-{bout.k}.npz"] = encode(*frames)
        winner = a if out.winner == "a" else b
        matches.append(MatchRecord(mid, len(matches), round_, group, a, b, out.bouts, out.wins, winner, out.decided_by))
        return winner

    fixtures = [group_fixtures(g) for g in cup.groups]
    per_round = [len(g) // 2 for g in cup.groups]  # a round of an odd group has a bye: still len // 2 matches
    for r in range(max((len(f) // k for f, k in zip(fixtures, per_round)), default=0)):
        for g, (pairs, k) in enumerate(zip(fixtures, per_round)):
            for a, b in pairs[r * k:(r + 1) * k]:
                play(a, b, "group", GROUP_NAMES[g])
    pairs = first_knockout([group_table(g, matches, ratings) for g in cup.groups])
    while pairs:
        winners = [play(a, b, round_name(len(pairs)), None) for a, b in pairs]
        pairs = list(zip(winners[::2], winners[1::2]))
    return replace(cup, matches=tuple(matches)), files


def running_order(cup: Cup, clips: Mapping[str, float], starts_at: datetime, show: dict | None = None) -> dict:
    """Every match after the shutter that cuts into it, from `starts_at`; `clips` gives each match clip's seconds.

    The live serves its grid five minutes ahead, so a shutter names the stage, never a duck: who plays a knockout match
    would tell who qualified. With the cup's written `show`, Peter and Ray are at the desk around the matches, each
    desk segment as long as its plan, in the show's order: the opening, an intro before every match, which is called,
    a recap after each group round and, after the final, the ceremony and the close. A shutter that names nothing
    cuts from a match into a recap or the ceremony.
    """
    def played(match: MatchRecord) -> list[dict]:
        called = {} if show is None else {"call": True}
        return [{"kind": "shutter", "duration_ms": SHUTTER_MS,
                 "next": {"match_id": match.match_id, "title": match_label(cup, match)}},
                {"kind": "match", "duration_ms": round(clips[match.match_id] * 1000), "match_id": match.match_id,
                 **called}]

    if show is None:
        laid = [segment for match in cup.matches for segment in played(match)]
    else:
        laid = []
        for segment_id, desk in show["desk"].items():
            if desk["kind"] in ("recap", "ceremony"):
                laid.append({"kind": "shutter", "duration_ms": SHUTTER_MS, "next": None})
            laid.append({"kind": "desk", "duration_ms": desk["plan"]["duration_ms"], "segment": segment_id,
                         "after": desk["after"]})
            if desk["kind"] == "intro":
                laid += played(cup.matches[desk["after"] + 1])
    starts = accumulate((segment["duration_ms"] for segment in laid), initial=0)
    return {"starts_at": iso(starts_at),
            "segments": [{"kind": segment["kind"], "at_ms": at, **segment} for segment, at in zip(laid, starts)]}


class Standing:
    """A drawn duck whose policy no longer loads: it holds its standing pose (an action of zeros) in every bout."""

    def act(self, obs: np.ndarray) -> np.ndarray:
        return np.zeros(NUM_JOINTS, dtype=np.float32)


class CupWorker:
    """Every cup of `events`, tick by tick, from close to its running order, each step read back from the store.

    Close, then draw.json (with the secret), then matches.json and the bouts, then one clip owed per match, then, once
    every match is called, show.json, then order.json once the event's previous cup has finished airing. Each write is
    one store commit made once, so a restart at any point picks up where the dataset left off, with the same secret
    and the same results. `show(cup, partial)` writes into `partial` what it can of the show now and returns it: the
    desk needs only the matches, a match's call its clip (its lines are timed on the clip's tape), so the show is
    written while the clips render, each call on the first tick its clip is ready, and a write cut off resumes on the
    next tick. With no `show` (no booth), or a show still unwritten BOOTH_PATIENCE past the premiere, the cup airs its
    matches alone.
    """

    def __init__(self, store, clips, *, events, load: Callable[[Entrant], object],
                 now: Callable[[], datetime] = lambda: datetime.now(UTC), log=print,
                 show: Callable[[Cup, dict], dict] | None = None):
        self.store = store
        self.clips = clips
        self.events = events
        self.load = load
        self.now = now
        self.log = log
        self.show = show
        self._relaunched: dict[str, datetime] = {}  # match id -> when its failed clip was last launched again
        self._tried: dict[tuple[str, int, str], datetime] = {}  # (event, number, "draw" | "play") -> first try here
        self._shows: dict[tuple[str, int], dict] = {}  # (event, number) -> the part of its show written so far
        self._failed: dict[tuple[str, int], datetime] = {}  # (event, number) -> when its show last failed, not on the router
        self._stopped = threading.Event()

    def tick(self) -> None:
        for manifest in self.events:
            try:
                self._advance(manifest)
            except Exception as exc:  # noqa: BLE001 — a cup that cannot move now moves next tick
                self.log(f"cups: {manifest.id} held ({type(exc).__name__}: {exc})")

    def start(self) -> None:
        threading.Thread(target=self._work, name="arena-cups", daemon=True).start()

    def stop(self) -> None:
        self._stopped.set()

    def _work(self) -> None:
        self.tick()
        while not self._stopped.wait(TICK_S):
            self.tick()

    def _advance(self, manifest: Manifest) -> None:
        now = self.now()
        for number in range(1, closed_cups(manifest.cup, now - DRAW_GRACE) + 1):
            cup, policies = load_cup(self.store, manifest.id, number), None
            if cup is None:
                cup, policies = self._draw(manifest, number, now)
            if cup is None or cup.skipped:
                continue
            if not cup.matches:
                cup = self._play(manifest, cup, policies, now)
                if cup is None:
                    continue
            if cup.order is None:
                self._schedule(manifest, cup, now)

    def _load(self, manifest: Manifest, number: int, step: str, entrants: Iterable[Entrant],
              now: datetime) -> dict | None:
        """Each entrant's policy by run id, leaving out those that fail; None while one fails within LOAD_PATIENCE of
        this process's first try at the step, so a Hub away for a moment costs nobody their place, however long after
        the close the process first looks (a deploy across it, a crash while the cup played). A policy gone from the Hub
        (PolicyGone) is not waited for."""
        first_try = self._tried.setdefault((manifest.id, number, step), now)
        policies, missing, gone = {}, [], []
        for entrant in entrants:
            try:
                policies[entrant.run_id] = self.load(entrant)
            except Exception as exc:  # noqa: BLE001 — whatever stops a policy playing, it cannot play
                (gone if isinstance(exc, PolicyGone) else missing).append(f"{entrant.user} ({type(exc).__name__}: {exc})")
        if missing and now < first_try + LOAD_PATIENCE:
            self.log(f"cups: {manifest.id} #{number} waits for {', '.join(missing)}")
            return None
        if failed := ", ".join(gone + missing):
            self.log(f"cups: {manifest.id} #{number} goes on without {failed}" if step == "draw" else
                     f"cups: {manifest.id} #{number} plays {failed} standing still: drawn, they keep their place")
        return policies

    def _draw(self, manifest: Manifest, number: int, now: datetime) -> tuple[Cup | None, dict | None]:
        close_at, premiere_at = cup_times(manifest.cup, number)
        withdrawn = frozenset(w.run_id for w in self.store.withdrawals() if w.withdrawn_at <= iso(close_at))
        found = entrants_at(self.store.runs(manifest.id), withdrawn, close_at)
        policies = self._load(manifest, number, "draw", found, now)
        if policies is None:
            return None, None
        entrants = tuple(e for e in found if e.run_id in policies)
        secret = secrets.token_hex(16)
        skipped = len(entrants) < manifest.cup.min_entrants
        groups = () if skipped else tuple(tuple(g) for g in draw_groups(entrants, secret))
        cup = Cup(manifest.id, number, iso(close_at), iso(premiere_at), secret, entrants, groups, skipped)
        self.store.put_cup_files(manifest.id, number, {"draw.json": cup.draw_json()})
        self.log(f"cups: {manifest.id} #{number} skipped, {len(entrants)} entrants of {manifest.cup.min_entrants}"
                 if skipped else f"cups: {manifest.id} #{number} drawn, {len(entrants)} entrants in {len(groups)} groups")
        return cup, policies

    def _play(self, manifest: Manifest, cup: Cup, policies: dict | None, now: datetime) -> Cup | None:
        """Every match of the drawn cup, with the policies of its draw; drawn on an earlier tick (a restart, a failed
        write), they are loaded again under the same patience. The draw is frozen: a duck whose policy no longer loads
        keeps its place and plays standing still, rather than holding the cup forever."""
        if policies is None:
            policies = self._load(manifest, cup.number, "play", cup.entrants, now)
            if policies is None:
                return None
        cup, files = compute_matches(manifest, cup, lambda e: policies.get(e.run_id, Standing()))
        self.store.put_cup_files(manifest.id, cup.number, {"matches.json": cup.matches_json(), **files})
        self.log(f"cups: {manifest.id} #{cup.number} played, {len(cup.matches)} matches")
        return cup

    def _schedule(self, manifest: Manifest, cup: Cup, now: datetime) -> None:
        seconds = {}
        for match in cup.matches:
            state, written = self.store.clip_state(match.match_id)
            if state == "ready":
                seconds[match.match_id] = written["layouts"]["landscape"]["seconds"]
            elif state == "none":
                self.store.mark_clip_pending(match.match_id, "arena", cup.event_id, iso(now))
                self.clips.enqueue(match.match_id)
            elif state == "failed" and now - self._relaunched.get(match.match_id, now - CLIP_RETRY) >= CLIP_RETRY:
                self._relaunched[match.match_id] = now
                self.clips.enqueue(match.match_id)
            # A pending clip is the clip jobs' to follow (their drain at boot, their rescan): queued again every tick, it
            # would race a launch in progress into a second job.
        show = None
        if self.show is not None:
            show = self._written_show(manifest, cup, now)
            if show is None and now < parse_iso(cup.premiere_at) + BOOTH_PATIENCE:
                return
        if len(seconds) < len(cup.matches):
            return
        # Read again: a show takes minutes to write, and the live relies on an order fixed ORDER_LEAD before it starts.
        now = self.now()
        if not self._previous_aired(cup, now):
            return
        starts_at = max(parse_iso(cup.premiere_at), (now + ORDER_LEAD).replace(microsecond=0))
        order = running_order(cup, seconds, starts_at, show=show)
        self.store.put_cup_files(cup.event_id, cup.number, {"order.json": json.dumps(order, indent=2).encode()})
        alone = " without the booth" if self.show is not None and show is None else ""
        self.log(f"cups: {cup.event_id} #{cup.number} airs from {order['starts_at']}{alone}")

    def _written_show(self, manifest: Manifest, cup: Cup, now: datetime) -> dict | None:
        """The cup's show.json, stored once every match is called; until then each tick writes what it can of it,
        what it wrote kept to go on from. None while a clip is not ready or the writer fails: resumed on the next tick
        when the router was down, SHOW_RETRY after any other failure."""
        key = (cup.event_id, cup.number)
        stored = self.store.cup_file(cup.event_id, cup.number, "show.json")
        if stored is not None:
            self._shows.pop(key, None)  # a write whose commit landed, though its call raised or a stale snapshot hid it
            return json.loads(stored)
        if now - self._failed.get(key, now - SHOW_RETRY) < SHOW_RETRY:
            return None
        title = cup_title(manifest.title, cup.number)
        if key not in self._shows:  # once, not on every tick the clips render
            self._shows[key] = {"desk": {}, "calls": {}}
            self.log(f"cups: writing the show of {title}")
        try:
            show = self.show(cup, self._shows[key])
        except Exception as exc:  # noqa: BLE001 — a show that cannot be written now is resumed later
            if not isinstance(exc, httpx.HTTPError):
                self._failed[key] = self.now()  # writing can take minutes: wait from the failure
            self.log(f"cups: the show of {title} waits ({type(exc).__name__}: {exc})")
            return None
        if len(show["calls"]) < len(cup.matches):
            return None
        self.store.put_cup_files(cup.event_id, cup.number,
                                 {"show.json": json.dumps(show, indent=2, ensure_ascii=False).encode()})
        del self._shows[key]
        self.log(f"cups: the show of {title} is written")
        return show

    def _previous_aired(self, cup: Cup, now: datetime) -> bool:
        """One show at a time per event: a cup gets no order until the one before it has finished airing."""
        if cup.number == 1:
            return True
        previous = load_cup(self.store, cup.event_id, cup.number - 1)
        return previous is not None and (previous.skipped or (previous.order is not None and ends_at(previous) <= now))
