"""Football: two policies on one pitch, a ball between them, a Reachy Mini in each goal.

A proposal, not an event. An event puts one policy on a course and ranks it by a number
it earns alone; a match puts two on the same physics and asks which one scores. So
nothing here is on the programme, the boards or the store: arena/football.toml is not
in arena/events/, and `arena football` plays it from the shell.
docs/superpowers/specs/2026-10-24-football-match-design.md is the proposal: what was
measured, and the decisions it leaves open.

A walking policy follows a velocity command and has never seen a ball. So each duck has
a coach (_Coach) that reads the pitch and asks its policy for a forward speed and a turn
rate, as a joystick would, and nothing else; and the strike is assisted
(_Pitchside._strike): a duck that walks into the ball facing the right way sends it on at
a set speed, the kick it cannot make yet. Whether it gets there, and on its feet, is
the policy's.

It is built from the engine's own parts and changes none of them. The model is built
the way a stage's is (arena.course.compile_stage): a rig's MJCF with its servos as BAM
motors, the second duck grafted on under its prefix. A play opens as every run does
(arena.runner._start: training's reset, the perturbation, the untimed settle), each
duck held on its mark through the settle (_opening), and steps the shared physics as a
stage does. The pitch, the ball, the keepers, the hold, the coaches and the referee
are new.

A match is data, as an event is: arena/football.toml, validated as strictly as a
manifest and refused with the same ManifestError.
"""

import math
import tomllib
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from itertools import combinations
from pathlib import Path

import mujoco
import numpy as np

from .constants import CTRL_DT, DEFAULT_POSE, JOINT_NAMES, TIMESTEP, TRACE_WIDTH
from .course import SPAWN_HEIGHT_M, _compiled, _motorized, _robot, _sub, _yaw_quat, duck_prefix
from .manifest import (
    KINDS,
    RIGS,
    ManifestError,
    Start,
    Termination,
    _command,
    _refuse_unknown,
    _require,
)
from .runner import _reset_by_mujoco, _start

# The match `arena football` plays.
FOOTBALL_TOML = Path(__file__).with_name("football.toml")

# Duck k kicks off from end k: duck 0 at -x, facing the goal at +x it attacks; duck 1
# the other way round. Keeper k keeps end k's goal, the one duck k defends.
YAWS_DEG = (0.0, 180.0)

NET_THICKNESS_M = 0.01
BALL_SLIDE = 0.8  # the ball's sliding friction; [ball] sets the other two
KEEPER_LIFT_M = 0.002  # off the floor: it slides on its rail, not on the turf
# The rail's position servo: stiff enough to be where it is sent within a control step.
KEEPER_KP = 400.0
KEEPER_KV = 40.0
KEEPER_FORCE_N = 40.0

# The coach, fitted to the reference walker (BEST_alpha_walking): it takes no step under
# a forward command of about 0.25 and will not turn on the spot under a turn rate of
# about 1.2, so every command it gives is outside both.
WALK_VX = 0.6  # forward, while the target is within TURN_ERR_RAD of its heading
STEER_GAIN = 2.0  # turn rate per radian off, while walking
MAX_STEER_WZ = 1.0
TURN_ERR_RAD = 0.5  # further round than this, it turns almost on the spot
TURN_VX = 0.3
TURN_WZ = 2.0
BACK_VX = -0.5  # backing off a board it faces square on
WALL_MARGIN_M = 0.12  # every target is kept this far inside the boards
WALL_NEAR_M = 0.12  # nearer a board it faces than this, it steps no further in
# Where it heads: BEHIND_M behind the ball on the line from its aim; round the ball by
# DETOUR_M when it is on the wrong side of it; and on through the ball by THROUGH_M once
# it is behind it within LANE_M of that line, LANE_EXIT_M to stay at it.
BEHIND_M = 0.12
DETOUR_M = 0.18
LANE_M = 0.06
LANE_EXIT_M = 0.12
THROUGH_M = 0.3
# Its aim: AIM_IN_M inside the goal, on whichever side of the keeper has the wider gap,
# the ball's radius and AIM_MARGIN_M in from the post. It changes side only for a gap
# AIM_SWITCH_M wider.
AIM_IN_M = 0.12
AIM_MARGIN_M = 0.06
AIM_SWITCH_M = 0.08

# A ball that moves STALL_MOVE_M is not stuck; one put down again is dropped from just
# above the turf.
STALL_MOVE_M = 0.05
RESTART_DROP_M = 0.005
# Out of play: over a side board by OVER_SIDE_M, through the floor, more than
# BEHIND_GOAL_M past the back of a goal, or over an end board beside or above a goal.
OVER_SIDE_M = 0.15
BEHIND_GOAL_M = 0.3
BELOW_FLOOR_M = 0.1

# How long a recorded play runs on after a goal, the ducks asked to stand still: the
# ball in the net. Watching only; the referee has already decided.
TAIL_S = 1.5

# A prop frame: the ball's position and quaternion (w, x, y, z), then each keeper's
# place on its rail.
PROP_WIDTH = 9


@dataclass(frozen=True)
class Pitch:
    length_m: float  # goal line to goal line
    width_m: float  # side board to side board
    corner_m: float  # each corner cut off this far along both its sides
    board_height_m: float
    board_thickness_m: float


@dataclass(frozen=True)
class Goal:
    width_m: float  # the mouth, post to post
    height_m: float
    depth_m: float  # the pocket behind the line


@dataclass(frozen=True)
class Ball:
    radius_m: float
    mass_kg: float
    spin: float  # MuJoCo's torsional friction
    roll: float  # and its rolling friction


@dataclass(frozen=True)
class Keeper:
    diameter_m: float
    height_m: float
    mass_kg: float
    line_m: float  # its axis this far in front of the goal line
    post_gap_m: float  # its rail stops this short of each post
    lag_s: float  # it goes where the ball was this long ago
    speed_m_s: float  # no faster than this


@dataclass(frozen=True)
class Save:
    hold_s: float
    speed_m_s: float
    cone_deg: float
    cooldown_s: float


@dataclass(frozen=True)
class Strike:
    front_deg: float
    shot_range_m: float
    align_deg: float
    shot_speed_m_s: float
    shot_cooldown_s: float
    touch_cone_deg: float
    touch_speed_m_s: float
    touch_cooldown_s: float
    noise_deg: float


@dataclass(frozen=True)
class Restart:
    stall_s: float
    jam_m: float
    spot_x_m: float
    spot_y_m: float
    free_m: float


