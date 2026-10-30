"""The engine without a web layer.

Everything the Space will do — validate, run, score, record, rank — is reachable
from here, which is what makes the platform plan a thin shell over tested code
rather than a place where behaviour is invented.
"""

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from . import stage
from .cast import cast_of, load_borrowed
from .constants import CTRL_DT
from .evaluate import evaluate, trace_file
from .hub_fetch import FetchError, fetch_references
from .index import ENTRANTS, leaderboard
from .manifest import ManifestError, all_events, higher_wins, load_event
from .policy import PolicyError, load_policy
from .store import LocalStore, RunRecord, lone_cast, new_id
from .timeline import TimelineError, load_troupe
from .tug import SIDES, entry_side


def _cmd_events(args) -> int:
    for manifest in all_events():
        print(f"{manifest.id:<20} {manifest.title:<16} rig={manifest.rig} "
              f"seeds={len(manifest.seeds)} limit={manifest.time_limit_s}s")
    return 0


def _print_sweep(result) -> None:
    print(f"sweep {len(result.scan)} commanded speeds "
          f"{result.scan[0].command_vx:.2f}–{result.scan[-1].command_vx:.2f} m/s")
    for point in result.scan:
        timing = f"{point.time_s:.2f}s" if point.time_s is not None else \
                 f"{point.status} at {point.progress_m:.2f}m"
        print(f"  {point.command_vx:>5.2f} m/s  {timing}")
    print(f"\nscored at {result.command_vx:.2f} m/s")

    for seed_result in result.per_seed:
        timing = f"{seed_result.time_s:.2f}s" if seed_result.time_s is not None else "—"
        print(f"seed {seed_result.seed}: {seed_result.status:<8} {timing}")
    print(f"\nscore {result.score:.3f}s · {result.seeds_finished}/"
          f"{len(result.per_seed)} finished · replay from seed {result.trace_seed}")


def _print_rating(result) -> None:
    """The format the training recipe's ledger reads: one line per seed, then the rating."""
    for r in result.per_seed:
        print(f"seed {r.seed}: {SIDES[entry_side(r.seed)]:<4} {r.status:<8} {r.score_cm:+7.1f} cm at {r.time_s:.2f} s")
    print(f"rating: {result.score:.1f} cm · replay from seed {result.trace_seed}")


def _print_stage(manifest, result, troupe, name: str | None) -> None:
    played = result.trace.shape[1] * CTRL_DT
    if troupe is None:
        what = "the event's default command"
    elif len(troupe.ducks) == 1:
        what = f"{name} ({len(troupe.ducks[0].timeline.times)} keyframes)"
    else:
        what = f"{name} ({len(troupe.ducks)} ducks)"
    if result.seeds_finished:
        print(f"stage: {played:.2f} s played, {what}")
    else:
        print(f"stage: stopped at {played:.2f} s, the simulation diverged; {what}")
    for k, done in enumerate(stage.summaries(result.trace, manifest.termination)):
        fell = "no" if done["fell_at"] is None else f"at {done['fell_at']:.2f} s"
        print(f"duck {k}: fell {fell} · seated {done['seated_s']:.1f} s · standing {done['standing_s']:.1f} s")


