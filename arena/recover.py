"""Rebuild the board from the Hub.

The run log can be lost — a Space whose `ARENA_DATASET`/`HF_TOKEN` are unset
keeps it on a container filesystem that every redeploy wipes. The POLICIES are
not lost with it: publishing writes each one into its author's own public repo,
tagged and manifested. So the board is re-derivable, and this is what derives it.

Two things this deliberately does NOT do.

It does not trust a recovered ranking. Times are RE-MEASURED by the same harness
that measures a live submission; nothing is read back from the Hub except the
weights, the author and the name. A leaderboard you cannot re-verify is a
leaderboard you should not restore.

And it does not enrol anyone who did not ask. The default scope is repos whose
`manifest.json` says `published_by: "microduck-arena"` — policies that went
through this Arena. `all_tagged=True` widens it to every `microduck-policy` repo
on the Hub, which is a census rather than a recovery, and is opt-in for that
reason.

Hub access is injected, so the planning logic is testable with no network.
"""

from dataclasses import dataclass

from .constants import RUNNER_VERSION
from .hub_fetch import rig_of
from .manifest import higher_wins

# The tag the ecosystem searches policies by.
TAG = "microduck-policy"
PUBLISHER = "microduck-arena"


@dataclass(frozen=True)
class Candidate:
    """A policy on the Hub that could hold a place on the board."""

    repo_id: str
    revision: str
    user: str
    policy_name: str
    rig: str
    # The event it was originally raced on, when the manifest records one.
    # Manifests written before this field existed have None, and those policies
    # are recovered onto every event their rig can enter.
    event_id: str | None


def _candidate(repo_id: str, revision: str, manifest: dict) -> Candidate | None:
    rig = rig_of(manifest or {})
    if rig is None:
        return None  # a policy for a machine this Arena has no event for
    user, _, slug = repo_id.partition("/")
    name = (manifest.get("name") or "").strip() or slug.removeprefix("microduck-")
    return Candidate(
        repo_id=repo_id,
        revision=revision,
        user=user,
        policy_name=name,
        rig=rig,
        event_id=((manifest.get("arena") or {}).get("event")) or None,
    )


def candidates(list_repos, read_manifest, all_tagged: bool = False) -> list[Candidate]:
    """Every Hub policy worth restoring, newest first.

    `list_repos()` yields `(repo_id, revision)`; `read_manifest(repo_id)` returns
    the parsed `manifest.json` or None. Both are injected so this needs no
    network to test.

    A repo with no manifest, or one this Arena did not publish, is skipped unless
    `all_tagged` is set. A repo whose manifest names a machine we have no event
    for is always skipped — racing it would be meaningless.
    """
    found = []
    for repo_id, revision in list_repos():
        manifest = read_manifest(repo_id)
        if not manifest:
            continue
        if not all_tagged and manifest.get("published_by") != PUBLISHER:
            continue
        candidate = _candidate(repo_id, revision, manifest)
        if candidate is not None:
            found.append(candidate)
    return found


def events_for(candidate: Candidate, events) -> list:
    """Which events this candidate belongs on.

    Its own if the manifest recorded one. Otherwise every event its rig can
    enter — the honest fallback for manifests written before the field existed,
    since the alternative is discarding the entry entirely. Never the tug, though:
    entering a versus enters its cup, and that takes a policy trained to pull,
    entered on purpose, not a walker found on the Hub.
    """
    if candidate.event_id:
        return [e for e in events if e.id == candidate.event_id]
    return [e for e in events if e.rig == candidate.rig and e.course.kind != "tug"]


def already_recorded(records, repo_id: str, revision: str) -> bool:
    """Whether this exact repo revision already holds a place.

    Keyed on the Hub revision rather than a checksum, so deciding costs no
    download. A run from a different RUNNER_VERSION does not count: it was
    measured by different physics and is not comparable.
    """
    for record in records:
        source = record.source or {}
        if (
            record.runner_version == RUNNER_VERSION
            and source.get("kind") == "hub"
            and source.get("repo_id") == repo_id
            and source.get("revision") == revision
        ):
            return True
    return False


def plan(found, events, runs_for_event, withdrawn=()) -> list[tuple[Candidate, object]]:
    """The (candidate, event) pairs that are missing and would have to be raced.

    `runs_for_event(event_id)` returns the records already stored for it. This is
    the whole reconciliation: on a durable store with nothing lost it returns an
    empty list, which is why running it at every boot costs one Hub listing and
    nothing else.
    """
    # Keyed on (repo_id, revision), the same key already_recorded uses. So a
    # withdrawal suppresses exactly the revision it withdrew: republishing the
    # policy is a new commit, a new revision, and it comes back — which is what
    # publishing again should mean.
    suppressed = {
        (w.repo_id, w.revision) for w in withdrawn if w.repo_id and w.revision
    }

    work = []
    for candidate in found:
        if (candidate.repo_id, candidate.revision) in suppressed:
            continue
        for event in events_for(candidate, events):
            if not already_recorded(runs_for_event(event.id), candidate.repo_id, candidate.revision):
                work.append((candidate, event))
    return work