@dataclass(frozen=True)
class Football:
    id: str
    title: str
    rig: str
    kind: str
    time_limit_s: float
    seeds: tuple[int, ...]
    # Read by arena.runner._start exactly as an event's is: the keyframe, the settle and
    # the perturbation. Of a manifest, _start reads nothing else but its id, which names
    # the random streams; a Football has both, under those names.
    start: Start
    setback_m: float
    # What each duck is asked when it is not playing: through the settle, and down.
    command: tuple[float, ...]
    pitch: Pitch
    goal: Goal
    ball: Ball
    keeper: Keeper
    save: Save
    strike: Strike
    restart: Restart
    termination: Termination

    @property
    def rail_m(self) -> float:
        """How far each keeper can slide from the middle of its goal, either way."""
        return self.goal.width_m / 2 - self.keeper.diameter_m / 2 - self.keeper.post_gap_m

    @property
    def keeper_x_m(self) -> float:
        """How far from the centre spot each keeper's rail runs: keeper 0's at -x."""
        return self.pitch.length_m / 2 - self.keeper.line_m


def _number(raw: dict, key: str, where: str, *, zero: bool = False) -> float:
    """A finite number above zero, or at least zero where `zero` allows it."""
    value = _require(raw, key, where)
    # bool first: TOML's true is a Python int, and would otherwise read as 1.
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
        or (value == 0 and not zero)
    ):
        need = "a number of at least 0" if zero else "a positive number"
        raise ManifestError(f"{where}: {key} must be {need}, got {value!r}")
    return float(value)


def _table(raw: dict, key: str, allowed: set[str], where: str, name: str) -> dict:
    table = _require(raw, key, where)
    if not isinstance(table, dict):
        raise ManifestError(f"{where}: {key} must be a table")
    _refuse_unknown(table, allowed, name)
    return table


def _section(raw: dict, where: str, cls, zero: frozenset[str] = frozenset()):
    """A table of numbers, one per field of `cls`, named after it: [pitch] is a Pitch."""
    name = cls.__name__.lower()
    keys = [field.name for field in fields(cls)]
    table = _table(raw, name, set(keys), where, f"[{name}]")
    return cls(**{key: _number(table, key, f"[{name}]", zero=key in zero) for key in keys})


def load_football(path: Path | None = None) -> Football:
    """The match at `path`: arena/football.toml (FOOTBALL_TOML) unless told otherwise."""
    path = FOOTBALL_TOML if path is None else path
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)
    where = str(path)
    _refuse_unknown(
        raw,
        {"id", "title", "rig", "kind", "time_limit_s", "seeds", "command", "start",
         "pitch", "goal", "ball", "keeper", "save", "strike", "restart", "termination"},
        where,
    )
    football_id = _require(raw, "id", where)
    if not isinstance(football_id, str) or not football_id:
        raise ManifestError(f"{where}: id must be a name, got {football_id!r}")
    rig = _require(raw, "rig", where)
    if rig not in RIGS:
        raise ManifestError(f"{where}: unknown rig {rig!r}, expected one of {RIGS}")
    kind = _require(raw, "kind", where)
    if kind not in KINDS:
        raise ManifestError(f"{where}: unknown kind {kind!r}, expected one of {KINDS}")
    seeds = _require(raw, "seeds", where)
    if not isinstance(seeds, list) or not seeds or not all(
        not isinstance(s, bool) and isinstance(s, int) for s in seeds
    ):
        raise ManifestError(f"{where}: seeds must be a list of whole numbers, got {seeds!r}")
    if len(set(seeds)) != len(seeds):
        raise ManifestError(f"{where}: duplicate seeds")

    start_raw = _table(raw, "start", {"keyframe", "settle_s", "setback_m", "perturbation"},
                       where, "[start]")
    perturb = _table(start_raw, "perturbation", {"joint_rad", "yaw_deg"},
                     "[start]", "[start.perturbation]")
    command_raw = _table(raw, "command", {"vel", "head", "body"}, where, "[command]")
    termination_raw = _table(raw, "termination", {"fall_gravity_z", "fall_hold_s"}, where,
                             "[termination]")
    pitch = _section(raw, where, Pitch)
    goal = _section(raw, where, Goal)
    ball = _section(raw, where, Ball, frozenset({"spin", "roll"}))
    keeper = _section(raw, where, Keeper, frozenset({"line_m"}))
    save = _section(raw, where, Save)
    strike = _section(raw, where, Strike, frozenset({"noise_deg"}))
    restart = _section(raw, where, Restart)

    gravity_z = _require(termination_raw, "fall_gravity_z", "[termination]")
    if (isinstance(gravity_z, bool) or not isinstance(gravity_z, (int, float))
            or not -1.0 < gravity_z < 1.0):
        raise ManifestError(f"{where}: [termination] fall_gravity_z must be a number between -1 "
                            f"and 1 (projected gravity's z), got {gravity_z!r}")
    termination = Termination(
        fall_gravity_z=float(gravity_z),
        fall_hold_s=_number(termination_raw, "fall_hold_s", "[termination]"),
    )
    if termination.fall_hold_s < CTRL_DT:
        raise ManifestError(f"{where}: [termination] fall_hold_s must be at least one control "
                            f"step ({CTRL_DT} s)")
    keyframe = _require(start_raw, "keyframe", "[start]")
    if not isinstance(keyframe, str) or not keyframe:
        raise ManifestError(f"{where}: [start] keyframe must be a name, got {keyframe!r}")

    football = Football(
        id=football_id,
        title=_require(raw, "title", where),
        rig=rig,
        kind=kind,
        time_limit_s=_number(raw, "time_limit_s", where),
        seeds=tuple(seeds),
        start=Start(
            keyframe=keyframe,
            settle_s=_number(start_raw, "settle_s", "[start]", zero=True),
            joint_rad=_number(perturb, "joint_rad", "[start.perturbation]", zero=True),
            yaw_deg=_number(perturb, "yaw_deg", "[start.perturbation]", zero=True),
        ),
        setback_m=_number(start_raw, "setback_m", "[start]"),
        command=_command(command_raw),
        pitch=pitch,
        goal=goal,
        ball=ball,
        keeper=keeper,
        save=save,
        strike=strike,
        restart=restart,
        termination=termination,
    )
    _check(football, where)
    return football


