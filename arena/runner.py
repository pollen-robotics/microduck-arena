"""Run one policy, on one event, at one seed — or, on a stage, a troupe of them.

No queue, no storage, no HTTP: this narrowness is what makes the determinism and
golden-run tests possible, and those tests are the only thing standing between a
physics change and a silently invalidated leaderboard.

The loop is training's, not the sandbox's: build the 61-D observation with the
actor's joint-velocity slot one control step old, run the policy, drive the BAM
servos (`arena.actuator.Servos`) once per physics substep and once more after
the four substeps, then call `mj_forward` — mirroring mjlab's `sim.forward()`.

Two of those drives are training's own behaviour rather than an idealised loop
(mjlab 1.3.0), and every policy trained under them:

- The fifth drive of a control step. After the substeps, mjlab's `step()`
  (envs/manager_based_rl_env.py) resets the environments that ended and calls
  `scene.write_data_to_sim()` before `sim.forward()` whenever any of them did —
  nearly every step at training's batch size — and that write runs every
  environment's actuator once more on the same target: one more delay-ring
  push, lag draw, friction write, torque write and voltage-sag update.
- The drive at reset. The reset clears the joint targets to 0 rad
  (entity/data.py, `clear_state`), and the reset's own `scene.write_data_to_sim()`
  runs the actuator once on them before `sim.forward()` (`reset()` and the reset
  block of `step()`), which backfills the command-delay ring with zeros: the
  first substeps of a run drive toward 0 rad, not toward the policy's target.
  Training's reset drive reads the forces the previous episode left behind,
  which a single run cannot copy; here a forward pass on the reset pose runs
  first, so the drive reads that pose's own forces — a consistent state.

A stage's troupe shares one physics (`arena.course.compile_stage`): at each
control step every duck observes the same state and its policy acts on its own
command, then each of the four substeps drives every duck's servos before its
one `mj_step`, and every duck's servos are driven a fifth time before the
forward pass. A lone duck, on a lane or a stage, is a troupe of one.
"""

import zlib
from collections.abc import Sequence
from dataclasses import dataclass

import mujoco
import numpy as np

from .actuator import Servos
from .constants import (
    ACTION_SCALE,
    CTRL_DT,
    DECIMATION,
    DEFAULT_POSE,
    JOINT_NAMES,
    NUM_JOINTS,
    OBS_SIZE,
    TIMESTEP,
    TRACE_WIDTH,
)
from .course import compile_course, compile_stage, duck_prefix, ramp_dir
from .lights import Red, timetable
from .manifest import Manifest, Steering
from .timeline import Start, Timeline

_WORLD_DOWN = np.array([0.0, 0.0, -1.0])

# How long a caught duck is simulated on with its motors off, so its replay shows it fall
# and lie still. It changes no score (Plan C may retune it).
COLLAPSE_S = 2.0


@dataclass(frozen=True)
class RunOutcome:
    seed: int
    status: str  # "finish" | "fall" | "timeout" | "caught" (moving under a red light)
    time_s: float | None
    progress_m: float
    # Where the start line landed in course coordinates, after settling. Exposed
    # so a test can assert the clock and the start line agree.
    start_progress_m: float
    # (frames, TRACE_WIDTH) float32 on a lane; (ducks, frames, TRACE_WIDTH) on a stage.
    trace: np.ndarray
    # The untimed settle before the trace: the reset pose, then a frame per
    # settle step, so a replay can start where the simulation did. Shaped as the
    # trace is, with settle steps + 1 frames.
    settle: np.ndarray
    # The index in `trace` of the step a duck was caught on; its trace runs on
    # COLLAPSE_S more seconds, past the time limit if need be.
    caught_frame: int | None = None


@dataclass(frozen=True)
class Performer:
    """One duck of a stage's troupe: its policy, its rig, where it starts, and what it is asked."""

    policy: object  # anything with .act(obs) -> action (arena.policy.Policy)
    rig: str
    start: Start
    timeline: Timeline


@dataclass(frozen=True)
class _Addresses:
    qpos: np.ndarray
    dof: np.ndarray
    act: np.ndarray
    gyro: int
    trunk: int
    # The qpos address of the trunk's free joint: position, then quaternion.
    free: int
    stand_key: int

    @classmethod
    def of(cls, model, keyframe: str, prefix: str) -> "_Addresses":
        """The duck whose names carry `prefix` (arena.course.duck_prefix)."""
        trunk = int(model.body(f"{prefix}trunk_base").id)
        return cls(
            qpos=np.array([int(model.joint(prefix + n).qposadr[0]) for n in JOINT_NAMES]),
            dof=np.array([int(model.joint(prefix + n).dofadr[0]) for n in JOINT_NAMES]),
            act=np.array([int(model.actuator(prefix + n).id) for n in JOINT_NAMES]),
            gyro=int(model.sensor(f"{prefix}imu_ang_vel").adr[0]),
            trunk=trunk,
            free=int(model.jnt_qposadr[model.body_jntadr[trunk]]),
            stand_key=int(model.key(keyframe).id),
        )


