import dataclasses
import math

import mujoco
import numpy as np
import pytest

import arena.football
from arena.assets import ASSET_ROOT
from arena.cli import main
from arena.constants import CTRL_DT, JOINT_NAMES, NUM_JOINTS, TRACE_WIDTH
from arena.football import (
    PROP_WIDTH,
    TAIL_S,
    Event,
    Match,
    Play,
    Played,
    _opening,
    _Pitchside,
    board_boxes,
    compile_football,
    load_football,
    net_boxes,
    play_match,
    record_match,
    record_play,
    run_play,
    standings,
)
from arena.football_watch import create_football_app
from arena.manifest import ManifestError, all_events
from arena.policy import load_policy

REFERENCE = str(ASSET_ROOT / "policies" / "BEST_alpha_walking.onnx")
TOML = arena.football.FOOTBALL_TOML.read_text()


class _ZeroPolicy:
    def act(self, obs):
        return np.zeros(NUM_JOINTS, dtype=np.float32)


class _LieDown:
    """Folds both legs under the trunk and holds them there, whatever it sees: held on its
    mark through the settle, it goes down once the clock starts."""

    def __init__(self):
        self.action = np.zeros(NUM_JOINTS, dtype=np.float32)
        for side, sign in (("left", 1.0), ("right", -1.0)):
            pose = (("hip_pitch", -0.8), ("knee", 1.2), ("ankle", -0.8), ("hip_roll", -0.4))
            for joint, angle in pose:
                self.action[JOINT_NAMES.index(f"{side}_{joint}")] = sign * angle

    def act(self, obs):
        return self.action


class _NaN:
    """A broken policy: no action of it is a number."""

    def act(self, obs):
        return np.full(NUM_JOINTS, np.nan, dtype=np.float32)