def _check(football: Football, where: str) -> None:
    """What no single number shows: that the pieces fit on the pitch together."""
    pitch, goal = football.pitch, football.goal
    if pitch.width_m / 2 - pitch.corner_m - goal.width_m / 2 <= 0:
        raise ManifestError(f"{where}: [goal] width_m must leave some end board between the "
                            "mouth and each corner cut")
    if 2 * pitch.corner_m >= pitch.length_m:
        raise ManifestError(f"{where}: [pitch] corner_m must leave some side board")
    if football.rail_m <= 0:
        raise ManifestError(f"{where}: [keeper] diameter_m and twice post_gap_m must be "
                            "narrower than the goal, or the keeper has no rail")
    if 2 * football.ball.radius_m >= goal.height_m:
        raise ManifestError(f"{where}: [ball] must fit under the bar ([goal] height_m)")
    if football.setback_m >= football.keeper_x_m - football.keeper.diameter_m:
        raise ManifestError(f"{where}: [start] setback_m must leave room in front of the keeper")
    restart = football.restart
    if (restart.spot_x_m >= pitch.length_m / 2 or restart.spot_y_m >= pitch.width_m / 2
            or restart.spot_x_m + restart.spot_y_m
            >= pitch.length_m / 2 + pitch.width_m / 2 - pitch.corner_m):
        raise ManifestError(f"{where}: [restart] spots must be on the pitch")
    for name, value, most in (("[strike] front_deg", football.strike.front_deg, 180.0),
                              ("[strike] align_deg", football.strike.align_deg, 180.0),
                              ("[strike] touch_cone_deg", football.strike.touch_cone_deg, 180.0),
                              ("[save] cone_deg", football.save.cone_deg, 90.0)):
        if value >= most:
            raise ManifestError(f"{where}: {name} must be under {most:g}")


Vec3 = tuple[float, float, float]
Box = tuple[str, Vec3, Vec3, float]


def board_boxes(pitch: Pitch, goal: Goal) -> list[Box]:
    """The boards round the pitch, as `(name, pos, half_extents, yaw_rad)`, the turf at
    z = 0: a side board along each touchline, the end boards either side of each mouth,
    and a board across each corner cut. One function for the physics and for whatever
    draws it (arena.football_watch sends them to football-venue.js)."""
    length, width = pitch.length_m, pitch.width_m
    height, thick, corner = pitch.board_height_m, pitch.board_thickness_m, pitch.corner_m
    boxes: list[Box] = []
    half_side = length / 2 - corner
    for j, y in enumerate((width / 2 + thick / 2, -width / 2 - thick / 2)):
        boxes.append((f"side{j}", (0.0, y, height / 2), (half_side, thick / 2, height / 2), 0.0))
    seg = width / 2 - corner - goal.width_m / 2
    for e, sx in enumerate((-1, 1)):
        x = sx * (length / 2 + thick / 2)
        for j, sy in enumerate((1, -1)):
            yc = sy * (goal.width_m / 2 + seg / 2)
            boxes.append((f"end{e}{j}", (x, yc, height / 2), (thick / 2, seg / 2, height / 2),
                          0.0))
    diag = math.hypot(corner, corner)
    for e, sx in enumerate((-1, 1)):
        for j, sy in enumerate((1, -1)):
            nx, ny = sx / math.sqrt(2), sy / math.sqrt(2)
            mx = sx * (length / 2 - corner / 2) + nx * thick / 2
            my = sy * (width / 2 - corner / 2) + ny * thick / 2
            boxes.append((f"corner{e}{j}", (mx, my, height / 2),
                          (diag / 2 + thick / 2, thick / 2, height / 2), math.atan2(-sy, sx)))
    return boxes


def net_boxes(pitch: Pitch, goal: Goal) -> list[Box]:
    """Each goal's pocket behind its mouth, as board_boxes gives them: the back net, a
    side net each side, the roof. Goal e is end e's: goal 0 at -x."""
    length, t = pitch.length_m, NET_THICKNESS_M
    width, height, depth = goal.width_m, goal.height_m, goal.depth_m
    boxes: list[Box] = []
    for e, sx in enumerate((-1, 1)):
        boxes.append((f"goal{e}_back", (sx * (length / 2 + depth + t / 2), 0.0, height / 2),
                      (t / 2, width / 2 + t, height / 2), 0.0))
        for j, sy in enumerate((1, -1)):
            boxes.append((f"goal{e}_side{j}",
                          (sx * (length / 2 + depth / 2), sy * (width / 2 + t / 2), height / 2),
                          (depth / 2, t / 2, height / 2), 0.0))
        boxes.append((f"goal{e}_roof", (sx * (length / 2 + depth / 2), 0.0, height + t / 2),
                      (depth / 2, width / 2 + t, t / 2), 0.0))
    return boxes


def _football_xml(football: Football) -> tuple[str, dict[str, bytes]]:
    """Duck 0's MJCF, with the physics step, the turf, the boards, the nets and a keyframe."""
    root, assets = _robot(football.rig)
    _sub(root, "option", timestep=TIMESTEP)
    worldbody = root.find("worldbody")
    course = _sub(worldbody, "body", name="course")
    _sub(course, "geom", name="floor", type="plane", size="0 0 0.05")
    for name, pos, size, yaw in (board_boxes(football.pitch, football.goal)
                                 + net_boxes(football.pitch, football.goal)):
        _sub(course, "geom", name=name, type="box", pos=" ".join(str(v) for v in pos),
             size=" ".join(str(v) for v in size), euler=f"0 0 {yaw}")

    # Every joint in document order, as a stage's STAND keyframe has them
    # (arena.course._inject_keyframe); where each duck stands is set once both are in the
    # model (compile_football).
    pose_by_name = dict(zip(JOINT_NAMES, DEFAULT_POSE))
    joints = [pose_by_name.get(j.get("name"), 0.0) for j in worldbody.iter("joint")]
    _sub(
        _sub(root, "keyframe"),
        "key",
        name=football.start.keyframe,
        qpos=" ".join(str(v) for v in (0.0, 0.0, SPAWN_HEIGHT_M, 1.0, 0.0, 0.0, 0.0, *joints)),
        ctrl=" ".join("0.0" for _ in JOINT_NAMES),
    )
    return ET.tostring(root, encoding="unicode"), assets


def _free(model, k: int) -> int:
    """The qpos address of duck k's trunk: its position, then its quaternion."""
    trunk = model.body(f"{duck_prefix(k)}trunk_base").id
    return int(model.jnt_qposadr[model.body_jntadr[trunk]])


