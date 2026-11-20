"""Benchmark: run every engine on every sample and score the results.

Sample layout (one folder per piece)::

    samples/
      my-piece/
        truth.musicxml        # hand-corrected ground truth (.musicxml/.mxl), optional
        photo.jpg             # one input "variant" ...
        scan.pdf              # ... and another
        photo2-1.jpg          # several pages of one variant: <variant>-<page>.<ext>
        photo2-2.jpg

Every variant is recognised by every engine and compared with ``truth``.
Without a truth file the run still happens; you just get the bar checks and timing.
"""

from __future__ import annotations

import csv
import json
import re
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

from .analysis import summarize
from .engines import Engine
from .evaluate import Evaluation, evaluate_summaries

INPUT_SUFFIXES = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".pdf", ".heic")
TRUTH_NAMES = ("truth.musicxml", "truth.mxl", "truth.xml")
_PAGE_RE = re.compile(r"^(?P<variant>.+?)-(?P<page>\d+)$")


@dataclass
class Sample:
    piece: str
    variant: str
    pages: list[Path]
    truth: Path | None

    @property
    def label(self) -> str:
        return f"{self.piece}/{self.variant}"


@dataclass
class RunResult:
    piece: str
    variant: str
    engine: str
    pages: int
    seconds: float | None = None
    output: str | None = None
    error: str | None = None
    evaluation: Evaluation | None = None
    bar_issues: list[str] = field(default_factory=list)

    def row(self) -> dict:
        row = {
            "piece": self.piece,
            "variant": self.variant,
            "engine": self.engine,
            "pages": self.pages,
            "seconds": round(self.seconds, 1) if self.seconds is not None else None,
            "output": self.output,
            "error": self.error,
            "bar_issues_detail": "; ".join(self.bar_issues),
        }
        if self.evaluation:
            row.update(self.evaluation.as_dict())
        return row


def discover_samples(root: Path) -> list[Sample]:
    root = Path(root)
    samples: list[Sample] = []
    for piece_dir in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        truth = next((piece_dir / n for n in TRUTH_NAMES if (piece_dir / n).exists()), None)
        variants: dict[str, list[tuple[int, Path]]] = {}
        for f in sorted(piece_dir.iterdir()):
            if f.suffix.lower() not in INPUT_SUFFIXES or f.name.startswith("."):
                continue
            match = _PAGE_RE.match(f.stem)
            variant, page = (match["variant"], int(match["page"])) if match else (f.stem, 0)
            variants.setdefault(variant, []).append((page, f))
        for variant, pages in sorted(variants.items()):
            samples.append(Sample(piece_dir.name, variant, [p for _, p in sorted(pages)], truth))
    return samples


def run_benchmark(
    samples: Iterable[Sample],
    engines: Iterable[Engine],
    out_dir: Path,
    progress: Callable[[str], None] = print,
) -> list[RunResult]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    engines = list(engines)
    truth_cache: dict[Path, object] = {}
    results: list[RunResult] = []

    for sample in samples:
        truth = None
        if sample.truth is not None:
            if sample.truth not in truth_cache:
                truth_cache[sample.truth] = summarize(sample.truth)
            truth = truth_cache[sample.truth]

        for engine in engines:
            progress(f"→ {sample.label} with {engine.name} ({len(sample.pages)} page(s))")
            run = RunResult(sample.piece, sample.variant, engine.name, len(sample.pages))
            work = out_dir / "work" / sample.piece / sample.variant / engine.name
            try:
                res = engine.recognize(sample.pages, work)
                run.seconds = res.seconds
                final = out_dir / "musicxml" / sample.piece / f"{sample.variant}.{engine.name}.musicxml"
                final.parent.mkdir(parents=True, exist_ok=True)
                final.write_bytes(res.musicxml.read_bytes())
                run.output = str(final.relative_to(out_dir))
                summary = summarize(final)
                run.bar_issues = [i.describe() for i in summary.bar_issues]
                if truth is not None:
                    run.evaluation = evaluate_summaries(summary, truth)
            except Exception as e:  # keep going: one failure must not stop the benchmark
                run.error = f"{type(e).__name__}: {e}".strip()
                (work / "error.txt").parent.mkdir(parents=True, exist_ok=True)
                (work / "error.txt").write_text(traceback.format_exc())
            progress("   " + _short(run))
            results.append(run)

    write_reports(results, out_dir)
    return results


