#!/usr/bin/env python
"""Publish this working tree to the Hugging Face Space.

Not `git push`. The Hub rejects binary files pushed through plain git — "Please
use Xet to store binary files" — and this repo vendors a 1.3 MB GLB, forty-odd
STLs and an ONNX policy. `upload_folder` speaks Xet natively, so the same call
that uploads the code uploads the meshes.

Only the tip of the tree is published, not the history. A Space is a deployment
target; the history lives in this repo.

    uv run python scripts/deploy_space.py
    uv run python scripts/deploy_space.py --dry-run
"""

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

from huggingface_hub import HfApi

SPACE = "pollen-robotics/microduck-arena"
ROOT = Path(__file__).resolve().parent.parent

# What never belongs in the image or the repo. app/dist and arena/frontend
# especially: the Dockerfile builds and bundles the site itself, and a stale
# host copy would be served in preference to nothing.
IGNORE = [
    ".git/**",
    ".venv/**",
    "**/node_modules/**",
    "app/dist/**",
    "arena/frontend/**",
    "**/__pycache__/**",
    "*.pyc",
    ".pytest_cache/**",
    ".ruff_cache/**",
    "arena-board/**",
    # Pollen's private dashboard is its own Space (.github/workflows/deploy-dashboard.yml).
    "dashboard/**",
]
# .dockerignore is NOT here on purpose: the Space builds the image, so it needs
# the file that tells the build what to leave out.


def git_revision() -> str:
    try:
        rev = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{rev}{'-dirty' if dirty else ''}"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def served_as_pointers(kept_in_lfs: list[str], attributes: str) -> list[str]:
    """The files the Space would serve as 131-byte LFS pointers instead of themselves.

    The Hub decides by itself to keep a large binary in LFS, whatever this
    repository does with it; the Space's build only turns a pointer back into its
    file where .gitattributes says LFS. A file on the first list and not under the
    second is checked out as its pointer, silently: the commentators' voices went
    out that way, and the booth's sound never opened.
    """
    rules = [line.split()[0] for line in attributes.splitlines() if "filter=lfs" in line.split()]
    return [path for path in kept_in_lfs
            if not any(fnmatch.fnmatch(path if "/" in rule else Path(path).name, rule)
                       for rule in rules)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--space", default=SPACE)
    parser.add_argument("--dry-run", action="store_true", help="list what would go, upload nothing")
    args = parser.parse_args()

    revision = git_revision()
    if revision.endswith("-dirty"):
        # A warning, not a refusal: deploying a work in progress by hand is a
        # normal thing to want. But the commit message should say so,
        # or nobody can tell later what is actually running.
        print("warning: working tree has uncommitted changes; they WILL be deployed")

    api = HfApi()
    if args.dry_run:
        print(f"would upload {ROOT} to {args.space}")
        print("ignoring:")
        for pattern in IGNORE:
            print(f"  {pattern}")
        return 0

    print(f"uploading {ROOT} -> {args.space} ({revision})")
    api.upload_folder(
        folder_path=str(ROOT),
        repo_id=args.space,
        repo_type="space",
        ignore_patterns=IGNORE,
        # Without this, upload_folder only ADDS and UPDATES: a file deleted or
        # renamed here lingers on the Space forever. Two renamed event manifests
        # is how this was found — the Space served nine events while the repo
        # held seven, and the two ghosts were raceable pages for events that no
        # longer existed.
        delete_patterns=["*"],
        commit_message=f"Deploy {revision}",
    )
    print(f"\n  https://huggingface.co/spaces/{args.space}")
    print("  the Space rebuilds itself now; watch its Logs tab")
    kept_in_lfs = [entry.path for entry in api.list_repo_tree(args.space, repo_type="space",
                                                              recursive=True)
                   if getattr(entry, "lfs", None)]
    pointers = served_as_pointers(kept_in_lfs, (ROOT / ".gitattributes").read_text())
    if pointers:
        # The upload has happened; what is left is to make it loud, so the deploy
        # goes red instead of a page failing quietly a week later.
        print("\nerror: the Hub keeps these in LFS and .gitattributes has no LFS rule for them,"
              "\nso the Space serves their pointers, not the files:", file=sys.stderr)
        for path in pointers:
            print(f"  {path}", file=sys.stderr)
        print("give each one a rule in .gitattributes, as microduck.glb has, and"
              " `git add --renormalize` it", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