def compile_football(football: Football) -> mujoco.MjModel:
    """Two ducks either side of the centre spot facing each other, the ball between them,
    a keeper on a rail in each goal.

    Duck 0 is its rig's MJCF with the servos as motors, as a troupe's first duck is
    (arena.course.compile_stage); duck 1 is the same rig grafted on under its prefix.
    The ball is a hollow sphere on a free joint. A keeper is a cylinder on a slide joint
    across its goal, driven by a position servo; it never touches the boards or the
    nets, so its rail runs through them as it must between the posts. Each duck has a
    mark, a mocap body its trunk is welded to through the settle (_opening). The
    keyframe has each duck standing in the default pose, the ball on the centre spot
    and each keeper in the middle of its goal.
    """
    spec = _motorized(*_football_xml(football))
    root, assets = _robot(football.rig)
    robot = _motorized(ET.tostring(root, encoding="unicode"), assets)
    frame = spec.worldbody.add_frame(pos=[football.setback_m, 0.0, 0.0],
                                     quat=_yaw_quat(YAWS_DEG[1]))
    spec.attach(robot, prefix=duck_prefix(1), frame=frame)

    ball = football.ball
    body = spec.worldbody.add_body(name="ball", pos=[0.0, 0.0, ball.radius_m])
    body.add_freejoint(name="ball")
    geom = body.add_geom(name="ball", type=mujoco.mjtGeom.mjGEOM_SPHERE,
                         size=[ball.radius_m, 0.0, 0.0], mass=ball.mass_kg, condim=6,
                         friction=[BALL_SLIDE, ball.spin, ball.roll])
    geom.typeinertia = mujoco.mjtGeomInertia.mjINERTIA_SHELL

    keeper, rail = football.keeper, football.rail_m
    for k, sx in enumerate((-1, 1)):
        body = spec.worldbody.add_body(name=f"keeper{k}", pos=[sx * football.keeper_x_m, 0.0, 0.0])
        body.add_joint(name=f"keeper{k}", type=mujoco.mjtJoint.mjJNT_SLIDE, axis=[0.0, 1.0, 0.0],
                       range=[-rail, rail], limited=True)
        body.add_geom(name=f"keeper{k}", type=mujoco.mjtGeom.mjGEOM_CYLINDER,
                      size=[keeper.diameter_m / 2, keeper.height_m / 2, 0.0],
                      pos=[0.0, 0.0, keeper.height_m / 2 + KEEPER_LIFT_M], mass=keeper.mass_kg)
        spec.add_exclude(bodyname1=f"keeper{k}", bodyname2="course")
        servo = spec.add_actuator(name=f"keeper{k}", target=f"keeper{k}",
                                  trntype=mujoco.mjtTrn.mjTRN_JOINT)
        servo.set_to_position(kp=KEEPER_KP, kv=KEEPER_KV)
        servo.forcelimited = True
        servo.forcerange = [-KEEPER_FORCE_N, KEEPER_FORCE_N]

    # Each duck's mark: a mocap body its trunk is welded to through the settle
    # (_opening), the weld off until then. Neither has a geom: nothing to hit or see.
    for k in range(2):
        spec.worldbody.add_body(name=f"{duck_prefix(k)}mark", mocap=True)
        spec.add_equality(
            name=f"{duck_prefix(k)}hold",
            type=mujoco.mjtEq.mjEQ_WELD,
            objtype=mujoco.mjtObj.mjOBJ_BODY,
            name1=f"{duck_prefix(k)}trunk_base",
            name2=f"{duck_prefix(k)}mark",
            active=False,
            # anchor, then the trunk's pose in the mark's frame (the same pose), torque scale
            data=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0],
        )

    model = _compiled(spec)
    pose = model.key_qpos[model.key(football.start.keyframe).id]
    for k, (start_x, yaw_deg) in enumerate(zip((-football.setback_m, football.setback_m),
                                               YAWS_DEG)):
        free = _free(model, k)
        pose[free : free + 7] = [start_x, 0.0, SPAWN_HEIGHT_M, *_yaw_quat(yaw_deg)]
        for name, angle in zip(JOINT_NAMES, DEFAULT_POSE):
            pose[model.joint(duck_prefix(k) + name).qposadr[0]] = angle
    ball_q = model.jnt_qposadr[model.joint("ball").id]
    pose[ball_q : ball_q + 7] = [0.0, 0.0, ball.radius_m, 1.0, 0.0, 0.0, 0.0]
    for k in range(2):
        pose[model.jnt_qposadr[model.joint(f"keeper{k}").id]] = 0.0
    return model


def _wrap(angle: float) -> float:
    return (angle + math.pi) % (2 * math.pi) - math.pi