def _short(run: RunResult) -> str:
    if run.error:
        return f"failed: {run.error.splitlines()[0]}"
    parts = [f"{run.seconds:.1f}s", f"{len(run.bar_issues)} doubtful bar(s)"]
    if run.evaluation:
        parts.insert(0, f"accuracy {run.evaluation.symbol_accuracy:.0%}")
    return ", ".join(parts)


# --- reports -------------------------------------------------------------------------

def _pct(x: float | None) -> str:
    return "–" if x is None else f"{x:.0%}"


def _yn(x: bool | None) -> str:
    return "–" if x is None else ("✓" if x else "✗")


def markdown_table(results: list[RunResult]) -> str:
    lines = [
        "| Piece | Variant | Engine | Notes+rests | Pitch | Rhythm | Key | Time | Bars (got/expected) | Doubtful bars | Time (s) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.error:
            lines.append(f"| {r.piece} | {r.variant} | {r.engine} | **failed** | | | | | | | `{r.error.splitlines()[0][:60]}` |")
            continue
        e = r.evaluation
        bars = f"{e.measures}/{e.measures_expected}" if e else "–"
        lines.append(
            f"| {r.piece} | {r.variant} | {r.engine} | {_pct(e and e.symbol_accuracy)} | "
            f"{_pct(e and e.pitch_accuracy)} | {_pct(e and e.rhythm_accuracy)} | "
            f"{_yn(e.key_ok if e else None)} | {_yn(e.time_ok if e else None)} | {bars} | "
            f"{len(r.bar_issues)} | {r.seconds:.1f} |"
        )
    return "\n".join(lines)


def engine_totals(results: list[RunResult]) -> str:
    """Average accuracy per engine and variant (e.g. photo vs. scan)."""
    groups: dict[tuple[str, str], list[RunResult]] = {}
    for r in results:
        variant_kind = re.sub(r"\d+$", "", r.variant)  # photo2 → photo
        groups.setdefault((r.engine, variant_kind), []).append(r)
    lines = [
        "| Engine | Variant | Runs | Failed | Avg notes+rests | Avg pitch | Avg rhythm | Avg time (s) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for (engine, kind), runs in sorted(groups.items()):
        ok = [r for r in runs if not r.error]
        scored = [r.evaluation for r in ok if r.evaluation]

        def avg(values):
            values = list(values)
            return sum(values) / len(values) if values else None

        secs = avg(r.seconds for r in ok)
        lines.append(
            f"| {engine} | {kind} | {len(runs)} | {len(runs) - len(ok)} | "
            f"{_pct(avg(e.symbol_accuracy for e in scored))} | {_pct(avg(e.pitch_accuracy for e in scored))} | "
            f"{_pct(avg(e.rhythm_accuracy for e in scored))} | {'–' if secs is None else f'{secs:.1f}'} |"
        )
    return "\n".join(lines)


def write_reports(results: list[RunResult], out_dir: Path) -> None:
    rows = [r.row() for r in results]
    (out_dir / "results.json").write_text(json.dumps(rows, indent=2, default=str))
    if rows:
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with (out_dir / "results.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    report = [
        f"# TransNote engine comparison — {datetime.now():%Y-%m-%d %H:%M}",
        "",
        "## Per engine",
        "",
        engine_totals(results),
        "",
        "## All runs",
        "",
        markdown_table(results),
        "",
        "Accuracy = 1 − (edits needed to turn the result into the truth) / (length of the truth).",
        "\"Notes+rests\" counts pitch, duration and ties together; \"Pitch\" and \"Rhythm\" count them separately.",
        "",
    ]
    (out_dir / "report.md").write_text("\n".join(report))
