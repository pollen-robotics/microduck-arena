"""Read-only endpoints: what events exist, and who is winning them.

These shape engine objects into the JSON the page renders. No ranking, scoring
or selection logic lives here — `arena.index.leaderboard` owns all of it, so the
web layer and the CLI can never disagree about who is first.
"""

import re
from collections import defaultdict
from datetime import UTC, datetime

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from .. import votes
from ..course import (
    RING_POST_RADIUS_M,
    RING_ROPE_RADIUS_M,
    ring_posts,
    ring_ropes,
    wall_boxes,
)
from ..cup import reached
from ..cupworker import all_cups
from ..evaluate import seed_row
from ..index import leaderboard, standing
from ..lights import served
from ..manifest import Manifest, ManifestError, all_events, load_event
from ..points import boards_by_user, receipts, revealed_final, standings
from ..store import CLIP_MEDIA, RunRecord, clip_version
from ..timeline import EDGE_MARGIN_M, MIN_SPACING_M
from ..trace import decode, decode_caught, decode_settle, decode_string

router = APIRouter(prefix="/api")


def _boxes(boxes) -> list[dict]:
    return [{"name": name, "pos": list(pos), "half": list(half)} for name, pos, half in boxes]


def _capsules(capsules, radius: float) -> list[dict]:
    return [{"name": name, "from": list(start), "to": list(end), "radius": radius} for name, start, end in capsules]


def event_summary(manifest: Manifest) -> dict:
    summary = {
        "id": manifest.id,
        "title": manifest.title,
        "rig": manifest.rig,
        # What kind of event this is, for the flyer's label and its shadow
        # colour. The board and the race page do not read it.
        "category": manifest.category,
        "metric": manifest.metric,
        # "lane", "stage" or "tug": what the page draws, and how it words a result. A stage has no
        # lane, no line and no speed (the lane fields below are a lane's alone).
        "course": manifest.course.kind,
        # The whole vote configuration, or null. The page reads this to decide
        # whether the VOTE badge, the vote button and the #/v/ route exist.
        "vote": (
            {
                "ballot_min": manifest.vote.ballot_min,
                "ballot_max": manifest.vote.ballot_max,
                "window_days": manifest.vote.window_days,
                "per_day": manifest.vote.per_day,
            }
            if manifest.vote
            else None
        ),
        "order": manifest.order,
        "time_limit_s": manifest.time_limit_s,
        "seeds": len(manifest.seeds),
        "clip": manifest.clip.to_dict(),
    }
    # A stage is an open floor that plays each entry's timeline: no lane to
    # draw and no speed to sweep.
    if manifest.course.kind == "lane":
        summary |= {
            "length_m": manifest.course.length_m,
            "width_m": manifest.course.width_m,
            "slope_deg": manifest.course.slope_deg,
            # The lane walls the PHYSICS uses, in MJCF coordinates, so the viewer can
            # draw exactly what the robot can hit rather than recomputing where the
            # walls ought to be. They are invisible unless you ask for them.
            "walls": _boxes(wall_boxes(manifest.course)),
            # The sweep, not a single command: the event no longer pins a speed,
            # it declares the range every entry is tried over.
            "sweep_lo": manifest.sweep.lo,
            "sweep_hi": manifest.sweep.hi,
            "sweep_step": manifest.sweep.step,
            "sweep_count": len(manifest.sweep.speeds()),
            # Every seed's timetable, so the page draws the giant in step with
            # any replay and never draws a random number itself.
            "lights": served(manifest) if manifest.lights else None,
        }
    elif manifest.course.kind == "stage":
        # The stage's floor and its cap, so the server's placement rules, the workshop's plan and
        # the drawn stage read the same numbers, as the walls are served for a lane.
        summary |= {
            "size_m": list(manifest.course.size_m),
            "max_ducks": manifest.course.max_ducks,
            # Where a duck may start, as arena.timeline refuses it: the workshop's placement plan
            # turns a spot magenta with the loader's own numbers rather than copies of them.
            "edge_margin_m": EDGE_MARGIN_M,
            "min_spacing_m": MIN_SPACING_M,
        }
    else:
        summary |= {
            "ring_m": manifest.course.ring_m,
            "string_m": manifest.course.string_m,
            "pit_m": manifest.course.pit_m,
            "pit_depth_m": manifest.course.pit_depth_m,
            # The capsules the physics compiles: the page draws what the ducks bounce off, never a
            # second arithmetic of it; the string it draws as recorded (/runs/{id}/string).
            "ropes": _capsules(ring_ropes(manifest.course), RING_ROPE_RADIUS_M),
            "posts": _capsules(ring_posts(manifest.course), RING_POST_RADIUS_M),
            "bout": {
                "time_limit_s": manifest.bout.time_limit_s,
                "bouts_to_win": manifest.bout.bouts_to_win,
                "max_bouts": manifest.bout.max_bouts,
            },
        }
    return summary


