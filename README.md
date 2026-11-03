---
title: Microduck Arena
emoji: 🦆
colorFrom: gray
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
short_description: Race Microduck policies on a clock you can trust
thumbnail: https://huggingface.co/spaces/pollen-robotics/microduck-arena/resolve/main/docs/thumbnail.png
hf_oauth: true
---

# microduck-arena

Race a Microduck policy against every other policy, on a clock you can trust.

New to competing? Read [Train your first policy](docs/guides/train-a-policy.md),
then open **Training & rules** on your chosen challenge.

Submitted policies are evaluated **server-side** on a fixed course over five
perturbed seeds, at every commanded speed in the event's declared sweep, and the
best result is recorded. A time reported by a browser is a number in devtools;
this one reproduces on the Space's hardware (x86_64 Linux), and you can download
any published policy and race it yourself. Elsewhere — a Mac, or another
architecture — the same run gives different numbers: the servo model is chaotic
enough that a run diverges after a few seconds of simulated time, so a local time
is indicative, not the board's.

It runs two ways, and both are first-class:

- **Locally**, with no Hugging Face account, no OAuth and no network. The run log
  is a directory on your disk.
- **As a Space** (this repo is one). Same code path; its times are the
  board's, and a local run on other hardware gives indicative ones.

## Deploying to the Space

The source of truth is the GitHub repo
[`pollen-robotics/microduck-arena`](https://github.com/pollen-robotics/microduck-arena).
**Every push to `main` deploys** — `.github/workflows/deploy-space.yml` publishes
the tree to <https://huggingface.co/spaces/pollen-robotics/microduck-arena>.

`git push` to the Hub does not work here: it rejects binary files pushed through
plain git and asks for Xet instead, and this repo vendors a GLB, forty-odd STLs
and an ONNX policy. So the deploy goes through the Hub API, which speaks Xet
natively — the same script the workflow runs is the one to run by hand:

```bash
uv run python scripts/deploy_space.py            # publishes the working tree
uv run python scripts/deploy_space.py --dry-run  # shows what would go
```

The run log is not part of this. It lives in the `ARENA_DATASET` dataset repo,
which a deploy never touches, so the board and the standings survive every
redeploy — see *Running as a Space* below.

The Space rebuilds itself on each upload. Its own Docker build re-measures the
golden run and fails if the physics does not reproduce, so a broken build is
better than a silently wrong leaderboard.

## Releasing

A tag `vX.Y.Z` matching `version` in `pyproject.toml` builds the wheel — package, built site,
meshes — and attaches it to a GitHub release (`.github/workflows/release.yml`). That wheel is
what `microduck-challenges` depends on:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

## Running as a Space

The container filesystem is ephemeral, so a Space needs somewhere durable to
keep the run log. Set two things in **Settings → Variables and secrets**:

| name | kind | value |
| --- | --- | --- |
| `ARENA_DATASET` | variable | the dataset repo that holds the log, e.g. `pollen-robotics/microduck-arena-runs` |
| `HF_TOKEN` | **secret** | a token with write access to that dataset |

Without both, the Space still boots and the board still works — but every
recorded run is lost the next time it restarts or wakes from sleep. A
published policy's `.onnx` is not at risk from this: it lives in the
publishing author's own Hub repo, not on the Space. `GET /api/health` reports
`"durable": true` once it is configured, and the startup log says `EPHEMERAL`
in capitals when it is not.

The pages report how they are used — each page view, each link that leaves the site, the
time a page was on screen — with a random id per browser and no name (`app/src/usage.js`).
The Space writes them in batches every ten minutes to `ARENA_USAGE_DATASET` (a variable,
e.g. `pollen-robotics/microduck-arena-usage`, written with `HF_TOKEN`); without it they go
to the store folder. Pollen's private dashboard (`dashboard/`, deployed to
`pollen-robotics/microduck-arena-dashboard` by `.github/workflows/deploy-dashboard.yml`)
draws them next to the run log's players and voters.