class _Coach:
    """One duck's coach: it reads the pitch and gives the duck's policy a forward speed
    and a turn rate, nothing else.

    It picks an aim inside the goal the duck attacks, beside the keeper on the wider side,
    and heads for the ball's far side from it: straight there when the duck is already
    behind the ball, round the ball when it is not, then on through the ball once the duck
    is lined up behind it, dribbling. Every target is kept off the boards, and up close to
    a board the duck faces it turns without stepping on into it.
    """

    def __init__(self, football: Football, goal_x: float, side: float):
        self.football = football
        self.goal_x = goal_x  # the line of the goal this duck attacks
        self.side = side  # the post it aims beside: +1 the one at +y
        self.dribbling = False
        self.aim = np.zeros(2)

    def __call__(self, duck_xy, yaw: float, ball_xy, keeper_y: float) -> tuple[float, float]:
        goal, keeper = self.football.goal, self.football.keeper
        half = goal.width_m / 2
        gaps = {1.0: half - (keeper_y + keeper.diameter_m / 2),
                -1.0: (keeper_y - keeper.diameter_m / 2) + half}
        if gaps[-self.side] > gaps[self.side] + AIM_SWITCH_M:
            self.side = -self.side
        self.aim = np.array([self.goal_x + math.copysign(AIM_IN_M, self.goal_x),
                             self.side * (half - self.football.ball.radius_m - AIM_MARGIN_M)])
        u = self.aim - ball_xy
        u /= max(np.linalg.norm(u), 1e-6)
        n = np.array([-u[1], u[0]])
        rel = duck_xy - ball_xy
        along, across = float(rel @ u), float(rel @ n)
        lane = LANE_EXIT_M if self.dribbling else LANE_M
        self.dribbling = along < -0.02 and abs(across) < lane
        if self.dribbling:
            target = ball_xy + u * THROUGH_M
        elif along < -BEHIND_M * 0.6:
            target = ball_xy - u * BEHIND_M
        else:
            s = 1.0 if across >= 0 else -1.0
            target = ball_xy + n * s * DETOUR_M - u * BEHIND_M * 0.5
        d = self._inside(target) - duck_xy
        return self._drive(_wrap(math.atan2(d[1], d[0]) - yaw), duck_xy, yaw)

    def _inside(self, target) -> np.ndarray:
        """The target, moved WALL_MARGIN_M inside the boards and the corner cuts."""
        pitch, m = self.football.pitch, WALL_MARGIN_M
        x = max(-(pitch.length_m / 2 - m), min(pitch.length_m / 2 - m, float(target[0])))
        y = max(-(pitch.width_m / 2 - m), min(pitch.width_m / 2 - m, float(target[1])))
        most = pitch.length_m / 2 + pitch.width_m / 2 - pitch.corner_m - m * math.sqrt(2)
        over = abs(x) + abs(y) - most
        if over > 0:
            x -= math.copysign(over / 2, x)
            y -= math.copysign(over / 2, y)
        return np.array([x, y])

    def _wall(self, xy) -> tuple[float, tuple[float, float]]:
        """How far the nearest board is, and its outward normal. The goals' mouths are
        board too, as far as the coach is concerned: it never walks into a net."""
        pitch = self.football.pitch
        x, y = float(xy[0]), float(xy[1])
        return min([
            (pitch.width_m / 2 - abs(y), (0.0, math.copysign(1, y))),
            (pitch.length_m / 2 - abs(x), (math.copysign(1, x), 0.0)),
            ((pitch.length_m / 2 + pitch.width_m / 2 - pitch.corner_m - abs(x) - abs(y))
             / math.sqrt(2), (math.copysign(1, x) / math.sqrt(2),
                              math.copysign(1, y) / math.sqrt(2))),
        ])

    def _drive(self, err: float, xy, yaw: float) -> tuple[float, float]:
        """A heading error, as (vx, wz) outside the walker's dead zones. Facing a board up
        close (cosine above 0.3), it turns without stepping in, backing off when square on
        to it (above 0.85) with the target behind."""
        if abs(err) > TURN_ERR_RAD:
            vx, wz = TURN_VX, math.copysign(TURN_WZ, err)
        else:
            vx, wz = WALK_VX, max(-MAX_STEER_WZ, min(MAX_STEER_WZ, STEER_GAIN * err))
        dist, normal = self._wall(xy)
        into = math.cos(yaw) * normal[0] + math.sin(yaw) * normal[1]
        if dist < WALL_NEAR_M and into > 0.3:
            vx = BACK_VX if into > 0.85 and abs(err) > TURN_ERR_RAD else 0.0
            if abs(wz) < TURN_WZ:
                wz = math.copysign(TURN_WZ, err)
        return vx, wz


@dataclass(frozen=True)
class Event:
    """Something the referee saw, as a replay marks it on the clock."""

    time_s: float
    kind: str  # "shot" | "touch" | "save" | "out" | "stall" | "fall"
    # The duck that struck the ball or went down, or the keeper that saved: k for end k.
    # None when the ball was put back on the pitch (out, stall).
    k: int | None


@dataclass(frozen=True)
class Play:
    """How one play ended, by end: duck k kicked off from end k, attacking the other."""

    seed: int
    scorer: int | None  # the end whose duck scored, or was given the goal; None for none
    end: str  # "goal" | "fault" | "whistle" | "down" | "void"
    time_s: float
    events: tuple[Event, ...]


def _strike_rng(football: Football, seed: int) -> np.random.Generator:
    """The scatter on every strike and save, a stream of its own: marked 4, after the
    runner's (arena.runner._streams), so no duck's start or servo delays move with it."""
    return np.random.default_rng([zlib.crc32(football.id.encode()), seed, 4])


def _still(football: Football) -> np.ndarray:
    """The command a duck gets when it is not playing: through the settle, and down."""
    return np.asarray((0.0, 0.0, 0.0) + football.command[3:], dtype=np.float64)


def _diverged(data) -> bool:
    return _reset_by_mujoco(data) or not np.all(np.isfinite(data.qpos))


def _faulted(sim) -> list[bool]:
    """Whether each duck's servos hold a control MuJoCo refuses: not finite, or past
    mjMAXVAL, as a policy's action that is not a number makes one. MuJoCo answers it
    by switching off every actuator in the model, the other duck's too, for as long
    as it is there; and it stays, the servo's next supply voltage being computed
    from the torque it last gave (arena.actuator.Servos.drive)."""
    ctrl = sim.data.ctrl
    return [bool(np.any(~(np.abs(ctrl[duck.servos.act_ids]) <= mujoco.mjMAXVAL)))
            for duck in sim.ducks]


def _frame(sim) -> np.ndarray:
    """This control step of both ducks, (2, TRACE_WIDTH), as a run's trace keeps it."""
    frame = np.empty((len(sim.ducks), TRACE_WIDTH), dtype=np.float32)
    sim.record(frame)
    return frame


def _opening(football: Football, model, policies: Sequence, seed: int):
    """Every run's opening (arena.runner._start), both ducks asked to stand still
    through the settle, duck k facing YAWS_DEG[k]: the simulation where the clock
    starts, and the settle's frames, (2, settle steps + 1, TRACE_WIDTH).

    Asked is not made: a policy deaf to its command walks off through the settle and
    meets the kick-off out of place. So each duck is held on its mark until the clock
    starts: its trunk welded where the reset put it, the spawn height, so it drops onto
    its feet at kick-off as every run's reset drops a duck. The policies run on
    through the hold as they do through any settle."""
    if len(policies) != 2:
        raise ValueError(f"a play takes two policies, got {len(policies)}")
    still = _still(football)
    commands = [still, still]
    sim, reset = _start(replace(football, start=replace(football.start, settle_s=0.0)), model,
                        policies, YAWS_DEG, seed, commands)
    data = sim.data
    holds = [model.equality(f"{duck_prefix(k)}hold").id for k in range(2)]
    marks = [int(model.body_mocapid[model.body(f"{duck_prefix(k)}mark").id]) for k in range(2)]
    for mark, duck in zip(marks, sim.ducks):
        data.mocap_pos[mark] = data.xpos[duck.adr.trunk]
        data.mocap_quat[mark] = data.xquat[duck.adr.trunk]
    data.eq_active[holds] = 1
    steps = round(football.start.settle_s / CTRL_DT)
    settle = np.empty((2, steps + 1, TRACE_WIDTH), dtype=np.float32)
    settle[:, 0] = reset[:, 0]
    for step in range(steps):
        sim.step(commands)
        sim.record(settle[:, step + 1])
    data.eq_active[holds] = 0
    return sim, settle


