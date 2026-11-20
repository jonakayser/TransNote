from fractions import Fraction

from conftest import MELODY, make_score
from transnote.analysis import summarize
from transnote.evaluate import accuracy, edit_distance, evaluate


def test_summary_reads_key_time_and_notes(melody):
    s = summarize(melody)
    assert s.key_sharps == -2
    assert s.time_signature == "4/4"
    assert s.measures == 4
    assert [e.pitches for e in s.events][:3] == [("B-4",), ("C5",), ("D5",)]
    assert s.events[3].kind == "rest"
    assert s.bar_issues == []


def test_ties_are_kept(tmp_path):
    # A half note starting on beat 4 gets split and tied by makeNotation.
    path = make_score(tmp_path / "t.musicxml", [("C5", 3), ("D5", 2), ("E5", 3)])
    ties = [e.tie for e in summarize(path).events]
    assert "start" in ties and "stop" in ties


def _bars_xml(notes_per_bar: list[int]) -> str:
    measures = []
    for i, n in enumerate(notes_per_bar, 1):
        attrs = "<attributes><divisions>1</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>" if i == 1 else ""
        notes = "<note><pitch><step>C</step><octave>5</octave></pitch><duration>1</duration><type>quarter</type></note>" * n
        measures.append(f'<measure number="{i}">{attrs}{notes}</measure>')
    return (
        '<?xml version="1.0"?><score-partwise version="4.0"><part-list>'
        '<score-part id="P1"><part-name>T</part-name></score-part></part-list>'
        f'<part id="P1">{"".join(measures)}</part></score-partwise>'
    )


def test_bar_check_finds_short_bar(tmp_path):
    # Written by hand: music21 itself would pad the short bar with a hidden rest.
    path = tmp_path / "short.musicxml"
    path.write_text(_bars_xml([4, 3, 4, 5, 2]))
    issues = summarize(path).bar_issues
    # bar 2 too short, bar 4 too long; the short last bar counts as a final partial bar
    assert [(i.measure, i.actual) for i in issues] == [(2, Fraction(3)), (4, Fraction(5))]
    assert "too short" in issues[0].describe()
    assert "too long" in issues[1].describe()


def test_hidden_padding_rests_are_ignored(tmp_path):
    from music21 import meter, note, stream

    part = stream.Part()
    m = stream.Measure(number=1)
    m.append(meter.TimeSignature("4/4"))
    m.append(note.Note("C5", quarterLength=3))
    part.append(m)
    path = tmp_path / "padded.musicxml"
    stream.Score([part]).write("musicxml", fp=str(path))  # adds a hidden quarter rest
    assert [e.kind for e in summarize(path).events] == ["note"]


def test_edit_distance_and_accuracy():
    assert edit_distance("kitten", "sitting") == 3
    assert accuracy([1, 2, 3], [1, 2, 3]) == 1.0
    assert accuracy([1, 9, 3], [1, 2, 3]) == 1 - 1 / 3
    assert accuracy([], [1, 2]) == 0.0
    assert accuracy([], []) == 1.0


def test_evaluate_identical_and_one_wrong_pitch(tmp_path, melody):
    assert evaluate(melody, melody).symbol_accuracy == 1.0

    wrong = list(MELODY)
    wrong[1] = ("C#5", 1)
    other = make_score(tmp_path / "result.musicxml", wrong, sharps=0)
    e = evaluate(other, melody)
    n_notes = sum(1 for p, _ in MELODY if p != "r")
    assert e.pitch_accuracy == 1 - 1 / n_notes
    assert e.rhythm_accuracy == 1.0
    assert not e.key_ok
    assert e.time_ok