def _event_or_404(event_id: str) -> Manifest:
    try:
        return load_event(event_id)
    except ManifestError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _withdrawn(store) -> frozenset[str]:
    return frozenset(w.run_id for w in store.withdrawals())


def _voted() -> dict:
    """Every event that takes ballots, with its rules. The fold needs both."""
    return {m.id: m.vote for m in all_events() if m.vote is not None}


def _event_ballots(request: Request, manifest: Manifest, now: datetime) -> list:
    """This event's ballots inside its own window: what its voted board counts."""
    days = manifest.vote.window_days
    # Filtered to THIS event, like points.boards_by_user already does — ballots.since() returns
    # every votable event's ballots inside the window, and without this an event's tally would
    # read another event's votes too. Correct today only because run ids are globally unique,
    # which made the leak invisible rather than absent.
    own = [b for b in request.app.state.ballots.since(votes.first_day(now, days)) if b.event_id == manifest.id]
    return votes.window(own, now, days)


def _ballots(request: Request, rules: dict, now: datetime) -> list:
    """Every ballot inside the widest window any votable event declares.

    Takes `rules` and `now` rather than computing them itself, so a request
    that also needs them (every caller does) parses the event programme once.
    """
    if not rules:
        return []
    widest = max(v.window_days for v in rules.values())
    return request.app.state.ballots.since(votes.first_day(now, widest))


def _all_runs(store) -> list[RunRecord]:
    """Every event's log, because points and ladders are across the programme."""
    return [record for manifest in all_events() for record in store.runs(manifest.id)]


@router.get("/events")
def list_events() -> dict:
    # Sorted here, once, rather than in the page: the order is a property of
    # the programme, and every client should read it the same way.
    programme = sorted(all_events(), key=lambda m: (m.order, m.title))
    return {"events": [event_summary(m) for m in programme]}


def _board_row(row) -> dict:
    """The fields every board shows, timed or voted."""
    record = row.record
    return {
        "rank": row.rank,
        "user": record.user,
        "policy_name": record.policy_name,
        "livery": record.livery,
        "score": record.score,
        "command_vx": record.command_vx,
        # Whether this row offers a download. False for runs recorded
        # before policies were kept, so the page shows nothing rather
        # than a link that 404s.
        "model_stored": record.model_stored,
        "env_url": record.env_url,
        # The single rule the board renders from: `model_stored` or a
        # Hub-backed source. See RunRecord.offers_download.
        "offers_download": record.offers_download,
        "policy_url": (record.source or {}).get("url"),
        "robot_command": record.robot_command,
        "seeds_finished": record.seeds_finished,
        "seeds_total": len(record.per_seed),
        "run_id": record.run_id,
        "submitted_at": record.submitted_at,
        # Who performs, duck by duck (arena.cast): a lane is a board row, so the row carries each
        # duck's place, its rig, what the replay sings and opens its beak from, and whose policy it
        # plays. A race's row is one duck of the event's rig.
        "cast": record.cast,
        "trace_seed": record.trace_seed,
    }


