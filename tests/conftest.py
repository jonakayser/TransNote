from __future__ import annotations

import os
import stat
import textwrap
from pathlib import Path

import pytest


def make_score(path: Path, notes: list[tuple[str, float]], time_sig: str = "4/4", sharps: int = -2,
               fill_bars: bool = True) -> Path:
    """Write a single-line score. ``notes`` is a list of (pitch or 'r', quarterLength)."""
    from music21 import key, meter, note, stream

    part = stream.Part()
    part.append(meter.TimeSignature(time_sig))
    part.append(key.KeySignature(sharps))
    for p, ql in notes:
        part.append(note.Rest(quarterLength=ql) if p == "r" else note.Note(p, quarterLength=ql))
    score = stream.Score([part])
    made = score.makeNotation() if fill_bars else score
    made.write("musicxml", fp=str(path))
    return path


MELODY = [("B-4", 1), ("C5", 1), ("D5", 2), ("r", 1), ("E-5", 1), ("F5", 2),
          ("D5", 1), ("C5", 1), ("B-4", 2), ("r", 4)]


@pytest.fixture
def melody(tmp_path) -> Path:
    return make_score(tmp_path / "truth.musicxml", MELODY)


@pytest.fixture
def fake_tool(tmp_path):
    """Create an executable shell script and return its path."""

    def _make(name: str, body: str) -> Path:
        path = tmp_path / "bin" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\nset -e\n" + textwrap.dedent(body))
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
        return path

    return _make