class _Pitchside:
    """Everything on the pitch but the ducks, through one play from kick-off: the ball, the
    keepers, each duck's coach, and the referee and what it keeps count of."""

    def __init__(self, football: Football, sim, seed: int):
        model = sim.model
        self.football, self.sim, self.data, self.seed = football, sim, sim.data, seed
        self.trunks = [duck.adr.trunk for duck in sim.ducks]
        ball = model.joint("ball").id
        self.ball_q, self.ball_v = model.jnt_qposadr[ball], model.jnt_dofadr[ball]
        self.ball_body, self.ball_geom = model.body("ball").id, model.geom("ball").id
        self.keeper_q = [model.jnt_qposadr[model.joint(f"keeper{k}").id] for k in range(2)]
        self.keeper_act = [model.actuator(f"keeper{k}").id for k in range(2)]
        self.keeper_geoms = [model.geom(f"keeper{k}").id for k in range(2)]
        # The duck each geom is part of, -1 for none.
        roots = model.body_rootid[model.geom_bodyid]
        self.geom_duck = np.full(model.ngeom, -1)
        for k, trunk in enumerate(self.trunks):
            self.geom_duck[roots == trunk] = k
        # Each coach starts aiming beside the post the seed's parity picks, the two
        # mirrored: a play and its swap of ends start the same, end for end.
        first = 1.0 if seed % 2 else -1.0
        half = football.pitch.length_m / 2
        self.coaches = [_Coach(football, half, first), _Coach(football, -half, -first)]
        self.lagged = [0.0] * max(1, round(football.keeper.lag_s / CTRL_DT))
        self.targets = [0.0, 0.0]
        self.rng = _strike_rng(football, seed)
        self.strike_cool = [0, 0]
        self.held, self.save_cool = [0, 0], [0, 0]
        self.anchor, self.idle = np.zeros(2), 0
        self.needed = round(football.termination.fall_hold_s / CTRL_DT)
        self.tipped, self.down = [0, 0], [False, False]
        self.events: list[Event] = []

    def play(self, frames: list | None = None, props: list | None = None) -> Play:
        """The timed play, from where _opening left the simulation. With `frames` and
        `props`, every step the referee judges is appended to them (_frame's, and
        self.props'): reading the physics writes none of it, so the play is the same
        recorded or not. A void play's last step is not among them."""
        sim = self.sim
        still = _still(self.football)
        steps = round(self.football.time_limit_s / CTRL_DT)
        for step in range(steps):
            ball = self.keepers()
            sim.step(self.commands(ball, still))
            time_s = (step + 1) * CTRL_DT
            if _diverged(sim.data):
                return self._over(None, "void", time_s)
            if frames is not None:
                frames.append(_frame(sim))
                props.append(self.props())
            faulted = _faulted(sim)
            if any(faulted):
                return self._over(None if all(faulted) else faulted.index(False), "fault", time_s)
            ruling = self.judge(time_s)
            if ruling is not None:
                return self._over(*ruling, time_s)
        return self._over(None, "whistle", steps * CTRL_DT)

    def tail(self, steps: int, frames: list, props: list) -> None:
        """`steps` more, recorded, once the play is over: both ducks asked to stand still,
        the keepers tracking the ball on. Stops early if the simulation diverges."""
        still = _still(self.football)
        for _ in range(steps):
            self.keepers()
            self.sim.step([still, still])
            if _diverged(self.data):
                break
            frames.append(_frame(self.sim))
            props.append(self.props())

    def _over(self, scorer: int | None, end: str, time_s: float) -> Play:
        return Play(self.seed, scorer, end, time_s, tuple(self.events))

    def props(self) -> np.ndarray:
        """This step's prop frame, (PROP_WIDTH,): the ball's position and quaternion, then
        each keeper's place on its rail."""
        frame = np.empty(PROP_WIDTH, dtype=np.float32)
        frame[0:7] = self.data.qpos[self.ball_q : self.ball_q + 7]
        frame[7:9] = self.data.qpos[self.keeper_q]
        return frame

    def keepers(self) -> np.ndarray:
        """Each keeper sent on toward where the ball was lag_s ago, no faster than its
        speed and never off its rail; returns where the ball is now."""
        ball = self.data.qpos[self.ball_q : self.ball_q + 3].copy()
        self.lagged.append(ball[1])
        seen = self.lagged.pop(0)
        rail, most = self.football.rail_m, self.football.keeper.speed_m_s * CTRL_DT
        for k in range(2):
            want = max(-rail, min(rail, seen))
            self.targets[k] += max(-most, min(most, want - self.targets[k]))
            self.data.ctrl[self.keeper_act[k]] = self.targets[k]
        return ball

    def commands(self, ball: np.ndarray, still: np.ndarray) -> list[np.ndarray]:
        """What each duck's policy is asked this step: its coach's forward speed and turn
        rate, the rest of the command as `still` has it; `still` itself once it is down."""
        commands = []
        for k, trunk in enumerate(self.trunks):
            if self.down[k]:
                commands.append(still)
                continue
            vx, wz = self.coaches[k](self.data.xpos[trunk][:2].copy(), self._yaw(k), ball[:2],
                                     self.data.qpos[self.keeper_q[1 - k]])
            command = still.copy()
            command[0], command[2] = vx, wz
            commands.append(command)
        return commands

    def _yaw(self, k: int) -> float:
        rotation = self.data.xmat[self.trunks[k]].reshape(3, 3)
        return math.atan2(rotation[1, 0], rotation[0, 0])

    def judge(self, time_s: float) -> tuple[int | None, str] | None:
        """The referee's look after a control step, at the ball where the step left it:
        the assisted strike, a stuck ball put back, the keepers' saves, a ball out of play
        put back; then a goal, and whether both ducks are down. (scorer, end) once the
        play is over, None while it goes on."""
        football, data = self.football, self.data
        bx, by, bz = (float(v) for v in data.qpos[self.ball_q : self.ball_q + 3])
        on_ball = self._on_ball()
        self._strike(time_s, bx, by, on_ball)
        ducks_xy = [data.xpos[trunk][:2] for trunk in self.trunks]
        self._unstick(time_s, bx, by, ducks_xy)
        self._saves(time_s, on_ball)
        if self._out(bx, by, bz):
            self._restart(bx, by, ducks_xy)
            self.events.append(Event(time_s, "out", None))
            return None
        line = football.pitch.length_m / 2 + football.ball.radius_m
        if bx > line:
            return 0, "goal"
        if bx < -line:
            return 1, "goal"
        self._falls(time_s)
        return (None, "down") if all(self.down) else None

    def _on_ball(self) -> list[int]:
        """Every geom touching the ball."""
        data, ball = self.data, self.ball_geom
        touching = []
        for i in range(data.ncon):
            contact = data.contact[i]
            if contact.geom1 == ball:
                touching.append(int(contact.geom2))
            elif contact.geom2 == ball:
                touching.append(int(contact.geom1))
        return touching

    def _strike(self, time_s: float, bx: float, by: float, on_ball: list[int]) -> None:
        """The kick a walking policy cannot make. A duck on its feet that touches the ball,
        alone, with the ball within front_deg of its heading, sends it on: a shot at its
        coach's aim when that goal is within shot_range_m and it faces the aim within
        align_deg; else a touch along its heading when it faces the goal's middle within
        touch_cone_deg. Scattered by up to noise_deg, a tenth either way on the speed;
        then that duck's cooldown before it strikes again."""
        football, data = self.football, self.data
        strike = football.strike
        self.strike_cool = [c - 1 for c in self.strike_cool]
        ducks = {int(self.geom_duck[g]) for g in on_ball if self.geom_duck[g] >= 0}
        if len(ducks) != 1:
            return  # nobody on it, or both: a scramble is nobody's kick
        (k,) = ducks
        if self.down[k] or self.strike_cool[k] > 0:
            return
        yaw = self._yaw(k)
        tx, ty = data.xpos[self.trunks[k]][:2]
        if abs(_wrap(math.atan2(by - ty, bx - tx) - yaw)) > math.radians(strike.front_deg):
            return
        goal_x = football.pitch.length_m / 2 * (1 if k == 0 else -1)
        aim = self.coaches[k].aim
        aim_dir = math.atan2(aim[1] - by, aim[0] - bx)
        shot = (abs(goal_x - bx) <= strike.shot_range_m
                and abs(_wrap(aim_dir - yaw)) <= math.radians(strike.align_deg))
        touch = (abs(_wrap(math.atan2(-by, goal_x - bx) - yaw))
                 <= math.radians(strike.touch_cone_deg))
        if not (shot or touch):
            return
        heading = (aim_dir if shot else yaw) + math.radians(
            self.rng.uniform(-strike.noise_deg, strike.noise_deg))
        speed = ((strike.shot_speed_m_s if shot else strike.touch_speed_m_s)
                 * self.rng.uniform(0.9, 1.1))
        v = np.array([speed * math.cos(heading), speed * math.sin(heading), 0.0])
        # Rolling, not sliding: the spin that goes with v on the turf, in the ball's own
        # frame, where its free joint keeps its angular velocity.
        spin = np.array([-v[1], v[0], 0.0]) / football.ball.radius_m
        data.qvel[self.ball_v : self.ball_v + 3] = v
        data.qvel[self.ball_v + 3 : self.ball_v + 6] = (
            data.xmat[self.ball_body].reshape(3, 3).T @ spin)
        self.strike_cool[k] = round(
            (strike.shot_cooldown_s if shot else strike.touch_cooldown_s) / CTRL_DT)
        self.events.append(Event(time_s, "shot" if shot else "touch", k))

    def _unstick(self, time_s: float, bx: float, by: float, ducks_xy) -> None:
        """A ball a duck on its feet is within jam_m of, that has not moved STALL_MOVE_M in
        stall_s, is stuck: against a board, or between the two of them. It is put back
        (_restart)."""
        restart = self.football.restart
        near = any(not self.down[k] and math.hypot(*(ducks_xy[k] - (bx, by))) < restart.jam_m
                   for k in range(2))
        if math.hypot(bx - self.anchor[0], by - self.anchor[1]) > STALL_MOVE_M or not near:
            self.anchor[:] = (bx, by)
            self.idle = 0
            return
        self.idle += 1
        if self.idle * CTRL_DT >= restart.stall_s:
            self._restart(bx, by, ducks_xy)
            self.events.append(Event(time_s, "stall", None))

    def _saves(self, time_s: float, on_ball: list[int]) -> None:
        """A keeper the ball has touched for hold_s clears it upfield at speed_m_s, within
        cone_deg of straight, then waits cooldown_s before it clears again: a keeper has
        no foot, and without it a ball at one's base stays there."""
        save, data = self.football.save, self.data
        for k in range(2):
            self.held[k] = self.held[k] + 1 if self.keeper_geoms[k] in on_ball else 0
            self.save_cool[k] -= 1
            if self.held[k] * CTRL_DT >= save.hold_s and self.save_cool[k] <= 0:
                angle = math.radians(self.rng.uniform(-save.cone_deg, save.cone_deg))
                upfield = 1.0 if k == 0 else -1.0
                data.qvel[self.ball_v : self.ball_v + 3] = [
                    upfield * save.speed_m_s * math.cos(angle),
                    save.speed_m_s * math.sin(angle),
                    0.0,
                ]
                self.save_cool[k] = round(save.cooldown_s / CTRL_DT)
                self.held[k] = 0
                self.events.append(Event(time_s, "save", k))

    def _out(self, bx: float, by: float, bz: float) -> bool:
        """Over a side board, through the turf, past the back of a goal, or over an end
        board beside a goal or above its bar. In a goal's mouth, under the bar, it is in
        play: a goal, once it is all the way over the line."""
        pitch, goal = self.football.pitch, self.football.goal
        mouth = abs(by) < goal.width_m / 2 and bz < goal.height_m
        return (abs(bx) > pitch.length_m / 2 + goal.depth_m + BEHIND_GOAL_M
                or abs(by) > pitch.width_m / 2 + OVER_SIDE_M
                or bz < -BELOW_FLOOR_M
                or (abs(bx) > pitch.length_m / 2 + self.football.ball.radius_m and not mouth))

    def _restart(self, bx: float, by: float, ducks_xy) -> None:
        """The ball put down again at rest on the nearest restart spot to where it was
        that has no duck within free_m, standing or down: the centre spot, or a spot in
        each quarter of the pitch. The nearest of all five if none is free."""
        restart = self.football.restart
        spots = [(0.0, 0.0)] + [(sx * restart.spot_x_m, sy * restart.spot_y_m)
                                for sx in (-1, 1) for sy in (-1, 1)]
        free = [q for q in spots
                if all(math.hypot(q[0] - d[0], q[1] - d[1]) > restart.free_m for d in ducks_xy)]
        x, y = min(free or spots, key=lambda q: math.hypot(q[0] - bx, q[1] - by))
        self.data.qpos[self.ball_q : self.ball_q + 7] = [
            x, y, self.football.ball.radius_m + RESTART_DROP_M, 1.0, 0.0, 0.0, 0.0]
        self.data.qvel[self.ball_v : self.ball_v + 6] = 0.0
        self.anchor[:] = (x, y)
        self.idle = 0

    def _falls(self, time_s: float) -> None:
        """The runner's fall rule (arena.runner.run_once): projected gravity's z,
        -R[2, 2], above fall_gravity_z for fall_hold_s straight control steps. A duck
        that goes down stays down, asked to stand still; the play goes on."""
        for k, trunk in enumerate(self.trunks):
            if self.down[k]:
                continue
            tipped = -self.data.xmat[trunk][8] > self.football.termination.fall_gravity_z
            self.tipped[k] = self.tipped[k] + 1 if tipped else 0
            if self.tipped[k] >= self.needed:
                self.down[k] = True
                self.events.append(Event(time_s, "fall", k))


