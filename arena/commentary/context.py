"""What the commentators may know about a run: public, allowlisted facts.

A Fact is a sentence with a reference, and the writer cites the references
it speaks from. Nothing here fetches, infers or scores; the worker passes
records it already holds. Editorial fiction lives in lore.py, never in a
fact about a player.
"""

import re
import unicodedata
from dataclasses import dataclass

from ..index import by_user, leaderboard, sort_key, standing
from ..manifest import Manifest, higher_wins
from ..points import Receipt
from ..store import RunRecord
from ..tug import FAULT_PITS


@dataclass(frozen=True)
class Fact:
    ref: str
    text: str
    kind: str  # result | notable | lore | recent
    tags: tuple[str, ...] = ()
    # Notability. Result facts are always worth citing; detectors score theirs.
    score: float = 1.0


def technical_text(text: str) -> bool:
    """Recognisable machine labels: never broadcast prose."""
    text = unicodedata.normalize("NFKC", text)
    return bool(re.search(
        r"https?://|[/\\]|\b\w+_\w+\b|"
        r"\b[\w.-]+\.(?:mp4|webm|mov|mkv|avi|wav|mp3|ogg|jsonl?|csv|onnx|wasm|npy|npz)\b|"
        r"\b[0-9a-f]{16,}\b|\b[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\b",
        text, re.IGNORECASE,
    ))


def label(value, limit: int = 80) -> bool:
    """Submitter-supplied text a fact may quote: short, printable, no markup,
    nothing machine-shaped — a fact quoting it would put it on the air."""
    return (isinstance(value, str) and 0 < len(value.strip()) <= limit
            and value.isprintable() and not any(c in value for c in "<>")
            and not technical_text(value))


# A gap in centimetres under which two ratings are close, and over which a better one is a big step.
NOTABLE_GAP_CM = 5.0


def measure(manifest: Manifest) -> tuple[str, str]:
    """What the board's score is called and counted in: a rating in centimetres where higher wins,
    else a time in seconds."""
    return ("rating", "cm") if higher_wins(manifest.id) else ("time", "s")


def nature(manifest: Manifest) -> tuple[str, tuple[str, ...]]:
    """What kind of contest this is, in words and in tags the bible matches on."""
    if manifest.course.kind == "stage":
        return "a performance on a stage decided by the public's votes", ("vote",)
    if manifest.course.kind == "tug":
        return ("a pulling contest against the Arena's reference duck: the two are tied by a string "
                "across a pit in a wrestling ring and each pulls by walking backwards"), ("tug",)
    length = f"{manifest.course.length_m:g} m"
    if manifest.lights is not None:
        return (f"a {length} sock heist: little microducks sneak up on a giant microduck's nest to "
                "steal its socks, and must freeze whenever it turns its head"), ("lights",)
    if manifest.course.slope_deg > 0:
        return f"a {length} climb up an {manifest.course.slope_deg:g} degree slope", ("hill",)
    if manifest.rig == "rollers":
        return f"a {length} race on roller skates", ("rollers",)
    return f"a {length} sprint on foot", ("sprint",)


ACTS = {
    "first_event": "a first run on this event",
    "own_best": "a new personal best",
    "podium": "a podium place held",
    "run": "a run of the day",
}
ACT_TAGS = {"first_event": "first-run", "own_best": "pb", "podium": "podium"}


def _unfinished(record: RunRecord) -> tuple[str, tuple[str, ...]]:
    """What stopped the seeds that did not finish, when it was more than the
    clock: a fall, or being caught moving while the giant looked. Nothing to say
    when every one of them simply ran out of time."""
    falls = sum(1 for s in record.per_seed if s.status == "fall")
    caught = sum(1 for s in record.per_seed if s.status == "caught")
    said = ([f"fell on {falls}"] if falls else []) + (
        [f"was caught moving while the giant looked on {caught}"] if caught else [])
    if not said:
        return "", ()
    tags = (("fall",) if falls else ()) + (("caught",) if caught else ())
    return f"the duck {' and '.join(said)} of them", tags