@router.get("/events/{event_id}/leaderboard")
def event_leaderboard(event_id: str, request: Request) -> dict:
    manifest = _event_or_404(event_id)
    config = request.app.state.config
    store = request.app.state.store
    withdrawn = _withdrawn(store)
    records = store.runs(manifest.id)

    if manifest.metric == "votes":
        # Votes are not a score but a count in a window (arena/votes.py), hence their own
        # function; index.sort_key ranks every scored event in its metric's direction.
        kept = _event_ballots(request, manifest, datetime.now(UTC))
        rows = votes.standings(votes.pool(records, withdrawn), kept)
        out = [_board_row(row) for row in rows]
        for shaped, row in zip(out, rows):
            shaped["votes"], shaped["shown"], shaped["rate"] = row.votes, row.shown, row.rate
        return {"event": event_summary(manifest), "rows": out}

    rows = leaderboard(records, entrant=config.entrant, withdrawn=withdrawn)
    return {"event": event_summary(manifest), "rows": [_board_row(row) for row in rows]}


@router.get("/standings")
def player_standings(request: Request) -> dict:
    """One ladder across every event: the sum of each player's receipts, ranked."""
    store = request.app.state.store
    rules, now = _voted(), datetime.now(UTC)
    cards = standings(
        receipts(
            _all_runs(store),
            _withdrawn(store),
            ballots=_ballots(request, rules, now),
            voted=rules,
            now=now,
            cups=all_cups(store),
        )
    )
    return {"rows": [{"rank": c.rank, "user": c.user, "points": c.points} for c in cards]}


@router.get("/players/{user}")
def player_page(user: str, request: Request) -> dict:
    """A player's total, rank, every publication they made and every cup they played, newest first."""
    store = request.app.state.store
    runs, withdrawn = _all_runs(store), _withdrawn(store)
    mine = sorted((r for r in runs if r.user == user), key=lambda r: r.submitted_at, reverse=True)
    if not mine:
        raise HTTPException(status_code=404, detail=f"{user!r} has not published yet")
    rules, now = _voted(), datetime.now(UTC)
    ballots = _ballots(request, rules, now)
    cups = all_cups(store)
    card = next(
        (c for c in standings(receipts(runs, withdrawn, ballots, rules, now, cups=cups)) if c.user == user),
        None,
    )
    events = {m.id: m for m in all_events()}
    seen = store.seen()
    by_event: dict[str, list[RunRecord]] = defaultdict(list)
    for run in runs:
        by_event[run.event_id].append(run)
    # A voted event ranks on its rate, not on time, so its rows come off its own
    # board the way the podium does: the run in the pool holds a rank and a
    # rate, an older run of the same person holds neither.
    voted_rows = {
        row.record.run_id: row
        for event_id, rows in boards_by_user(runs, withdrawn, ballots, rules, now).items()
        if events[event_id].metric == "votes"
        for row in rows
    }
    publications = []
    for run in mine:
        voted = events[run.event_id].metric == "votes"
        place = standing(by_event[run.event_id], run.run_id, withdrawn=withdrawn)
        row = voted_rows.get(run.run_id)
        publications.append({
            "run_id": run.run_id,
            "event_id": run.event_id,
            "event_title": events[run.event_id].title,
            "metric": events[run.event_id].metric,
            "policy_name": run.policy_name,
            "score": run.score,
            "seeds_finished": run.seeds_finished,
            "seeds_total": len(run.per_seed),
            "rank": (row.rank if row else None) if voted else place.rank,
            "on_board": row is not None if voted else place.on_board,
            "withdrawn": run.run_id in withdrawn,
            "submitted_at": run.submitted_at,
            "seen": run.run_id in seen,
            # None off a timed event, a rate and a count off a voted one — so the
            # page can tell a reader what the rank next to it was EARNED by. A
            # bare "#1 · 18.46s" reads as a time on a board actually ranked
            # by votes.
            "votes": (row.votes if row else 0) if voted else None,
            "rate": (row.rate if row else 0.0) if voted else None,
        })
    return {
        "user": user,
        "points": card.points if card else 0,
        "rank": card.rank if card else None,
        "publications": publications,
        "cups": [
            {"event_id": cup.event_id, "event_title": events[cup.event_id].title, "number": cup.number,
             "starts_at": cup.order["starts_at"], "reached": got}
            for cup in sorted(cups, key=lambda cup: cup.premiere_at, reverse=True) if revealed_final(cup, now)
            for entrant, got in zip(cup.entrants, reached(cup)) if entrant.user == user
        ],
    }