def _cmd_score(args) -> int:
    manifest = load_event(args.event)
    policy = load_policy(Path(args.onnx))
    cast = None
    if manifest.course.kind == "stage":
        troupe = load_troupe(Path(args.timeline), manifest) if args.timeline else None
        # "self" is the ONNX given here; every other duck's policy comes from the Hub, at its commit.
        references = fetch_references(troupe, manifest) if troupe else {}
        cast = cast_of(manifest, troupe, policy, None, load_borrowed(troupe, references))
        result = evaluate(manifest, policy, cast.performers)
        _print_stage(manifest, result, troupe, Path(args.timeline).name if args.timeline else None)
    elif args.timeline:
        print(f"{manifest.id} is not a stage: --timeline is for stage events", file=sys.stderr)
        return 1
    elif manifest.course.kind == "tug":
        result = evaluate(manifest, policy)
        _print_rating(result)
    else:
        result = evaluate(manifest, policy)
        _print_sweep(result)

    if args.store:
        record = RunRecord(
            run_id=new_id(),
            event_id=manifest.id,
            submitted_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            user=args.user,
            policy_name=args.name or Path(args.onnx).stem,
            source={"kind": "local", "path": str(Path(args.onnx).resolve())},
            model_sha256=policy.sha256,
            score=result.score,
            command_vx=result.command_vx,
            model_stored=True,
            seeds_finished=result.seeds_finished,
            per_seed=result.per_seed,
            trace_seed=result.trace_seed,
            runner_version=result.runner_version,
            livery=args.livery,
            cast=cast.record if cast else lone_cast(),
        )
        LocalStore(Path(args.store)).append(
            record,
            trace_file(result),
            Path(args.onnx).read_bytes(),
        )
        print(f"recorded {record.run_id}")
    return 0


def _cmd_board(args) -> int:
    manifest = load_event(args.event)
    rows = leaderboard(
        LocalStore(Path(args.store)).runs(manifest.id), entrant=ENTRANTS[args.rank_by]
    )
    if not rows:
        print(f"no runs recorded for {manifest.id}")
        return 0

    rating = higher_wins(manifest.id)
    # A tug's fixed command walks backwards, no speed it was scored at: no cmd column.
    cmd = "" if rating else f"{'cmd':>10}"
    print(f"{manifest.title}\n")
    print(f"{'#':<4}{'who':<16}{'policy':<20}{'rating' if rating else 'time':>10}{'seeds':>8}{cmd}")
    for row in rows:
        r = row.record
        score = f"{r.score:>7.1f} cm" if rating else f"{r.score:>9.3f}s"
        speed = "" if rating else f"{r.command_vx:>8.2f}m/s"
        print(f"{row.rank:<4}{r.user:<16}{r.policy_name:<20}"
              f"{score}{r.seeds_finished:>5}/{len(r.per_seed)}{speed}")
    return 0


def _cmd_recover(args) -> int:
    """Rebuild the board from what is published on the Hub.

    The run log can be lost — a Space without a dataset repo keeps it on a
    filesystem every redeploy wipes — but the policies are not: each one lives
    in its author's own repo. This re-races them and re-derives the board.
    """
    from .recover import recover

    store = LocalStore(Path(args.store))
    events = [load_event(args.event)] if args.event else all_events()
    restored = recover(
        store,
        events,
        all_tagged=args.all_tagged,
        on_event=lambda message: print(f"  {message}"),
    )
    print(f"\n{len(restored)} run(s) restored")
    return 0


def _app_on_loopback(store_dir, reveal_all: bool = False) -> tuple | None:
    """The app on a free loopback port, answering, launching no clip jobs.

    The recorder's Chrome needs the clip page and the API; this process is the
    clip job, or a render by hand, and owes nothing itself. With `reveal_all`
    it serves a cup's matches before they air. The config, the app, the running
    server and its origin — or None, the failure already reported.
    """
    import socket
    import threading

    import httpx
    import uvicorn

    from .web.app import create_app
    from .web.config import ArenaConfig

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    config = ArenaConfig.from_env(store_dir=store_dir, origin=origin, clip_worker=False,
                                  reveal_all=reveal_all)
    app = create_app(config)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        try:
            if httpx.get(f"{origin}/api/health", timeout=1).status_code == 200:
                return config, app, server, origin
        except httpx.HTTPError:
            pass
        # Outside the except: a non-200 answer is not an error either, and
        # must not spin the loop any faster than a connection refused does.
        time.sleep(0.1)
    print(f"the app did not come up on {origin}", file=sys.stderr)
    server.should_exit = True
    return None


