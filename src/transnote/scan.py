"""The everyday pipeline: pages → OMR → instrument tag → checked MusicXML."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .analysis import BarIssue, summarize
from .engines import Engine
from .instrument import Instrument
from .musicxml import read_tree, write_tree
from .instrument import tag_instrument


@dataclass
class ScanResult:
    output: Path
    engine: str
    seconds: float
    bar_issues: list[BarIssue]
    key_sharps: int | None
    time_signature: str | None
    measures: int


_PAGE_NUMBER = re.compile(r"^(?P<base>.*?)[\s_\-.]*\(?(?P<num>\d+)\)?$")


def _split_page(stem: str) -> tuple[str, int]:
    """'Image 2' → ('Image', 2), 'page-03' → ('page', 3), 'Image' → ('Image', 0)."""
    m = _PAGE_NUMBER.match(stem)
    if m and m.group("base"):
        return m.group("base"), int(m.group("num"))
    return stem, 0


def order_pages(inputs: Sequence[Path]) -> list[Path]:
    """Sort pages naturally: Image.jpeg, Image 2.jpeg, … 10 after 9, not after 1."""
    def key(p: Path):
        base, num = _split_page(p.stem)
        return base.casefold(), num, p.name.casefold()
    return sorted((Path(p) for p in inputs), key=key)


def default_output(inputs: Sequence[Path]) -> Path:
    first = Path(inputs[0])
    stem = first.stem
    if len(inputs) > 1:
        bases = {_split_page(Path(p).stem)[0].casefold() for p in inputs}
        if len(bases) == 1:
            stem = _split_page(stem)[0]  # page-1.jpg, page-2.jpg → page.musicxml
    return first.with_name(f"{stem}.musicxml")


def scan(
    inputs: Sequence[Path],
    engine: Engine,
    output: Path | None = None,
    instrument: Instrument | None = None,
    keep_work: Path | None = None,
) -> ScanResult:
    inputs = [Path(p) for p in inputs]
    output = Path(output) if output else default_output(inputs)

    work_ctx = None
    if keep_work:
        work_dir = Path(keep_work)
    else:
        work_ctx = tempfile.TemporaryDirectory(prefix="transnote-")
        work_dir = Path(work_ctx.name)
    try:
        result = engine.recognize(inputs, work_dir)
        tree = read_tree(result.musicxml)
        if instrument is not None:
            tag_instrument(tree, instrument)
        write_tree(tree, output)
    finally:
        if work_ctx is not None:
            work_ctx.cleanup()

    summary = summarize(output)
    return ScanResult(
        output=output,
        engine=engine.name,
        seconds=result.seconds,
        bar_issues=summary.bar_issues,
        key_sharps=summary.key_sharps,
        time_signature=summary.time_signature,
        measures=summary.measures,
    )


def find_musescore() -> Path | None:
    """Locate MuseScore Studio (newest version first)."""
    env = os.environ.get("TRANSNOTE_MUSESCORE")
    if env:
        return Path(env)
    if sys.platform == "darwin":
        apps = []
        for base in (Path("/Applications"), Path.home() / "Applications"):
            apps += list(base.glob("MuseScore*.app"))
        return sorted(apps, reverse=True)[0] if apps else None
    for name in ("mscore4portable", "mscore4", "musescore4", "mscore", "musescore"):
        found = shutil.which(name)
        if found:
            return Path(found)
    return None


def open_in_musescore(path: Path) -> None:
    musescore = find_musescore()
    if sys.platform == "darwin":
        cmd = ["open", "-a", str(musescore), str(path)] if musescore else ["open", str(path)]
    elif musescore:
        cmd = [str(musescore), str(path)]
    else:
        cmd = ["xdg-open", str(path)]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def describe_key(sharps: int | None) -> str:
    if sharps is None:
        return "no key signature"
    if sharps == 0:
        return "no sharps or flats (C major / A minor)"
    majors_sharp = ["C", "G", "D", "A", "E", "B", "F♯", "C♯"]
    majors_flat = ["C", "F", "B♭", "E♭", "A♭", "D♭", "G♭", "C♭"]
    n = abs(sharps)
    if n > 7:
        return f"{sharps:+d}"
    major = majors_sharp[n] if sharps > 0 else majors_flat[n]
    return f"{n} {'sharp' if sharps > 0 else 'flat'}{'s' if n > 1 else ''} ({major} major)"