def seed_rng(event_id: str, seed: int) -> np.random.Generator:
    """A generator that is identical in every process.

    Python's hash() is salted per process, so it must never appear here: a run
    that is not reproducible cannot be verified, and verification is the whole
    point of running server-side.
    """
    return np.random.default_rng([zlib.crc32(event_id.encode()), seed])


def _streams(event_id: str, seed: int, k: int) -> tuple[np.random.Generator, np.random.Generator]:
    """Duck k's start perturbation and servo command delays, each its own stream.

    Duck 0 keeps a lone duck's — the perturbation `seed_rng`, the delays marked by
    a trailing 1 — so a troupe of one is the run it always was. Every other duck's
    are marked 2 and 3, then its index.
    """
    crc = zlib.crc32(event_id.encode())
    if k == 0:
        return seed_rng(event_id, seed), np.random.default_rng([crc, seed, 1])
    return np.random.default_rng([crc, seed, 2, k]), np.random.default_rng([crc, seed, 3, k])


def _observe(model, data, adr, last_action, command, joint_vel) -> np.ndarray:
    obs = np.empty(OBS_SIZE, dtype=np.float32)
    obs[0:3] = data.sensordata[adr.gyro : adr.gyro + 3]
    # Projected gravity: world -z rotated into the trunk frame. xmat is
    # body->world, so its transpose takes a world vector into the body frame.
    rotation = data.xmat[adr.trunk].reshape(3, 3)
    obs[3:6] = rotation.T @ _WORLD_DOWN
    obs[6:20] = data.qpos[adr.qpos] - DEFAULT_POSE
    obs[20:34] = joint_vel
    obs[34:48] = last_action
    obs[48:61] = command
    return obs


def _perturb(data, adr, manifest, rng, yaw_deg: float) -> None:
    """The start's noise on every joint, and the trunk's heading: the duck's own yaw plus noise."""
    start = manifest.start
    data.qpos[adr.qpos] += rng.uniform(-start.joint_rad, start.joint_rad, NUM_JOINTS)
    yaw = np.radians(yaw_deg + rng.uniform(-start.yaw_deg, start.yaw_deg))
    data.qpos[adr.free + 3 : adr.free + 7] = [np.cos(yaw / 2), 0.0, 0.0, np.sin(yaw / 2)]


def _record(frame: np.ndarray, data, adr) -> None:
    frame[0:7] = data.qpos[adr.free : adr.free + 7]
    frame[7:TRACE_WIDTH] = data.qpos[adr.qpos]


class _Duck:
    """One robot between control steps: where it sits in the model, its servos
    and its policy, and the two things its next observation carries over."""

    def __init__(self, data, adr, servos, policy):
        self.adr, self.servos, self.policy = adr, servos, policy
        self.last_action = np.zeros(NUM_JOINTS, dtype=np.float32)
        # The actor's joint-velocity observation is one control step old — a fixed
        # lag in training (delay_min_lag = delay_max_lag = 1 on its joint_vel term),
        # not a randomisation; the first step uses the reset state's qvel.
        self.prev_qvel = data.qvel[adr.dof].copy()

    def act(self, model, data, command: np.ndarray) -> np.ndarray:
        """Observe, act, and return the target its servos are driven toward this control step.

        The observation's joint velocity is the one recorded a control step ago,
        matching training (mjlab resamples the observation before the servo
        updates its own delayed target, so the two delays are independent). The
        qvel kept for the NEXT step's observation is read here, before any of
        this step's substeps run.
        """
        obs = _observe(model, data, self.adr, self.last_action, command, self.prev_qvel)
        self.prev_qvel = data.qvel[self.adr.dof].copy()
        self.last_action = self.policy.act(obs)
        return DEFAULT_POSE + self.last_action * ACTION_SCALE


