# Sock Heist D — the training folder and the reference — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. D3 is a loop the controller runs itself: a subagent launches or judges and returns, the controller waits (Monitor, never `sleep`) and decides.

**Goal:** A training folder `sock_heist_6m` in microduck-challenges that trains under the 6 m Sock Heist's own rules, and a policy trained with it that finishes every seed on x86 faster than the reference walker: the event's published reference.

**Architecture:**
- **The rules, copied and pinned.** `lights.py` copies the event's numbers (the HF job installs no Arena) and the Arena's arithmetic: each episode draws its reds from the event's ranges in whole steps, as `arena.lights.timetable` draws a seed's; red, mark and watch fall on the steps `_LightSteps.of` puts them; the lane's hold is `_steered`'s formula. Tests pin every copy against the Arena worktree.
- **One command carries the game.** A command term (`LightsCommand`) gives the policy its twist: `[speed, 0, hold]` on green, zeros through the settle and every red. It owns each episode's reds, the lane (the spawn line) and the mark. `freeze` pays for standing within the tolerance while watched, `caught` ends the episode, and the critic alone is told the light and the lane.
- **The sprint's walk, started as the walker.** `env.py` is the sprint's environment with that command. The learner starts as the Arena's reference walker (`walker.onnx`), as the Tug of War's reference t20 did. `check.py` replays a policy on the Arena's physics and says why each seed ended. D3's decision procedure reads it: the Mac triages, and x86 decides.

**Tech Stack:** Python 3.12, mjlab 1.3.0 (mujoco_warp), rsl_rl, torch, onnx, onnxruntime, mjlab_microduck (as locked), the Arena worktree installed editable, HF Jobs l4x1, pytest.

**Spec:** `docs/superpowers/specs/2026-10-27-sock-heist-design.md` ("The training folder and the reference", "Decisions taken by the owner"), on PR #3's `docs/superpowers/specs/2026-10-21-red-light-green-light-design.md` (the lights, the hold, "the reference was not trained to stop"). **Contract:** `docs/superpowers/plans/2026-10-28-sock-heist-interfaces.md` (binding: names, the event file, "Training (Plan D)").

**Preconditions:**
- Plan A Tasks A1–A2 are committed in ARENA: `load_event("sock-heist-6m")` carries `Lights(first_green_s, green_s, red_s, turn_s, tolerance_m)`. `arena.lights` has `Red` and `timetable`, and `arena.runner._LightSteps.of(reds, turn, steps)` exists.
- D1.3 also needs the collapse (`RunOutcome.caught_frame`).
- D3's x86 judgement needs A6's job and the walker's x86 score.

## Global Constraints

- **Places**, always written in full in every call:
  - WT = `/Users/nicolasrabault/Projects/HuggingFace/microduck-challenges/.claude/worktrees/sock-heist`, branch `sock-heist` from challenges `main` 4b675eb;
  - ARENA = `/Users/nicolasrabault/Projects/HuggingFace/microduck-arena/.claude/worktrees/sock-heist`, branch `red-light-green-light`;
  - FOLDER = `WT/src/microduck_challenges/sock_heist_6m`, ONNX = `WT/logs/sock_heist_6m/onnx`, LEDGER = `WT/logs/sock_heist_6m/ledger.md` (`logs/` is git-ignored).