def _rating_result(record: RunRecord, manifest: Manifest) -> Fact:
    bonus = manifest.rating.pit_bonus_cm
    won = sum(1 for s in record.per_seed if s.status in ("won", "pit_won"))
    faults = sum(1 for s in record.per_seed if s.status == "fault")
    text = (f"The rating is {record.score:.1f} cm: the ground the duck won from the reference duck in "
            f"{len(record.per_seed)} bouts, on average, {bonus:g} cm more for dragging it into the pit and "
            f"{bonus:g} cm less for being dragged in; it won {won} of them.")
    if faults:
        text += (f" It faulted in {faults}, {FAULT_PITS * bonus:g} cm less each: the bout stopped because the duck "
                 f"gave no valid action, or broke the simulation.")
    traced = next(s.status for s in record.per_seed if s.seed == record.trace_seed)
    return Fact("run#/result", text, "result", (traced,))


def _result(record: RunRecord, manifest: Manifest) -> Fact:
    if manifest.course.kind == "stage":
        # A performance is not a race: its length is the only time it has, and
        # it ends early only when the simulation breaks down, which is no fall.
        text = (f"The performance lasts {record.score:.2f} s." if record.seeds_finished
                else "The performance was cut short.")
        return Fact("run#/result", text, "result", ("performance",))
    if manifest.course.kind == "tug":
        return _rating_result(record, manifest)
    who = f"@{record.user}"
    total = len(record.per_seed)
    how, tags = _unfinished(record)
    if record.seeds_finished == 0:
        text = f"{who} did not finish: none of the {total} seeds reached the line"
        text += f", {how}." if how else "."
        return Fact("run#/result", text, "result", ("dnf", *tags))
    text = f"The mean finish time is {record.score:.2f} s"
    if record.seeds_finished == total:
        return Fact("run#/result", text + f", every one of the {total} seeds finished.", "result",
                    ("clean",))
    text += (f", with {record.seeds_finished} of {total} seeds finished; an unfinished seed "
             f"counts as the {manifest.time_limit_s:g} s limit")
    text += f", and {how}." if how else "."
    return Fact("run#/result", text, "result", tags or ("partial",))


def _board(record: RunRecord, manifest: Manifest, event_runs) -> Fact:
    rows = leaderboard(event_runs, entrant=by_user)
    others = [row.record for row in rows if row.record.user != record.user]
    if not others:
        return Fact("run#/board", f"This run opens the {manifest.title} board: nobody else has "
                    "published on it.", "result", ("open-board", "first-run"))
    rank = standing(event_runs, record.run_id).rank
    size = len(others) + 1
    if rank == 1:
        return Fact("run#/board", f"This run takes the lead of the {manifest.title} board, "
                    f"with {size} entrants ranked.", "result", ("lead", "podium"))
    leader = min(others, key=sort_key)
    text = f"On the {manifest.title} board this run ranks {rank} of {size}"
    tags = ["podium"] if rank <= 3 else []
    if record.seeds_finished:
        unit = measure(manifest)[1]
        gap = abs(record.score - leader.score)
        text += f", {gap:.2f} {unit} behind the leader, @{leader.user}."
        if gap < (NOTABLE_GAP_CM if unit == "cm" else 0.5):
            tags.append("close")
        return Fact("run#/board", text, "result", tuple(tags))
    return Fact("run#/board", text + ".", "result", tuple(tags))


def _points(record: RunRecord, receipts: list[Receipt]) -> Fact | None:
    mine = [r for r in receipts if r.source_id == record.run_id]
    if not mine:
        return None
    total = sum(r.points for r in mine)
    parts = ", ".join(f"{ACTS[r.act]} ({r.points})" for r in mine)
    tags = tuple(dict.fromkeys(ACT_TAGS[r.act] for r in mine if r.act in ACT_TAGS))
    return Fact("run#/points", f"This run earned {total} points: {parts}.", "result", tags)


