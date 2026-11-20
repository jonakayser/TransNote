"""Turn a score into comparable data, and check it for obvious recognition errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

from .musicxml import parse_score


@dataclass(frozen=True)
class Event:
    """One note, chord or rest of a single-line part, in reading order."""

    kind: str  # "note" | "chord" | "rest"
    pitches: tuple[str, ...]  # spelled pitches, e.g. ("B-4",); empty for rests
    duration: Fraction  # in quarter notes
    tie: str | None = None  # "start" | "stop" | "continue" | None

    @property
    def tied_to_next(self) -> bool:
        return self.tie in ("start", "continue")

    @property
    def symbol(self) -> tuple:
        """Everything that matters: kind, spelled pitch, duration and tie.

        Only "tied to the next note" counts; the tie's end is implied by its start.
        """
        return (self.kind, self.pitches, self.duration, self.tied_to_next)

    @property
    def rhythm(self) -> tuple:
        return (self.kind == "rest", self.duration)


@dataclass(frozen=True)
class BarIssue:
    """A bar whose content does not add up to its time signature."""

    measure: int | str
    expected: Fraction
    actual: Fraction

    def describe(self) -> str:
        what = "too short" if self.actual < self.expected else "too long"
        return f"bar {self.measure}: {_fmt(self.actual)} of {_fmt(self.expected)} quarters ({what})"


@dataclass
class ScoreSummary:
    events: list[Event]
    key_sharps: int | None  # first key signature: +sharps / −flats
    time_signature: str | None  # first time signature, e.g. "4/4"
    measures: int
    bar_issues: list[BarIssue] = field(default_factory=list)
    parts: int = 1


def _fmt(q: Fraction) -> str:
    return str(q.numerator) if q.denominator == 1 else f"{q.numerator}/{q.denominator}"


def _frac(x) -> Fraction:
    return Fraction(x).limit_denominator(64)


def summarize(path: Path, part_index: int = 0) -> ScoreSummary:
    """Read a MusicXML file and summarise one part (default: the first)."""
    score = parse_score(Path(path))
    parts = list(score.parts)
    if not parts:
        return ScoreSummary([], None, None, 0, [], 0)
    part = parts[min(part_index, len(parts) - 1)]

    from music21 import meter, key as m21key

    keys = list(part.recurse().getElementsByClass(m21key.KeySignature))
    times = list(part.recurse().getElementsByClass(meter.TimeSignature))
    measures = list(part.getElementsByClass("Measure"))

    return ScoreSummary(
        events=extract_events(part),
        key_sharps=keys[0].sharps if keys else None,
        time_signature=times[0].ratioString if times else None,
        measures=len(measures),
        bar_issues=check_bars(part),
        parts=len(parts),
    )


def extract_events(part) -> list[Event]:
    events: list[Event] = []
    for el in part.recurse().notesAndRests:
        if el.duration.isGrace:
            continue
        if el.isRest and el.style.hideObjectOnPrint:
            continue  # invisible padding rest, not on the page
        duration = _frac(el.duration.quarterLength)
        tie = el.tie.type if getattr(el, "tie", None) is not None else None
        if el.isRest:
            events.append(Event("rest", (), duration))
        elif el.isChord:
            pitches = tuple(sorted(p.nameWithOctave for p in el.pitches))
            events.append(Event("chord", pitches, duration, tie))
        else:
            events.append(Event("note", (el.pitch.nameWithOctave,), duration, tie))
    return events


def check_bars(part) -> list[BarIssue]:
    """Find bars whose length doesn't match the time signature.

    The first bar may be a pickup (shorter), and so may the last bar; both are
    only reported when they are too long.
    """
    measures = list(part.getElementsByClass("Measure"))
    issues: list[BarIssue] = []
    for i, m in enumerate(measures):
        try:
            expected = _frac(m.barDuration.quarterLength)
        except Exception:  # no time signature in context
            continue
        actual = _frac(m.highestTime)
        if actual == expected:
            continue
        is_edge = i == 0 or i == len(measures) - 1
        if is_edge and actual < expected:
            continue  # pickup / final partial bar
        issues.append(BarIssue(m.number if m.number is not None else i + 1, expected, actual))
    return issues