@pytest.fixture
def mujoco_log_aside(tmp_path, monkeypatch):
    """MuJoCo writes a control it refuses to MUJOCO_LOG.TXT in the working directory: not the
    checkout."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture(scope="module")
def game():
    return load_football()


@pytest.fixture(scope="module")
def model(game):
    return compile_football(game)


@pytest.fixture(scope="module")
def walker():
    return load_policy(ASSET_ROOT / "policies" / "BEST_alpha_walking.onnx")


def _ball_at(model, sim, pos, vel=(0.0, 0.0, 0.0)):
    """The ball put at `pos`, unspun, moving at `vel`."""
    ball = model.joint("ball").id
    q, v = model.jnt_qposadr[ball], model.jnt_dofadr[ball]
    sim.data.qpos[q : q + 7] = [*pos, 1.0, 0.0, 0.0, 0.0]
    sim.data.qvel[v : v + 6] = [*vel, 0.0, 0.0, 0.0]
    mujoco.mj_forward(model, sim.data)


def kicked(game, model, policies, seed, pos, vel=(0.0, 0.0, 0.0), **changes):
    """A play whose kick-off has the ball at `pos` moving at `vel` the moment the settle is
    over, recorded: the Play, its trace and its props."""
    game = dataclasses.replace(game, **changes)
    sim, _ = _opening(game, model, policies, seed)
    _ball_at(model, sim, pos, vel)
    frames, props = [], []
    play = _Pitchside(game, sim, seed).play(frames, props)
    return play, np.stack(frames, axis=1), np.stack(props)


def test_the_football_match_loads(game):
    assert (game.id, game.title, game.rig, game.kind) == ("football", "Football", "legs",
                                                          "perpetual")
    assert (game.time_limit_s, game.seeds) == (20.0, (1, 2, 3))
    assert (game.pitch.length_m, game.pitch.width_m) == (2.2, 1.5)
    assert (game.goal.width_m, game.goal.height_m) == (0.6, 0.3)
    # A keeper's side stays post_gap_m clear of each post, its rail along the goal line.
    assert game.rail_m == pytest.approx(0.6 / 2 - 0.16 / 2 - 0.08)
    assert game.keeper_x_m == pytest.approx(2.2 / 2 - 0.02)


def test_the_match_is_not_an_event():
    """Not on the programme, the boards or the store: arena/events/ knows nothing of it."""
    assert arena.football.FOOTBALL_TOML.parent.name == "arena"
    assert "football" not in {manifest.id for manifest in all_events()}


@pytest.mark.parametrize(
    "changes, match",
    [
        ([('rig          = "legs"', 'rig          = "wings"')], "unknown rig"),
        ([("seeds        = [1, 2, 3]", "seeds        = [1, 1]")], "duplicate seeds"),
        ([("[ball]\n", "[ball]\nbounce = 1.0\n")], "unknown keys"),
        ([("mass_kg  = 0.03", "mass_kg  = 0.0")], "mass_kg must be a positive number"),
        ([("width_m  = 0.6", "width_m  = 1.0")], "end board"),
        ([("width_m           = 1.5", "width_m           = 3.0"),
          ("corner_m          = 0.25", "corner_m          = 1.1")], "some side board"),
        ([("diameter_m = 0.16", "diameter_m = 0.45")], "no rail"),
        ([("radius_m = 0.035", "radius_m = 0.15")], "under the bar"),
        ([("setback_m = 0.45", "setback_m = 0.95")], "in front of the keeper"),
        ([("spot_x_m = 0.75", "spot_x_m = 1.2")], "spots must be on the pitch"),
        ([("cone_deg   = 40.0", "cone_deg   = 90.0")], "cone_deg must be under 90"),
        ([("front_deg        = 60.0", "front_deg        = 180.0")],
         "front_deg must be under 180"),
        ([("fall_hold_s    = 0.3", "fall_hold_s    = 0.01")], "one control step"),
        ([("fall_gravity_z = -0.5", "fall_gravity_z = -1.5")], "between -1 and 1"),
    ],
)
def test_a_malformed_football_match_is_refused(tmp_path, changes, match):
    text = TOML
    for old, new in changes:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    path = tmp_path / "football.toml"
    path.write_text(text)
    with pytest.raises(ManifestError, match=match):
        load_football(path)


def test_the_model_holds_two_ducks_a_ball_two_keepers_the_boards_and_the_nets(game, model):
    for name in ("ball", "keeper0", "keeper1", "trunk_base", "duck1/trunk_base"):
        assert model.body(name).id >= 0
    boxes = board_boxes(game.pitch, game.goal) + net_boxes(game.pitch, game.goal)
    assert len(boxes) == 2 + 4 + 4 + 8
    for name, pos, half, _ in boxes:
        geom = model.geom(name)
        assert np.allclose(geom.pos, pos)
        assert np.allclose(geom.size, half)
    # The keepers run on rails across their goal mouths, the ball's hollow.
    for k, sx in enumerate((-1, 1)):
        joint = model.joint(f"keeper{k}")
        assert np.allclose(model.body(f"keeper{k}").pos, [sx * game.keeper_x_m, 0.0, 0.0])
        assert np.allclose(joint.range, [-game.rail_m, game.rail_m])
    assert model.geom("ball").size[0] == game.ball.radius_m


def test_the_ducks_kick_off_facing_each_other_either_side_of_the_ball(game, model, walker):
    sim, settle = _opening(game, model, (walker, walker), 1)
    assert settle.shape == (2, round(game.start.settle_s / CTRL_DT) + 1, TRACE_WIDTH)
    for k, (sx, facing) in enumerate(((-1, 1.0), (1, -1.0))):
        trunk = sim.ducks[k].adr.trunk
        x, y = sim.data.xpos[trunk][:2]
        assert x == pytest.approx(sx * game.setback_m, abs=0.03)
        assert abs(y) < 0.03
        forward = sim.data.xmat[trunk].reshape(3, 3)[:, 0]
        assert forward[0] * facing > math.cos(math.radians(10))
    ball = model.jnt_qposadr[model.joint("ball").id]
    assert np.allclose(sim.data.qpos[ball : ball + 3], [0.0, 0.0, game.ball.radius_m], atol=1e-3)


@pytest.mark.parametrize("side, scorer", [(1, 0), (-1, 1)])
def test_the_ball_all_the_way_over_a_goal_line_is_a_goal(game, model, side, scorer):
    """Over goal 1's line at +x is end 0's goal: duck 0 attacks it."""
    r = game.ball.radius_m
    play, _, props = kicked(game, model, (_ZeroPolicy(), _ZeroPolicy()), 1,
                            (side * (game.pitch.length_m / 2 + r + 0.01), side * 0.25, r))
    assert (play.scorer, play.end, play.time_s) == (scorer, "goal", CTRL_DT)
    assert props.shape == (1, PROP_WIDTH)


def test_a_ball_on_the_line_is_not_yet_a_goal(game, model):
    r = game.ball.radius_m
    play, _, _ = kicked(game, model, (_ZeroPolicy(), _ZeroPolicy()), 1,
                        (game.pitch.length_m / 2 + r - 0.01, 0.25, r), time_limit_s=0.1)
    assert (play.scorer, play.end) == (None, "whistle")


def test_a_ball_over_the_boards_is_put_back_on_the_nearest_free_spot(game, model):
    r = game.ball.radius_m
    play, _, props = kicked(game, model, (_ZeroPolicy(), _ZeroPolicy()), 1, (0.3, 0.95, r),
                            time_limit_s=0.1)
    assert play.end == "whistle"
    assert play.events[0] == Event(CTRL_DT, "out", None)
    # The step that saw it out still shows it there; the next has it on the spot.
    assert props[0, 1] > game.pitch.width_m / 2
    spot = (game.restart.spot_x_m, game.restart.spot_y_m)
    assert np.allclose(props[1, 0:2], spot, atol=0.01)


def test_a_ball_beside_a_goal_over_the_end_board_is_out(game, model):
    r = game.ball.radius_m
    play, _, _ = kicked(game, model, (_ZeroPolicy(), _ZeroPolicy()), 1,
                        (game.pitch.length_m / 2 + 0.1, 0.4, r), time_limit_s=0.1)
    assert play.end == "whistle"
    assert play.events[0] == Event(CTRL_DT, "out", None)


def test_a_keeper_the_ball_reaches_clears_it_upfield(game, model):
    r = game.ball.radius_m
    play, _, props = kicked(game, model, (_ZeroPolicy(), _ZeroPolicy()), 1, (0.85, 0.0, r),
                            vel=(1.0, 0.0, 0.0), time_limit_s=0.6)
    assert play.end == "whistle"
    saves = [e for e in play.events if e.kind == "save"]
    assert saves and saves[0].k == 1
    at = round(saves[0].time_s / CTRL_DT) - 1
    # Cleared back the way it came, keeper 1 clearing toward -x.
    assert props[at + 5, 0] < props[at, 0]


def test_a_duck_that_goes_down_stays_down_and_the_play_goes_on(game, model, walker):
    play, _, _ = kicked(game, model, (_LieDown(), walker), 1, (0.0, 0.0, 0.035),
                        time_limit_s=1.5)
    assert (play.end, play.time_s) == ("whistle", 1.5)
    assert [(e.kind, e.k) for e in play.events if e.kind == "fall"] == [("fall", 0)]


def test_both_down_ends_the_play_goalless(game, model):
    play, _, _ = kicked(game, model, (_LieDown(), _LieDown()), 1, (0.0, 0.0, 0.035),
                        time_limit_s=3.0)
    assert (play.scorer, play.end) == (None, "down")
    assert sorted(e.k for e in play.events if e.kind == "fall") == [0, 1]
    assert play.time_s < 3.0


def test_a_policy_whose_action_is_not_a_number_gives_the_goal_away(game, model, walker,
                                                                    mujoco_log_aside):
    match = play_match(game, _NaN(), walker, model)
    assert match.goals == (0, 2 * len(game.seeds))
    assert {(p.play.end, p.play.time_s) for p in match.plays} == {("fault", CTRL_DT)}
    both = run_play(game, model, (_NaN(), _NaN()), 1)
    assert (both.scorer, both.end) == (None, "fault")


def test_a_simulation_mujoco_resets_is_void(game, model, walker, monkeypatch):
    monkeypatch.setattr(arena.football, "_diverged", lambda data: True)
    assert run_play(game, model, (walker, walker), 2) == Play(2, None, "void", CTRL_DT, ())
    recorded = record_play(game, model, (walker, walker), 2)
    assert recorded.trace.shape == (2, 0, TRACE_WIDTH)
    assert recorded.props.shape == (0, PROP_WIDTH)


def test_a_play_is_the_same_every_time_and_the_same_recorded(game, model, walker):
    first = run_play(game, model, (walker, walker), 1)
    assert first == run_play(game, model, (walker, walker), 1)
    recorded = record_play(game, model, (walker, walker), 1)
    assert recorded.play == first
    judged = round(first.time_s / CTRL_DT)
    tail = round(TAIL_S / CTRL_DT) if first.end == "goal" else 0
    assert recorded.trace.shape == (2, judged + tail, TRACE_WIDTH)
    assert recorded.props.shape == (judged + tail, PROP_WIDTH)
    assert recorded.settle.shape == (2, round(game.start.settle_s / CTRL_DT) + 1, TRACE_WIDTH)
    # Through the settle the ball sits on the centre spot and each keeper mid-goal.
    assert np.allclose(recorded.kickoff[0:3], [0.0, 0.0, game.ball.radius_m], atol=2e-3)
    assert np.allclose(recorded.kickoff[7:9], 0.0, atol=1e-3)
    # The keepers never leave their rails.
    assert np.all(np.abs(recorded.props[:, 7:9]) <= game.rail_m + 1e-3)


def test_a_recorded_goal_runs_on_to_show_the_ball_in_the_net(game, model, monkeypatch):
    real = arena.football._opening
    r = game.ball.radius_m

    def opening(*args):
        sim, settle = real(*args)
        _ball_at(model, sim, (game.pitch.length_m / 2 + r + 0.01, -0.25, r),
                 vel=(0.3, 0.0, 0.0))
        return sim, settle

    monkeypatch.setattr(arena.football, "_opening", opening)
    recorded = record_play(game, model, (_ZeroPolicy(), _ZeroPolicy()), 1)
    assert (recorded.play.scorer, recorded.play.end) == (0, "goal")
    tail = round(TAIL_S / CTRL_DT)
    assert recorded.trace.shape == (2, 1 + tail, TRACE_WIDTH)
    assert recorded.props.shape == (1 + tail, PROP_WIDTH)
    # Still in goal 1's pocket at the end of the tail, behind the line and under the bar.
    x, y, z = recorded.props[-1, 0:3]
    assert game.pitch.length_m / 2 < x < game.pitch.length_m / 2 + game.goal.depth_m
    assert abs(y) < game.goal.width_m / 2 and z < game.goal.height_m


def test_a_match_plays_every_seed_from_both_ends(game, model, walker):
    short = dataclasses.replace(game, time_limit_s=1.0, seeds=(1, 2))
    match = play_match(short, walker, walker, model)
    assert [(p.play.seed, p.ends) for p in match.plays] == [(1, 0), (1, 1), (2, 0), (2, 1)]
    # The same policy at both ends: swapping them changes nothing.
    assert match.plays[0].play == match.plays[1].play
    assert (match.goals, match.winner) == ((0, 0), None)


def _scored(*scorers) -> Match:
    """A match whose plays end with these scorers, as the match numbers them (0 is A)."""
    return Match(tuple(
        Played(Play(1, s, "whistle" if s is None else "goal", 1.0, ()), 0) for s in scorers))


def test_a_goal_counts_for_whoever_kicked_off_from_the_scoring_end():
    goal_from_end_0 = Play(1, 0, "goal", 3.0, ())
    assert Played(goal_from_end_0, 0).scorer == 0
    assert Played(goal_from_end_0, 1).scorer == 1
    assert Played(Play(1, None, "whistle", 20.0, ()), 1).scorer is None
    assert (_scored(0, 1, 0, None).goals, _scored(0, 1, 0, None).winner) == ((2, 1), 0)
    assert (_scored(1, None).winner, _scored(None, None).winner) == (1, None)


def test_the_table_counts_three_for_a_win_one_for_a_draw():
    matches = {(0, 1): _scored(0, 0), (0, 2): _scored(0, 1), (1, 2): _scored(0)}
    table = standings(["a", "b", "c"], matches)
    assert [(s.name, s.won, s.drawn, s.lost, s.scored, s.conceded, s.points)
            for s in table] == [("a", 1, 1, 0, 3, 1, 4), ("b", 1, 0, 1, 1, 2, 3),
                                ("c", 0, 1, 1, 1, 2, 1)]


def test_the_table_breaks_a_tie_on_difference_then_goals_then_name():
    matches = {(0, 1): _scored(0, 1), (0, 2): _scored(0, 0, 0), (1, 2): _scored(0, 0)}
    table = standings(["c", "b", "a"], matches)
    # c and b both won one and drew one; c by three, b by two.
    assert [(s.name, s.points, s.difference) for s in table] == [
        ("c", 4, 3), ("b", 4, 2), ("a", 0, -5)]
    level = {(0, 1): _scored(0, 1), (0, 2): _scored(None), (1, 2): _scored(None)}
    assert [s.name for s in standings(["z", "y", "x"], level)] == ["y", "z", "x"]


@pytest.fixture
def probe(tmp_path, monkeypatch):
    """A short football match, in arena/football.toml's place as the shell finds it."""
    text = (TOML.replace('id           = "football"', 'id           = "probe"')
            .replace("time_limit_s = 20.0", "time_limit_s = 0.2")
            .replace("seeds        = [1, 2, 3]", "seeds        = [1]"))
    (tmp_path / "probe.toml").write_text(text)
    monkeypatch.setattr(arena.football, "FOOTBALL_TOML", tmp_path / "probe.toml")