An entry arrives from `uv run publish --enter`, from the workshop or a shell,
with the entrant's Hugging Face token (in practice a write token, the one
`publish` uploads with). The Space asks the Hub's whoami-v2 whose token it is,
then drops it: it never stores or logs it. The site keeps Hugging Face OAuth,
scope `openid profile`, for signing in, votes and withdrawing one's own
entries. Entering the board takes a Hugging Face repo the
author published themselves, raced at a pinned revision, and the board's
`.onnx` link resolves straight to that repo. A `.onnx` in hand is raced locally with
`arena score <onnx> --event <id>` and entered with
`uv run publish --onnx … --enter --event <id>`; the site itself has no entry form.

## Social clips

Every published run gets two clips — landscape and vertical — and the Space
renders none of them. The moment a publish completes it launches an HF Job of
its own on its own image, which runs `arena clip <run>`: a headless Chromium
photographs the arena's stage frame by frame on the job's GPU, ffmpeg encodes
the video, and the job writes the clip into the dataset. That is why the image
carries Chromium, ffmpeg and the EGL dispatchers (`libegl1`, `libgles2`).

Measured on 2026-10-05 on a 386-frame sprint clip: 75 s on a **t4-small** job,
against 588 s in SwiftShader on the Space's own eight vCPUs and 553 s on a
sixteen-vCPU job; about a cent a clip. The publication page follows the job,
frame by frame from its log. When the Jobs API refuses a launch, nothing is
rendered elsewhere: the run stays owed — its `clips/<run>/pending.json` marker
is the list — and is launched again later, and at every boot.

| name | kind | value |
| --- | --- | --- |
| `CHROME` | variable | the browser binary, if not at one of the usual paths |
| `ARENA_CLIPS` | variable | `0` stops owing clips |
| `ARENA_CLIP_FLAVOR` | variable | the job's hardware, default `t4-small` |
| `ARENA_CLIP_NAMESPACE` | variable | the account that runs and pays for the jobs, default the Space's owner |
| `ARENA_CLIP_TOKEN` | secret | the token that launches the jobs, with `job.read` and `job.write` on that account; default `HF_TOKEN`. The jobs themselves write to the dataset with `HF_TOKEN` |
| `ARENA_CLIP_JOBS` | variable | jobs running at once at most, default 16: a cup's match clips render in about half an hour |
| `ARENA_CLIP_PARALLEL` | variable | layouts a job renders at once, default half its cores |
| `ARENA_CLIP_BACKFILL` | variable | `1` also owes a clip to every run that has none — the log as it stood before clips — newest first, behind fresh publishes; once caught up a boot finds nothing to do |
| `ARENA_ORIGIN` | variable | where the recorder's Chrome loads `clip.html`, if not this server's own loopback address |

Each event's `[clip]` manifest section tunes its framing, duration and sounds
— see `arena/manifest.py`.

To render one run's clips by hand — a historical run, or a retry — run
`arena clip <run_id> --store DIR`; with `ARENA_DATASET` set it writes to the
dataset, as a job does, and `ARENA_CLIP_GPU=1` draws on the machine's GPU.

## Recovering the board

The run log can be lost — without `ARENA_DATASET` and `HF_TOKEN` it lives on a
container filesystem that every redeploy wipes. The **policies** are not lost
with it: publishing writes each one into its author's own public repo, tagged
`microduck-policy` and carrying a `manifest.json`. So the board is re-derivable.

```bash
uv run arena recover --store ~/arena-board                    # every event
uv run arena recover --store ~/arena-board --event sprint-2m
uv run arena recover --store ~/arena-board --all-tagged       # the whole ecosystem
```

With `ARENA_RECOVER=1` the same reconciliation runs at every startup, in a
background thread so it never blocks the Space coming up. It re-races only what
is **missing**, keyed on the Hub revision, so on a durable store it costs one
listing and finds nothing to do — measured: a second pass over a full store
restores 0 runs in 6 s. It is off by default because the local path must keep
working with no account and no network.

Two limits worth knowing. It restores only what reached the Hub — a `Test` run,
or anything published before policies went to the Hub, left nothing to recover.
And times are **re-measured**, never read back: a ranking you cannot re-verify
is not one worth restoring.

