import json
from pathlib import Path

from conftest import MELODY, make_score
from transnote.cli import main
from transnote.compare import discover_samples, run_benchmark
from transnote.engines.base import Engine


class CopyEngine(Engine):
    """Pretends to recognise by returning a prepared file."""

    def __init__(self, name, result: Path | None):
        super().__init__()
        self.name = name
        self.result = result

    def find_executable(self):
        return Path("/bin/true")

    def _recognize(self, inputs, work_dir):
        if self.result is None:
            raise RuntimeError("engine crashed")
        return self.result, ""


def _samples(tmp_path):
    piece = tmp_path / "samples" / "march"
    piece.mkdir(parents=True)
    make_score(piece / "truth.musicxml", MELODY)
    for name in ("photo.jpg", "scan.pdf", "multi-2.jpg", "multi-1.jpg", "notes.txt"):
        (piece / name).write_bytes(b"x")
    return tmp_path / "samples"


def test_discover_samples(tmp_path):
    samples = discover_samples(_samples(tmp_path))
    assert [(s.variant, [p.name for p in s.pages]) for s in samples] == [
        ("multi", ["multi-1.jpg", "multi-2.jpg"]),
        ("photo", ["photo.jpg"]),
        ("scan", ["scan.pdf"]),
    ]
    assert all(s.truth and s.truth.name == "truth.musicxml" for s in samples)


def test_benchmark_scores_and_survives_failures(tmp_path):
    root = _samples(tmp_path)
    wrong = list(MELODY)
    wrong[0] = ("A4", 1)
    imperfect = make_score(tmp_path / "imperfect.musicxml", wrong)
    engines = [
        CopyEngine("perfect", root / "march" / "truth.musicxml"),
        CopyEngine("imperfect", imperfect),
        CopyEngine("broken", None),
    ]
    out = tmp_path / "results"
    results = run_benchmark(discover_samples(root), engines, out, progress=lambda m: None)
    assert len(results) == 9
    by_engine = {r.engine: r for r in results if r.variant == "photo"}
    assert by_engine["perfect"].evaluation.symbol_accuracy == 1.0
    assert by_engine["imperfect"].evaluation.symbol_accuracy < 1.0
    assert "engine crashed" in by_engine["broken"].error
    assert (out / "report.md").read_text().count("| march |") == 9
    assert len(json.loads((out / "results.json").read_text())) == 9


def test_cli_check_and_tag(tmp_path, melody, capsys):
    assert main(["check", str(melody)]) == 0
    assert "2 flats (B♭ major)" in capsys.readouterr().out
    out = tmp_path / "tagged.musicxml"
    assert main(["tag", str(melody), "-o", str(out)]) == 0
    assert "<transpose>" in out.read_text()


def test_cli_scan_with_fake_homr(tmp_path, fake_tool, melody, monkeypatch, capsys):
    exe = fake_tool("homr", f'for last; do :; done\ncp "{melody}" "${{last%.*}}.musicxml"\n')
    monkeypatch.setenv("TRANSNOTE_HOMR", str(exe))
    page = tmp_path / "song.jpg"
    page.write_bytes(b"x")
    assert main(["scan", str(page)]) == 0
    text = capsys.readouterr().out
    assert "song.musicxml" in text and "All bars add up" in text
    assert "Trumpet in B♭" in (tmp_path / "song.musicxml").read_text()


def test_page_order_and_default_name(capsys):
    from transnote.scan import default_output, order_pages

    pages = [Path("/m/Image 2.jpeg"), Path("/m/Image 10.jpeg"), Path("/m/Image.jpeg")]
    assert [p.name for p in order_pages(pages)] == ["Image.jpeg", "Image 2.jpeg", "Image 10.jpeg"]
    assert default_output(order_pages(pages)) == Path("/m/Image.musicxml")
    assert default_output([Path("/m/page-1.jpg"), Path("/m/page-2.jpg")]) == Path("/m/page.musicxml")
    assert default_output([Path("/m/IMG_4501.jpg")]) == Path("/m/IMG_4501.musicxml")
    assert default_output([Path("/m/march.jpg"), Path("/m/waltz.jpg")]) == Path("/m/march.musicxml")

    assert main(["plan", "/m/scan_2.png", "/m/scan_1.png"]) == 0
    assert capsys.readouterr().out.splitlines() == ["/m/scan.musicxml", "/m/scan_1.png", "/m/scan_2.png"]