def test_football_prints_every_play_and_the_score(probe, capsys):
    assert main(["football", REFERENCE, REFERENCE]) == 0
    out = capsys.readouterr().out
    assert "each played from both ends" in out
    assert out.count("seed 1  ") == 2
    assert "the whistle: no goal" in out
    assert "BEST_alpha_walking (1) 0–0 BEST_alpha_walking (2)" in out


def test_three_policies_play_a_football_league(probe, capsys):
    assert main(["football", REFERENCE, REFERENCE, REFERENCE]) == 0
    out = capsys.readouterr().out
    assert "for  against  points" in out
    assert out.count("0–0") == 3
    assert "seed 1  " not in out


def test_football_needs_two_policies(capsys):
    assert main(["football", REFERENCE]) == 1
    assert "two policies" in capsys.readouterr().err


@pytest.mark.parametrize("port", ["0", "70000", "-1", "http"])
def test_football_refuses_a_port_it_cannot_serve_on(port, capsys):
    """Before any match is played, as the shell refuses any argument."""
    with pytest.raises(SystemExit) as refused:
        main(["football", REFERENCE, REFERENCE, "--watch", "--port", port])
    assert refused.value.code == 2
    assert "not a port" in capsys.readouterr().err


def test_football_takes_a_port_from_1_to_65535():
    from arena.cli import _port

    assert (_port("1"), _port("8767"), _port("65535")) == (1, 8767, 65535)


