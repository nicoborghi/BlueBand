"""Durable JSON storage for a competition.

Layout under the competition root:

    <root>/
      programme.yaml
      entries_import.json      entries_overlay.json
      comunicati.json
      races/<race_id>.json
      out/<NNN>_<CAT>_<specialita>_<fase>_<batteria>.pdf
      .snapshots/<relpath>/<ts>.json     previous content of every overwrite
      journal.jsonl                      append-only log of every write

Every write is atomic (tmp file + os.replace) and keeps the previous content as
a snapshot, so nothing typed by the jury can be lost by a crash, a bad edit or
a browser reload.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import RaceState, race_id as make_race_id

SNAP_DIR = ".snapshots"
JOURNAL = "journal.jsonl"
SETTINGS = "settings.json"
DEFAULT_OUT = "out"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ts() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S%f")[:-3]


# ── Store ───────────────────────────────────────────────────────────────────

class Store:
    """File-backed store rooted at one competition folder."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "races").mkdir(exist_ok=True)
        (self.root / "out").mkdir(exist_ok=True)
        (self.root / SNAP_DIR).mkdir(exist_ok=True)

    # -- raw json ------------------------------------------------------------

    def path(self, rel: str | Path) -> Path:
        return self.root / rel

    def exists(self, rel: str | Path) -> bool:
        return self.path(rel).exists()

    def read_json(self, rel: str | Path, default: Any = None) -> Any:
        p = self.path(rel)
        if not p.exists():
            return default
        with p.open(encoding="utf-8") as fh:
            return json.load(fh)

    def write_json(self, rel: str | Path, data: Any, *, action: str = "write",
                   snapshot: bool = True, actor: str = "") -> Path:
        """Atomically write `data` as JSON, snapshotting the previous content."""
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        if snapshot and p.exists():
            self._snapshot(rel)
        tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1, default=str)
        os.replace(tmp, p)
        self.journal(action=action, target=str(rel), actor=actor)
        return p

    def write_text(self, rel: str | Path, text: str, *, action: str = "render",
                   snapshot: bool = False, actor: str = "") -> Path:
        """Atomically write text. `snapshot` keeps the previous content aside.

        Off by default because most of what goes through here is a rendered
        document, which is produced again from the race whenever it is wanted.
        The programme is the other case: it is *the* source, and overwriting a
        good one is exactly what `.snapshots/` exists for.
        """
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        if snapshot and p.exists():
            self._snapshot(rel)
        tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, p)
        self.journal(action=action, target=str(rel), actor=actor)
        return p

    # -- settings ------------------------------------------------------------

    @property
    def settings(self) -> dict:
        """Per-machine settings (output folder, ...) - not part of the programme."""
        return self.read_json(SETTINGS, {}) or {}

    def set_setting(self, key: str, value, *, actor: str = "") -> None:
        data = self.settings
        if value in (None, ""):
            data.pop(key, None)
        else:
            data[key] = value
        self.write_json(SETTINGS, data, action=f"set_{key}", actor=actor)

    @property
    def out_dir(self) -> Path:
        """Where comunicati are written. Defaults to `<competition>/out`.

        May point anywhere the user likes - a Drive folder, a USB stick - so it
        is stored as an absolute path and created on demand.
        """
        raw = self.settings.get("out_dir")
        return Path(raw).expanduser() if raw else self.root / DEFAULT_OUT

    def set_out_dir(self, path: str | Path | None, *, actor: str = "") -> Path:
        """Set (or reset, with None) the output folder. Returns the new one."""
        value = "" if not path else str(Path(path).expanduser())
        if value and Path(value) == self.root / DEFAULT_OUT:
            value = ""                       # the default, stored as unset
        self.set_setting("out_dir", value, actor=actor)
        return self.out_dir

    def write_out(self, name: str, data: bytes | str, *,
                  action: str = "archive_document", actor: str = "") -> Path:
        """Write a produced document into the output folder."""
        d = self.out_dir
        d.mkdir(parents=True, exist_ok=True)
        p = d / name
        tmp = p.with_suffix(p.suffix + f".tmp{os.getpid()}")
        if isinstance(data, bytes):
            tmp.write_bytes(data)
        else:
            tmp.write_text(data, encoding="utf-8")
        os.replace(tmp, p)
        self.journal(action=action, target=str(p), actor=actor)
        return p

    # -- races ---------------------------------------------------------------

    def race_rel(self, rid: str) -> str:
        return f"races/{rid}.json"

    def load_race(self, rid: str) -> RaceState | None:
        d = self.read_json(self.race_rel(rid))
        return RaceState.from_dict(d) if d else None

    def get_race(self, cat: str, event: str, round_key: str = "",
                 fmt: str = "") -> RaceState:
        """Load a race, or create an empty one (not yet written to disk)."""
        rid = make_race_id(cat, event, round_key)
        st = self.load_race(rid)
        if st is None:
            st = RaceState(race_id=rid, cat=cat, event=event,
                           round_key=round_key, fmt=fmt, created_at=now_iso())
        elif fmt and not st.fmt:
            st.fmt = fmt
        return st

    def save_race(self, state: RaceState, *, action: str = "save_race",
                  actor: str = "") -> Path:
        state.updated_at = now_iso()
        if not state.created_at:
            state.created_at = state.updated_at
        return self.write_json(self.race_rel(state.race_id), state.to_dict(),
                               action=action, actor=actor)

    def list_races(self) -> list[str]:
        return sorted(p.stem for p in (self.root / "races").glob("*.json"))

    def recent_races(self, n: int = 6) -> list[RaceState]:
        """The races last saved, most recent first.

        Read off the file times rather than the states themselves: it is one
        `stat` per race instead of parsing every file on the disk, and a race
        is written exactly when it is worked on. Only the last few are read.

        Two races written inside the same clock tick cannot be told apart by
        their time - it happens when a batch is composed, and on a filesystem
        that keeps whole seconds it happens often. The name breaks the tie, so
        that the row of pills is at least the *same* row from one rerun to the
        next: a shortcut that reshuffles itself is not one.
        """
        files = sorted((self.root / "races").glob("*.json"),
                       key=lambda p: (p.stat().st_mtime_ns, p.name),
                       reverse=True)
        out = []
        for path in files[:max(0, n)]:
            state = self.load_race(path.stem)
            if state is not None:
                out.append(state)
        return out

    def delete_race(self, rid: str, *, actor: str = "") -> None:
        rel = self.race_rel(rid)
        if self.exists(rel):
            self._snapshot(rel)
            self.path(rel).unlink()
            self.journal(action="delete_race", target=rel, actor=actor)

    # -- snapshots / undo ----------------------------------------------------

    def _snapshot(self, rel: str | Path) -> Path:
        """Copy the current content aside. Never overwrites an older snapshot:
        two saves inside the same millisecond would otherwise collide and the
        earlier version would be lost."""
        src = self.path(rel)
        folder = self.root / SNAP_DIR / str(rel)
        folder.mkdir(parents=True, exist_ok=True)
        stamp = _ts()
        dst = folder / f"{stamp}{src.suffix}"
        n = 0
        while dst.exists():
            n += 1
            dst = folder / f"{stamp}-{n}{src.suffix}"
        shutil.copy2(src, dst)
        return dst

    def snapshots(self, rel: str | Path) -> list[Path]:
        """Snapshots of one file, newest first."""
        d = self.root / SNAP_DIR / str(rel)
        return sorted(d.glob("*"), reverse=True) if d.exists() else []

    def restore(self, rel: str | Path, snapshot: str | Path | None = None,
                *, actor: str = "") -> Path | None:
        """Restore a file from a snapshot (default: the most recent one)."""
        snaps = self.snapshots(rel)
        if not snaps:
            return None
        src = Path(snapshot) if snapshot else snaps[0]
        if not src.is_absolute():
            src = self.root / SNAP_DIR / str(rel) / src.name
        dst = self.path(rel)
        if dst.exists():
            self._snapshot(rel)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        self.journal(action="restore", target=str(rel), actor=actor,
                     extra={"from": src.name})
        return dst

    def backup(self, dest: str | Path | None = None) -> Path:
        """Full copy of the competition folder, snapshots excluded (off-site backup)."""
        dest = (Path(dest) if dest
                else self.root.parent / f"{self.root.name}_backup_{_ts()}")
        shutil.copytree(self.root, dest,
                        ignore=shutil.ignore_patterns(SNAP_DIR, "*.tmp*"))
        self.journal(action="backup", target=str(dest))
        return dest

    # -- journal -------------------------------------------------------------

    def journal(self, *, action: str, target: str = "", actor: str = "",
                extra: dict | None = None) -> None:
        rec = {"ts": now_iso(), "actor": actor or os.environ.get("USER", ""),
               "action": action, "target": target}
        if extra:
            rec.update(extra)
        with (self.root / JOURNAL).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    def read_journal(self, limit: int = 200) -> list[dict]:
        p = self.root / JOURNAL
        if not p.exists():
            return []
        lines = p.read_text(encoding="utf-8").splitlines()
        out = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out


# ── Competition roots ───────────────────────────────────────────────────────

def competitions_root() -> Path:
    """Base folder holding one subfolder per competition.

    `events/` is the name this folder had before the code adopted the UCI
    vocabulary (where an *event* is the Sprint or the Omnium, not the meeting);
    it is still honoured so an older data directory keeps working.
    """
    env = os.environ.get("COMMISSAIRE_TRACK_DATA")
    if env:
        return Path(env)
    here = Path(__file__).resolve().parent.parent
    legacy = here / "events"
    return legacy if legacy.is_dir() else here / "competitions"


def list_competitions() -> list[str]:
    root = competitions_root()
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith("."))


CURRENT = ".current_competition"


def current_competition() -> str:
    """The competition chosen in Impostazioni. Chosen once, kept across sessions."""
    competitions = list_competitions()
    p = competitions_root() / CURRENT
    if p.exists():
        name = p.read_text(encoding="utf-8").strip()
        if name in competitions:
            return name
    return competitions[0] if competitions else ""


def set_current_competition(name: str) -> str:
    (competitions_root() / CURRENT).write_text(name, encoding="utf-8")
    return name


def open_competition(name: str) -> Store:
    return Store(competitions_root() / name)
