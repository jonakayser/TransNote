"""Command-line interface: ``transnote scan | compare | evaluate | check | tag | doctor``."""

from __future__ import annotations

import argparse
import platform
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .engines import ENGINES, EngineError, get_engine
from .instrument import INSTRUMENTS

DEFAULT_ENGINE = "homr"
DEFAULT_INSTRUMENT = "bb-trumpet"


def _instrument(key: str):
    return None if key == "none" else INSTRUMENTS[key]


def cmd_scan(args) -> int:
    from .scan import describe_key, open_in_musescore, scan

    engine = get_engine(args.engine)
    print(f"Recognising {len(args.inputs)} page(s) with {engine.name} …", file=sys.stderr)
    try:
        result = scan(
            args.inputs, engine, output=args.output, instrument=_instrument(args.instrument),
            keep_work=args.keep_work,
        )
    except EngineError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    print(f"Saved {result.output}  ({result.seconds:.1f}s)")
    print(f"  Key: {describe_key(result.key_sharps)}   Time: {result.time_signature or '?'}   Bars: {result.measures}")
    if result.bar_issues:
        print(f"  ⚠ {len(result.bar_issues)} doubtful bar(s) — check these in MuseScore:")
        for issue in result.bar_issues:
            print(f"    - {issue.describe()}")
    else:
        print("  ✓ All bars add up to the time signature.")
    if args.open:
        open_in_musescore(result.output)
    return 0


def cmd_compare(args) -> int:
    from .compare import discover_samples, engine_totals, markdown_table, run_benchmark

    samples = discover_samples(args.samples)
    if args.only:
        samples = [s for s in samples if s.piece in args.only]
    if not samples:
        print(f"No samples found in {args.samples}. See samples/README.md for the layout.", file=sys.stderr)
        return 1
    engines = [get_engine(n) for n in args.engines]
    missing = [e.name for e in engines if not e.is_available()]
    if missing:
        print(f"Warning: not installed: {', '.join(missing)} (runs will be marked as failed)", file=sys.stderr)

    out = args.out or Path("results") / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    results = run_benchmark(samples, engines, out, progress=lambda m: print(m, file=sys.stderr))
    print()
    print(engine_totals(results))
    print()
    print(markdown_table(results))
    print(f"\nFull report: {out / 'report.md'}")
    return 0


def cmd_evaluate(args) -> int:
    from .evaluate import evaluate

    e = evaluate(args.result, args.truth)
    print(f"Notes+rests: {e.symbol_accuracy:.1%}   Pitch: {e.pitch_accuracy:.1%}   Rhythm: {e.rhythm_accuracy:.1%}")
    print(f"Key: {'ok' if e.key_ok else 'WRONG'}   Time: {'ok' if e.time_ok else 'WRONG'}")
    print(f"Bars: {e.measures}/{e.measures_expected}   Events: {e.events}/{e.events_expected}   Doubtful bars: {e.bar_issues}")
    return 0


def cmd_check(args) -> int:
    from .analysis import summarize
    from .scan import describe_key

    s = summarize(args.file)
    print(f"Key: {describe_key(s.key_sharps)}   Time: {s.time_signature or '?'}   Bars: {s.measures}   Notes+rests: {len(s.events)}")
    for issue in s.bar_issues:
        print(f"  ⚠ {issue.describe()}")
    if not s.bar_issues:
        print("  ✓ All bars add up to the time signature.")
    return 0


def cmd_tag(args) -> int:
    from .instrument import tag_instrument
    from .musicxml import read_tree, write_tree

    tree = read_tree(args.file)
    tag_instrument(tree, INSTRUMENTS[args.instrument])
    out = write_tree(tree, args.output or args.file.with_suffix(".musicxml"))
    print(f"Saved {out} as {INSTRUMENTS[args.instrument].name}")
    return 0


def cmd_doctor(args) -> int:
    from .scan import find_musescore

    print(f"TransNote {__version__} — Python {platform.python_version()} on {platform.system()} {platform.machine()}")
    ok = True
    for name, cls in ENGINES.items():
        engine = cls()
        exe = engine.find_executable()
        if exe:
            version = engine.version() if args.versions else None
            print(f"  ✓ {name:10s} {exe}" + (f"  (version {version})" if version else ""))
        else:
            ok = False
            print(f"  ✗ {name:10s} not found (set {engine.env_var} or run the setup script)")
    musescore = find_musescore()
    print(f"  {'✓' if musescore else '–'} {'musescore':10s} {musescore or 'not found (only needed for --open)'}")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="transnote", description="Sheet music photos/scans → MusicXML for MuseScore.")
    p.add_argument("--version", action="version", version=f"transnote {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scan", help="Recognise one piece (one or more pages) into MusicXML")
    s.add_argument("inputs", nargs="+", type=Path, help="Images or PDF, pages in order")
    s.add_argument("-e", "--engine", choices=list(ENGINES), default=DEFAULT_ENGINE)
    s.add_argument("-o", "--output", type=Path, help="Output file (.musicxml or .mxl). Default: next to the input")
    s.add_argument("-i", "--instrument", choices=[*INSTRUMENTS, "none"], default=DEFAULT_INSTRUMENT,
                   help=f"Instrument the part is written for (default: {DEFAULT_INSTRUMENT})")
    s.add_argument("--open", action="store_true", help="Open the result in MuseScore Studio")
    s.add_argument("--keep-work", type=Path, metavar="DIR", help="Keep the engine's intermediate files here")
    s.set_defaults(func=cmd_scan)

    c = sub.add_parser("compare", help="Benchmark the engines on the sample pages")
    c.add_argument("samples", nargs="?", type=Path, default=Path("samples"))
    c.add_argument("-e", "--engines", nargs="+", choices=list(ENGINES), default=list(ENGINES))
    c.add_argument("--only", nargs="+", metavar="PIECE", help="Only these sample folders")
    c.add_argument("-o", "--out", type=Path, help="Results folder (default: results/<timestamp>)")
    c.set_defaults(func=cmd_compare)

    ev = sub.add_parser("evaluate", help="Score one MusicXML result against a ground-truth file")
    ev.add_argument("result", type=Path)
    ev.add_argument("truth", type=Path)
    ev.set_defaults(func=cmd_evaluate)

    ch = sub.add_parser("check", help="Show key, time signature and doubtful bars of a MusicXML file")
    ch.add_argument("file", type=Path)
    ch.set_defaults(func=cmd_check)

    t = sub.add_parser("tag", help="Mark an existing MusicXML file as written for an instrument")
    t.add_argument("file", type=Path)
    t.add_argument("-i", "--instrument", choices=list(INSTRUMENTS), default=DEFAULT_INSTRUMENT)
    t.add_argument("-o", "--output", type=Path)
    t.set_defaults(func=cmd_tag)

    d = sub.add_parser("doctor", help="Check which engines are installed")
    d.add_argument("--versions", action="store_true", help="Also ask each engine for its version (slow)")
    d.set_defaults(func=cmd_doctor)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