def test_football_watch_shows_one_match(capsys):
    assert main(["football", REFERENCE, REFERENCE, REFERENCE, "--watch"]) == 1
    assert "two policies" in capsys.readouterr().err


def test_football_watch_refuses_a_busy_port(capsys):
    import socket

    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        assert main(["football", REFERENCE, REFERENCE, "--watch", "--port", str(port)]) == 1
    assert "busy" in capsys.readouterr().err


@pytest.mark.parametrize(
    "play, said",
    [
        (Play(1, 0, "goal", 4.5, ()), "goal, a, at 4.50 s"),
        (Play(1, 1, "goal", 9.24, ()), "goal, b, at 9.24 s"),
        (Play(1, 1, "fault", 0.02, ()), "a faulted at 0.02 s: the goal to b"),
        (Play(1, None, "fault", 0.02, ()), "both faulted at 0.02 s: no goal"),
        (Play(1, None, "down", 7.1, ()), "both down at 7.10 s: no goal"),
        (Play(1, None, "void", 0.4, ()), "void at 0.40 s: MuJoCo had to reset the simulation"),
        (Play(1, None, "whistle", 20.0, ()), "the whistle: no goal"),
    ],
)
def test_the_shell_says_how_a_play_ended(play, said):
    from arena.cli import _football_how

    assert _football_how(play, ["a", "b"]) == said


