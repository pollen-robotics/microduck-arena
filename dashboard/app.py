"""Pollen's private dashboard of how the Microduck Arena is used.

Serves one page, built from two shallow clones kept up to date: the run log (who published and
voted) and the usage log (what the Arena's pages report, arena/usage.py). A clone, not the Hub
API: the run log holds thousands of small files, which git fetches in one pack in seconds and the
API one request at a time in minutes.
"""

import json
import os
import subprocess
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from stats import build, load

DATASETS = {
    "runs": os.environ.get("ARENA_DATASET", "pollen-robotics/microduck-arena-runs"),
    "usage": os.environ.get("ARENA_USAGE_DATASET", "pollen-robotics/microduck-arena-usage"),
}
DATA = Path(os.environ.get("DASHBOARD_DATA", "/tmp/dashboard"))
FRESH_S = 600
PAGE = Path(__file__).with_name("page.html")

_lock = threading.Lock()
_built = {"at": 0.0, "html": b""}


def sync(repo: str, folder: Path) -> None:
    """Clone `repo` at its tip, or move an existing clone to the new tip.

    LFS files (traces, clips: gigabytes) stay pointers wherever git-lfs is installed."""
    def git(*args: str) -> None:
        subprocess.run(["git", *args], check=True, env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"})

    if not (folder / ".git").is_dir():
        git("clone", "-q", "--depth", "1",
            f"https://user:{os.environ['HF_TOKEN']}@huggingface.co/datasets/{repo}", str(folder))
        return
    git("-C", str(folder), "fetch", "-q", "--depth", "1", "origin")
    git("-C", str(folder), "reset", "-q", "--hard", "FETCH_HEAD")


def page() -> bytes:
    """The page, rebuilt from fresh data at most every FRESH_S seconds."""
    with _lock:
        if time.time() - _built["at"] > FRESH_S:
            for name, repo in DATASETS.items():
                sync(repo, DATA / name)
            stats = build(*load(DATA / "runs", DATA / "usage"), datetime.now(UTC).date())
            stats["built_at"] = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
            # Closing tags inside the JSON must not close the page's script.
            data = json.dumps(stats).replace("</", "<\\/")
            _built.update(at=time.time(), html=PAGE.read_text().replace("/*STATS*/null", data).encode())
        return _built["html"]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?")[0] != "/":
            self.send_error(404)
            return
        body = page()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "7860"))), Handler).serve_forever()