def run_play(football: Football, model, policies: Sequence, seed: int) -> Play:
    """One play on `model` (compile_football's): policies[k] kicks off from end k, from
    `seed`'s start, and the first goal ends it.

    The opening is _opening's: every run's reset, each duck held on its mark through the
    settle asked to stand still. From the first timed step each is asked what its coach
    says. The referee looks after every control step: a simulation MuJoCo had to reset
    ends the play void; a duck whose servos hold a control MuJoCo refuses gives the goal
    away (_faulted: MuJoCo has switched off its rival's servos too; both at once,
    nobody's); the ball all the way over a goal line, between the posts and under the
    bar, is a goal; a duck that goes down by the fall rule stays down, and both down
    ends the play; and the whistle, at time_limit_s, ends it goalless.
    """
    sim, _ = _opening(football, model, policies, seed)
    return _Pitchside(football, sim, seed).play()


@dataclass(frozen=True, eq=False)
class Recorded:
    """A play as a replay plays it: how it ended, both ducks' frames by end, the props'."""

    play: Play
    settle: np.ndarray  # (2, settle steps + 1, TRACE_WIDTH): the untimed settle, as a run's
    # (2, frames, TRACE_WIDTH): every step the referee judged, a frame each, so the play
    # was decided on frame round(play.time_s / CTRL_DT) - 1; then the tail.
    trace: np.ndarray
    kickoff: np.ndarray  # (PROP_WIDTH,): the props through the settle, where nothing moves them
    props: np.ndarray  # (frames, PROP_WIDTH): the props with each of the trace's frames