@pytest.fixture(scope="module")
def watched(game, model, walker):
    """A short match recorded, and its names, as `arena football --watch` serves one."""
    short = dataclasses.replace(game, time_limit_s=0.2, seeds=(1,))
    match, recorded = record_match(short, walker, _ZeroPolicy(), model)
    return short, ["walker", "zero"], match, recorded


def test_the_watch_app_serves_the_match(watched, tmp_path):
    from fastapi.testclient import TestClient

    (tmp_path / "football.html").write_text("<!doctype html><title>football</title>")
    game, names, match, recorded = watched
    client = TestClient(create_football_app(game, names, match, recorded, tmp_path))
    summary = client.get("/api/football").json()
    assert (summary["id"], summary["title"], summary["names"]) == ("football", "Football", names)
    assert summary["goals"] == list(match.goals)
    assert summary["pitch"]["length_m"] == game.pitch.length_m
    assert len(summary["pitch"]["boards"]) == len(board_boxes(game.pitch, game.goal))
    assert len(summary["pitch"]["nets"]) == len(net_boxes(game.pitch, game.goal))
    assert summary["keeper"]["x_m"] == pytest.approx(game.keeper_x_m)
    assert summary["keeper"]["rail_m"] == pytest.approx(game.rail_m)
    assert [play["on_end"] for play in summary["plays"]] == [names, names[::-1]]
    assert [play["frames"] for play in summary["plays"]] == [r.trace.shape[1] for r in recorded]
    for k, each in enumerate(recorded):
        assert summary["plays"][k]["kickoff"] == pytest.approx(each.kickoff.tolist())
        for part, frames in (("trace", each.trace), ("settle", each.settle)):
            sent = client.get(f"/api/football/plays/{k}/{part}")
            assert sent.headers["X-Frame-Count"] == str(frames.shape[1])
            got = np.frombuffer(sent.content, dtype="<f4").reshape(frames.shape)
            assert np.array_equal(got, frames)
        sent = client.get(f"/api/football/plays/{k}/props")
        assert sent.headers["X-Frame-Count"] == str(each.props.shape[0])
        assert sent.headers["X-Prop-Width"] == str(PROP_WIDTH)
        got = np.frombuffer(sent.content, dtype="<f4").reshape(each.props.shape)
        assert np.array_equal(got, each.props)
    for part in ("trace", "settle", "props"):
        assert client.get(f"/api/football/plays/{len(recorded)}/{part}").status_code == 404
    assert "<title>football</title>" in client.get("/").text


def test_the_watch_app_says_when_the_football_page_is_not_built(watched):
    from fastapi.testclient import TestClient

    client = TestClient(create_football_app(*watched, frontend_dir=None))
    page = client.get("/")
    assert page.status_code == 503
    assert "npm run build" in page.text
    assert client.get("/api/football").status_code == 200


def test_watch_plays_the_football_match_then_serves_it(probe, monkeypatch, capsys):
    from fastapi.testclient import TestClient

    import arena.workshop.cli

    served = {}
    monkeypatch.setattr(arena.workshop.cli, "serve",
                        lambda app, port: served.update(app=app, port=port))
    assert main(["football", REFERENCE, REFERENCE, "--watch", "--no-browser",
                 "--port", "8799"]) == 0
    out = capsys.readouterr().out
    assert "BEST_alpha_walking (1) 0–0 BEST_alpha_walking (2)" in out
    assert "http://127.0.0.1:8799/" in out
    assert served["port"] == 8799
    summary = TestClient(served["app"]).get("/api/football").json()
    assert (summary["id"], len(summary["plays"])) == ("probe", 2)
