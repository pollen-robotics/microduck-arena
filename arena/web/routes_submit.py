"""Entering a policy: a Hub repo, raced here, recorded on the board.

The server does the timing: it downloads the repo at the revision given, validates the ONNX
with the same `load_policy` the CLI uses (so a refusal carries the engine's own wording),
races it and appends the run to the log. Nothing is recorded unless the evaluation completes.

An entry is made by `uv run publish … --enter`, from a shell or from the workshop, with the
user's Hugging Face token; the site has no entry form, and nothing here races a policy
without entering it. The Space writes into no one's namespace and keeps no weights.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from ..cast import cast_of, load_borrowed
from ..constants import RUNNER_VERSION
from ..envlink import EnvLinkError, normalise_env_url
from ..evaluate import evaluate, evaluate_at, seed_row, trace_file
from ..hub_fetch import FetchedPolicy, FetchError, fetch_policy, hub_name, parse_repo_ref
from ..manifest import ManifestError, load_event
from ..policy import PolicyError, load_policy
from ..store import RunRecord, Withdrawal, lone_cast, new_id
from .hub_identity import HubUnreachable, TokenRefused, whoami
from .routes_auth import current_user
from .routes_read import _withdrawn
from .session import Session

router = APIRouter(prefix="/api")


def _fetch_from_hub(repo_id: str, revision: str | None, event) -> FetchedPolicy:
    """Wrapped so tests replace one function rather than the Hub client."""
    return fetch_policy(repo_id, revision=revision, event=event)


def _require_session(request: Request) -> Session:
    """Withdrawing an entry and marking it seen are its author's alone: both need a signed-in name.

    Watching does not: the board, the replays and the downloads are open to
    anyone who can open the page.
    """
    session = current_user(request)
    if session is None:
        raise HTTPException(status_code=401, detail="Please sign in with Hugging Face.")
    return session


ENTER_WITH_PUBLISH = (
    "Enter from the workshop, or with `uv run publish … --enter`: it sends your Hugging Face "
    "token, which says who you are."
)


def _whoami(token: str):
    """Wrapped so tests replace one function rather than the Hub."""
    return whoami(token)


async def _entrant(request: Request) -> tuple[str, frozenset[str] | None]:
    """Who is entering, and the organisations whose repos they may enter too.

    On the Space: the Hugging Face token `publish --enter` sends, checked with the Hub and then
    dropped. The session cookie does not enter: the site has no entry form. A local Arena has no
    identity to check: its dev user enters, from any namespace (None).
    """
    config = request.app.state.config
    if not config.oauth_enabled:
        return config.dev_user, None
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail=ENTER_WITH_PUBLISH)
    try:
        user = await run_in_threadpool(_whoami, token.strip())
    except TokenRefused:
        raise HTTPException(status_code=401, detail="Hugging Face refused this token.") from None
    except HubUnreachable as exc:
        raise HTTPException(
            status_code=503, detail=f"The Arena could not ask Hugging Face who you are ({exc}). Try again."
        ) from None
    if user.kind != "user":
        raise HTTPException(
            status_code=403,
            detail="An entry is credited to a person: enter with your own token, not an organisation's.",
        )
    return user.name, user.orgs


def _require_own_repo(repo_id: str, user: str, orgs: frozenset[str] | None) -> None:
    """Credit goes to whoever enters: a repo in someone else's namespace is theirs to enter."""
    if orgs is None:
        return
    try:
        owner = parse_repo_ref(repo_id)[0].split("/")[0].casefold()
    except FetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if owner != user.casefold() and owner not in {org.casefold() for org in orgs}:
        raise HTTPException(
            status_code=403,
            detail=f"{repo_id} is not yours to enter: its namespace is neither {user} nor one of your organisations.",
        )