One thing this deployment does NOT have yet:

- **Submissions are synchronous and CPU-bound.** One entry is 33 simulated runs
  — about 3 s on a developer laptop, and proportionally longer on a shared
  2-vCPU Space. It works; it is not instant, and there is no queue.

## Run it

Python 3.12 (`uv` installs it: `uv python install 3.12`).

```bash
uv sync
cd app && npm install && npm run build && cd ..
uv run arena serve --store ~/arena-board --user $USER
```

`arena serve` finds the built site in `app/dist`. A wheel of this package (`uv build --wheel`
after `uv run python scripts/bundle_frontend.py`) carries it inside the package instead, at
`arena/frontend/`, so an installed Arena serves its site with nothing else on disk; that is
what the release workflow attaches to a tag. After building a wheel, delete `arena/frontend/`
(`rm -rf arena/frontend`) — an editable install prefers it over every later `npm run build` of
`app/dist`.

Open <http://127.0.0.1:8000>.

The home page is the club: `Season standings` ranks players by the points
their publications earned (first publication on an event 100, each published
run 10 capped at three a day, beating your own best 25 once per event, and
250/150/100 while you hold a podium place), and `Pick your round` lists the
events. The chip top-right opens your page, `#/p/<user>`; the standings link
to everyone else's. Points are folded from the run log on every request, like
the board — `GET /api/standings` and `GET /api/players/<user>`.

## From the command line

```bash
uv run arena events

# The repo vendors one reference policy, so this works with no setup:
REF=arena/assets/policies/BEST_alpha_walking.onnx
uv run arena score $REF --event sprint-2m
uv run arena score $REF --event sprint-2m --user me --name reference --store ~/arena-board
uv run arena board --event sprint-2m --store ~/arena-board

# A stage event plays a command timeline (arena/timeline.py) instead of racing:
uv run arena score $REF --event got-a-talent --timeline timeline.json
```

## What a policy has to be

One ONNX file with a **61-D observation input** and a **14-D action output** — the
same contract `robotd` enforces on the real robot, so a policy the Arena accepts
will load there too. A wrong shape is rejected with the reason:

```
observation width is 51, expected 61
```

## The events

| Event | Rig | Course | Command |
| --- | --- | --- | --- |
| `sprint-2m` | legs | 2 m flat | 0.25 m/s forward |
| `roller-sprint-2m` | rollers | 2 m flat | 0.6 m/s forward |
| `hill-climb-1m5` | legs | 1.5 m at 8° | 0.25 m/s forward |

Locally the board shows **one row per policy**, so your own `v1` and `v2` race each other;
resubmitting the same name only improves that row. A deployed multi-user Space sets
`ARENA_RANK_BY=user` to show one row per person instead, and `arena board --rank-by user`
does the same from the command line.

An entry is scored as the **mean finish time over five perturbed starts**, with
any failure to finish counted at the event's time limit — so a policy that is
quick four times and falls once ranks below a steady one. The replay you watch is
the median finishing run, not the best.

Two things about the shipped reference policy are worth knowing before reading
too much into a time: it tracks about 44% of its commanded velocity, and below
roughly 0.2 m/s commanded it does not walk at all. Both are measured; see the
design doc's calibration table.

## Developing

```bash
uv run --extra dev pytest        # engine + API
cd app && npm test               # frontend units
cd app && npm run dev            # UI on :5173, proxying /api to :8000
```

`app/src/rig.js` and the vendored `app/public/robot/` assets come from
[the Microduck sandbox Space](https://huggingface.co/spaces/pollen-robotics/microduck-simulator)
at a pinned commit — see `arena/assets/PROVENANCE.md`. Re-vendoring can change
what a policy scores, so `RUNNER_VERSION` in `arena/constants.py` must be bumped
in the same commit.

## Design

- `docs/superpowers/specs/2026-09-03-microduck-arena-design.md` — the design and every decision behind it
- `docs/probe-results.md` — measured cost of an evaluation
