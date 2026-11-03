"""Everything the dashboard shows, folded from the run log and the usage log.

Pure but for `load`: `build` takes the records and the day it is, and returns what the page draws.
A visitor is the random id a browser keeps (app/src/usage.js), a visit one page load; a player is
whoever published a run, a voter whoever cast a ballot, both by Hub name.
"""

import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

PERIODS = (7, 30, 90)
# The challenges drawn in their own colour; the rest are summed as "other".
EVENTS_SHOWN = 6
OUTS = {
    "store.pollen-robotics.com": "Store (buy)",
    "discord.com": "Discord",
    "pollen-robotics.com": "Pollen's site",
    "github.com": "GitHub",
    "huggingface.co": "Hugging Face",
}


def load(runs_root: Path, usage_root: Path) -> tuple[list[dict], list[dict], list[dict]]:
    """The hits, runs and votes in two dataset checkouts."""
    hits = [json.loads(line) for path in sorted(Path(usage_root).glob("usage/*/*.jsonl"))
            for line in path.read_text().splitlines() if line]
    runs = [{"at": r["submitted_at"], "user": r["user"], "event": r["event_id"]}
            for r in map(json.loads, map(Path.read_text, sorted(Path(runs_root).glob("runs/*/*.json"))))]
    votes = [{"at": v["cast_at"], "voter": v["voter"], "event": v["event_id"]}
             for v in map(json.loads, map(Path.read_text, sorted(Path(runs_root).glob("votes/*/*.json"))))]
    return hits, runs, votes


def page_group(page: str) -> str:
    """A page's kind, or its event for the pages each event has."""
    parts = page.split("?")[0].strip("/").split("/")
    kinds = {"e": "Board", "v": "Vote", "c": "Cup"}
    if parts[0] in kinds and len(parts) > 1:
        return f"{kinds[parts[0]]} · {parts[1]}"
    return {"": "Home", "r": "A run's page", "p": "A player's page", "m": "A cup match",
            "live": "Live", "guides": "Guides"}.get(parts[0], page)


def out_label(href: str) -> str:
    host = urlsplit(href).hostname or ""
    return next((label for domain, label in OUTS.items()
                 if host == domain or host.endswith("." + domain)), host or href)


def is_buy(hit: dict) -> bool:
    return hit["kind"] == "out" and out_label(hit.get("href", "")) == "Store (buy)"


def day_of(record: dict) -> str:
    return record["at"][:10]


def between(records: list[dict], start: str, end: str) -> list[dict]:
    """The records from `start` to `end`, both days included."""
    return [r for r in records if start <= day_of(r) <= end]