def _cmd_clip(args) -> int:
    """Render one run's clips, or a match's, into the store: what a clip job runs, or by hand."""
    from .clips import ClipRenderer

    # A match's clip is rendered before its cup's show: this app reads it before it airs.
    started = _app_on_loopback(args.store, reveal_all=True)
    if started is None:
        return 1
    config, app, server, origin = started

    renderer = ClipRenderer(
        app.state.store, origin, config.frontend_dir, args.parallel or config.clip_parallel,
        gpu=config.clip_gpu,
    )
    if not renderer.available:
        print("no renderer here: needs a Chrome ($CHROME or the usual paths), ffmpeg, and a built clip.html",
              file=sys.stderr)
        server.should_exit = True
        return 1
    if app.state.store.clip_state(args.run_id)[0] == "ready":
        print(f"{args.run_id} already has a clip; delete clips/{args.run_id} to render it again",
              file=sys.stderr)
        server.should_exit = True
        return 1
    rendered = renderer.render_one(args.run_id)
    server.should_exit = True
    if not rendered:
        return 1
    _, manifest = app.state.store.clip_state(args.run_id)
    for name, layout in manifest["layouts"].items():
        print(f"{name}: {layout['seconds']} s, {layout['timing']['total_wall_ms'] / 1000:.0f} s wall, "
              f"{layout['timing']['capture_ms_per_frame']} ms/frame capture")
    print(f"written to {config.store_description()}")
    return 0


def _cmd_commentary(args) -> int:
    """Write (or, with --dry-run, print) Peter and Ray's lines for one run.

    A dry run touches neither a browser nor the store: it is how the tone is
    judged before the reserve is let loose. The real thing starts the app on a
    loopback port for the plan page, like `arena clip`, and puts a broadcast in
    the book the running server reads, where the channel will find it.
    """
    import random

    from . import commentary
    from .broadcasts import BroadcastBook, utcnow
    from .commentary.generator import Rejected, directed, write
    from .commentary.lore import load
    from .commentary.tab import PlanTab
    from .recorder import find_chrome
    from .web.config import ArenaConfig

    config = ArenaConfig.from_env(store_dir=args.store)
    token = commentary.hub_token(config)
    if not token:
        print("no Hub token: set HF_TOKEN or run `hf auth login`", file=sys.stderr)
        return 1
    lore = load()
    model = config.commentary_model
    provider = commentary.router_provider(model, token)
    book = BroadcastBook(config.broadcast_dir)
    rng = random.Random()
    if args.dry_run:
        store = config.build_store()
        try:
            facts, drawn = commentary.briefing(store, args.run_id, lore=lore, book=book, rng=rng)
        except LookupError as exc:
            print(exc, file=sys.stderr)
            return 1
        for i, fact in enumerate(facts):
            print(f"[{i}] {fact.text}" + ("  (memory)" if fact.kind == "lore" else ""))
        print(f"\n{directed(drawn)}")
        try:
            written = write(facts, drawn, lore=lore, provider=provider, model=model)
        except Rejected as why:
            print(f"\nnot on air: {why}", file=sys.stderr)
            return 1
        print()
        for turn in written["turns"]:
            print(f"{lore.characters[turn['speaker']]['name']}: {turn['text']}")
        print(f"\n{written['model']}, {written['usage']['prompt_tokens']} + "
              f"{written['usage']['completion_tokens']} tokens")
        return 0

    started = _app_on_loopback(args.store)
    if started is None:
        return 1
    config, app, server, origin = started
    if app.state.store.clip_state(args.run_id)[0] != "ready":
        print(f"{args.run_id} has no ready clip; render it first with `arena clip`", file=sys.stderr)
        server.should_exit = True
        return 1
    if not (config.frontend_dir and (config.frontend_dir / "plan.html").is_file()
            and find_chrome()):
        print("needs a Chrome ($CHROME or the usual paths) and a built plan.html", file=sys.stderr)
        server.should_exit = True
        return 1
    try:
        written = commentary.compose(app.state.store, args.run_id, lore=lore, provider=provider,
                                     model=model, book=book, rng=rng)
    except Rejected as why:
        print(f"not on air: {why}", file=sys.stderr)
        server.should_exit = True
        return 1
    with PlanTab(origin) as tab:
        plan = tab.prepare({"run_id": args.run_id, "turns": written["turns"]})
    made = book.put(args.run_id, {"turns": written["turns"], "lore_refs": written["lore_refs"],
                                  "brief": written["brief"]}, plan, utcnow())
    server.should_exit = True
    print(f"broadcast {made.id} for {args.run_id}, {plan['duration_ms'] / 1000:.1f} s "
          f"under {book.directory}")
    return 0