def _find_run(store, run_id: str) -> RunRecord:
    """Scan every event for a run id.

    Run ids are globally unique, so the id alone addresses a run and the URL
    needs no event. With one small local store, scanning is cheaper than
    maintaining an index; the deployed version gets the in-memory index instead.
    """
    for manifest in all_events():
        for record in store.runs(manifest.id):
            if record.run_id == run_id:
                return record
    raise HTTPException(status_code=404, detail=f"no such run: {run_id!r}")


@router.get("/runs/{run_id}")
def run_detail(run_id: str, request: Request) -> dict:
    """One run and everything its page shows: where it stands, what it earned,
    whether its author has seen it. Placed by `index.standing`, priced by
    `points.receipts` — nothing is decided here."""
    store = request.app.state.store
    record = _find_run(store, run_id)
    runs, withdrawn = _all_runs(store), _withdrawn(store)
    rules, now = _voted(), datetime.now(UTC)
    manifest = load_event(record.event_id)
    if manifest.metric == "votes":
        # A voted event's publication stands where its rate puts it, as on the event's own board
        # and the player's page: on a stage, a time would only be the performance's length.
        rank, on_board, rows = votes.placed(store.runs(record.event_id), run_id,
                                            _event_ballots(request, manifest, now), withdrawn)
        board = [{**_board_row(row), "votes": row.votes, "shown": row.shown, "rate": row.rate,
                  "you": row.record.run_id == record.run_id} for row in rows]
    else:
        place = standing(store.runs(record.event_id), run_id, withdrawn=withdrawn)
        rank, on_board = place.rank, place.on_board
        board = [{**_board_row(row), "you": row.record.run_id == record.run_id} for row in place.board]
    return {
        "run_id": record.run_id,
        "event": event_summary(manifest),
        "user": record.user,
        "policy_name": record.policy_name,
        "livery": record.livery,
        # Every duck, credited: the page names each borrowed policy's author and links its repo.
        "cast": record.cast,
        "score": record.score,
        "command_vx": record.command_vx,
        "seeds_finished": record.seeds_finished,
        "seeds_total": len(record.per_seed),
        "per_seed": [seed_row(s) for s in record.per_seed],
        "trace_seed": record.trace_seed,
        "submitted_at": record.submitted_at,
        "runner_version": record.runner_version,
        "offers_download": record.offers_download,
        "policy_url": (record.source or {}).get("url"),
        "robot_command": record.robot_command,
        "env_url": record.env_url,
        "withdrawn": record.run_id in withdrawn,
        "on_board": on_board,
        "rank": rank,
        # The same columns as the event's board: the page draws the same table.
        "board": board,
        # Podium receipts are HELD, so this list can change between two reads.
        "receipts": [
            {"act": r.act, "points": r.points}
            # No cup: its receipts are paid to the matches that decided them, never to a run.
            for r in receipts(runs, withdrawn, _ballots(request, rules, now), rules, now)
            if r.source_id == record.run_id
        ],
        "seen": record.run_id in store.seen(),
    }


# Same cap the intake enforces, so a download cannot be larger than an upload
# was allowed to be.
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")


def safe_stem(*parts: str) -> str:
    """A filename stem a person can find again, from submitter-supplied text.

    Sanitised rather than trusted: a policy called `../../etc/passwd` or one
    with a quote in it must not be able to shape a Content-Disposition header
    or a path. Dots are dropped, so `..` and `policy.onnx.exe` are gone too.
    """
    stem = _SAFE_NAME.sub("-", "-".join(parts))
    stem = re.sub(r"-{2,}", "-", stem).strip("-")[:60].strip("-")
    return stem or "policy"


def policy_filename(policy_name: str, user: str) -> str:
    return f"{safe_stem(user, policy_name)}.onnx"