def by_day(records: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for record in records:
        grouped[day_of(record)].append(record)
    return grouped


def monday(day: str) -> str:
    d = date.fromisoformat(day)
    return (d - timedelta(days=d.weekday())).isoformat()


def days_between(first: str, last: str) -> list[str]:
    start, end = date.fromisoformat(first), date.fromisoformat(last)
    return [(start + timedelta(days=n)).isoformat() for n in range((end - start).days + 1)]


def firsts(records: list[dict], who: str) -> dict[str, str]:
    """Each person's first day."""
    first: dict[str, str] = {}
    for record in sorted(records, key=day_of):
        first.setdefault(record[who], day_of(record))
    return first


def per_visit(hits: list[dict]) -> tuple[float, float]:
    """Pages viewed and minutes looked, per visit."""
    visits = len({h["visit"] for h in hits})
    if not visits:
        return 0.0, 0.0
    views = sum(h["kind"] == "view" for h in hits)
    seconds = sum(h.get("seconds", 0) for h in hits if h["kind"] == "time")
    return round(views / visits, 2), round(seconds / 60 / visits, 2)


def totals(hits, runs, votes, first_hit, first_run, first_vote, start: str, end: str) -> dict:
    """What happened from `start` to `end`, both included."""
    hits, runs, votes = between(hits, start, end), between(runs, start, end), between(votes, start, end)
    visitors = {h["visitor"] for h in hits}
    buyers = {h["visitor"] for h in hits if is_buy(h)}
    players = {r["user"] for r in runs}
    pages, minutes = per_visit(hits)
    return {
        "visitors": len(visitors),
        "new_visitors": sum(start <= first_hit[v] for v in visitors),
        "visits": len({h["visit"] for h in hits}),
        "pages_per_visit": pages,
        "minutes_per_visit": minutes,
        "signed_in_visitors": len({h["visitor"] for h in hits if h.get("signed_in")}),
        "buy_clicks": sum(map(is_buy, hits)),
        "buyers": len(buyers),
        "buy_rate": round(len(buyers) / len(visitors), 4) if visitors else 0.0,
        "players": len(players),
        "new_players": sum(start <= first_run[p] for p in players),
        "runs": len(runs),
        "voters": len({v["voter"] for v in votes}),
        "new_voters": sum(start <= first_vote[v] for v in {v["voter"] for v in votes}),
        "votes": len(votes),
    }


def tables(hits: list[dict]) -> dict:
    """Where the visits of a period went, came from, and left to."""
    views = [h for h in hits if h["kind"] == "view"]
    pages: dict[str, list] = defaultdict(lambda: [0, set()])
    for h in views:
        row = pages[page_group(h["page"])]
        row[0] += 1
        row[1].add(h["visitor"])
    # A visit's first view says where it came from and on what.
    openings = [h for h in views if "embedded" in h]
    outs: dict[str, list] = defaultdict(lambda: [0, set()])
    for h in hits:
        if h["kind"] == "out":
            row = outs[out_label(h.get("href", ""))]
            row[0] += 1
            row[1].add(h["visitor"])
    return {
        "pages": [{"label": k, "views": n, "visitors": len(v)}
                  for k, (n, v) in sorted(pages.items(), key=lambda kv: -kv[1][0])],
        "referrers": [{"label": k, "visits": n} for k, n in Counter(
            h.get("referrer") or "(none)" for h in openings).most_common(12)],
        "devices": [{"label": label, "visits": n} for label, n in Counter(
            ("Phone or tablet" if h.get("mobile") else "Computer")
            + (", on huggingface.co" if h.get("embedded") else ", on its own address")
            for h in openings).most_common()],
        "outs": [{"label": k, "clicks": n, "visitors": len(v)}
                 for k, (n, v) in sorted(outs.items(), key=lambda kv: -kv[1][0])],
    }


def build(hits: list[dict], runs: list[dict], votes: list[dict], today: date) -> dict:
    last = today.isoformat()
    first_hit, first_run, first_vote = firsts(hits, "visitor"), firsts(runs, "user"), firsts(votes, "voter")
    first_day = min([*first_hit.values(), *first_run.values(), *first_vote.values(), last])
    hits_on, runs_on, votes_on = by_day(hits), by_day(runs), by_day(votes)

    days = []
    for day in days_between(first_day, last):
        on = hits_on.get(day, [])
        visitors = {h["visitor"] for h in on}
        pages, minutes = per_visit(on)
        days.append({
            "day": day,
            "visitors": len(visitors),
            "new_visitors": sum(first_hit[v] == day for v in visitors),
            "visits": len({h["visit"] for h in on}),
            "pages_per_visit": pages,
            "minutes_per_visit": minutes,
            "buy_clicks": sum(map(is_buy, on)),
            "runs": len(runs_on.get(day, [])),
            "votes": len(votes_on.get(day, [])),
        })

    events = [e for e, _ in Counter(r["event"] for r in runs).most_common()]
    shown = events[:EVENTS_SHOWN]
    weeks = []
    for week in sorted({monday(d) for d in days_between(first_day, last)}):
        end = (date.fromisoformat(week) + timedelta(days=6)).isoformat()
        week_runs, week_votes = between(runs, week, end), between(votes, week, end)
        players = {r["user"] for r in week_runs}
        voters = {v["voter"] for v in week_votes}
        weeks.append({
            "week": week,
            "players": len(players),
            "new_players": sum(week <= first_run[p] for p in players),
            "voters": len(voters),
            "new_voters": sum(week <= first_vote[v] for v in voters),
            "runs": dict(Counter(r["event"] if r["event"] in shown else "other" for r in week_runs)),
        })

    members, players, voters = [], set(), set()
    for day in days_between(first_day, last):
        players |= {r["user"] for r in runs_on.get(day, [])}
        voters |= {v["voter"] for v in votes_on.get(day, [])}
        members.append({"day": day, "players": len(players), "voters": len(voters),
                        "members": len(players | voters)})

    def period(length: int | None) -> dict:
        start = (today - timedelta(days=length - 1)).isoformat() if length else first_day
        now = totals(hits, runs, votes, first_hit, first_run, first_vote, start, last)
        before = None
        if length:
            previous = (today - timedelta(days=2 * length - 1)).isoformat()
            ending = (today - timedelta(days=length)).isoformat()
            before = totals(hits, runs, votes, first_hit, first_run, first_vote, previous, ending)
        return {"start": start, "now": now, "before": before,
                **tables(between(hits, start, last))}

    return {
        "today": last,
        "usage_since": min(first_hit.values(), default=None),
        "events": shown + (["other"] if len(events) > EVENTS_SHOWN else []),
        "days": days,
        "weeks": weeks,
        "members": members,
        "periods": {**{str(n): period(n) for n in PERIODS}, "all": period(None)},
    }
