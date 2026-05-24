"""Doc-drift invariant.

Per docs/architecture/00-overview.md sec 8 (design principles) and
docs/build-plan.md sec 9.8: every fenced code block in docs/ whose info-string
contains a ``file=<path>`` token must equal the contents of the referenced
file (relative to the repo root). Blocks without ``file=<path>`` are ignored.

This makes "docs cite real files" a checked CI invariant, not a wish.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_GLOBS = ["docs/build-plan.md", "docs/architecture/*.md"]

_FENCE_RE = re.compile(
    r"^(?P<fence>```+|~~~+)(?P<info>[^\n]*)\n(?P<body>.*?)(?P=fence)\s*$",
    re.MULTILINE | re.DOTALL,
)
_FILE_TAG_RE = re.compile(r"(?:^|\s)file=(?P<path>\S+)")


def _iter_doc_files() -> list[Path]:
    files: list[Path] = []
    for pattern in DOC_GLOBS:
        files.extend(sorted(REPO_ROOT.glob(pattern)))
    return files


def _iter_tagged_blocks(doc: Path):
    text = doc.read_text()
    for match in _FENCE_RE.finditer(text):
        info = match.group("info")
        tag = _FILE_TAG_RE.search(info)
        if not tag:
            continue
        body = match.group("body")
        # Strip exactly one trailing newline added by markdown rendering, if any.
        if body.endswith("\n"):
            body = body[:-1]
        yield tag.group("path"), body, match.start()


def _collect() -> list[tuple[Path, str, str, int]]:
    rows: list[tuple[Path, str, str, int]] = []
    for doc in _iter_doc_files():
        for path, body, offset in _iter_tagged_blocks(doc):
            rows.append((doc, path, body, offset))
    return rows


@pytest.mark.parametrize(
    "doc,path,body,offset",
    _collect(),
    ids=lambda v: v.name if isinstance(v, Path) else str(v),
)
def test_doc_snippet_matches_file(
    doc: Path, path: str, body: str, offset: int
) -> None:
    target = REPO_ROOT / path
    assert target.exists(), f"{doc.name}: file=<{path}> does not exist"
    on_disk = target.read_text()
    # Both ends normalized to no trailing newline for comparison.
    if on_disk.endswith("\n"):
        on_disk_cmp = on_disk[:-1]
    else:
        on_disk_cmp = on_disk
    assert body == on_disk_cmp, (
        f"{doc.name} (offset {offset}) declares file={path!r} but the fenced "
        f"block does not match the on-disk file. Update the doc snippet to "
        f"match the file, or update the file to match the doc."
    )


def test_at_least_one_tagged_block_exists() -> None:
    """Guard against a regex change silently disabling the invariant."""
    assert _collect(), "no file=<path> tagged blocks found across docs"