def _step(model, data, ducks: Sequence[_Duck], commands: Sequence[np.ndarray], crossed=None) -> int | None:
    """One control step of the shared physics: every duck observes the same
    state and acts on its own command; then each substep drives every duck's
    servos before its one mj_step, and every duck's servos are driven once more
    after them (training's post-reset write, see the module docstring) before
    the forward pass.

    `crossed`, a race's finish line, is asked after each substep; the first
    substep it holds at is returned, None when it held at none."""
    targets = [duck.act(model, data, command) for duck, command in zip(ducks, commands)]
    first = None
    for substep in range(DECIMATION):
        for duck, target in zip(ducks, targets):
            duck.servos.drive(data, target)
        mujoco.mj_step(model, data)
        if first is None and crossed is not None and crossed():
            first = substep
    for duck, target in zip(ducks, targets):
        duck.servos.drive(data, target)
    mujoco.mj_forward(model, data)
    return first


class _Sim:
    """One run's simulation between control steps: the physics, every duck on it, and the sites
    whose points it reads (a tug's string; none on a lane or a stage)."""

    def __init__(self, model, data, ducks: list[_Duck], sites=()):
        self.model, self.data, self.ducks, self.sites = model, data, ducks, sites

    def step(self, commands: Sequence[np.ndarray], crossed=None) -> int | None:
        return _step(self.model, self.data, self.ducks, commands, crossed)

    def record(self, frames: np.ndarray) -> None:
        """This step's frame of every duck, into `frames`, (ducks, TRACE_WIDTH)."""
        for duck, frame in zip(self.ducks, frames):
            _record(frame, self.data, duck.adr)

    def points(self, out: np.ndarray) -> None:
        """This step's position of every site, into `out`, (sites, 3). Only called with sites:
        `site_xpos[()]` would be every site of the model."""
        out[:] = self.data.site_xpos[self.sites]


def _start(
    manifest: Manifest, model, policies, yaws_deg, seed: int, commands, sites=()
) -> tuple[_Sim, np.ndarray, np.ndarray]:
    """Every run's opening, lane, stage or tug: training's reset of every duck on
    `model` (one policy and one yaw per duck, in duck order), then the untimed
    settle, each duck on its command. Returns the simulation where the clock
    starts, the settle's frames, (ducks, settle steps + 1, TRACE_WIDTH), and the
    points of `sites` beside each, (settle steps + 1, sites, 3): a lane and a
    stage pass none and record none."""
    data = mujoco.MjData(model)
    adrs = [_Addresses.of(model, manifest.start.keyframe, duck_prefix(k)) for k in range(len(policies))]
    streams = [_streams(manifest.id, seed, k) for k in range(len(policies))]

    # A fresh Servos per duck every run, constructed BEFORE the reset below: the
    # compiled model is shared across an evaluation's runs (evaluate.py
    # compiles once), Servos writes model.dof_frictionloss / model.dof_damping,
    # and its construction resets them — so nothing in this run sees the
    # friction state the run before it left on the shared model.
    servos = [Servos(model, adr.dof, adr.act, delays) for adr, (_, delays) in zip(adrs, streams)]

    # Training's reset (module docstring): the perturbed pose, a forward pass so
    # the reset drive reads that pose's own forces (training's would read the
    # previous episode's), the servos driven once toward the cleared 0 rad
    # targets, then the forward pass that picks up their torques.
    mujoco.mj_resetDataKeyframe(model, data, adrs[0].stand_key)
    for adr, (perturbation, _), yaw_deg in zip(adrs, streams, yaws_deg):
        _perturb(data, adr, manifest, perturbation, yaw_deg)
    mujoco.mj_forward(model, data)
    for each in servos:
        each.drive(data, np.zeros(NUM_JOINTS))
    mujoco.mj_forward(model, data)

    ducks = [_Duck(data, adr, each, policy) for adr, each, policy in zip(adrs, servos, policies)]
    sim = _Sim(model, data, ducks, sites)
    # Settle with the policies running and the clock stopped: nobody is timed on
    # standing up.
    settle_steps = round(manifest.start.settle_s / CTRL_DT)
    settle = np.empty((len(policies), settle_steps + 1, TRACE_WIDTH), dtype=np.float32)
    settle_points = np.empty((settle_steps + 1, len(sites), 3), dtype=np.float32)
    for frame in range(settle_steps + 1):
        if frame:
            sim.step(commands)
        sim.record(settle[:, frame])
        if len(sites):
            sim.points(settle_points[frame])
    return sim, settle, settle_points


