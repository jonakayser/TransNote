import pytest

from conftest import MELODY, make_score
from transnote.analysis import summarize
from transnote.engines import AudiverisEngine, EngineError, EngineNotFound, HomrEngine


def test_homr_engine_runs_cli_and_collects_output(tmp_path, fake_tool, melody):
    # Fake homr: writes <stem>.musicxml next to the (last) input, like the real one.
    exe = fake_tool("homr", f"""
        for last; do :; done
        cp "{melody}" "${{last%.*}}.musicxml"
        echo "args: $@"
    """)
    page = tmp_path / "page.jpg"
    page.write_bytes(b"not really a jpeg")
    res = HomrEngine(executable=exe).recognize([page], tmp_path / "work")
    assert res.musicxml.exists()
    assert "--no-title" in res.log
    assert len(summarize(res.musicxml).events) == len(MELODY)
    assert not (tmp_path / "page.musicxml").exists()  # input folder untouched


def test_audiveris_merges_movements_in_order(tmp_path, fake_tool):
    a = make_score(tmp_path / "a.musicxml", [("C5", 4)])
    b = make_score(tmp_path / "b.musicxml", [("D5", 4)])
    exe = fake_tool("Audiveris", f"""
        out=""; while [ "$1" != "--" ]; do [ "$1" = "-output" ] && out="$2"; shift; done; shift
        stem=$(basename "${{1%.*}}")
        cp "{b}" "$out/$stem.mvt2.musicxml"
        cp "{a}" "$out/$stem.mvt1.musicxml"
    """)
    page = tmp_path / "scan.pdf"
    page.write_bytes(b"%PDF-fake")
    res = AudiverisEngine(executable=exe).recognize([page], tmp_path / "work")
    pitches = [e.pitches[0] for e in summarize(res.musicxml).events]
    assert pitches == ["C5", "D5"]


def test_engine_failure_is_reported(tmp_path, fake_tool):
    exe = fake_tool("homr", "echo boom; exit 3\n")
    page = tmp_path / "p.png"
    page.write_bytes(b"x")
    with pytest.raises(EngineError, match="exit code 3"):
        HomrEngine(executable=exe).recognize([page], tmp_path / "w")


def test_missing_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSNOTE_HOMR", str(tmp_path / "nope"))
    page = tmp_path / "p.png"
    page.write_bytes(b"x")
    with pytest.raises(EngineNotFound):
        HomrEngine().recognize([page], tmp_path / "w")