def _event_or_404(event_id: str):
    try:
        return load_event(event_id)
    except ManifestError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _speed(manifest, value: str | None) -> float | None:
    """A trial's chosen speed, or None for the full sweep — and always None on a stage, which plays
    its timeline at no speed: a speed sent to one is ignored.

    Clamped to the event's own declared range rather than rejected: the picker
    is built from that range, so a value outside it is a stale page or a hand-
    made request, and neither is worth a 400. Anything unparseable falls back to
    the sweep, which is the honest answer to "I don't know what you asked for".
    """
    if manifest.sweep is None or value is None or str(value).strip() == "":
        return None
    try:
        vx = float(value)
    except (TypeError, ValueError):
        return None
    return min(manifest.sweep.hi, max(manifest.sweep.lo, vx))


def _env_url(value: str | None) -> str | None:
    """The submitter's training-environment link, or a 400 saying why not.

    400 rather than silently dropping it: someone who typed a link and got a row
    with no button would have no idea which of the two happened.
    """
    try:
        return normalise_env_url(value)
    except EnvLinkError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _livery(value: str | None) -> str:
    """Capped, not validated against a list.

    The four names live in the frontend; the viewer falls back to `classic` for
    anything it does not recognise, and that fallback is tested. Keeping a copy
    of the list here would give the two sides a chance to disagree.
    """
    return (value or "classic").strip()[:32] or "classic"


DESCRIPTION_MAX = 500


def _description(fetched: FetchedPolicy) -> str | None:
    """What the author wrote for the commentators, from the manifest: None when it is missing, too
    long, or only one of the defaults `publish` falls back to (the training task's id, the name)."""
    manifest = fetched.manifest or {}
    text = manifest.get("description")
    if not isinstance(text, str):
        return None
    text = text.strip()
    training = manifest.get("training")
    task_id = training.get("task_id") if isinstance(training, dict) else None
    defaults = {str(manifest.get("name") or "").strip(), str(task_id or "").strip()}
    return text if 1 <= len(text) <= DESCRIPTION_MAX and text not in defaults else None


def _label(name: str | None, fallback: str) -> str:
    # Capped: this is submitter-supplied text that ends up on a shared board, and
    # nothing downstream bounds it. 80 characters is generous for a policy name.
    return ((name or "").strip() or fallback)[:80]


ENTER_A_REPO = "The Arena enters a Hugging Face repo: enter from the workshop, or with `uv run publish … --enter`."


def _seed_rows(per_seed) -> list[dict]:
    return [seed_row(s) for s in per_seed]


def _evaluate(manifest, policy, command_vx: float | None, cast):
    if command_vx is None:
        return evaluate(manifest, policy, cast)
    return evaluate_at(manifest, policy, command_vx)


def _page_url(request: Request, run_id: str) -> str:
    """Where a browser sees the entry: on Hugging Face, the Space's own page (which hands the
    hash to the Space and opens it for anyone logged in there, private or not); else here."""
    space = request.app.state.config.space_id
    if space:
        return f"https://huggingface.co/spaces/{space}#/r/{run_id}"
    return f"{str(request.base_url).rstrip('/')}/#/r/{run_id}"


def _already_entered(store, event_id: str, user: str, sha256: str, timeline_sha256: str | None) -> RunRecord | None:
    """This user's entry of this very policy, if one is on the board.

    Keyed on the ONNX's sha256 and, on a stage, the timeline's: a retry after a lost answer is
    the same files, while the same weights with another timeline are another performance. Not
    the revision or the speed: a pinned speed can only match or lose to the sweep, which already
    keeps the best. An entry withdrawn, or raced by an older runner, is no longer on the board.
    """
    withdrawn = _withdrawn(store)
    return next(
        (r for r in store.runs(event_id)
         if r.user == user and r.model_sha256 == sha256 and r.timeline_sha256 == timeline_sha256
         and r.runner_version == RUNNER_VERSION and r.run_id not in withdrawn),
        None,
    )


