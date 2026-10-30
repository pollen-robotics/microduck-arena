"""Every checkpoint, evaluated: exported as `publish` would, then played with the Arena's own evaluator.

The export is publishing.export. `arena.evaluate` is the code the Space runs, on this machine's
MuJoCo: the score is indicative — only the Space times an entry, and replays drift apart between
machines after a few seconds.

A worker evaluates every checkpoint of the open challenges' runs, one at a time: the newest run first,
its checkpoints in order, so a training's tickets fill in as it goes. A result is stored next to its
checkpoint, per Arena runner version and per FORMAT, trace included, so a page replays it at once. A
checkpoint that cannot be measured — a failed export, a policy that does not load, a race that breaks,
a duck the troupe cannot cast — is stored as a failure, with the checkpoint file's modification time,
and tried again only once that file changes. A troupe's Hub policy that cannot be fetched (an offline
laptop, a Hub outage, a repo gone) is the Hub's state, not the checkpoint's: nothing is stored, and the
worker sets that challenge aside for RETRY_S, evaluating the others' checkpoints meanwhile. A
checkpoint file younger than FRESH_S waits: a local training may still be writing it.

On a stage, each checkpoint plays the challenge's timeline.json with its whole troupe, the checkpoint
as the star ("self"). `troupe.timeline_key` names that performance: an edit, or a local duck's
checkpoint file rewritten, makes every stored evaluation stale. Every ONNX exported is kept beside its
checkpoint and played again, so a stale checkpoint costs a performance, not an export.
"""

import base64
import json
import os
import tempfile
import time

from ..cast import duck_record
from ..constants import RUNNER_VERSION
from ..evaluate import evaluate, seed_row
from ..hub_fetch import FetchError
from ..manifest import load_event
from ..policy import load_policy
from ..stage import summaries
from ..timeline import constant_timeline, load_troupe, solo
from ..trace import as_ducks
from .challenges import timeline_file
from .publishing import PublishError, export
from .runs import find_runs
from .troupe import performers_for, timeline_key

FRESH_S = 30.0
IDLE_S = 5.0
# How long a challenge whose troupe's Hub policy could not be fetched waits before the Hub is asked again.
RETRY_S = 60.0
# What a stored evaluation holds. 2: every duck's trace, duck-major, with the cast and a stage summary
# per duck. 3: a tug's checkpoint carries its string. A body of another form is measured again, as one of
# another runner version is.
FORMAT = 3


def _path(run, n: int):
    return run.path / "workshop" / f"model_{n}.json"


def _mtime(run, n: int) -> float:
    return (run.path / f"model_{n}.pt").stat().st_mtime


def stored(run, n: int, timeline: str | None) -> dict | None:
    """The stored evaluation of checkpoint n on this runner version, played with this timeline — a
    result, or a failure still true of the checkpoint file as it is — or None: never evaluated,
    stale, or unreadable."""
    try:
        body = json.loads(_path(run, n).read_text())
    except (OSError, ValueError):
        return None  # missing, or corrupt (a crash mid-write): as good as never evaluated
    if not isinstance(body, dict) or (body.get("runner_version"), body.get("format")) != (RUNNER_VERSION, FORMAT):
        return None
    if body.get("timeline") != timeline:
        return None  # played with another timeline: stale, a failure included
    if "error" in body:
        try:
            return body if body.get("mtime") == _mtime(run, n) else None
        except OSError:
            return None
    return body


def summary(run, timeline: str | None) -> dict[int, dict]:
    """What each evaluated checkpoint of `run` shows on its ticket, without its trace."""
    keep = ("score", "seeds_finished", "seeds_total", "command_vx")
    found = {}
    for n in run.checkpoints:
        body = stored(run, n, timeline)
        if body is not None:
            row = {"status": "failed"} if "error" in body else {"status": "evaluated", **{k: body[k] for k in keep}}
            if "stage" in body:
                row["stage"] = body["stage"]
            found[n] = row
    return found