def _troupe(record: RunRecord) -> Fact | None:
    """Who performs when more than one duck does, in order: each by its author and its policy's name,
    the entry's own first as the star, a policy already named "again". A name that is not a label goes
    unsaid, as the participant's does. None for one duck: the participant fact says it all."""
    if len(record.cast) < 2:
        return None
    seen, ducks = set(), []
    for k, duck in enumerate(record.cast):
        source = duck["policy"]
        if source == "self":
            who, name, which = record.user, record.policy_name, "self"
        else:
            who, name, which = source["user"], source["policy_name"], (source["repo_id"], source["revision"])
        said = f"@{who}'s {name}" if label(name) else f"@{who}'s policy"
        if k == 0:
            said += " (the star)"
        elif which in seen:
            said += " again"
        seen.add(which)
        ducks.append(said)
    listed = ", ".join(ducks[:-1]) + " and " + ducks[-1]
    return Fact("run#/troupe", f"The performance has {len(ducks)} ducks: {listed}.", "result")


NOTE_MAX = 280
# What an author may write in a note and not in a name: a unit (m/s, km/h, rad/s: a short word,
# one slash, a shorter one, not a path's a/b/c) and a snake_case word.
NOTE_ALLOWS = re.compile(r"(?<![\w/])[^\W_]{1,5}/[^\W_]{1,3}(?![\w/])|\b[^\W_]+(?:_[^\W_]+)+\b")
# What a note may not hold although a name may: a link without its :// (that slash is refused
# anyway) and a file name, a word with an extension.
NOTE_REFUSES = re.compile(r"\bwww\.|\b[^\W_][\w-]+\.[a-z][a-z0-9]{0,4}\b", re.IGNORECASE)


def _quotable(text: str) -> bool:
    """A note a fact may quote: `label`'s checks, with NOTE_ALLOWS let through (masked at the same
    length) and NOTE_REFUSES refused."""
    text = unicodedata.normalize("NFKC", text)
    return (not NOTE_REFUSES.search(text)
            and label(NOTE_ALLOWS.sub(lambda m: "x" * len(m[0]), text), limit=NOTE_MAX))


def _note(record: RunRecord) -> Fact | None:
    """The author's own words about the policy, quoted as theirs: never a result, and only when they
    read as prose (`_quotable`). Its line breaks and runs of spaces are a textarea's layout: quoted
    as single spaces."""
    text = " ".join((record.description or "").split())
    if not _quotable(text):
        return None
    return Fact("run#/note", f'@{record.user} says about the policy: "{text}"', "notable")


def result_facts(record: RunRecord, manifest: Manifest, event_runs, receipts) -> tuple[Fact, ...]:
    """The run itself: the event, who ran, what the clock says (on a stage, how
    long the performance lasts, and who performs when a troupe does), where it stands and what it earned. `event_runs`
    are the counting runs of the event as they stood when this one was published,
    this one included; a voted event's board is not a clock, so it gets no board
    fact."""
    what, tags = nature(manifest)
    who = f"@{record.user}"
    policy = record.policy_name if label(record.policy_name) else None
    note = _note(record)
    doing = {"stage": "performing", "tug": "pulling with"}.get(manifest.course.kind, "racing")
    facts = [
        Fact("run#/event", f"The event is the {manifest.title}, {what}.", "result", tags),
        Fact("run#/participant",
             f"The participant is {who}, {doing} a policy named {policy}." if policy
             else f"The participant is {who}.",
             "result", ("participant",)),
        _result(record, manifest),
    ]
    troupe = _troupe(record)
    if troupe:
        facts.append(troupe)
    if note:
        facts.append(note)
    if manifest.metric != "votes":
        facts.append(_board(record, manifest, event_runs))
    points = _points(record, receipts)
    if points:
        facts.append(points)
    return tuple(facts)
