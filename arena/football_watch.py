"""`arena football A B --watch`: a football match, played, then shown on a pitch in the
Arena's stadium on 127.0.0.1.

Separate from arena/web: no OAuth, no store, never deployed, and up only while the
command runs. The match is played before it serves
(arena.football.record_match), so everything it answers is in memory: the pitch and
the plays as JSON, each play's frames as every trace is served
(routes_read.frames_response), each play's props (ball and keepers) beside them, and
football.html, built with the site, which plays them in the site's own viewer. It
answers GETs of what it played and nothing else.
"""

from collections.abc import Sequence
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .constants import CTRL_DT
from .football import PROP_WIDTH, Football, Match, Recorded, board_boxes, net_boxes
from .web.routes_read import frames_response

NO_SITE = (
    "The football page has not been built.\n\n"
    "    cd app && npm install && npm run build\n\n"
    "in the Arena's checkout (an installed Arena wheel carries it already).\n"
)


def _boxes(boxes) -> list[dict]:
    return [{"name": name, "pos": list(pos), "half": list(half), "yaw_rad": yaw}
            for name, pos, half, yaw in boxes]


def props_response(props: np.ndarray) -> Response:
    """A play's (frames, PROP_WIDTH) props on the wire, as frames_response sends a trace:
    little-endian float32, frame-major. Each frame is the ball's position and quaternion
    (w, x, y, z), then each keeper's place along its rail."""
    return Response(
        content=np.ascontiguousarray(props, dtype="<f4").tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Frame-Count": str(props.shape[0]),
            "X-Prop-Width": str(PROP_WIDTH),
            "Cache-Control": "no-store",
        },
    )


def football_summary(football: Football, names: Sequence[str], match: Match,
                     recorded: Sequence[Recorded]) -> dict:
    """What football.html needs besides the frames: the pitch to build, and the plays.

    A play's scorer is its end (0 kicked off from -x and attacks the goal at +x), as
    arena.football.Play keeps it, and on_end names who kicked off from each. Its trace's
    frame f is the play at (f + 1) * ctrl_dt, so the frames past time_s are the tail
    (arena.football.record_play). Through the settle the props stand at `kickoff`.
    """
    pitch, goal, keeper = football.pitch, football.goal, football.keeper
    return {
        "id": football.id,
        "title": football.title,
        "rig": football.rig,
        "names": list(names),
        "ctrl_dt": CTRL_DT,
        "time_limit_s": football.time_limit_s,
        "pitch": {
            "length_m": pitch.length_m,
            "width_m": pitch.width_m,
            "corner_m": pitch.corner_m,
            "board_height_m": pitch.board_height_m,
            "board_thickness_m": pitch.board_thickness_m,
            "boards": _boxes(board_boxes(pitch, goal)),
            "nets": _boxes(net_boxes(pitch, goal)),
        },
        "goal": {"width_m": goal.width_m, "height_m": goal.height_m, "depth_m": goal.depth_m},
        "ball": {"radius_m": football.ball.radius_m},
        "keeper": {
            "diameter_m": keeper.diameter_m,
            "height_m": keeper.height_m,
            "x_m": football.keeper_x_m,
            "rail_m": football.rail_m,
        },
        "start_x_m": football.setback_m,
        "fall_hold_s": football.termination.fall_hold_s,
        "goals": list(match.goals),
        "plays": [
            {
                "seed": played.play.seed,
                "on_end": [names[0], names[1]] if played.ends == 0 else [names[1], names[0]],
                "scorer": played.play.scorer,
                "end": played.play.end,
                "time_s": played.play.time_s,
                "events": [{"time_s": e.time_s, "kind": e.kind, "k": e.k}
                           for e in played.play.events],
                "kickoff": [float(v) for v in each.kickoff],
                "settle_frames": int(each.settle.shape[1]),
                "frames": int(each.trace.shape[1]),
            }
            for played, each in zip(match.plays, recorded, strict=True)
        ],
    }


def create_football_app(football: Football, names: Sequence[str], match: Match,
                        recorded: Sequence[Recorded], frontend_dir: Path | None = None) -> FastAPI:
    """`recorded[k]` is match.plays[k]'s frames (arena.football.record_match's pair)."""
    app = FastAPI(title="Microduck football", docs_url=None, redoc_url=None)
    summary = football_summary(football, names, match, recorded)

    def play(k: int) -> Recorded:
        if not 0 <= k < len(recorded):
            raise HTTPException(404, f"the match has plays 0 to {len(recorded) - 1}")
        return recorded[k]

    @app.get("/api/football")
    def the_match() -> dict:
        return summary

    @app.get("/api/football/plays/{k}/trace")
    def play_trace(k: int) -> Response:
        return frames_response(play(k).trace)

    @app.get("/api/football/plays/{k}/settle")
    def play_settle(k: int) -> Response:
        return frames_response(play(k).settle)

    @app.get("/api/football/plays/{k}/props")
    def play_props(k: int) -> Response:
        return props_response(play(k).props)

    if frontend_dir is None:
        @app.get("/")
        def no_site() -> PlainTextResponse:
            return PlainTextResponse(NO_SITE, status_code=503)
    else:
        page = frontend_dir / "football.html"

        @app.get("/")
        def football_page() -> FileResponse:
            return FileResponse(page, headers={"Cache-Control": "no-store"})

        # Last, so /api/football wins: the bundle, the meshes, the design tokens.
        app.mount("/", StaticFiles(directory=frontend_dir), name="site")
    return app
