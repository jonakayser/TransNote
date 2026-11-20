"""Common interface for OMR engines."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


class EngineError(RuntimeError):
    """The engine ran but failed, or produced no MusicXML."""


class EngineNotFound(EngineError):
    """The engine is not installed (or could not be located)."""


@dataclass
class EngineResult:
    engine: str
    inputs: list[Path]
    musicxml: Path
    seconds: float
    log: str = ""


class Engine(ABC):
    #: Short name used on the command line, e.g. "homr".
    name: str = ""
    #: Environment variable that can point to the executable.
    env_var: str = ""
    #: Default timeout per run, in seconds.
    timeout: float = 1800

    def __init__(self, executable: Path | str | None = None, timeout: float | None = None):
        self._executable = Path(executable) if executable else None
        if timeout is not None:
            self.timeout = timeout

    # --- discovery -----------------------------------------------------------------
    def candidates(self) -> list[Path]:
        """Places to look for the executable, most specific first."""
        return []

    def find_executable(self) -> Path | None:
        if self._executable:
            return self._executable if self._executable.exists() else None
        env = os.environ.get(self.env_var) if self.env_var else None
        if env:
            return Path(env) if Path(env).exists() else None
        for candidate in self.candidates():
            if candidate and candidate.exists():
                return candidate
        return None

    def require_executable(self) -> Path:
        exe = self.find_executable()
        if exe is None:
            hint = f" (or set {self.env_var})" if self.env_var else ""
            raise EngineNotFound(f"{self.name} is not installed{hint}. Run scripts/setup-mac.sh.")
        return exe

    def is_available(self) -> bool:
        return self.find_executable() is not None

    def version(self) -> str | None:
        return None

    # --- recognition ---------------------------------------------------------------
    def recognize(self, inputs: Sequence[Path], work_dir: Path) -> EngineResult:
        """Recognise one piece (one or more pages, in order) into a single MusicXML file."""
        inputs = [Path(p).resolve() for p in inputs]
        if not inputs:
            raise ValueError("No input files given")
        for p in inputs:
            if not p.exists():
                raise FileNotFoundError(p)
        work_dir = Path(work_dir).resolve()
        work_dir.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        musicxml, log = self._recognize(inputs, work_dir)
        return EngineResult(self.name, inputs, musicxml, time.perf_counter() - start, log)

    @abstractmethod
    def _recognize(self, inputs: list[Path], work_dir: Path) -> tuple[Path, str]:
        ...

    # --- helpers -------------------------------------------------------------------
    def _run(self, cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                env={**os.environ, **(env or {})},
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise EngineError(f"{self.name} timed out after {self.timeout:.0f}s") from e
        log = proc.stdout or ""
        if proc.returncode != 0:
            tail = "\n".join(log.strip().splitlines()[-15:])
            raise EngineError(f"{self.name} failed (exit code {proc.returncode}):\n{tail}")
        return log


def copy_inputs(inputs: Sequence[Path], dest: Path) -> list[Path]:
    """Copy inputs into ``dest`` (engines may write next to their input files)."""
    dest.mkdir(parents=True, exist_ok=True)
    copies = []
    for i, src in enumerate(inputs, 1):
        target = dest / (f"{i:02d}-{src.name}" if len(inputs) > 1 else src.name)
        shutil.copyfile(src, target)
        copies.append(target)
    return copies


def find_musicxml(folder: Path, exclude: Sequence[Path] = ()) -> list[Path]:
    """All MusicXML files under ``folder``, sorted by name."""
    excluded = {Path(p).resolve() for p in exclude}
    found = [
        p for p in folder.rglob("*")
        if p.suffix.lower() in (".musicxml", ".mxl", ".xml") and p.resolve() not in excluded
        and not p.name.startswith(".")
    ]
    return sorted(found)
