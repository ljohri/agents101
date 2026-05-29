"""Memory persistence: global + local files and in-process session memory."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from root_agent.settings import expand_path

Tier = str  # "global" | "local" | "session"


class MemoryStore:
    """Reads/writes the three memory tiers.

    Global and local memory are Markdown files (like Claude's memory files);
    session memory is kept in process, keyed by conversation id, and is lost on
    restart.
    """

    def __init__(self, global_path: str, local_path: str, *, enable_session: bool = True) -> None:
        self.global_path = Path(expand_path(global_path) or global_path)
        self.local_path = Path(expand_path(local_path) or local_path)
        self.enable_session = enable_session
        self._sessions: dict[str, list[str]] = {}

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text().strip()
        except FileNotFoundError:
            return ""

    def load_global(self) -> str:
        return self._read(self.global_path)

    def load_local(self) -> str:
        return self._read(self.local_path)

    def session(self, conversation_id: str | None) -> str:
        if not (self.enable_session and conversation_id):
            return ""
        return "\n".join(self._sessions.get(conversation_id, []))

    def tiers_loaded(self) -> dict[str, bool]:
        return {
            "global": self.global_path.exists(),
            "local": self.local_path.exists(),
            "session": self.enable_session,
        }

    def append(self, tier: Tier, note: str, *, conversation_id: str | None = None) -> None:
        """Append a memory note to the given tier."""
        note = note.strip()
        if not note:
            return
        stamped = f"- ({datetime.now(UTC).date().isoformat()}) {note}"
        if tier == "global":
            self._append_file(self.global_path, stamped)
        elif tier == "local":
            self._append_file(self.local_path, stamped)
        elif tier == "session":
            if not (self.enable_session and conversation_id):
                return
            self._sessions.setdefault(conversation_id, []).append(stamped)
        else:
            raise ValueError(f"unknown memory tier {tier!r}")

    @staticmethod
    def _append_file(path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        prefix = "" if not path.exists() or not path.read_text().strip() else "\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(prefix + line + "\n")