def _write(run, n: int, body: dict) -> None:
    """Atomically: a reader (a ticket, a replay) must never see a half-written file. The temp file is
    unique to this write, so two writers of the same checkpoint never race on one temp name."""
    path = _path(run, n)
    path.parent.mkdir(exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(dir=path.parent, delete=False, prefix=path.name, suffix=".tmp")
    try:
        tmp.write(json.dumps(body).encode())
    finally:
        tmp.close()
    os.replace(tmp.name, path)


def _measure(root, run, n: int, challenge, key: str | None) -> dict:
    onnx = export(root, run, n)
    event = load_event(challenge.event)
    body = {"checkpoint": n}
    if event.course.kind == "stage":
        # Without a timeline.json, the troupe of one the event plays: its own command for its time limit.
        troupe = (load_troupe(timeline_file(challenge), event, allow_local=True) if key
                  else solo(constant_timeline(event.command, event.time_limit_s)))
        cast = performers_for(root, troupe, onnx, event.rig, event)
        result = evaluate(event, cast[0].policy, cast)
        # A duck's policy as the timeline names it: "self", a Hub reference, or a local checkpoint.
        body["cast"] = [duck_record(duck.policy, performer.rig, duck) for duck, performer in zip(troupe.ducks, cast)]
        body["stage"] = summaries(result.trace, event.termination)
    else:
        result = evaluate(event, load_policy(onnx))
        body["cast"] = None  # a race: one duck, nothing to place or hear
    if result.string is not None:
        body["string_b64"] = base64.b64encode(result.string.astype("<f4").tobytes()).decode("ascii")
    if result.seed_traces is not None:
        body["caught_frame"] = result.seed_traces[result.trace_seed].caught
    return body | {
        "score": result.score,
        "command_vx": result.command_vx,
        "seeds_finished": result.seeds_finished,
        "seeds_total": len(result.per_seed),
        "per_seed": [seed_row(s) for s in result.per_seed],
        "trace_seed": result.trace_seed,
        # Duck-major, as the Arena serves a trace: the page cuts it into `ducks` traces.
        "ducks": len(as_ducks(result.trace)),
        "trace_b64": base64.b64encode(result.trace.astype("<f4").tobytes()).decode("ascii"),
        "runner_version": result.runner_version,
        "format": FORMAT,
        "timeline": key,
    }


def evaluate_checkpoint(root, run, n: int, challenge) -> dict:
    """Measure checkpoint n with the challenge's timeline as it is now, store what came of it, and
    return that body. A FetchError (a Hub policy of the troupe out of reach) is raised, not stored."""
    mtime = _mtime(run, n)
    key = timeline_key(root, challenge)
    try:
        body = _measure(root, run, n, challenge, key)
    except FetchError:
        raise
    except Exception as exc:  # noqa: BLE001 — stored, so the worker moves on to the next checkpoint
        error = str(exc) if isinstance(exc, PublishError) else f"{type(exc).__name__}: {exc}"
        body = {"checkpoint": n, "error": error, "mtime": mtime, "runner_version": RUNNER_VERSION,
                "format": FORMAT, "timeline": key}
    _write(run, n, body)
    return body


def next_checkpoint(root, challenges, now: float | None = None):
    """(challenge, run, n) to evaluate next, or None: the newest run first, its checkpoints in order."""
    now = time.time() if now is None else now
    keys = {c.event: timeline_key(root, c) for c in challenges}
    runs = sorted(((c, r) for c in challenges for r in find_runs(root, c.task)), key=lambda cr: cr[1].id, reverse=True)
    for challenge, run in runs:
        for n in run.checkpoints:
            if stored(run, n, keys[challenge.event]) is not None:
                continue
            try:
                if now - _mtime(run, n) < FRESH_S:
                    continue
            except OSError:
                continue  # gone while we looked
            return challenge, run, n
    return None


def evaluate_next(ws, now: float | None = None) -> bool:
    """Evaluate one checkpoint of a challenge not set aside; False when none is waiting. A FetchError
    sets its challenge aside for RETRY_S, and is raised for the worker to say."""
    now = time.time() if now is None else now
    ready = [c for c in ws.challenges.values() if ws.aside.get(c.event, now) <= now]
    found = next_checkpoint(ws.root, ready, now)
    if found is None:
        return False
    challenge, run, n = found
    try:
        evaluate_checkpoint(ws.root, run, n, challenge)
    except FetchError:
        ws.aside[challenge.event] = now + RETRY_S
        raise
    return True


def evaluate_forever(ws) -> None:
    while not ws.stopping.is_set():
        try:
            if not evaluate_next(ws):
                ws.stopping.wait(IDLE_S)
        except Exception as exc:  # noqa: BLE001 — one bad run must not stop the worker for the others
            print(f"[workshop] evaluation: {type(exc).__name__}: {exc}", flush=True)
            ws.stopping.wait(IDLE_S)
