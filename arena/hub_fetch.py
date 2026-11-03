"""Fetch a policy that is already on the Hub.

13 of the 14 repos tagged `microduck-policy` ship an `.onnx`, and 11 call it
`policy.onnx` at the root — so that name is preferred, a single differently
named `.onnx` is accepted, and anything ambiguous is refused rather than
guessed. Racing the wrong file out of a repo that holds two would be a silent
wrong answer on a leaderboard.

`info` and `download` are handed in so the selection rules are testable without
a network.

The 64 MiB cap (`arena.policy.MAX_MODEL_BYTES`) is checked against the size
the Hub itself declares for the chosen file, BEFORE `download` is ever
called — a repo can hold anything, and the constraint is "the cap applies to
a fetched policy too," not "eventually, after paying for the download." A
repo that declines to report a size (`None`) is not refused on that account —
an unknown size is not evidence of a large file — and `load_policy` remains
the backstop that catches an oversized file downstream if the declared size
was ever missing or wrong.

A repo's `manifest.json`, when it has one, is read at the same pinned revision
and, when the caller names the event, checked against it before the ONNX is
downloaded: the observation and action sizes, the robot the event races, the
kind of policy it takes — each one the manifest declares. A repo without one
is accepted as before.

A stage entry's `timeline.json` — the command it performs, and when — is read at
the same revision too, when the event named is a stage, and checked with the
Arena's own loader before the weights: a file the Arena will not play is refused
with the reason. A repo without one plays the event's own command. A race never
reads it.

A stage entry's timeline.json may hold a troupe (version 2) whose other ducks play policies of other
repos, each pinned to a full commit. Each one is read once, at that commit, under the entry's own
rules (the ONNX picked, the declared size capped, the manifest checked), after the entry's timeline
and before the entry's weights. Its own timeline.json is never read: in a troupe, every duck plays
the keyframes the entry gives it. A refusal names the first duck that plays it. On a stage each duck
stands on its own rig, legs or rollers, as its manifest says; a race keeps its event's.
"""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .constants import NUM_JOINTS, OBS_SIZE
from .manifest import RIGS
from .policy import MAX_MODEL_BYTES
from .timeline import LOCAL, TimelineError, Troupe, load_troupe, split_reference

PREFERRED = "policy.onnx"
MANIFEST = "manifest.json"
TIMELINE = "timeline.json"
# What this Arena's own publisher (removed) wrote for the roller rig, before
# `uv run publish` described rollers as an accessory of the one microduck.
LEGACY_ROLLERS_MODEL = "microduck passive rollers"


class FetchError(Exception):
    """The reference cannot be resolved, with a reason fit to show a human."""


class PolicyGone(FetchError):
    """The Hub answers 404: the repo or its commit is not there, private or deleted. Unlike a Hub away for a
    moment, it will not be back in a few minutes."""


@dataclass(frozen=True)
class FetchedPolicy:
    repo_id: str
    filename: str
    revision: str
    path: Path
    url: str
    # The repo's manifest.json, parsed, or None when it has none.
    manifest: dict | None = None
    # A stage entry's performance (its timeline.json at the same revision), checked: one duck or a
    # troupe. None when the repo has none (the event's own command plays), for a race, which never
    # reads it, and for a borrowed policy, whose own timeline.json no troupe plays.
    troupe: Troupe | None = None
    # The sha256 of that file's bytes: the same weights with another timeline, or beside other
    # ducks, are another entry.
    timeline_sha256: str | None = None
    # The rig its manifest describes (rig_of), or None without one: the event's rig applies.
    rig: str | None = None
    # What a stage entry's other ducks play, by reference, each read at its pinned commit.
    borrowed: dict[str, "FetchedPolicy"] = field(default_factory=dict)


def hub_name(fetched: FetchedPolicy) -> str:
    """The name a Hub policy goes by when nobody typed one: its manifest's, else its repo's."""
    named = str((fetched.manifest or {}).get("name") or "").strip()
    return named or fetched.repo_id.rsplit("/", 1)[-1].removeprefix("microduck-")


def first_duck(troupe: Troupe, reference: str) -> str:
    """How a refusal names a borrowed policy: the first duck that plays it, then its repo."""
    k = next(k for k, duck in enumerate(troupe.ducks) if duck.policy == reference)
    return f"ducks[{k}]: {split_reference(reference)[0]}"