@router.get("/runs/{run_id}/policy")
def run_policy(run_id: str, request: Request) -> Response:
    """The published .onnx itself, so anyone can race someone else's policy.

    This is what makes the board more than a scoreboard: a time you cannot
    reproduce is a claim, and a time whose weights you can download and run
    yourself is a result. Only published runs are here — a trial is evaluated
    and kept nowhere, which is the whole point of having a trial button.
    """
    store = request.app.state.store
    record = _find_run(store, run_id)
    source = record.source or {}
    if source.get("kind") == "hub" and source.get("url"):
        # The weights live with their author. Redirect rather than proxy: the
        # Hub serves them faster than this Space can, and a proxied download
        # would put every byte through a 2-vCPU container.
        return RedirectResponse(source["url"])
    if not record.model_stored:
        raise HTTPException(
            status_code=404,
            detail=f"run {run_id} was recorded before policies were kept, "
            "so its weights are not in the store",
        )
    return Response(
        content=store.model(record.model_sha256),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition":
                f'attachment; filename="{policy_filename(record.policy_name, record.user)}"',
            # The name is a hash of the contents, so the bytes behind this run
            # can never change. Worth caching hard.
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Model-SHA256": record.model_sha256,
        },
    )


def _seed_key(record: RunRecord, seed: int | None) -> int | None:
    """The seed to read a trace file with: a lights event keeps a trace per seed, the run's trace
    seed unless asked; any other keeps its trace seed's alone, which is read without a key."""
    if load_event(record.event_id).lights is not None:
        return record.trace_seed if seed is None else seed
    if seed is None or seed == record.trace_seed:
        return None
    raise HTTPException(status_code=404, detail=f"run {record.run_id} keeps no trace of seed {seed}")


def _no_trace_of(record: RunRecord, seed: int | None) -> HTTPException:
    return HTTPException(status_code=404, detail=f"run {record.run_id} keeps no trace of seed {seed}")


@router.get("/runs/{run_id}/trace")
def run_trace(run_id: str, request: Request, seed: int | None = None) -> Response:
    """Raw little-endian float32, TRACE_WIDTH values per frame, every duck's frames
    one duck after another (`frames_response`).

    The stored form is compressed float16 npz, which a browser cannot read. This
    decodes it server-side so the frontend is one `new Float32Array(buffer)` away
    from a replay — no numpy-in-JavaScript, no base64 bloat.

    `seed` picks which seed's trace a Sock Heist run serves (its trace seed unless
    asked; X-Caught-Frame says where that seed's duck was caught); any other run
    serves its trace seed and no other.
    """
    store = request.app.state.store
    record = _find_run(store, run_id)  # 404 before touching the trace file
    key = _seed_key(record, seed)
    blob = store.trace(run_id)
    try:
        response = frames_response(decode(blob, key))
    except KeyError:
        raise _no_trace_of(record, key) from None
    if key is not None and (caught := decode_caught(blob, key)) is not None:
        response.headers["X-Caught-Frame"] = str(caught)
    return response


@router.get("/runs/{run_id}/settle")
def run_settle(run_id: str, request: Request, seed: int | None = None) -> Response:
    """The untimed settle that led into the trace, from the reset pose, in the
    trace's own format: where a clip starts. Empty for a run stored before
    settles were recorded. `seed` is the trace route's."""
    store = request.app.state.store
    record = _find_run(store, run_id)
    key = _seed_key(record, seed)
    try:
        return frames_response(decode_settle(store.trace(run_id), key))
    except KeyError:
        raise _no_trace_of(record, key) from None


@router.get("/runs/{run_id}/string")
def run_string(run_id: str, request: Request) -> Response:
    """A tug's string, the settle's frames then the timed ones (`points_response`); a 404 for a run without one."""
    store = request.app.state.store
    _find_run(store, run_id)
    try:
        settle, string = decode_string(store.trace(run_id))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"run {run_id} has no string") from None
    return points_response(settle, string)