- **git:** `/usr/bin/git` in both repos (the shell's `git` is rewritten and refused in a worktree).
- **uv:**
  - in WT, `uv run --no-config --no-sync …` after D1.1 Step 1. A `uv sync` or a non-frozen `uv run` swaps the editable Arena back for the locked 0.6.0 wheel; that happened once in the Tug of War's worktree.
  - in ARENA, `uv run --frozen …`.
- **Shorthands:**
  - TESTS = `cd WT && uv run --no-config --no-sync pytest -q -p no:cacheprovider tests`, in the foreground with `timeout: 600000`, never as a background run waited on;
  - SCORE `<onnx>` = `cd ARENA && uv run --frozen arena score <onnx> --event sock-heist-6m`;
  - CHECK = `cd WT && uv run --no-config --no-sync python -m microduck_challenges.sock_heist_6m.check`.
- **The locked wheel does not know the event.** challenges locks Arena 0.6.0, where `sock-heist-6m` does not exist. Code paths:
  - `publish` (`mjlab_microduck.publish.cli`) never imports the Arena. It reads `event` from `challenge.toml` through the challenge registry, writes `"arena": {"event": "sock-heist-6m"}` into the manifest, and validates only its shape. So `publish --dry-run` works on the locked wheel.
  - `--enter` would POST to the Space, which knows the event only after Plan E deploys it, so this plan never passes `--enter`.
  - The workshop skips a folder whose event its Arena does not race (`arena.workshop.challenges.open_challenges`).
  - `tests/test_challenges.py` (`load_event`) and `tests/test_sock_heist_6m.py` need the event. They pass in WT, whose venv holds ARENA editable, and on the branch they fail against the locked wheel until Plan E Task 5 relocks on 0.7.0. Judging also runs ARENA's code (SCORE, CHECK), never the locked wheel.
- **Rules:**
  - `env.py`, `lights.py`, `rewards.py`, `walker.py` and `tasks.py` never import `arena`; tests and `check.py` do.
  - English only. Unsigned commits in the challenges' style: one plain sentence saying what changed and why, no prefix. A training's commit message is its hypothesis.
  - Nothing pushed. `publish` only with `--dry-run`, never `--enter`. No dead code.
- **HF Jobs:**
  - trainings are authorised, up to 10 (D3), each launch reported to the owner with its config;
  - `--namespace Nico-robot` (the Tug of War's grant), l4x1, `--detach`, private ckpt repos `Nico-robot/mjlab-sockheist6m-microduck-sh<n>`, at most 2 in flight;
  - never `hf jobs logs` on a running job (it streams until the job ends): use `hf jobs inspect`;
  - an x86 judgement (A6's job) needs the owner's yes each time.
- **The event's numbers today** (contract; A6 may retune the ranges, and the parity tests then fail until the copies follow):
  - `first_green_s = [0.6, 1.0]`, `green_s = [1.6, 3.0]`, `red_s = [1.4, 2.4]`, `turn_s = 0.4`, `tolerance_m = 0.03`;
  - `[steering]` `lookahead_m = 0.5`, `gain = 2.0`, `max_yaw_rate = 1.0`;
  - `[start]` `settle_s = 0.5`, `yaw_deg = 2.0`, `[sweep]` 0.20 to 1.20;
  - `CTRL_DT = 0.02`.
- **Mac numbers triage, x86 decides.** A Sock Heist crossing lasts some 15–20 s, and the platforms' physics part ways after 1–3 s.

## Review Focus

1. **The env's timetable drifting from the Arena's.** The risks are a range A6 retunes, an off-by-one at a range's ends, the turn, and the mark step. Training must draw exactly the event's phases and judge the mark and the watch on the Arena's steps. Pinned in D1.1: `test_the_rules_are_the_events`, `test_every_phase_is_drawn_from_its_range_ends_included`, `test_the_light_steps_are_the_arenas`. TESTS runs before every launch (D3 Step 2).
2. **A policy that learns never to move.** Standing is never caught. Walking on green must pay far more than standing there, and the judge must name a duck that never left the line. Pinned in D1.2 by `test_walking_on_green_pays_far_more_than_standing_still`, in D1.3 by `test_a_duck_that_never_left_the_line_is_named`, and by D3's lever L9.
3. **A red that begins mid-stride at the scored speed**, with the duck falling forward as it stops. The stop must start on the red's first step, as on the Arena (not one late, which would make training's stops easier), and the judge must tell a fall on a stop from a fall on green. Pinned in D1.2 by `test_the_twist_is_zero_from_a_reds_first_step_to_its_last`, and in D1.3 by `test_a_fall_tipping_in_a_reds_first_moments_is_on_a_stop`.
4. **The steering hold differing from the Arena's.** The risks are the sign of y, the lookahead, the short way round, a yaw read off a tilted trunk, and the lane taken from somewhere other than the spawn line. Pinned in D1.1 by `test_the_hold_is_the_arenas`, and in D1.2 by `test_the_hold_steers_from_the_spawn_line`.
5. **An ONNX whose observation layout differs from the Arena's 61 numbers.** Pinned in D1.2 by `test_the_actor_reads_the_arenas_61_numbers` and `test_the_walker_walks_in_the_training_env` (the Arena's walker fed the training's actor observation walks), and in D2 by `publish`'s `61 -> 14` and SCORE.

---

### Task D1.1: The rules, copied and pinned

**Files:**
- Create: `FOLDER/__init__.py` (empty), `FOLDER/lights.py`
- Test: `WT/tests/test_sock_heist_6m.py`

**Interfaces:**
- Consumes (tests only): `arena.manifest.load_event`, `arena.constants.CTRL_DT`, `arena.lights.Red(onset, length)`, `arena.lights.timetable(lights, event_id, seed, steps)`, `arena.runner._LightSteps.of(reds, turn, steps)` (`.red`, `.mark`, `.watch`), `arena.runner._steered(steering, data, adr, command)`.
- Produces (`lights.py`): the constants `CTRL_DT`, `SETTLE_S`, `FIRST_GREEN_S`, `GREEN_S`, `RED_S`, `TURN_S`, `TOLERANCE_M`, `LOOKAHEAD_M`, `GAIN`, `MAX_YAW_RATE`, each with a comment naming its table in `arena/events/sock-heist-6m.toml` (or `arena.constants`), and:
  - `steps(seconds: float) -> int`;
  - `draw_reds(n: int, episode_steps: int, device) -> tuple[Tensor, Tensor]`: `(onset, length)`, each `(n, R)` int64, onsets counted from the episode's first step (the settle's steps come first);
  - `light_steps(onset: Tensor, length: Tensor, turn: int, k: Tensor) -> tuple[Tensor, Tensor, Tensor]`: `(red, mark, watch)`, each `(n,)` bool at each env's step `k` `(n,)`;
  - `hold_yaw_rate(y: Tensor, quat: Tensor) -> Tensor`: `(n,)` from `y` `(n,)` off the lane and `quat` `(n, 4)` wxyz.

- [ ] **Step 1: The workspace.**
  1. `/usr/bin/git -C /Users/nicolasrabault/Projects/HuggingFace/microduck-challenges worktree add .claude/worktrees/sock-heist -b sock-heist main`.
  2. `cd WT && uv sync --frozen --group workshop`: the only sync this plan runs.
  3. `cd WT && uv pip install --python .venv/bin/python --no-deps -e ARENA`. `--no-deps` because the 0.6.0 wheel's dependencies are ARENA's (`mujoco==3.10.0`, `onnxruntime==1.24.4`, `numpy==2.4.1`), and nothing else may move.
  4. Check: `cd WT && uv run --no-config --no-sync python -c "import arena; from arena.manifest import load_event; print(arena.__file__, load_event('sock-heist-6m').lights)"` prints `ARENA/arena/__init__.py` and the `Lights` above.
  5. TESTS: all pass. Write the count N0 into LEDGER.
- [ ] **Step 2: Write the failing tests** in `tests/test_sock_heist_6m.py`:

```python
EVENT = load_event("sock-heist-6m")
SETTLE = lights.steps(lights.SETTLE_S)


def test_the_rules_are_the_events():
    l, s = EVENT.lights, EVENT.steering
    assert lights.CTRL_DT == ARENA_CTRL_DT and lights.SETTLE_S == EVENT.start.settle_s
    assert (lights.FIRST_GREEN_S, lights.GREEN_S, lights.RED_S) == (l.first_green_s, l.green_s, l.red_s)
    assert (lights.TURN_S, lights.TOLERANCE_M) == (l.turn_s, l.tolerance_m)
    assert (lights.LOOKAHEAD_M, lights.GAIN, lights.MAX_YAW_RATE) == (s.lookahead_m, s.gain, s.max_yaw_rate)


def test_every_phase_is_drawn_from_its_range_ends_included():
    torch.manual_seed(0)
    onset, length = lights.draw_reds(4096, 1000, "cpu")
    every = lambda r: set(range(lights.steps(r[0]), lights.steps(r[1]) + 1))
    assert set((onset[:, 0] - SETTLE).tolist()) == every(lights.FIRST_GREEN_S)     # 30..50
    assert set(length.flatten().tolist()) == every(lights.RED_S)                   # 70..120
    greens = onset[:, 1:] - onset[:, :-1] - length[:, :-1]
    assert set(greens.flatten().tolist()) == every(lights.GREEN_S)                 # 80..150
    assert (onset[:, -1] >= 1000).all()                                            # the table outlasts the episode


@pytest.mark.parametrize("turn", [lights.steps(lights.TURN_S), 0])
def test_the_light_steps_are_the_arenas(turn):
    steps = 3000
    for seed in EVENT.seeds:
        reds = timetable(EVENT.lights, EVENT.id, seed, steps)
        onset = torch.tensor([[r.onset + SETTLE for r in reds]]).expand(steps, -1)
        length = torch.tensor([[r.length for r in reds]]).expand(steps, -1)
        red, mark, watch = lights.light_steps(onset, length, turn, torch.arange(SETTLE, SETTLE + steps))
        expected = arena_runner._LightSteps.of(reds, turn, steps)
        assert (red.tolist(), mark.tolist(), watch.tolist()) == (
            expected.red.tolist(), expected.mark.tolist(), expected.watch.tolist())


def test_the_hold_is_the_arenas():
    command = np.asarray(EVENT.command, dtype=np.float64)
    for y in (-0.35, -0.05, 0.0, 0.12, 0.35):
        for yaw in (-3.1, -1.0, -0.1, 0.0, 0.2, 1.5, 3.1):
            q = _quat(yaw, roll=0.1, pitch=-0.08)                  # a tilted trunk: the yaw formula, not just qz
            data = SimpleNamespace(qpos=np.concatenate([[0.0, y, 0.12], q]))
            want = arena_runner._steered(EVENT.steering, data, SimpleNamespace(free=0), command)[2]
            got = lights.hold_yaw_rate(torch.tensor([y]), torch.tensor([q], dtype=torch.float32)).item()
            assert got == pytest.approx(want, abs=1e-5)
    rate = lambda y, yaw: lights.hold_yaw_rate(torch.tensor([y]), torch.tensor([_quat(yaw)])).item()
    assert rate(0.2, 0.0) < 0 < rate(-0.2, 0.0)                    # left of the line it turns right
    assert (rate(0.0, 3.0), rate(0.0, -3.0)) == (-1.0, 1.0)        # facing back: the short way round, capped
```

  `_quat(yaw, roll=0.0, pitch=0.0) -> np.ndarray` is the test's wxyz helper (z-y-x order), float32-safe.

- [ ] **Step 3: Run them:** `TESTS` with `tests/test_sock_heist_6m.py`. Expected: FAIL on `ModuleNotFoundError: microduck_challenges.sock_heist_6m.lights`.
- [ ] **Step 4: Implement `FOLDER/lights.py`.**
  - The module docstring says the job installs no Arena and the tests pin each copy.
  - `steps` is `round(seconds / CTRL_DT)`.
  - `draw_reds` draws, per env, the first green from `FIRST_GREEN_S`, then red, green, red, … from `RED_S` and `GREEN_S`. Each draw is `torch.randint(lo, hi + 1)` over the range turned into steps, the arithmetic `timetable` uses: whole steps, ends included. `onset[:, 0] = steps(SETTLE_S) + first`, and `onset[:, j] = onset[:, j-1] + length[:, j-1] + green[:, j-1]` (a cumulative sum). `R = ceil((episode_steps - steps(SETTLE_S) - steps(FIRST_GREEN_S[0])) / (steps(GREEN_S[0]) + steps(RED_S[0]))) + 1`, so the last onset is never reached (8 for 1000 steps).
  - `light_steps` is `_LightSteps.of` at one step: `red = onset <= k < onset + length`, `mark = k == onset + turn - 1`, `watch = onset + turn <= k < onset + length`, each `any` over the R reds.
  - `hold_yaw_rate`:
    - yaw `atan2(2(w qz + qx qy), 1 − 2(qy² + qz²))`;
    - error `torch.remainder(atan2(−y, LOOKAHEAD_M) − yaw + π, 2π) − π`. Use `remainder`, not `fmod`: it is numpy's `%`, which `_steered` uses;
    - `clip(GAIN · error, ±MAX_YAW_RATE)`.
- [ ] **Step 5: Run them:** TESTS. Expected: the four tests PASS, and N0 still pass.
- [ ] **Step 6: Commit:** `/usr/bin/git -C WT add src/microduck_challenges/sock_heist_6m tests/test_sock_heist_6m.py && /usr/bin/git -C WT commit -m "Sock Heist's rules for training, copied from the Arena and pinned against it: each episode's reds drawn from the event's ranges in whole steps, the turn, the mark, the watch and the lane's heading hold"`.

### Task D1.2: The environment

**Files:**
- Modify: `FOLDER/lights.py` (the command term)
- Create:
  - `FOLDER/env.py`: a copy of `sprint_2m/env.py` at 4b675eb, then the changes below;
  - `FOLDER/tasks.py`: the sprint's, with its docstring naming Sock Heist;
  - `FOLDER/challenge.toml`, `FOLDER/rewards.py`, `FOLDER/walker.py`;
  - `FOLDER/walker.onnx`: a copy of `ARENA/arena/assets/policies/BEST_alpha_walking.onnx`, 793,705 bytes, sha256 `e36332d383997d51401897734cd3e79cf5038406feddb18b4d57ecfb141daa6c`;
  - `FOLDER/AGENTS.md`: the first draft.
- Modify:
  - `src/microduck_challenges/__init__.py`: `from .sock_heist_6m import tasks as _sock_heist_6m  # noqa: F401`, last;
  - `.gitignore`: `!src/microduck_challenges/sock_heist_6m/walker.onnx` under the tug's line. Without it the HF job's tarball (`git ls-files -co --exclude-standard`) leaves the walker behind;
  - `AGENTS.md`: the row `| 6 m Sock Heist | sock-heist-6m | [src/microduck_challenges/sock_heist_6m/AGENTS.md](src/microduck_challenges/sock_heist_6m/AGENTS.md) |` after the Tug of War's;
  - `README.md`: the row `| sock_heist_6m | sock-heist-6m | Mjlab-SockHeist6m-MicroDuck |` last;
  - `tests/test_challenges.py`:
    - `CHALLENGES["sock_heist_6m"] = {"forward_reward": ("track_linear_velocity", 3.7), "freeze_reward": ("freeze", 1.3), "upright_reward": ("upright", 1.3), "step_reward": ("air_time", 4.1)}`;
    - `"sock_heist_6m"` in `RACES` and in `test_walking_training_reaches_the_top_of_the_sweep`'s list. Not in the heading-hold tests: the lane's hold replaces `heading_hold`.
- Test: `WT/tests/test_sock_heist_6m.py`

**Interfaces:**
- Consumes: D1.1's `lights` functions and constants. From `tug_of_war.opponent`, `load_actor(path) -> torch.nn.Sequential`, imported, not copied.
- Produces:
  - `lights.LightsCommandCfg(microduck_mdp.VelocityCommandCommandOnlyCfg)`, whose `build` returns `LightsCommand(microduck_mdp.VelocityCommandCommandOnly)`, with:
    - `speed (n,)`: the episode's forward command, saved from the base draw;
    - `onset, length (n, R)` int64, drawn by `draw_reds` in `_resample_command`;
    - `lane_y (n,)` and `mark (n, 2)`, with `turn: int = steps(TURN_S)`;
    - `stepped() -> (red, mark, watch)` at the step just simulated, `episode_length_buf - 1`;
    - `drift() -> (n,)`: the trunk's floor distance from its mark, read off the free joint's qpos, as `run_once` reads it.
  - `rewards.freeze(env, command_name: str, std: float) -> (n,)`: `exp(-(drift/std)²)` on watched steps, else 0.
  - `rewards.caught(env, command_name: str) -> (n,) bool`: `watch & (drift > TOLERANCE_M)`.
  - `rewards.light_state(env, command_name) -> (n, 4)`, for the step about to run: standing (settle or red), watched, seconds until the twist next changes, and the drift over `TOLERANCE_M` once marked (0 before).
  - `rewards.lane_state(env, command_name) -> (n, 2)`: y off the lane, and yaw.
  - `env.SWEEP = (0.20, 1.20)`, `env.YAW_PERTURBATION_DEG = 2.0`, `env.make_env_cfg(play=False)`, `env.RL_CFG`.
  - `walker.WALKER`, `walker.WALKER_SEEN = 502 * 24 * 4096` (t20's start from the walker used this count; the walker's own is unknown), `walker.WARM_START_STD = 0.3` (t20's, commit 8391bf7), `walker.WalkerActor(MLPModel)`.
  - The task id `Mjlab-SockHeist6m-MicroDuck`, logging under `logs/rsl_rl/sock_heist_6m/`.

**`LightsCommand._update_command`**, called after `sim.forward()` (mjlab's step: physics, `episode_length_buf += 1`, terminations, rewards, resets, forward, commands, observations), in this order:
  1. Where `stepped()`'s mark holds, `mark = qpos[:, 0:2]`.
  2. Where `episode_length_buf == 0` (a fresh episode, both after `env.reset()` and after an auto-reset), `lane_y = qpos[:, 1]`.
  3. For `k = episode_length_buf`, the step the policy is about to take: a twist of zeros where `k < steps(SETTLE_S)` or `light_steps(...)` is red, else `[speed, 0, hold_yaw_rate(qpos y − lane_y, qpos quat)]`.

  The lane runs along +x through the spawn point, as the Arena's runs along its x axis from y = 0. Every tensor is created on `self.device`. A CPU test cannot catch a tensor left on the CPU; the first GPU job does, and D3's counting rule covers it.

**`env.py`'s changes to the sprint**, each with its comment:
- `ENABLE_VELOCITY_PUSHES = False`: a push while watched catches a duck that did nothing, and the Arena pushes nobody.
- `cfg.events["reset_base"].params["pose_range"]["yaw"] = (-math.radians(YAW_PERTURBATION_DEG), math.radians(YAW_PERTURBATION_DEG))`: the event's `[start.perturbation]`, the lane along +x.
- `cfg.commands["twist"] = lights.LightsCommandCfg(**vars(command))` with:
  - `ranges.lin_vel_x = SWEEP` (the event's `[sweep]`), `lin_vel_y = ang_vel_z = (0.0, 0.0)` (the hold writes the yaw rate);
  - `heading_command = False`, `ranges.heading = None`;
  - `rel_standing_envs = rel_heading_envs = rel_forward_envs = rel_world_envs = init_velocity_prob = 0.0`: no standing episodes (the reds stand about 45 % of each), no flying start, and no speed forced to 0.3 or more;
  - `resampling_time_range = (60.0, 60.0)`: one speed an episode, as the Arena holds one a run.
- Rewards: no `heading_hold`. Add `freeze` (weight `knobs["freeze_reward"]`, `params={"command_name": "twist", "std": lights.TOLERANCE_M}`).
- Terminations: add `caught` (`rewards.caught`, `params={"command_name": "twist"}`, `time_out=False`).
- Critic: no `heading_error` (the function goes too). Add `light` (`rewards.light_state`) and `lane` (`rewards.lane_state`), both `{"command_name": "twist"}`. The actor's terms are the sprint's, untouched.
- Curriculum: no `standing_envs`.
- `RL_CFG`:
  - `actor.class_name = "microduck_challenges.sock_heist_6m.walker:WalkerActor"`;
  - `experiment_name = run_name = "sock_heist_6m"`;
  - `save_interval = 100`: warm-started tug runs peaked early and fell between 250-iteration checkpoints.
- Everything else is the sprint's: the knobs' terms, pose, air_time's window, the domain randomisation, the noise, and the action-rate, CoM and head-bias curricula.

**The reward design** (starting weights, the AGENTS.md table carries it):

| Term | Weight | Why |
| --- | --- | --- |
| `track_linear_velocity` | `forward_reward` 2.0, std √0.1 | Progress on green at the commanded speed, and stillness on red (a zero command). At 0.45 m/s standing earns 13 % of walking; the tug's t4/t5 never walked at 41 %. |
| `track_angular_velocity` | 2.0, std √0.5 | The lane's hold steers through the yaw rate, so tracking it is the steering. |
| `freeze` (new) | `freeze_reward` 2.0, std 0.03 m | The rule is 3 cm, and nothing else sees a few centimetres of creep: tracking's std is 0.32 m/s. |
| `upright` | `upright_reward` 2.0, std √0.05 | The sprint's. A forward lean is what ends in a fall on a stop. |
| `air_time` | `step_reward` 3.0, threshold 0.01 | The sprint's. It pays steps only on a non-zero command, so stepping in place under a red earns nothing. |
| `pose` | 1.0 | The sprint's: on a zero command its standing std pulls the legs to the standing pose. |
| `heading_hold` | removed | The hold commands the yaw rate. An angle reward on the spawn heading would fight it when it steers back to the line. |
| gait and smoothness terms | the sprint's | Unchanged shaping of the walk the walker already has. |
| `caught` (termination) | none | It costs every reward still to come (γ 0.99), as a fall does in the sprint. There is no explicit penalty, so standing is never made cheaper than walking. |

There is no new curriculum at first: the walker already walks and stands, and the event's rules hold from iteration 0. D3's lever L2 adds one.

**`challenge.toml`**:
- `event = "sock-heist-6m"`, `task = "Mjlab-SockHeist6m-MicroDuck"`, `kind = "perpetual"`;
- a header comment telling the game in two lines;
- `[command] twist = "[vx: the speed the Arena times you at, 0 from the moment the giant starts turning its head until it looks away; unused; yaw rate: the lane's heading hold, 0 while the giant turns or looks]"`;
- `[recipe]` `num_envs = 4096`, `max_iterations = 1000`, `seed = 1`;
- `[params.forward_reward]` "Walk on green" 2.0 (0.5–5.0), `[params.freeze_reward]` "Freeze while watched" 2.0 (0.0–6.0), `[params.upright_reward]` "Stay upright" 2.0 (0.5–5.0), `[params.step_reward]` "Lift your feet" 3.0 (0.0–6.0).

**`FOLDER/AGENTS.md`, first draft**, built like `sprint_2m/AGENTS.md`:
- the opening rules (simple, transparent, efficient; no job, publish or push without the user's yes);
- **The challenge**, from the event file: the 6 m lane; the giant, its random timetable per seed (the same five for every entrant) and the three ranges; the 0.4 s turn; the mark and the 3 cm; caught scored as the time limit; the hold's formula; the sweep; the time limit as A6 set it;
- **The policy**: 61 numbers, and the only signal is its command, so on red the twist is zero;
- **The recipe**: the walker start, the rules in `lights.py`, `freeze`, no pushes, and no walls in training (the hold kept the walker within 0.30 m of the centre line at 1.0 m/s on #3's lane);
- **Files and knobs**, with the do-not-change list: the robot, the 61 numbers, `experiment_name`, the copies in `lights.py` and the tests pinning them, `walker.onnx`, `pyproject.toml` and `uv.lock`;
- **Running a training**, **Judging every checkpoint** (`publish --dry-run`, then `arena score --event sock-heist-6m`, then CHECK) and **Reporting**, in the users' commands (`uv run --group workshop …`);
- **What is known**: PR #3's walker facts only (never trained to stop; stands at 0.20 m/s; on 15 m it finished 0.45–1.00 m/s and was caught in the first red from 1.10). D2 adds the walker's 6 m numbers, D4 the trainings.

- [ ] **Step 1: Write the failing tests** (a module fixture `live`: `cfg = env.make_env_cfg(); cfg.scene.num_envs = 2; ManagerBasedRlEnv(cfg, device="cpu")`, reset, closed at the end). `_set_reds(live, onset, length)` resets `live`, then gives every env one red (`term.onset[:, 0] = onset`, `term.onset[:, 1:] = 10**6`, `term.length[:] = length`). `_qpos(live)` is the robot's free-joint qpos `(2, 7)`.

```python
def test_the_training_never_imports_the_arena():
    code = ("import sys; sys.modules['arena'] = None; "
            "import microduck_challenges.sock_heist_6m.env, microduck_challenges.sock_heist_6m.walker")
    subprocess.run([sys.executable, "-c", code], check=True)


def test_the_command_and_the_start_are_the_events(cfg):
    twist = cfg.commands["twist"]
    assert isinstance(twist, lights.LightsCommandCfg)
    assert twist.ranges.lin_vel_x == (EVENT.sweep.lo, EVENT.sweep.hi) == env.SWEEP
    assert twist.ranges.lin_vel_y == twist.ranges.ang_vel_z == (0.0, 0.0) and not twist.heading_command
    assert (twist.rel_standing_envs, twist.rel_heading_envs, twist.rel_forward_envs, twist.rel_world_envs,
            twist.init_velocity_prob) == (0.0,) * 5
    assert twist.resampling_time_range[0] > cfg.episode_length_s
    assert "standing_envs" not in cfg.curriculum and "push_robot" not in cfg.events
    yaw = math.radians(EVENT.start.yaw_deg)
    assert env.YAW_PERTURBATION_DEG == EVENT.start.yaw_deg
    assert cfg.events["reset_base"].params["pose_range"]["yaw"] == pytest.approx((-yaw, yaw))
    assert cfg.actions["joint_pos"].scale == ACTION_SCALE


def test_the_actor_reads_the_arenas_61_numbers(cfg, live):
    sprint = importlib.import_module("microduck_challenges.sprint_2m.env").make_env_cfg()
    actor, critic = cfg.observations["actor"].terms, cfg.observations["critic"].terms
    assert list(actor) == list(sprint.observations["actor"].terms)
    assert {"light", "lane", "base_lin_vel"} <= set(critic) and not {"light", "lane", "heading_error"} & set(actor)
    assert "heading_error" not in critic
    assert live.observation_manager.group_obs_dim["actor"] == (OBS_SIZE,)


def test_walking_on_green_pays_far_more_than_standing_still(cfg):
    # The tug's t4/t5 stood when standing kept 0.41 of tracking: here it keeps 0.13 at 0.45 m/s.
    term = cfg.rewards["track_linear_velocity"]
    assert term.weight == 2.0 and term.params["std"] == pytest.approx(math.sqrt(0.1))
    assert "heading_hold" not in cfg.rewards
    paid = lambda vx: term.weight * term.func(_tracking_env(0.45, vx), **term.params).item()
    assert paid(0.45) == pytest.approx(2.0) and paid(0.0) <= 2.0 / 6


def test_freeze_pays_only_while_watched_and_fades_at_the_tolerance(cfg):
    fake = lambda watch, drift: SimpleNamespace(command_manager=SimpleNamespace(get_term=lambda name: SimpleNamespace(
        stepped=lambda: (None, None, torch.tensor(watch)), drift=lambda: torch.tensor(drift))))
    params = cfg.rewards["freeze"].params
    got = rewards.freeze(fake([True, True, False], [0.0, 0.03, 0.0]), **params)
    assert got.tolist() == pytest.approx([1.0, math.exp(-1.0), 0.0])


def test_the_twist_is_zero_from_a_reds_first_step_to_its_last(live):
    term = live.command_manager.get_term("twist")
    _set_reds(live, onset=40, length=30)
    for _ in range(80):
        k = live.episode_length_buf.clone()
        twist, qpos = live.command_manager.get_command("twist"), _qpos(live)
        stand = (k < SETTLE) | ((40 <= k) & (k < 70))
        assert (twist[stand] == 0).all()
        hold = lights.hold_yaw_rate(qpos[:, 1] - term.lane_y, qpos[:, 3:7])
        walk = torch.stack([term.speed, torch.zeros_like(hold), hold], dim=-1)
        assert torch.allclose(twist[~stand], walk[~stand], atol=1e-6)
        live.step(torch.zeros(2, 14))


def test_the_hold_steers_from_the_spawn_line(live):
    term = live.command_manager.get_term("twist")
    _set_reds(live, onset=10**6, length=1)
    assert torch.allclose(term.lane_y, _qpos(live)[:, 1])
    for _ in range(SETTLE):
        live.step(torch.zeros(2, 14))
    _nudge(live, env_id=0, dy=0.2)                       # 20 cm left of its line
    live.step(torch.zeros(2, 14))
    assert live.command_manager.get_command("twist")[0, 2] < -0.5   # turns right, back to it


def test_moving_past_the_tolerance_while_watched_is_caught(live):
    _set_reds(live, onset=40, length=40)                 # turning 40-59, marked at 59, watched 60-79
    for k in range(66):
        if k == 50:
            _nudge(live, env_id=1, dx=0.04)              # while the head turns: nothing counts
        if k == 65:
            _nudge(live, env_id=0, dx=0.04)
            _nudge(live, env_id=1, dx=0.015)             # watched: 4 cm is caught, 1.5 cm is not
        live.step(torch.zeros(2, 14))
        assert live.termination_manager.get_term("caught").tolist() == ([True, False] if k == 65 else [False, False])


def test_the_learner_starts_as_the_walker():
    assert sha256(walker.WALKER) == sha256(ASSET_ROOT / "policies" / "BEST_alpha_walking.onnx")
    # as the tug's test_the_learner_starts_as_the_reference: WalkerActor built from RL_CFG.actor matches
    # onnxruntime on walker.onnx over 32 random rows (atol 1e-5), its std 0.3 on all 14 actions, and still
    # within 1e-2 after one update_normalization on 4096 copies of one row.


def test_the_walker_walks_in_the_training_env(live):
    """The Arena's walker, fed the training's actor observation, walks: the layout is the Arena's."""
    term = live.command_manager.get_term("twist")
    _set_reds(live, onset=10**6, length=1)
    term.speed[:] = 0.6
    session = onnxruntime.InferenceSession(str(walker.WALKER), providers=["CPUExecutionProvider"])
    x0 = _qpos(live)[:, 0].clone()
    for _ in range(150):
        rows = live.obs_buf["actor"].numpy()
        live.step(torch.from_numpy(np.concatenate([session.run(None, {"obs": r[None]})[0] for r in rows])))
        assert not live.reset_terminated.any()
    assert (_qpos(live)[:, 0] - x0 > 0.4).all()          # 2.5 s of green: #3 measured ~0.3 m/s at 0.6


def test_the_recipe_judges_every_hundred_iterations():
    recipe = tomllib.loads((FOLDER / "challenge.toml").read_text())["recipe"]
    assert recipe == {"num_envs": 4096, "max_iterations": 1000, "seed": 1} and env.RL_CFG.save_interval == 100
```

  - `_tracking_env(command_vx, vx)` is the tug test's `SimpleNamespace` env, which `track_linear_velocity` reads.
  - `_nudge(live, env_id, dx=0.0, dy=0.0)` shifts that env's `root_link_pose_w` and writes it with `write_root_link_pose_to_sim`, then `live.sim.forward()`, as `test_down_reads_the_head_the_neck_and_a_body_on_the_course` does.

- [ ] **Step 2: Run them:** TESTS. Expected: FAIL at import (`microduck_challenges.sock_heist_6m.env`), and `test_challenges.py` fails on its new row.
- [ ] **Step 3: Implement** the files above. `walker.WalkerActor.__init__` is the tug's `ReferenceActor.__init__` on `WALKER`, `WALKER_SEEN` and `WARM_START_STD`. It is not a subclass of it, because `ReferenceActor` reads the tug's module constants.
- [ ] **Step 4: Run them:** TESTS. Expected: N0 plus every new test PASS, the test_challenges rows included.
- [ ] **Step 5: Commit:** `git add` the folder, `src/microduck_challenges/__init__.py`, `.gitignore`, `AGENTS.md`, `README.md` and both test files. The message: `"A training folder for the 6 m Sock Heist: the sprint's walk on a command that stops under the giant's eye and steers down the lane, a reward for freezing while watched, caught as a termination, and a learner that starts as the reference walker"`.

### Task D1.3: The judge, `check.py`

**Files:**
- Create: `FOLDER/check.py`
- Test: `WT/tests/test_sock_heist_6m.py`

**Interfaces:**
- Consumes: `arena.runner.run_once(manifest, policy, seed, model=None, command=None) -> RunOutcome`, with `caught_frame` from Plan A; `arena.lights.timetable`; `arena.course.compile_course`; `arena.evaluate.evaluate`; `manifest.command_at(vx)`; `arena.policy.load_policy`.
- Produces:
  - `CAUGHT_EARLY_S = 0.2`: caught within this of the watch's start means still moving when the head finished turning.
  - `STOP_WINDOW_S = 0.6`: a fall tipping within this of a red's start is on a stop, within this of its end on a start.
  - `LEFT_THE_LINE_M = 0.5`.
  - `judge(outcome: RunOutcome, reds: tuple[Red, ...], turn: int, fall_hold: int) -> tuple[str, str]`: `(kind, line)`. `kind` is one of `finish`, `caught early`, `caught late`, `fell on a stop`, `fell on a start`, `fell under a red`, `fell on green`, `out of time`, `never left the line`.
  - `tally(kinds: list[str], times: list[float]) -> str`.
  - `main(argv=None) -> int`. The CLI is `python -m microduck_challenges.sock_heist_6m.check policy.onnx [--speed V] [--seeds N]`: seeds 1..N (default 5, the event's), at `--speed` or, by default, at the command `evaluate` scores it at (printing `scored at V m/s` first).

**The lines** (pinned; `k` is the run's last timed step, `caught_frame` for a catch; times are `(k + 1) · CTRL_DT`, a finish's is `outcome.time_s`):
- `seed {s} · finish {t:.2f} s · {tail}`
- `seed {s} · caught at {t:.2f} s, {w:.2f} s into the watch, {v:.2f} m/s as the red began · {tail}`: `w` counts from `onset + turn` to `k`, and `v` is the trunk's x speed over the 5 steps before the onset.
- `seed {s} · fell at {t:.2f} s on a stop, tipping {d:.2f} s after a red began · {tail}`. The others: `… on a start, tipping {d:.2f} s after a red ended`, `… under a red`, `… on green`. Tipping begins at `k − fall_hold + 1`.
- `seed {s} · out of time at {p:.2f} m · {tail}`, or `seed {s} · never left the line ({p:.2f} m) · {tail}` when `p` < `LEFT_THE_LINE_M`. `p` is the trunk's x at `k` less the settle's last frame's.
- `{tail}` = `{n} red{s} met · worst drift {d:.1f} cm · {v:.2f} m/s on green`. A red is met when its onset ≤ k. The worst drift is the largest distance from the mark over the watched steps before `k`, 0.0 with none. The green speed is the trunk's x from the settle's last frame to `k`, over the green steps.
- The tally: `finished {f}/{n} · caught {c} (early {e}) · fell {x} (on a stop {a}, on a start {b}) · out of time {o} (never left the line {z}) · mean {m:.2f} s`, with an unfinished seed at the time limit, as the Arena scores.

- [ ] **Step 1: Write the failing tests.** They use synthetic outcomes: a `RunOutcome` whose trace is zeros but its x column, `reds = (Red(50, 70),)`, `turn = 20`, `fall_hold = 15`.

```python
def test_a_catch_says_how_far_into_the_watch_and_how_fast_the_duck_came():
    x = np.minimum(np.arange(140) * 0.01, 0.72)            # 0.5 m/s, then still from step 72
    kind, line = check.judge(_outcome("caught", x, caught_frame=72), (Red(50, 70),), 20, 15)
    assert kind == "caught early"
    assert line.startswith("caught at 1.46 s, 0.04 s into the watch, 0.50 m/s as the red began · 1 red met")


def test_a_fall_tipping_in_a_reds_first_moments_is_on_a_stop():
    kind, line = check.judge(_outcome("fall", np.zeros(75)), (Red(50, 70),), 20, 15)
    assert (kind, line.split(" · ")[0]) == ("fell on a stop", "fell at 1.50 s on a stop, tipping 0.20 s after a red began")


def test_a_fall_far_from_any_red_is_on_green():
    assert check.judge(_outcome("fall", np.zeros(75)), (Red(200, 70),), 20, 15)[0] == "fell on green"


def test_a_duck_that_never_left_the_line_is_named():
    kind, line = check.judge(_outcome("timeout", np.full(500, 0.1)), (Red(50, 70),), 20, 15)
    assert (kind, line.split(" · ")[0]) == ("never left the line", "never left the line (0.10 m)")


def test_the_worst_drift_is_read_over_the_watched_steps():
    x = np.zeros(200); x[69:] = 0.05; x[75] = 0.07          # marked at 69 (0.05 m), 2 cm off at 75
    assert "worst drift 2.0 cm" in check.judge(_outcome("finish", x, time_s=4.0), (Red(50, 70),), 20, 15)[1]


def test_the_tally_counts_each_kind():
    kinds = ["finish", "caught early", "fell on a stop", "finish", "never left the line"]
    assert check.tally(kinds, [10.0, 30.0, 30.0, 12.0, 30.0]) == (
        "finished 2/5 · caught 1 (early 1) · fell 1 (on a stop 1, on a start 0) · out of time 1 (never left the line 1) · mean 22.40 s")


def test_check_judges_the_walker(capsys):
    assert check.main([str(walker.WALKER), "--speed", "0.95", "--seeds", "1"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("seed 1 · ") and lines[-1].startswith("finished ")   # no verdict: platforms differ
```

  `_outcome(status, x, caught_frame=None, time_s=None)` builds the `RunOutcome`: the trace `(len(x), TRACE_WIDTH)` with `x` in column 0, and a one-frame settle at x 0. For a finish the trace is the whole `x`; for a catch it runs on past `caught_frame`, as the collapse records.

- [ ] **Step 2: Run them:** TESTS. Expected: FAIL on `ModuleNotFoundError: microduck_challenges.sock_heist_6m.check`.
- [ ] **Step 3: Implement `FOLDER/check.py`.**
  - Its docstring is the CLI line.
  - `main` loads the event and policy, compiles the course once, and runs `run_once(manifest, policy, seed, model, command=manifest.command_at(speed))` per seed, with `timetable(manifest.lights, manifest.id, seed, round(manifest.time_limit_s / CTRL_DT))`.
  - `turn` and `fall_hold` come from the event.
- [ ] **Step 4: Run them:** TESTS. Expected: all PASS.
- [ ] **Step 5: Commit:** `"Sock Heist's check says why each seed ended: caught still moving or creeping, a fall on a stop, a start or green, a duck that never left the line, and how far it drifted while watched"`.

### Task D2: The smoke run, end to end

**Files:** none tracked; LEDGER. Gets the Mac triage's bar.

- [ ] **Step 1: Train two iterations on the CPU:** `cd WT && uv run --no-config --no-sync train Mjlab-SockHeist6m-MicroDuck --gpu-ids None --env.scene.num-envs 2 --agent.max-iterations 2 --agent.logger tensorboard --agent.run-name smoke`. Expected: `Learning iteration 1/2` and `logs/rsl_rl/sock_heist_6m/<stamp>_smoke/model_1.pt`.
- [ ] **Step 2: Export it as publish does:** `cd WT && uv run --no-config --no-sync publish --run logs/rsl_rl/sock_heist_6m/<stamp>_smoke --repo local/microduck-smoke --dry-run --allow-dirty`. Expected: `[publish] policy.onnx: 61 -> 14, ok`, `smoke run: finite, non-constant output`, and `WT/publish-smoke/`. In it, `manifest.json` reads `"kind": "perpetual"` and `"arena": {"event": "sock-heist-6m"}` (check with `python -c json.load`). This confirms the locked wheel never had to know the event.
- [ ] **Step 3: Score it on the Arena:** SCORE `WT/publish-smoke/policy.onnx`. Expected: the sweep, `scored at …`, five `seed N:` lines and `score …`. Two tiny updates on two envs leave a walker that walks. If no seed gets 1 m out, the warm start or the layout broke behind D1.2's tests: stop and find out why.
- [ ] **Step 4: The bar on the Mac:**
  1. SCORE `ARENA/arena/assets/policies/BEST_alpha_walking.onnx`: W_mac, its scored command V_w and its seed lines, into LEDGER.
  2. CHECK `src/microduck_challenges/sock_heist_6m/walker.onnx --speed V_w --seeds 25`: its 25 lines and tally, into LEDGER.
  3. Write the walker's 6 m numbers into AGENTS.md's "What is known" (Mac, indicative).
- [ ] **Step 5: The job's view of the folder:**
  1. `/usr/bin/git -C WT ls-files -co --exclude-standard src/microduck_challenges/sock_heist_6m` lists `walker.onnx` beside the nine other files.
  2. `cd WT && uv run --no-config --no-sync train Mjlab-SockHeist6m-MicroDuck --env.scene.num-envs 4096 --agent.max-iterations 1000 --hf-jobs --dry-run --no-wandb --namespace Nico-robot` prints `[dry-run] would submit job:` and a `TRAIN_ARGS` starting `Mjlab-SockHeist6m-MicroDuck`, and submits nothing. No real job runs here: a job is one of the owner's ten trainings.
- [ ] **Step 6:** `rm -rf WT/logs/rsl_rl/sock_heist_6m/*_smoke WT/publish-smoke`. Commit the AGENTS.md lines: `"Sock Heist's guide gives the reference walker's numbers on the 6 m lane, measured on a Mac"`.

### Task D3: The trainings, up to 10

A loop, not ten tasks. Each training `sh<n>` (n = 1…10) runs the cycle below, and the decision table picks the next one's single change. The first that clears the bar is THE reference, and training stops there.

**Counting and reporting:**
- A training counts once its job reaches its first checkpoint. A job that fails before (bootstrap, a device error) is fixed, committed and relaunched without counting; both are reported.
- At each launch, tell the owner: `sh<n> (n/10) launched: commit <sha> "<hypothesis>"; <warm start | scratch>, seed <s>, 4096 envs, <iterations> its, l4x1; job <id>; checkpoints Nico-robot/mjlab-sockheist6m-microduck-sh<n>`. Nothing waits for an answer.
- While an x86 judgement is waiting for the owner's yes, no new training is launched.

**The gates:**
- **M, the Mac triage**, on each checkpoint:
  - SCORE says `5/5 finished` with `score` < W_mac;
  - then CHECK at its scored command with `--seeds 25` says `finished` ≥ 24/25.
- **X, the bar, on x86**:
  - A6's job, with its command as Plan A writes it, scoring the candidates' ONNX files in place of the walker's;
  - `5/5 finished` and `score` < W_x86, the walker's x86 score from A6.

- [ ] **Step 1: State the hypothesis and make the change.**
  - sh1 and sh2 are the recipe as committed, seeds 1 and 2, launched together: seeds diverge, as the tug's t15/t16 did.
  - From sh3 on, take the best training so far (the most CHECK finishes over 25 seeds on its best checkpoint, then the lowest Mac score) and apply the one lever the table gives. The change goes in `challenge.toml` or `env.py`/`lights.py`/`rewards.py`, with the tests it invalidates updated in the same commit.
  - The commit message is the hypothesis, naming the diagnosis and the lever.
- [ ] **Step 2: Test:** TESTS, which include the parity tests, so the training runs on the event's numbers as they stand.
- [ ] **Step 3: Launch** (a subagent, which returns at once): `cd WT && uv run --no-config --no-sync train Mjlab-SockHeist6m-MicroDuck --env.scene.num-envs 4096 --agent.max-iterations <the recipe's> --agent.seed <s> --agent.logger tensorboard --agent.run-name sh<n> --hf-jobs --detach --no-wandb --namespace Nico-robot --ckpt-repo Nico-robot/mjlab-sockheist6m-microduck-sh<n>`. Then:
  - put `[job] id:` into LEDGER;
  - `uv run --no-config --no-sync hf jobs inspect <id> --namespace Nico-robot` reaches RUNNING; an ERROR naming a volume mount is resubmitted;
  - report the launch.
- [ ] **Step 4: Wait.** The controller runs Monitor with an until-loop on `hf jobs inspect`'s stage: COMPLETED, ERROR or CANCELED.
  - Fetch the run with `uv run --no-config --no-sync hf download Nico-robot/mjlab-sockheist6m-microduck-sh<n> --local-dir logs/rsl_rl`.
  - Read the curves with the AGENTS.md TensorBoard one-liner: `Train/mean_episode_length`, `Episode_Termination/{caught,fell_over,nan_state}`, `Episode_Reward/{track_linear_velocity,freeze,track_angular_velocity}`.
  - The never-move sign is `track_linear_velocity` falling while `freeze` rises, and episodes lengthening with no finishes. If the run shows it before its end, judge the checkpoints already up. If two in a row fail M on finishes, cancel the job (`hf jobs cancel`); it still counts.
- [ ] **Step 5: Judge every checkpoint** `N` (100, 200, …, the last):
  1. `cd WT && uv run --no-config --no-sync publish --run logs/rsl_rl/sock_heist_6m/<stamp>_sh<n> --checkpoint N --repo local/microduck-eval --dry-run && cp publish-eval/policy.onnx logs/sock_heist_6m/onnx/sh<n>-N.onnx`. There is no `--allow-dirty`: a refusal means the run did not train from its commit, and is reported.
  2. SCORE the file.
  3. CHECK `--seeds 25` at its scored command for the three best by (finishes, score), and for any that passes SCORE's half of M.
  4. LEDGER block: `## sh<n> (k/10) · commit · seed · iterations · job · repo`, then the hypothesis, the curves at the end, a line per checkpoint (`N: score f/5 at vx`), the CHECK tallies, M, X, the diagnosis and the next lever.
- [ ] **Step 6: x86.**
  - If checkpoints pass M, ask the owner: "x86 judgement of sh<n>-<N1>[, <N2>, <N3>] (Mac <scores>, check <tallies>): launch A6's job?" Send the (at most three) best by Mac score.
  - On the yes, run A6's job on them and record the x86 lines.
  - The lowest x86 score among those passing X is **THE reference**. Cancel any training still running, report, and go to D4.
- [ ] **Step 7: Diagnose and pick the next lever.**
  - Take the training's best checkpoint B (the most CHECK finishes over 25 seeds, then the lowest Mac score) and its CHECK tally.
  - The class is the tally's largest failure count. Ties go caught, then fell, then never left the line. A B finishing ≥ 24/25 but no faster than W_mac is "slow". A B that passed M but failed X is a "near miss".
  - Use the class's first lever not yet tried.
  - A lever stays when the next training's B loses fewer seeds to its class, and is reverted otherwise (a revert commit). Then go to Step 1.

| Class (B's CHECK over 25 seeds) | 1st lever | 2nd | 3rd |
| --- | --- | --- | --- |
| caught early: still moving as the head finished turning | **L1** `freeze_reward` 2.0 → 4.0 | **L2** the turn's grace as a curriculum: `turn_s` 0.8, then 0.6 from iteration 300, then the event's 0.4 from 600 to the end | **L3** `lin_vel_x`'s top cut to the fastest command at which B's SCORE sweep finished, plus 0.10 |
| caught late: creeping or swaying while watched | **L6** `freeze` std 0.03 → 0.015 m | L1 | — |
| fell on a stop, or on a start | **L7a** `upright_reward` 2.0 → 3.0 | **L7b** a fall penalty: reward `fall` = the tug's `rewards.ended_by` on `("fell_over",)`, weight −20 | L2 |
| fell on green or under a red | the same commit, next seed | L7a | — |
| never left the line, or out of time | **L9** `forward_reward` 2.0 → 3.5 and its std √0.05: the tug's t4/t5 fix, two changes on purpose | **L10** from scratch | — |
| slow: finishes, no faster than the walker | **L4** `lin_vel_x = (0.60, 1.20)`: train where the race is won. `sock_heist_6m` leaves `RACES` in `test_challenges.py`, its own test pins the range | **L5** `forward_reward` 2.0 → 3.0 | **L12** 2000 iterations |
| near miss: M passed, X missed (a seed short, or not faster than W_x86) | the same commit, next seed | — | — |
| the warm start decays: every checkpoint after 100 finishes fewer CHECK seeds than 100 | **L10** from scratch | — | — |
| the best is the last checkpoint and its Mac score is still falling | **L12** `[recipe] max_iterations = 2000` | — | — |

- **L2:**
  - `LightsCommand.turn` becomes the attribute a curriculum term `rewards.turn_grace(env, env_ids, command_name: str, stages: list[dict]) -> Tensor` sets. Stages are `{"step": iteration × 24, "turn_s": …}`, and the term returns the current `turn_s`.
  - Test: the last stage's `turn_s == lights.TURN_S`, reached at iteration 600 of 1000.
  - `freeze`, `caught` and `light_state` read `turn` from the term.
- **L10:**
  - `RL_CFG.actor.class_name` becomes rsl_rl's `"MLPModel"`, with `[recipe] max_iterations = 3000` (the sprint's) and `save_interval = 250`;
  - `walker.py`, `walker.onnx`, its `.gitignore` line and its tests go in the same commit: no dead code.

- [ ] **Step 8: Stop rules.**
  - A reference found: go to D4.
  - Ten trainings without one:
    1. stop, and launch nothing more;
    2. report to the owner: the ten LEDGER blocks summed up, the best checkpoint over all of them with its Mac and x86 numbers, what each lever did, and a proposal;
    3. wait.

### Task D4: The folder's AGENTS.md, final

**Files:** Modify `FOLDER/AGENTS.md`, `WT/README.md` (one paragraph). Test: TESTS.

- [ ] **Step 1: The shipped recipe is the reference's.** `/usr/bin/git -C WT diff <reference commit> HEAD -- src/microduck_challenges/sock_heist_6m/{challenge.toml,env.py,lights.py,rewards.py,walker.py}` is empty. Otherwise `git checkout <reference commit> -- <those files>` with their tests, and commit `"Sock Heist's recipe as shipped is the one that trained its reference"`.
- [ ] **Step 2: Write the final AGENTS.md:**
  - **The challenge**: what the policy sees (only its command: on red, from the first step of the turn, the twist is zero, and on green its yaw rate is the hold's); the time it has to stop (`turn_s`, 0.4 s); what gets it caught (the trunk more than 3 cm across the floor from where it stood when the head finished turning, until the head turns away); that the timetable is random per seed and the same five for every entrant; the ranges; the time limit as A6 set it.
  - **The recipe**: the walker start, or scratch if L10 won; each lever that stayed, with its why.
  - **Judging**: SCORE and CHECK as users run them, with CHECK's line and tally formats explained word by word, as the tug's guide explains its own.
  - **What is known**, from LEDGER, numbers per platform:
    - the walker's 6 m numbers (Mac and x86);
    - one line per training (lever, best checkpoint, Mac score and finishes, CHECK tally);
    - what worked and what did not;
    - that checkpoints differ, and which;
    - the reference: training and checkpoint, commit, the command that trained it, the scored command, the Mac and x86 scores, and its 25-seed CHECK tally;
    - the line `uv run hf download pollen-robotics/microduck-sock-heist-6m-reference policy.onnx --local-dir logs/reference/sock-heist-6m`, marked as published by the release.
- [ ] **Step 3: README.md**, after the Tug of War's paragraph: the game in two sentences, the check line (`uv run --frozen --group workshop python -m microduck_challenges.sock_heist_6m.check policy.onnx [--speed V] [--seeds N]`), and that the recipe starts as the reference walker.
- [ ] **Step 4: Run every command the guide quotes** in WT's form (`--no-config --no-sync` for `--group workshop`): the smoke, one checkpoint's export and SCORE, CHECK. The outputs must match the quoted lines. Then TESTS: all PASS.
- [ ] **Step 5: Commit:** `"Sock Heist's guide says what its trainings found and how its reference was trained, with its numbers on a Mac and on the Space's x86"`.

### Task D5: The reference, staged for publication

**Files:** none tracked; `WT/publish-sock-heist-6m-reference/` (git-ignored) and LEDGER. The publication is Plan E Task 6's, on the owner's yes.

- [ ] **Step 1: Stage it:** `cd WT && uv run --no-config --no-sync publish --run logs/rsl_rl/sock_heist_6m/<stamp>_sh<k> --checkpoint <N> --repo pollen-robotics/microduck-sock-heist-6m-reference --dry-run`. Expected: `61 -> 14, ok`, the smoke run, and `WT/publish-sock-heist-6m-reference/` holding `policy.onnx`, `manifest.json`, `README.md` and `checkpoint.pt`.
- [ ] **Step 2: Verify it:**
  - `policy.onnx`'s sha256 equals `ONNX/sh<k>-<N>.onnx`'s, the bytes x86 judged. If the export is not byte-stable, SCORE the staged file: it must print the judged Mac score to the millisecond.
  - `manifest.json` reads `"kind": "perpetual"`, `"arena": {"event": "sock-heist-6m"}`, `training.commit` = sh<k>'s commit with `dirty` false, and `training.checkpoint` = N.
- [ ] **Step 3: Hand over to Plan E**, in LEDGER, for E Task 6:
  - the repo proposed, `pollen-robotics/microduck-sock-heist-6m-reference`, like the other events' references (the owner decides the account);
  - the command `cd WT && uv run --frozen --group workshop publish --run logs/rsl_rl/sock_heist_6m/<stamp>_sh<k> --checkpoint <N> --repo <repo> --no-private --enter`. It runs after E Task 5, so its `--enter` finds the event live and the recipe's commit on GitHub;
  - the x86 score E Task 6 Step 3 must see, to the millisecond, and ARENA's HEAD when it was measured;
  - the rule: if `arena/runner.py`, `arena/lights.py`, `arena/evaluate.py`, `arena/actuator.py`, `arena/course.py`, `arena/constants.py` or `arena/events/sock-heist-6m.toml` changed since, re-run A6's job on the staged file, on the owner's yes, before publishing.
- [ ] **Step 4: Report to the owner:** the reference, its numbers, the staged directory, and that the release (Plan E) can start.