@dataclass(frozen=True)
class _LightSteps:
    """The giant's timetable laid over a run's timed control steps, indexed by step.

    `red`: the duck is asked to stand during that step. `mark`: the giant
    has just finished turning its head once that step is over, so where the duck
    stands then is where it has to stay. `watch`: the giant is looking once that
    step is over, so a duck that has strayed from its mark by then is caught.
    """

    red: np.ndarray
    mark: np.ndarray
    watch: np.ndarray

    @classmethod
    def of(cls, reds: tuple[Red, ...], turn: int, steps: int) -> "_LightSteps":
        red, mark, watch = (np.zeros(steps, dtype=bool) for _ in range(3))
        for r in reds:
            # Step i ends at (i + 1) * CTRL_DT, so the step that ends as the giant
            # faces the lanes, turn steps into the red, is onset + turn - 1:
            # with no turn at all, the last green step. A first green is at least
            # one step, so that is never below 0.
            if r.onset + turn - 1 < steps:
                mark[r.onset + turn - 1] = True
            red[r.onset:r.onset + r.length] = True
            watch[r.onset + turn:r.onset + r.length] = True
        return cls(red=red, mark=mark, watch=watch)


def _steered(steering: Steering, data, adr, command: np.ndarray) -> np.ndarray:
    """`command` with its yaw rate turning the duck toward the lane's centre line
    (y = 0) `lookahead_m` ahead of it, from where it stands at the start of this
    control step: the state the duck observes (arena.manifest.Steering)."""
    y = float(data.qpos[adr.free + 1])
    w, qx, qy, qz = (float(v) for v in data.qpos[adr.free + 3:adr.free + 7])
    yaw = np.arctan2(2.0 * (w * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))
    error = (np.arctan2(-y, steering.lookahead_m) - yaw + np.pi) % (2.0 * np.pi) - np.pi
    steered = command.copy()
    steered[2] = np.clip(steering.gain * error, -steering.max_yaw_rate, steering.max_yaw_rate)
    return steered


def run_once(manifest: Manifest, policy, seed: int, model=None, command=None) -> RunOutcome:
    # Converted once per run, not per step. The manifest holds an immutable tuple
    # so a loaded event cannot be mutated in place by anything downstream.
    #
    # `command` overrides it for one run, which is how the speed sweep works
    # (see evaluate.py). The event still owns the shape of the command; the
    # sweep only gets to say how fast.
    command = np.asarray(manifest.command if command is None else command, dtype=np.float64)
    model = model if model is not None else compile_course(manifest)

    # The giant's lights (arena.manifest.Lights): under a red light the duck
    # is asked to stand, its command's twist zeroed and its head and body left as
    # declared. It settles standing, too, on the line, and walks off when the
    # clock starts on the first green: nobody gets a flying start.
    lights = manifest.lights
    stand = None
    if lights is not None:
        stand = command.copy()
        stand[0:3] = 0.0
    sim, settle, _ = _start(manifest, model, [policy], [0.0], seed, [command if stand is None else stand])
    data, adr = sim.data, sim.ducks[0].adr

    direction = ramp_dir(manifest.course.slope_deg)
    start_progress = float(direction @ data.qpos[0:3])
    max_steps = round(manifest.time_limit_s / CTRL_DT)
    fall_steps_needed = round(manifest.termination.fall_hold_s / CTRL_DT)

    collapse_steps = round(COLLAPSE_S / CTRL_DT) if lights is not None else 0
    frames = np.empty((1, max_steps + collapse_steps, TRACE_WIDTH), dtype=np.float32)
    caught_frame = None
    tipped_for = 0
    status = "timeout"
    time_s = None
    progress = 0.0
    written = 0

    if lights is not None:
        schedule = _LightSteps.of(
            timetable(lights, manifest.id, seed, max_steps), round(lights.turn_s / CTRL_DT), max_steps
        )
        mark = None
    # A long lane's heading hold (arena.manifest.Steering) turns the duck on the
    # steps it is asked to walk. Not in the settle, where it stands on the line,
    # nor under a red light, where it is asked to stand still.
    steering = manifest.steering

    def past_the_line() -> bool:
        return float(direction @ data.qpos[0:3]) - start_progress >= manifest.course.length_m

    for step in range(max_steps):
        if lights is not None and schedule.red[step]:
            asked = stand
        elif steering is not None:
            asked = _steered(steering, data, adr, command)
        else:
            asked = command
        # The line is timed to the physics step that crosses it (5 ms), not to
        # the control step it falls in (20 ms): a five-seed mean to the
        # millisecond rather than to 4 ms.
        crossing = sim.step([asked], past_the_line)
        sim.record(frames[:, written])
        written += 1

        if not np.all(np.isfinite(data.qpos)):
            status = "fall"  # a solver explosion is a fall, not a mystery
            break

        # Fall is judged BEFORE finish, and the order matters. Reaching the fall
        # branch means the robot has been tipped for fall_hold_s — 0.3 s, fifteen
        # straight steps — so a step where both fire is a robot that was already
        # collapsing and slid over the line. That is not a win.
        #
        # This does not penalise a sprinter falling past the tape: such a robot
        # has tipped_for == 0 at the crossing step, so finish still wins there.
        rotation = data.xmat[adr.trunk].reshape(3, 3)
        gravity_z = float((rotation.T @ _WORLD_DOWN)[2])
        tipped_for = tipped_for + 1 if gravity_z > manifest.termination.fall_gravity_z else 0
        if tipped_for >= fall_steps_needed:
            status = "fall"
            break

        # Caught is judged after the fall and before the finish: a duck the giant
        # sees moving does not get to cross the line on that step. A duck still
        # coasting while the giant turns its head is not seen, and if it crosses then
        # it has finished.
        if lights is not None:
            here = data.qpos[adr.free:adr.free + 2]
            if schedule.mark[step]:
                mark = here.copy()
            elif schedule.watch[step] and float(np.hypot(*(here - mark))) > lights.tolerance_m:
                status = "caught"
                caught_frame = written - 1
                break

        progress = float(direction @ data.qpos[0:3]) - start_progress
        if crossing is not None:
            status = "finish"
            time_s = (step * DECIMATION + crossing + 1) * TIMESTEP
            break

    # A caught duck's motors go off, its gearboxes left as the last drive wrote them
    # (measured: it folds and lies still within a second): no policy, no servo drive.
    if status == "caught":
        data.ctrl[adr.act] = 0.0
        for _ in range(collapse_steps):
            for _ in range(DECIMATION):
                mujoco.mj_step(model, data)
            mujoco.mj_forward(model, data)
            sim.record(frames[:, written])
            written += 1

    return RunOutcome(
        seed=seed,
        status=status,
        time_s=time_s,
        progress_m=progress,
        start_progress_m=start_progress,
        trace=frames[0, :written].copy(),
        settle=settle[0],
        caught_frame=caught_frame,
    )