def record_play(football: Football, model, policies: Sequence, seed: int,
                tail_s: float = TAIL_S) -> Recorded:
    """run_play's play, recorded, and run on for tail_s after a goal: both ducks asked to
    stand still, so a replay shows the ball in the net. A play anything else ended has
    no tail."""
    sim, settle = _opening(football, model, policies, seed)
    pitchside = _Pitchside(football, sim, seed)
    kickoff = pitchside.props()
    frames: list[np.ndarray] = []
    props: list[np.ndarray] = []
    play = pitchside.play(frames, props)
    if play.end == "goal":
        pitchside.tail(round(tail_s / CTRL_DT), frames, props)
    if not frames:
        return Recorded(play, settle, np.empty((2, 0, TRACE_WIDTH), dtype=np.float32), kickoff,
                        np.empty((0, PROP_WIDTH), dtype=np.float32))
    return Recorded(play, settle, np.stack(frames, axis=1), kickoff, np.stack(props))


@dataclass(frozen=True)
class Played:
    """One play of a match, and which of the match's two policies kicked off from end 0."""

    play: Play
    ends: int  # 0: A from end 0 and B from end 1; 1: the other way round

    @property
    def scorer(self) -> int | None:
        """The policy that scored, as the match numbers them (0 is A), or None."""
        if self.play.scorer is None:
            return None
        return self.play.scorer if self.ends == 0 else 1 - self.play.scorer


@dataclass(frozen=True)
class Match:
    plays: tuple[Played, ...]

    @property
    def goals(self) -> tuple[int, int]:
        """A's and B's: a goal a play, the first; a play nobody scored in is none."""
        return (sum(p.scorer == 0 for p in self.plays), sum(p.scorer == 1 for p in self.plays))

    @property
    def winner(self) -> int | None:
        """The policy with more goals (0 is A), or None for a draw."""
        a, b = self.goals
        return 0 if a > b else 1 if b > a else None


def play_match(football: Football, a, b, model=None) -> Match:
    """A against B: a play from every seed twice, the policies swapping ends between the
    two, so neither keeps one end's start perturbation or servo delays."""
    model = compile_football(football) if model is None else model
    return Match(tuple(
        Played(run_play(football, model, (a, b) if ends == 0 else (b, a), seed), ends)
        for seed in football.seeds
        for ends in (0, 1)
    ))


def record_match(football: Football, a, b, model=None) -> tuple[Match, tuple[Recorded, ...]]:
    """play_match's match, and every play of it recorded (record_play's), in its order."""
    model = compile_football(football) if model is None else model
    plays = [
        (record_play(football, model, (a, b) if ends == 0 else (b, a), seed), ends)
        for seed in football.seeds
        for ends in (0, 1)
    ]
    return Match(tuple(Played(r.play, ends) for r, ends in plays)), tuple(r for r, _ in plays)


def round_robin(football: Football, policies: Sequence) -> dict[tuple[int, int], Match]:
    """Every pair once: (i, j) is policies[i] as A against policies[j] as B, i < j."""
    model = compile_football(football)
    return {
        (i, j): play_match(football, policies[i], policies[j], model)
        for i, j in combinations(range(len(policies)), 2)
    }


@dataclass(frozen=True)
class Standing:
    name: str
    won: int
    drawn: int
    lost: int
    scored: int
    conceded: int

    @property
    def points(self) -> int:
        return 3 * self.won + self.drawn

    @property
    def difference(self) -> int:
        return self.scored - self.conceded


def standings(names: Sequence[str], matches: Mapping[tuple[int, int], Match]) -> list[Standing]:
    """The table, counted match by match as a league's is: three points for a win and one
    for a draw; then goal difference, goals scored, and by name."""
    tally = [[0, 0, 0, 0, 0] for _ in names]
    for (i, j), match in matches.items():
        a, b = match.goals
        for side, scored, conceded in ((i, a, b), (j, b, a)):
            tally[side][3] += scored
            tally[side][4] += conceded
        if match.winner is None:
            tally[i][1] += 1
            tally[j][1] += 1
        else:
            won, lost = (i, j) if match.winner == 0 else (j, i)
            tally[won][0] += 1
            tally[lost][2] += 1
    table = [Standing(name, *counts) for name, counts in zip(names, tally)]
    return sorted(table, key=lambda s: (-s.points, -s.difference, -s.scored, s.name))
