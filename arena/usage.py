"""How the Arena is used: page views, links that leave the site, time looked at.

The page reports each hit (app/src/usage.js); routes_usage.py checks it and
hands it here. Nothing here names anyone: a visitor is a random id its browser
keeps, and a signed-in visitor is only "signed in". Pollen's private dashboard
(dashboard/) reads what is written.

Hits are held in memory and written out as one file per batch, every few
minutes, to a dataset of their own (ARENA_USAGE_DATASET): a commit per hit
would be thousands a day, and in the run log's dataset each would set the
store refreshing. A crash loses the batch in hand, which is fine for counting
visits; a restart writes it first.
"""

import json
import threading
from collections.abc import Callable
from pathlib import Path

from .store import new_id

FLUSH_EVERY_S = 600.0
# The most hits held at once. Anyone can post them, so a flood is dropped
# rather than kept in memory.
MAX_HELD = 50_000


class UsageLog:
    def __init__(self, write: Callable[[str, bytes], None], every_s: float = FLUSH_EVERY_S):
        self._write = write
        self._every_s = every_s
        self._held: list[dict] = []
        self._lock = threading.Lock()
        self._stopped = threading.Event()

    def record(self, hit: dict) -> None:
        with self._lock:
            if len(self._held) < MAX_HELD:
                self._held.append(hit)

    def flush(self) -> None:
        """Write the hits in hand as one file. A failed write keeps them for the next one."""
        with self._lock:
            batch, self._held = self._held, []
        if not batch:
            return
        path = f"usage/{batch[0]['at'][:10]}/{new_id()}.jsonl"
        try:
            self._write(path, "".join(json.dumps(hit) + "\n" for hit in batch).encode())
        except Exception as exc:  # noqa: BLE001 — a lost count must never take the arena down
            print(f"usage: writing {len(batch)} hit(s) failed ({type(exc).__name__}: {exc})")
            with self._lock:
                self._held = (batch + self._held)[:MAX_HELD]

    def start(self) -> None:
        threading.Thread(target=self._run, name="arena-usage", daemon=True).start()

    def _run(self) -> None:
        while not self._stopped.wait(self._every_s):
            self.flush()

    def stop(self) -> None:
        self._stopped.set()
        self.flush()


def to_hub(repo_id: str, token: str) -> Callable[[str, bytes], None]:
    from huggingface_hub import HfApi

    api = HfApi(token=token)

    def write(path: str, data: bytes) -> None:
        api.upload_file(path_or_fileobj=data, path_in_repo=path, repo_id=repo_id,
                        repo_type="dataset", commit_message=f"Usage {path}")

    return write


def to_folder(root: Path) -> Callable[[str, bytes], None]:
    def write(path: str, data: bytes) -> None:
        target = Path(root) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    return write
