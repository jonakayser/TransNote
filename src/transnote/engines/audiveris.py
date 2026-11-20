"""Audiveris — mature classic OMR, strong on clean scans (https://github.com/Audiveris/audiveris).

Runs in batch mode: ``Audiveris -batch -export -output DIR -- FILE...``
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from .base import Engine, EngineError, copy_inputs, find_musicxml
from ..merge import merge_scores


def _natural_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


class AudiverisEngine(Engine):
    name = "audiveris"
    env_var = "TRANSNOTE_AUDIVERIS"

    def candidates(self) -> list[Path]:
        paths = [
            Path("/Applications/Audiveris.app/Contents/MacOS/Audiveris"),
            Path.home() / "Applications/Audiveris.app/Contents/MacOS/Audiveris",
            Path("/opt/audiveris/bin/Audiveris"),
        ]
        for name in ("Audiveris", "audiveris"):
            found = shutil.which(name)
            if found:
                paths.append(Path(found))
        return paths

    def _env(self) -> dict[str, str]:
        if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
            opts = os.environ.get("JAVA_TOOL_OPTIONS", "")
            return {"JAVA_TOOL_OPTIONS": f"{opts} -Djava.awt.headless=true".strip()}
        return {}

    def version(self) -> str | None:
        exe = self.find_executable()
        if not exe:
            return None
        try:
            out = subprocess.run(
                [str(exe), "-batch", "-version"], capture_output=True, text=True, timeout=120,
                env={**os.environ, **self._env()},
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        match = re.search(r"\b(\d+\.\d+(?:\.\d+)?)\b", out.stdout + out.stderr)
        return match.group(1) if match else None

    def _recognize(self, inputs: list[Path], work_dir: Path) -> tuple[Path, str]:
        exe = self.require_executable()
        in_dir = work_dir / "audiveris-input"
        out_dir = work_dir / "audiveris-output"
        for d in (in_dir, out_dir):
            if d.exists():
                shutil.rmtree(d)
        out_dir.mkdir(parents=True)
        copies = copy_inputs(inputs, in_dir)

        cmd = [str(exe), "-batch", "-export", "-output", str(out_dir), "--", *map(str, copies)]
        log = self._run(cmd, cwd=work_dir, env=self._env())

        # Each input is its own "book"; a book may be split into movements
        # (name.mvt1.mxl, name.mvt2.mxl, ...). Keep input order, then movement order.
        all_outputs = find_musicxml(out_dir)
        ordered: list[Path] = []
        for copy in copies:
            mine = [p for p in all_outputs if p.name.startswith(copy.stem + ".") or p.stem == copy.stem]
            ordered += sorted(mine, key=_natural_key)
        if not ordered:
            ordered = sorted(all_outputs, key=_natural_key)
        if not ordered:
            raise EngineError(f"Audiveris finished but exported no MusicXML.\n{log[-2000:]}")

        result = work_dir / "audiveris.musicxml"
        merge_scores(ordered, result)
        return result, log
