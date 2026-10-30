# Sock Heist E — the release — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Every task here
> starts with a stop for the owner's yes. This plan is run in the main session, never by a subagent.

**Goal:** Ship Sock Heist through the contributor's PR #3. Their commits stay as they are in `main`,
the Arena gets a new minor version with its wheel, microduck-challenges gets the new folder, and the
trained reference is published.

**Architecture:** Our commits are pushed to the contributor's branch, so #3 shows the whole Sock
Heist. The PR is retitled and redescribed, then merged with a merge commit. A push to `main` ships
the Space, so the merge is the deploy. Then come a version tag (its workflow attaches the wheel),
the challenges relock, and the reference.

**Tech Stack:** git, `gh`, `hf`, uv.

**Spec:** `docs/superpowers/specs/2026-10-27-sock-heist-design.md` ("Release", "Anti-goals": closing or
replacing the contributor's PR). **Contract:** `docs/superpowers/plans/2026-10-28-sock-heist-interfaces.md`.

## Global Constraints

- Each task's first step asks the owner for a yes, and nothing in it runs without one. A yes for one
  task never covers the next.
- Never close #3, never squash or rebase it, never force-push the contributor's branch.
- No assistant signature anywhere: commits, PR title, PR description, release notes. English only.
- GitHub notifies anyone named with `@`: name the contributor `@jrubiosainz` once in the PR
  description (credit), nowhere else.
- `/usr/bin/git` in the worktree. `uv run --frozen` in the Arena; the relock in microduck-challenges
  follows its own README.

## Review Focus

1. **LFS objects refused on the contributor's fork.** The new GLBs and the card are LFS objects, and
   a maintainer's push to a fork may not be able to upload them. `git lfs` uploads before the ref
   moves, so a refusal leaves nothing half-pushed. Task 2 says what to do then.
2. **`main` moved since our last merge:** Task 1 merges `origin/main` in again, with a merge, before
   the push.
3. **A Space deploy that fails on a binary without an LFS rule** (it happened once with a PNG):
   Task 1 checks that every new binary is in `git lfs ls-files`.
4. **The challenges relocked on a wheel that does not exist yet:** Task 5 waits for the release's
   asset.
5. **The reference published before the event is live:** Task 6 comes after Task 4's deploy check.

---

### Task 1: Ready to push

- [ ] **Step 1: Ask the owner** whether to prepare the push. Plan D's reference must have cleared its
  bar on x86 by now, and the owner must have seen the event page and a clip locally.
- [ ] **Step 2:** `/usr/bin/git fetch origin` and `/usr/bin/git fetch jrubiosainz`. If `origin/main`
  moved, `/usr/bin/git merge origin/main` (a merge, never a rebase) and resolve. If
  `jrubiosainz/red-light-green-light` moved (the contributor pushed), merge it in too and tell the owner.
- [ ] **Step 3:** The full checks: pytest in batches covering the whole suite
  (`uv run --frozen --extra dev pytest -q`), `cd app && npx vitest run` (only the 4 known brightness
  failures), `npm run build`, `uv run --frozen ruff check .` (the 6 errors already on main, no new
  one).
- [ ] **Step 4:** `/usr/bin/git lfs ls-files` lists `app/public/venue/sock-nest.glb`,
  `app/public/venue/socks.glb` and `app/public/cards/sock-heist-6m.webp`, and no binary added since
  74104f6 is missing from it (`/usr/bin/git diff --stat 74104f6 --diff-filter=A`).
- [ ] **Step 5:** `/usr/bin/git log --format='%h %an %s' origin/main..HEAD` still shows the
  contributor's twelve commits by their author, unchanged hashes.

### Task 2: Push to the contributor's branch

- [ ] **Step 1: Ask the owner:** "Push N commits to jrubiosainz/red-light-green-light (PR #3)?"
- [ ] **Step 2:** `/usr/bin/git push jrubiosainz red-light-green-light` (no `--force`).
- [ ] **Step 3: If LFS is refused** on the fork, stop and bring the owner two ways forward:
  - ask the contributor to push the branch themselves from a bundle we send them;
  - push the same branch to `pollen-robotics/microduck-arena` and point a PR there that carries the
    contributor's commits, then close #3 as merged through it. This closes #3 by hand, so it needs the
    owner's explicit choice.
- [ ] **Step 4:** `gh pr view 3 --json commits --jq '.commits | length'` counts our commits too, and
  the PR's checks run. Wait for them and report.

### Task 3: The PR says Sock Heist

- [ ] **Step 1: Ask the owner** with the title and the description below, written out in full.
- [ ] **Step 2:** `gh pr edit 3 --title "6 m Sock Heist: red light, green light under a giant microduck"
  --body-file <scratchpad>/pr3.md`. The description covers:
  - the contributor's design and what of it stands: `[lights]`, caught as a fourth status, the
    heading hold, the float32 trace, the chase camera;
  - what Sock Heist changes: 6 m, the giant in its nest of socks, random timetables per seed, the
    collapse, five traces a run, the clip to the last lane, the trained reference and its numbers;
  - how to train for it (the challenges folder).

  No attribution or generated-by line: the owner's rule is no signature on GitHub.

### Task 4: Merge #3, which deploys

- [ ] **Step 1: Ask the owner:** "Merge #3 with a merge commit? This deploys the Space."
- [ ] **Step 2:** `gh pr merge 3 --merge` (never `--squash`, never `--rebase`).
- [ ] **Step 3:** Watch the Space build until it runs. The recipe is in the owner's notes
  ("Space deploys from GitHub main"). Then open the event page `/events/sock-heist-6m` on the Space
  and check that the giant, the nest and the socks are there and the board is empty.
- [ ] **Step 4:** Update the local `main` in the main checkout only if the owner says so. It holds
  someone's uncommitted work.

### Task 5: Version 0.7.0, the wheel, the challenges

- [ ] **Step 1: Ask the owner:** "Version 0.7.0, tag v0.7.0, relock microduck-challenges on it and push
  its sock-heist folder?"
- [ ] **Step 2:** On `main`: `version = "0.7.0"` in `pyproject.toml`, `uv lock`, then a commit in the
  style of bbddfe5: `Version 0.7.0: Sock Heist, a 6 m red light, green light under a giant microduck's
  eye, on five random timetables, with a trained reference`. Then `/usr/bin/git tag v0.7.0` and push
  `main` and the tag.
- [ ] **Step 3:** Wait until `gh release view v0.7.0 -R pollen-robotics/microduck-arena` lists
  `microduck_arena-0.7.0-py3-none-any.whl`.
- [ ] **Step 4:** In microduck-challenges, merge branch `sock-heist` into `main`. Relock the Arena wheel
  on the v0.7.0 GitHub URL, as challenges a3e0c0f did for v0.4.3. Run its tests, commit, push.

### Task 6: Publish the reference

- [ ] **Step 1: Ask the owner:** the repo name Plan D staged, the account it goes under, and whether to
  enter it on the board.
- [ ] **Step 2:** Publish it with the challenges' `publish`, as Plan D Task D5 staged it.
- [ ] **Step 3:** If entered, follow the run until its clip renders (HF clip job), then open the run
  page. Its score must equal Plan D's x86 number to the millisecond.
- [ ] **Step 4:** Update the owner's notes: the Sock Heist memory gets the release state.