# ── Running the plan ─────────────────────────────────────────────────────
#
# Everything above is pure and testable offline. Everything below touches the
# Hub and the store, and is the thin part.


def hub_reader(api=None, on_event=None):
    """`(list_repos, read_manifest)` against the real Hub.

    Both swallow per-repo failures, because one repo that went private between
    the listing and the read must not abandon a recovery. But neither swallows
    them SILENTLY: every skip goes to `on_event`, or a recovery that quietly
    restores nothing is indistinguishable from one that had nothing to restore.
    """
    import json

    from huggingface_hub import HfApi, hf_hub_download
    from huggingface_hub.errors import HfHubHTTPError

    api = api or HfApi()
    report = on_event or (lambda _message: None)

    def list_repos():
        for model in api.list_models(filter=TAG, limit=200):
            try:
                yield model.id, api.model_info(model.id).sha
            except (HfHubHTTPError, OSError) as exc:
                report(f"skipped {model.id}: unreadable ({type(exc).__name__})")

    def read_manifest(repo_id):
        try:
            with open(hf_hub_download(repo_id, "manifest.json")) as fh:
                return json.load(fh)
        except (HfHubHTTPError, OSError, ValueError) as exc:
            # No manifest, or one that is not JSON. Not a candidate, and the
            # reason is worth saying: a policy missing its manifest looks
            # identical to one nobody published.
            report(f"skipped {repo_id}: no usable manifest.json ({type(exc).__name__})")
            return None

    return list_repos, read_manifest


def recover(store, events, all_tagged=False, reader=None, on_event=None) -> list:
    """Re-race whatever the Hub holds and the store does not. Returns the records.

    Every failure is per-candidate and non-fatal: one unreachable repo, one
    policy the loader rejects, must not abandon the rest of a recovery.
    """
    from datetime import UTC, datetime

    from .cast import cast_of, load_borrowed
    from .evaluate import evaluate, trace_file
    from .hub_fetch import fetch_policy
    from .policy import load_policy
    from .store import RunRecord, lone_cast, new_id

    list_repos, read_manifest = reader or hub_reader(on_event=on_event)
    found = candidates(list_repos, read_manifest, all_tagged=all_tagged)
    work = plan(found, events, lambda event_id: store.runs(event_id), store.withdrawals())

    restored = []
    for candidate, event in work:
        try:
            # At the revision the listing found and against its event: the record says that
            # revision, and a stage's timeline.json is read with the weights it goes with.
            fetched = fetch_policy(candidate.repo_id, revision=candidate.revision, event=event)
            policy = load_policy(fetched.path)
            # A stage plays its troupe, borrowed policies included. One that left the Hub has refused
            # the fetch above: that run cannot be raced again, and the store keeps none of it.
            cast = (cast_of(event, fetched.troupe, policy, fetched.rig, load_borrowed(fetched.troupe, fetched.borrowed))
                    if event.course.kind == "stage" else None)
            result = evaluate(event, policy, cast.performers if cast else None)
            record = RunRecord(
                run_id=new_id(),
                event_id=event.id,
                submitted_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                user=candidate.user,
                policy_name=candidate.policy_name,
                source={
                    "kind": "hub",
                    "repo_id": fetched.repo_id,
                    "filename": fetched.filename,
                    "revision": candidate.revision,
                    "url": fetched.url,
                },
                model_sha256=policy.sha256,
                score=result.score,
                command_vx=result.command_vx,
                seeds_finished=result.seeds_finished,
                per_seed=result.per_seed,
                trace_seed=result.trace_seed,
                runner_version=result.runner_version,
                model_stored=False,
                livery="classic",
                timeline_sha256=fetched.timeline_sha256,
                cast=cast.record if cast else lone_cast(),
            )
            store.append(
                record,
                trace_file(result),
            )
            restored.append(record)
            if on_event:
                score = f"{result.score:.1f} cm" if higher_wins(event.id) else f"{result.score:.3f}s"
                on_event(f"recovered {candidate.repo_id} on {event.id}: {score}")
        except Exception as exc:  # noqa: BLE001
            # Deliberately broad, and reported rather than hidden. A recovery
            # races arbitrary third-party ONNX files through MuJoCo; the set of
            # things one of them can raise is not enumerable, and one failure
            # must not cost the whole restore.
            if on_event:
                on_event(f"skipped {candidate.repo_id} on {event.id}: {type(exc).__name__}: {exc}")
    return restored