# MuJoCo answers a non-finite position, velocity or acceleration by resetting the whole
# simulation to the model's defaults and counting a warning (mj_checkPos, mj_checkVel,
# mj_checkAcc). The state stays finite, so a diverged run would carry on from the reset
# pose; these counters are what says it happened.
_RESET_WARNINGS = (
    mujoco.mjtWarning.mjWARN_BADQPOS,
    mujoco.mjtWarning.mjWARN_BADQVEL,
    mujoco.mjtWarning.mjWARN_BADQACC,
)


def _reset_by_mujoco(data) -> bool:
    return any(data.warning[w].number for w in _RESET_WARNINGS)


def _commands(cast: Sequence[Performer], t: float) -> list[np.ndarray]:
    return [np.asarray(p.timeline.command_at(t), dtype=np.float64) for p in cast]


def run_stage(manifest: Manifest, cast: Sequence[Performer], seed: int) -> RunOutcome:
    """Play a troupe on a stage: no line to cross, and no fall stops the performance.

    Every duck plays its own timeline on the shared physics: the settle plays
    its first keyframe; timed step k plays its command at k * CTRL_DT. Only a
    simulation MuJoCo had to reset ends a performance early, the whole troupe's
    since the physics is one: a solver explosion is not a performance, and the
    trace stops before it.
    """
    model = compile_stage(manifest, [(p.rig, p.start) for p in cast])
    policies, yaws_deg = [p.policy for p in cast], [p.start.yaw_deg for p in cast]
    sim, settle, _ = _start(manifest, model, policies, yaws_deg, seed, _commands(cast, 0.0))
    steps = round(cast[0].timeline.duration_s / CTRL_DT)
    frames = np.empty((len(cast), steps, TRACE_WIDTH), dtype=np.float32)
    status, time_s, written = "finish", steps * CTRL_DT, 0
    for step in range(steps):
        sim.step(_commands(cast, step * CTRL_DT))
        if _reset_by_mujoco(sim.data):
            status, time_s = "fall", None
            break
        sim.record(frames[:, written])
        written += 1
    return RunOutcome(
        seed=seed,
        status=status,
        time_s=time_s,
        progress_m=0.0,
        start_progress_m=0.0,  # a stage has no line
        trace=frames[:, :written].copy(),
        settle=settle,
    )
