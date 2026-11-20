"""Join several recognised pages into one score."""

from __future__ import annotations

import shutil
from pathlib import Path

from .musicxml import parse_score, read_tree, write_tree


def merge_scores(paths: list[Path], output: Path) -> Path:
    """Append the measures of each page's parts to the first page's parts.

    Parts are matched by position; pages with fewer parts just contribute less.
    """
    paths = [Path(p) for p in paths]
    if not paths:
        raise ValueError("Nothing to merge")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if len(paths) == 1:
        if paths[0].resolve() == output.resolve():
            return output
        if paths[0].suffix.lower() == output.suffix.lower():
            shutil.copyfile(paths[0], output)
        else:  # e.g. compressed .mxl → plain .musicxml
            write_tree(read_tree(paths[0]), output)
        return output

    first = parse_score(paths[0])
    target_parts = list(first.parts)
    for path in paths[1:]:
        page = parse_score(path)
        for target, source in zip(target_parts, page.parts):
            number = _last_measure_number(target)
            for measure in list(source.getElementsByClass("Measure")):
                number += 1
                measure.number = number
                target.append(measure)
    first.write("musicxml", fp=str(output))
    return output


def _last_measure_number(part) -> int:
    measures = list(part.getElementsByClass("Measure"))
    return measures[-1].number if measures and measures[-1].number is not None else len(measures)