def _cmd_serve(args) -> int:
    import uvicorn

    from .web.app import create_app
    from .web.config import ArenaConfig

    config = ArenaConfig.from_env(
        store_dir=args.store, dev_user=args.user, origin=f"http://127.0.0.1:{args.port}"
    )
    config.ensure_store()
    app = create_app(config)
    print(f"store  {config.store_description()}")
    print(f"user   {config.dev_user}")
    if config.frontend_dir is None:
        print("frontend  NOT BUILT — run: cd app && npm install && npm run build")
    else:
        print(f"frontend  {config.frontend_dir}")
    clips = app.state.clips
    on = f"on (jobs on {clips.flavor}, paid by {clips.namespace})"
    print(f"clips  {on if clips.available else 'off (no Space, dataset or token to run jobs with)'}")
    booth = "on" if app.state.booth_off is None else f"off ({app.state.booth_off})"
    print(f"booth  {booth}")
    print(f"\n  http://{args.host}:{args.port}\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="arena", description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)

    subs.add_parser("events", help="list the events").set_defaults(func=_cmd_events)

    score = subs.add_parser("score", help="score a policy on an event")
    score.add_argument("onnx")
    score.add_argument("--event", required=True)
    score.add_argument("--user", default="local")
    score.add_argument("--name", default=None)
    score.add_argument("--store", default=None, help="record the run into this directory")
    score.add_argument("--timeline", default=None,
                       help="a stage event's timeline.json (default: the event's own command)")
    score.add_argument(
        "--livery", default="classic", help="which colourway to race in"
    )
    score.set_defaults(func=_cmd_score)

    board = subs.add_parser("board", help="print a leaderboard")
    board.add_argument("--event", required=True)
    board.add_argument("--store", required=True)
    board.add_argument(
        "--rank-by",
        choices=sorted(ENTRANTS),
        default="policy",
        dest="rank_by",
        help="one row per 'policy' (local default) or per 'user' (public boards)",
    )
    board.set_defaults(func=_cmd_board)

    serve = subs.add_parser("serve", help="run the Arena locally in a browser")
    serve.add_argument("--store", default=None, help="run log directory")
    serve.add_argument("--user", default=None, help="name to attribute submissions to")
    recover = subs.add_parser(
        "recover", help="rebuild the board by re-racing policies published on the Hub"
    )
    recover.add_argument("--store", required=True)
    recover.add_argument("--event", help="one event; default is every event")
    recover.add_argument(
        "--all-tagged",
        action="store_true",
        help="every microduck-policy repo on the Hub, not only ones published here",
    )
    recover.set_defaults(func=_cmd_recover)

    clip = subs.add_parser("clip", help="render one run's social clips into the store")
    clip.add_argument("run_id")
    clip.add_argument("--store", required=True)
    clip.add_argument("--parallel", type=int, default=None,
                      help="layouts rendered at once; default half the cores")
    clip.set_defaults(func=_cmd_clip)

    booth = subs.add_parser("commentary", help="write Peter and Ray's lines for one run")
    booth.add_argument("run_id")
    booth.add_argument("--store", required=True)
    booth.add_argument("--dry-run", action="store_true", dest="dry_run",
                       help="print the facts and the dialogue; write nothing")
    booth.set_defaults(func=_cmd_commentary)

    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=_cmd_serve)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (ManifestError, PolicyError, TimelineError, FetchError) as exc:
        print(f"{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