def points_response(settle: np.ndarray, string: np.ndarray) -> Response:
    """A string's (frames, 17, 3) points on the wire: little-endian float32, the settle's frames then the
    timed ones. X-Frame-Count counts the timed frames, X-Settle-Frame-Count the settle's."""
    return Response(
        content=np.ascontiguousarray(np.concatenate([settle, string]), dtype="<f4").tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Frame-Count": str(len(string)),
            "X-Settle-Frame-Count": str(len(settle)),
            "X-Point-Count": str(string.shape[1]),
            "Cache-Control": "no-store",
        },
    )


def frames_response(ducks: np.ndarray) -> Response:
    """A (ducks, frames, TRACE_WIDTH) trace on the wire: little-endian float32, duck-major, so one
    duck's bytes are what a lone duck's always were. X-Frame-Count counts one duck's frames."""
    return Response(
        content=np.ascontiguousarray(ducks, dtype="<f4").tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Frame-Count": str(ducks.shape[1]),
            "X-Duck-Count": str(ducks.shape[0]),
            "Cache-Control": "no-store",
        },
    )


@router.get("/runs/{run_id}/clip")
def run_clip(run_id: str, request: Request) -> JSONResponse:
    """Where this run's clip stands, and its files when it is ready. Polled by
    the publication page while a render is owed, so never cached.

    The store answers only for what it has written — a clip, or the reason
    there is none. Everything in between is the worker's to answer: whether the
    run is waiting in a line or being photographed right now, and how far in.
    A backfilled run marks nothing pending at all, so the store alone would
    call its clip `none` all the way through the making of it."""
    store = request.app.state.store
    _find_run(store, run_id)
    state, written = store.clip_state(run_id)
    if state == "ready":
        body = {
            "state": state,
            "poster": clip_url(run_id, written["poster"], written),
            "layouts": {
                name: {"url": clip_url(run_id, layout["file"], written), "width": layout["width"],
                       "height": layout["height"], "seconds": layout["seconds"]}
                for name, layout in written["layouts"].items()
            },
        }
    elif state == "failed":
        body = {"state": state, "reason": written.get("reason"),
                "failed_at": written.get("failed_at")}
    elif (standing := request.app.state.clips.progress(run_id)) is None:
        # Nothing written and no worker holding it. A pending marker that
        # outlived the process which owed it is still owed — the next drain
        # takes it — so waiting is honest there; nothing at all is not.
        body = {"state": "queued", "ahead": None} if state == "pending" else {"state": "none"}
    elif "ahead" in standing:
        body = {"state": "queued", **standing}
    else:
        body = {"state": "rendering", **standing}
    return JSONResponse(body, headers={"Cache-Control": "no-store"})


_CLIP_TYPES = {"mp4": "video/mp4", "png": "image/png"}


def clip_url(run_id: str, name: str, manifest: dict, origin: str = "") -> str:
    """Where one of a clip's files is served, versioned by the render it
    belongs to — the route below caches them as immutable."""
    return f"{origin}/api/runs/{run_id}/clip/{name}?v={clip_version(manifest)}"


@router.get("/runs/{run_id}/clip/{name}")
def run_clip_file(run_id: str, name: str, request: Request, download: int = 0) -> FileResponse:
    """A clip's file; `download=1` makes the answer an attachment with a name worth keeping."""
    store = request.app.state.store
    record = _find_run(store, run_id)
    stem = safe_stem(record.user, record.policy_name, name.removesuffix(".mp4"))
    return clip_file_response(
        store, run_id, name,
        f'attachment; filename="microduck-arena-{stem}.mp4"' if download and name.endswith(".mp4") else None,
    )


def clip_file_response(store, clip_id: str, name: str, disposition: str | None = None) -> FileResponse:
    """A ready clip's file. Streamed from here because the dataset is private; the
    bytes behind a ready clip never change, so cached hard."""
    if name not in CLIP_MEDIA or store.clip_state(clip_id)[0] != "ready":
        raise HTTPException(status_code=404, detail=f"no clip file {name!r} for {clip_id}")
    headers = {"Cache-Control": "public, max-age=31536000, immutable"}
    if disposition:
        headers["Content-Disposition"] = disposition
    return FileResponse(
        store.clip_file(clip_id, name), media_type=_CLIP_TYPES[name.rsplit(".", 1)[-1]], headers=headers,
    )