def parse_repo_ref(text: str) -> tuple[str, str | None]:
    """`owner/name`, optionally `owner/name:path/to/file.onnx`. URLs allowed."""
    raw = str(text or "").strip()
    for prefix in ("https://huggingface.co/", "http://huggingface.co/", "hf.co/"):
        raw = raw.removeprefix(prefix)
    # A pasted URL may carry /tree/main, /blob/main or /resolve/main. /tree/
    # names a directory, so it is simply dropped. /blob/ and /resolve/ name a
    # FILE — the whole point of the paste — so that filename is kept, with the
    # revision segment right after the marker skipped over.
    url_filename = None
    if "/tree/" in raw:
        raw = raw.split("/tree/", 1)[0]
    else:
        for marker in ("/blob/", "/resolve/"):
            if marker in raw:
                repo_part, rest = raw.split(marker, 1)
                _revision, _, path = rest.partition("/")
                raw = repo_part
                url_filename = path or None
                break
    repo, _, filename = raw.partition(":")
    filename = filename or url_filename
    parts = [p for p in repo.strip("/").split("/") if p]
    if len(parts) != 2 or any(p in (".", "..") for p in parts):
        raise FetchError(
            f"{text!r} is not a repo id — expected owner/name, "
            "optionally owner/name:policy.onnx"
        )
    return "/".join(parts), ((filename or "").strip() or None)


def _default_info(repo_id: str, revision: str | None):
    from huggingface_hub import HfApi

    # files_metadata=True is what makes each sibling carry `.size` — without
    # it the Hub returns the file list alone, and there is nothing to check
    # the cap against before downloading.
    info = HfApi().model_info(repo_id, revision=revision, files_metadata=True)
    siblings = info.siblings or []
    files = [s.rfilename for s in siblings]
    sizes = {s.rfilename: s.size for s in siblings}
    return files, info.sha, sizes


def _default_download(repo_id: str, filename: str, revision: str):
    from huggingface_hub import hf_hub_download

    return hf_hub_download(repo_id, filename, revision=revision)


def _pick(files: list[str], wanted: str | None, repo_id: str) -> str:
    onnx = [f for f in files if f.endswith(".onnx")]
    if wanted:
        if wanted not in files:
            raise FetchError(f"{repo_id} has no {wanted}")
        return wanted
    if not onnx:
        raise FetchError(f"{repo_id} has no .onnx file")
    if PREFERRED in onnx:
        return PREFERRED
    if len(onnx) == 1:
        return onnx[0]
    listed = ", ".join(sorted(onnx)[:6])
    raise FetchError(
        f"{repo_id} has several .onnx files — say which one, "
        f"as {repo_id}:<file>. Found: {listed}"
    )


def rig_of(manifest: dict) -> str | None:
    """The Arena rig a policy manifest describes, or None for a machine no event races."""
    robot = manifest.get("robot") or {}
    model = robot.get("model")
    if model == LEGACY_ROLLERS_MODEL:
        return "rollers"
    if model != "microduck":
        return None
    return "rollers" if "rollers" in (robot.get("accessories") or []) else "legs"


def check_manifest(manifest: dict, event) -> None:
    """Refuse a policy whose manifest.json disagrees with `event`, naming the field.

    Only what the manifest declares is checked: real repos publish one without
    obs_len or kind, and the ONNX is validated whatever the manifest says.
    On a stage the robot is each duck's own: legs or rollers.
    """
    declared = {k: v for k, v in manifest.items() if v is not None}
    if declared.get("obs_len", OBS_SIZE) != OBS_SIZE:
        raise FetchError(f"{MANIFEST}: obs_len is {declared['obs_len']!r}; the Arena feeds {OBS_SIZE} observations")
    if declared.get("action_len", NUM_JOINTS) != NUM_JOINTS:
        raise FetchError(f"{MANIFEST}: action_len is {declared['action_len']!r}; the Arena drives {NUM_JOINTS} joints")
    robot = declared.get("robot", {})
    if not isinstance(robot, dict):
        raise FetchError(f"{MANIFEST}: robot is {robot!r}, not an object with a model")
    if not isinstance(robot.get("accessories") or [], list):
        raise FetchError(f"{MANIFEST}: robot accessories is {robot['accessories']!r}, not a list")
    if robot.get("model") is not None:
        said = f"robot {robot['model']!r} with accessories {robot.get('accessories') or []}"
        # A race is run on its event's rig. On a stage each duck stands on its own, legs or rollers,
        # beside the others.
        if event.course.kind == "stage":
            if rig_of(manifest) not in RIGS:
                raise FetchError(f"{MANIFEST}: {said} is neither of the robots {event.title} stages, legs or rollers")
        elif rig_of(manifest) != event.rig:
            raise FetchError(f"{MANIFEST}: {said} is not the {event.rig} robot {event.title} races")
    if declared.get("kind", event.kind) != event.kind:
        raise FetchError(f"{MANIFEST}: kind is {declared['kind']!r}; {event.title} takes {event.kind} policies")


def _read_manifest(repo_id: str, revision: str, download) -> dict:
    try:
        path = Path(download(repo_id, MANIFEST, revision))
    except Exception as exc:
        raise FetchError(f"could not download {repo_id}/{MANIFEST}: {exc}") from exc
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError) as exc:
        raise FetchError(f"could not read {repo_id}/{MANIFEST}: {exc}") from exc
    try:
        manifest = json.loads(text)
    except ValueError as exc:
        raise FetchError(f"{repo_id}/{MANIFEST} is not valid JSON: {exc}") from exc
    if not isinstance(manifest, dict):
        raise FetchError(f"{repo_id}/{MANIFEST} is not a JSON object")
    return manifest


