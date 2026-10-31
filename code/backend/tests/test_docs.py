"""Keeps the documentation's links into the code true. Run: .venv/bin/python -m pytest

A line link such as [`privacy_mask`](../code/backend/providers/base.py#L36-L41)
must point at an existing file, and the name in backticks (up to any bracket)
must still be on those lines. Fix the link in the commit that moves the code.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
DOCS = [ROOT / "readme.md", ROOT / "AGENTS.md", *sorted((ROOT / "documentation").glob("*.md"))]
# [label](target#L12-L20); other anchors such as #heading are allowed but not checked.
LINK = re.compile(r"\[([^\]\n]*)\]\(([^)#\s]+)(?:#L(\d+)(?:-L(\d+))?|#[^)\s]*)?\)")


def local_links():
    for doc in DOCS:
        text = re.sub(r"```.*?```", "", doc.read_text(), flags=re.S)  # code blocks hold no links
        for label, target, start, end in LINK.findall(text):
            if not re.match(r"[a-z]+:", target):  # https:, mailto: and the like
                anchor = f"#L{start}" if start else ""
                yield pytest.param(doc, label, target, start, end, id=f"{doc.name}:{target}{anchor}")


@pytest.mark.parametrize("doc, label, target, start, end", list(local_links()))
def test_link_points_at_code(doc, label, target, start, end):
    path = (doc.parent / target).resolve()
    assert path.exists(), f"{doc.name} links to {target}, which does not exist"
    if start:
        lines = path.read_text().splitlines()[int(start) - 1:int(end or start)]
        assert lines, f"{doc.name} links to line {start} of {target}, which is shorter"
        name = re.match(r"`([^`(]+)", label)
        if name:
            where = f"{target}#L{start}-L{end or start}"
            assert name.group(1) in "\n".join(lines), f"{doc.name}: `{name.group(1)}` is no longer on {where}"