def _answer(record: RunRecord, manifest, page_url: str, already: bool) -> dict:
    return {
        "run_id": record.run_id,
        "user": record.user,
        "policy_name": record.policy_name,
        "livery": record.livery,
        "score": record.score,
        "command_vx": record.command_vx,
        "model_stored": record.model_stored,
        "offers_download": record.offers_download,
        "policy_url": (record.source or {}).get("url"),
        "seeds_finished": record.seeds_finished,
        "seeds_total": len(record.per_seed),
        "per_seed": _seed_rows(record.per_seed),
        "trace_seed": record.trace_seed,
        "page_url": page_url,
        "already_entered": already,
        "course": manifest.course.kind,
        # Every event's: the publish CLI says a rating in centimetres from it; an older CLI ignores it.
        "metric": manifest.metric,
    }


@router.post("/events/{event_id}/submit")
async def submit(
    event_id: str,
    request: Request,
    repo_id: str | None = Form(default=None),
    name: str | None = Form(default=None),
    livery: str | None = Form(default=None),
    command_vx: str | None = Form(default=None),
    env_url: str | None = Form(default=None),
    revision: str | None = Form(default=None),
) -> dict:
    # Who, before any of the expensive work: an entry nobody can be credited with is not worth
    # thirty seconds of a shared CPU.
    user, orgs = await _entrant(request)
    if not repo_id:
        raise HTTPException(status_code=400, detail=ENTER_A_REPO)
    manifest = _event_or_404(event_id)
    _require_own_repo(repo_id, user, orgs)
    # Checked before racing: a link this server will refuse should cost nobody thirty seconds
    # of simulation first.
    link = _env_url(env_url)
    racing = request.app.state.racing
    if user in racing:
        raise HTTPException(status_code=409, detail="Your previous entry is still racing: wait for its result.")
    racing.add(user)
    try:
        return await _enter(request, manifest, user, repo_id, revision, name, livery, command_vx, link)
    finally:
        racing.discard(user)


async def _enter(request, manifest, user, repo_id, revision, name, livery, command_vx, link) -> dict:
    try:
        # Offloaded to a worker thread: this is a network call. On a stage it also reads every
        # policy the troupe borrows, each at its commit.
        fetched = await run_in_threadpool(_fetch_from_hub, repo_id, revision, manifest)
    except FetchError as exc:
        # 400, not 500: the reference is the problem, and the message is written to be read
        # by the person who sent it.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        # An ONNX session load, off the event loop. The 64 MiB cap is checked here too.
        policy = await run_in_threadpool(load_policy, fetched.path)
    except PolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    store = request.app.state.store
    kept = _already_entered(store, manifest.id, user, policy.sha256, fetched.timeline_sha256)
    if kept is not None:
        return _answer(kept, manifest, _page_url(request, kept.run_id), already=True)

    cast = None
    if manifest.course.kind == "stage":
        try:
            # Every borrowed policy's session too, off the event loop: each loaded once however
            # many ducks play it, and one that does not load is refused naming its first duck.
            borrowed = await run_in_threadpool(load_borrowed, fetched.troupe, fetched.borrowed)
        except PolicyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        cast = cast_of(manifest, fetched.troupe, policy, fetched.rig, borrowed)

    # `command_vx` pins the commanded speed for this entry; omit it for the full
    # sweep, which stays the default.
    #
    # An earlier version refused it here, on the reasoning that a board where
    # entrants choose their own speed ranks whoever guessed best. That objection
    # does not survive the arithmetic: the sweep already keeps the BEST time
    # across every speed in the range, including whichever one you would have
    # pinned. Pinning can therefore only match or lose to sweeping — it is
    # self-penalising, not exploitable.
    #
    # One honest caveat. The sweep's shortlist is chosen from a ONE-SEED scan, so
    # it can miss a speed that would have won over five. A pinned entry can
    # occasionally beat the sweep's answer for the same policy by a hair. The
    # board shows each row's commanded speed, so this is visible rather than
    # hidden.
    try:
        # Five simulated runs per speed, CPU-bound: off the event loop.
        result = await run_in_threadpool(
            _evaluate, manifest, policy, _speed(manifest, command_vx), cast.performers if cast else None
        )
    except PolicyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record = RunRecord(
        run_id=new_id(),
        event_id=manifest.id,
        # Zero-padded ISO-8601 ending in Z. arena/index.py breaks a full tie by
        # comparing this as a STRING, so an isoformat() offset would misorder it.
        submitted_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        user=user,
        policy_name=_label(name, hub_name(fetched)),
        source={
            "kind": "hub",
            "repo_id": fetched.repo_id,
            "filename": fetched.filename,
            "revision": fetched.revision,
            "url": fetched.url,
        },
        model_sha256=policy.sha256,
        score=result.score,
        command_vx=result.command_vx,
        seeds_finished=result.seeds_finished,
        per_seed=result.per_seed,
        trace_seed=result.trace_seed,
        runner_version=result.runner_version,
        # The weights live in the author's own repo, at this revision; the
        # Space keeps none, and anyone can download and race them from there.
        model_stored=False,
        env_url=link,
        livery=_livery(livery),
        description=_description(fetched),
        timeline_sha256=fetched.timeline_sha256,
        cast=cast.record if cast else lone_cast(),
    )
    store.append(
        record, trace_file(result)
    )

    clips = request.app.state.clips
    if clips.available:
        # Owed now, rendered later: the response does not wait for a video.
        # The run is already on the board at this point, so a marker that
        # fails to write must not turn a successful publish into a 500.
        try:
            store.mark_clip_pending(
                record.run_id, record.user, record.event_id, record.submitted_at
            )
            clips.enqueue(record.run_id)
        except Exception as exc:  # noqa: BLE001 — see above
            print(f"clip: {record.run_id} not queued ({type(exc).__name__}: {exc})")

    return _answer(record, manifest, _page_url(request, record.run_id), already=False)