def _read_troupe(repo_id: str, revision: str, download, event) -> tuple[Troupe, str]:
    try:
        path = Path(download(repo_id, TIMELINE, revision))
    except Exception as exc:
        raise FetchError(f"could not download {repo_id}/{TIMELINE}: {exc}") from exc
    try:
        troupe = load_troupe(path, event)
    except TimelineError as exc:
        raise FetchError(f"{repo_id}/{TIMELINE} cannot be played: {exc}") from exc
    return troupe, hashlib.sha256(path.read_bytes()).hexdigest()


def _checked(repo_id: str, wanted: str | None, revision: str | None, event, download, info):
    """Everything about a repo but its weights: the commit its listing comes from, the ONNX picked,
    its declared size within the cap, its manifest checked. Returns the listing, that commit, the
    ONNX's name and the manifest (or None)."""
    try:
        files, sha, sizes = info(repo_id, revision)
    except FetchError:
        raise
    except Exception as exc:
        gone = getattr(getattr(exc, "response", None), "status_code", None) == 404
        raise (PolicyGone if gone else FetchError)(f"could not read {repo_id}: {exc}") from exc
    # Every file is read at the commit the listing came from, so the manifest
    # checked and the weights raced are one publication, not two.
    pinned = sha or revision or "main"

    filename = _pick(list(files), wanted, repo_id)

    # Refused BEFORE downloading anything: a declared size over the cap costs
    # nothing to reject. A missing (None) size is not evidence of a large
    # file, so it is not grounds for refusal — `load_policy` still checks the
    # actual bytes once they exist, downstream.
    size = (sizes or {}).get(filename)
    if size is not None and size > MAX_MODEL_BYTES:
        raise FetchError(
            f"{repo_id}/{filename} is {size} bytes, larger than the "
            f"{MAX_MODEL_BYTES} byte limit"
        )

    manifest = _read_manifest(repo_id, pinned, download) if MANIFEST in files else None
    if manifest is not None and event is not None:
        check_manifest(manifest, event)  # before the weights: a refusal costs one small file
    return files, pinned, filename, manifest


def _weights(repo_id: str, filename: str, pinned: str, manifest: dict | None, download,
             **performance) -> FetchedPolicy:
    """The weights at the commit checked, completing the FetchedPolicy; `performance` is a stage
    entry's troupe, its timeline's sha256 and its borrowed policies."""
    try:
        path = Path(download(repo_id, filename, pinned))
    except Exception as exc:
        raise FetchError(f"could not download {repo_id}/{filename}: {exc}") from exc
    return FetchedPolicy(
        repo_id=repo_id,
        filename=filename,
        revision=pinned,
        path=path,
        url=f"https://huggingface.co/{repo_id}/resolve/{pinned}/{filename}",
        manifest=manifest,
        rig=rig_of(manifest) if manifest is not None else None,
        **performance,
    )


def fetch_policy(
    repo_ref: str,
    revision: str | None = None,
    event=None,
    download=_default_download,
    info=_default_info,
) -> FetchedPolicy:
    repo_id, wanted = parse_repo_ref(repo_ref)
    files, pinned, filename, manifest = _checked(repo_id, wanted, revision, event, download, info)
    if event is None or event.course.kind != "stage" or TIMELINE not in files:
        return _weights(repo_id, filename, pinned, manifest, download)
    # Before the weights too: a performance the Arena will not play costs one small file, and a
    # borrowed policy it cannot have costs that policy's files, never the entry's weights.
    troupe, timeline_sha256 = _read_troupe(repo_id, pinned, download, event)
    borrowed = fetch_references(troupe, event, download, info)
    return _weights(repo_id, filename, pinned, manifest, download,
                    troupe=troupe, timeline_sha256=timeline_sha256, borrowed=borrowed)


def fetch_references(troupe: Troupe, event, download=_default_download, info=_default_info) -> dict[str, FetchedPolicy]:
    """Every policy a troupe borrows, by reference: read once however many ducks play it, at its pinned
    commit, under the entry's own rules, its weights last. Its own timeline.json is never read. A
    refusal names the first duck that plays it."""
    borrowed = {}
    for reference in troupe.references():
        if reference.startswith(LOCAL):
            continue  # a checkpoint of the workshop's own machine: it plays from there, never the Hub
        repo_id, commit = split_reference(reference)
        try:
            _, pinned, filename, manifest = _checked(repo_id, None, commit, event, download, info)
            borrowed[reference] = _weights(repo_id, filename, pinned, manifest, download)
        except FetchError as exc:
            raise FetchError(f"{first_duck(troupe, reference)}: {exc}") from exc
    return borrowed
