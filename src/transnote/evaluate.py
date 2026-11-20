"""Score a recognised file against a hand-corrected "ground truth" file."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Sequence, Hashable

from .analysis import ScoreSummary, summarize


@dataclass
class Evaluation:
    symbol_accuracy: float  # notes/rests right in pitch, duration and tie
    pitch_accuracy: float  # sequence of pitches only
    rhythm_accuracy: float  # sequence of durations and note/rest only
    key_ok: bool
    time_ok: bool
    measures: int
    measures_expected: int
    events: int
    events_expected: int
    bar_issues: int

    def as_dict(self) -> dict:
        return asdict(self)


def edit_distance(a: Sequence[Hashable], b: Sequence[Hashable]) -> int:
    """Levenshtein distance between two sequences (insert/delete/substitute = 1)."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (x != y)))
        previous = current
    return previous[-1]


def accuracy(result: Sequence[Hashable], truth: Sequence[Hashable]) -> float:
    """1.0 = identical; 0.0 = as many edits as the truth has items (or worse)."""
    if not truth:
        return 1.0 if not result else 0.0
    return max(0.0, 1.0 - edit_distance(result, truth) / len(truth))


def evaluate_summaries(result: ScoreSummary, truth: ScoreSummary) -> Evaluation:
    def pitches(s: ScoreSummary):
        return [e.pitches for e in s.events if e.kind != "rest"]

    return Evaluation(
        symbol_accuracy=accuracy([e.symbol for e in result.events], [e.symbol for e in truth.events]),
        pitch_accuracy=accuracy(pitches(result), pitches(truth)),
        rhythm_accuracy=accuracy([e.rhythm for e in result.events], [e.rhythm for e in truth.events]),
        key_ok=result.key_sharps == truth.key_sharps,
        time_ok=result.time_signature == truth.time_signature,
        measures=result.measures,
        measures_expected=truth.measures,
        events=len(result.events),
        events_expected=len(truth.events),
        bar_issues=len(result.bar_issues),
    )


def evaluate(result_path: Path, truth_path: Path) -> Evaluation:
    return evaluate_summaries(summarize(result_path), summarize(truth_path))