@router.post("/runs/{run_id}/withdraw")
def withdraw(run_id: str, request: Request) -> dict:
    """Take one of YOUR OWN entries off the board.

    Not a delete. The log is append-only, so this appends a withdrawal: the row
    leaves the board, the run stays on disk, and the history is never rewritten.

    It also stops recovery resurrecting the entry. Without that the button would
    appear to work and the row would be back at the next restart, because the
    policy is still published on the Hub and the boot reconciliation would
    re-race it.

    The policy repo itself is untouched. It belongs to its author, who can
    delete it on the Hub if they want to. The Space holds no permission on
    anyone's repo: the sign-in behind a withdrawal asks for no Hub scope, and
    the token an entry arrives with goes to whoami-v2 once and is dropped.
    """
    from datetime import UTC, datetime

    from .routes_read import _find_run

    session = _require_session(request)
    store = request.app.state.store
    record = _find_run(store, run_id)

    # Ownership is decided from the SESSION, never from anything the browser
    # sent. A withdrawal is destructive to someone's standing, and the only
    # thing that may authorise it is who the server believes you are.
    if record.user != session.username:
        raise HTTPException(
            status_code=403,
            detail=f"{run_id} was published by {record.user}, not you.",
        )

    source = record.source or {}
    store.withdraw(
        Withdrawal(
            run_id=record.run_id,
            event_id=record.event_id,
            user=record.user,
            withdrawn_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            repo_id=source.get("repo_id"),
            revision=source.get("revision"),
        )
    )
    # The channel must not play a run its author just took off the board.
    request.app.state.programme.invalidate()
    return {"withdrawn": record.run_id, "event_id": record.event_id}


@router.post("/runs/{run_id}/seen")
def mark_seen(run_id: str, request: Request) -> dict:
    """The author has opened this run's page: the reveal has played, the dot goes out.

    Owner-only, decided from the session exactly as a withdrawal is. Idempotent:
    the store keeps the first visit and ignores the rest.
    """
    from .routes_read import _find_run

    session = _require_session(request)
    store = request.app.state.store
    record = _find_run(store, run_id)
    if record.user != session.username:
        raise HTTPException(
            status_code=403,
            detail=f"{run_id} was published by {record.user}, not you.",
        )
    store.mark_seen(
        record.run_id, record.user, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    return {"seen": True}
