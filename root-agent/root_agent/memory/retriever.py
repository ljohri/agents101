"""Build a relevant, budget-bounded MemoryContext for a request.

v1 retrieval is intentionally simple: keep the most specific tiers first
(session > local > global) and, when over budget, score individual lines by
keyword overlap with the request. The interface is stable so an embedding or
LLM-based retriever can replace the internals later without touching callers.
"""

from __future__ import annotations

import re

from root_agent.memory.schema import MemoryContext
from root_agent.memory.store import MemoryStore

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


class MemoryRetriever:
    def __init__(self, store: MemoryStore, *, max_chars: int = 4000) -> None:
        self.store = store
        self.max_chars = max_chars

    def build_context(self, request: str, conversation_id: str | None = None) -> MemoryContext:
        global_text = self.store.load_global()
        local_text = self.store.load_local()
        session_text = self.store.session(conversation_id)

        merged = self._merge(request, global_text, local_text, session_text)
        return MemoryContext(
            global_text=global_text,
            local_text=local_text,
            session_text=session_text,
            merged=merged,
        )

    def _merge(self, request: str, global_text: str, local_text: str, session_text: str) -> str:
        # Highest-precedence tiers first so they survive truncation.
        sections: list[tuple[str, str]] = []
        if session_text:
            sections.append(("Session memory", session_text))
        if local_text:
            sections.append(("Local memory", local_text))
        if global_text:
            sections.append(("Global memory", global_text))
        if not sections:
            return ""

        blocks = [f"## {title}\n{body}" for title, body in sections]
        merged = "\n\n".join(blocks)
        if len(merged) <= self.max_chars:
            return merged

        # Over budget: keep request-relevant lines, preserving tier order.
        return self._filter_relevant(request, sections)

    def _filter_relevant(self, request: str, sections: list[tuple[str, str]]) -> str:
        want = _tokens(request)
        out: list[str] = []
        budget = self.max_chars
        for title, body in sections:
            kept: list[str] = []
            # Rank lines by keyword overlap; ties keep original order.
            lines = [ln for ln in body.splitlines() if ln.strip()]
            ranked = sorted(lines, key=lambda ln: len(_tokens(ln) & want), reverse=True)
            for line in ranked:
                if budget - len(line) <= 0:
                    break
                kept.append(line)
                budget -= len(line) + 1
            if kept:
                # Restore original order for readability.
                kept_set = set(kept)
                ordered = [ln for ln in lines if ln in kept_set]
                out.append(f"## {title}\n" + "\n".join(ordered))
            if budget <= 0:
                break
        return "\n\n".join(out)
