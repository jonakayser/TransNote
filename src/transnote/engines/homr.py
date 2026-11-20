"""homr — deep-learning OMR built for camera photos (https://github.com/liebharc/homr).

Installed as a separate command-line tool (``uv tool install 'homr[cpu]'``), so its
dependencies and its AGPL licence stay separate from TransNote.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .base import Engine, EngineError, copy_inputs, find_musicxml
from ..merge import merge_scores


class HomrEngine(Engine):
    name = "homr"
    env_var = "TRANSNOTE_HOMR"

    def __init__(self, executable=None, timeout=None, detect_title: bool = False):
        super().__init__(executable, timeout)
        self.detect_title = detect_title

    def candidates(self) -> list[Path]:
        found = shutil.which("homr")
        return [p for p in (Path(found) if found else None, Path.home() / ".local/bin/homr") if p]

    def _recognize(self, inputs: list[Path], work_dir: Path) -> tuple[Path, str]:
        exe = self.require_executable()
        in_dir = work_dir / "homr-input"
        if in_dir.exists():
            shutil.rmtree(in_dir)
        copies = copy_inputs(inputs, in_dir)

        cmd = [str(exe)]
        if not self.detect_title:
            cmd.append("--no-title")
        # Several files given at once are merged by homr into one score.
        cmd += [str(p) for p in copies]
        log = self._run(cmd, cwd=in_dir)

        outputs = find_musicxml(in_dir)
        if not outputs:
            raise EngineError(f"homr finished but wrote no MusicXML.\n{log[-2000:]}")
        result = work_dir / "homr.musicxml"
        merge_scores(outputs, result)
        return result, log
