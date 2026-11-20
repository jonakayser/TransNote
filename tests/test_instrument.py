import xml.etree.ElementTree as ET

from transnote.instrument import INSTRUMENTS, tag_instrument
from transnote.musicxml import parse_score, read_tree, write_tree


def test_tag_bb_trumpet(tmp_path, melody):
    tree = read_tree(melody)
    tag_instrument(tree, INSTRUMENTS["bb-trumpet"])
    out = write_tree(tree, tmp_path / "tagged.musicxml")

    root = read_tree(out).getroot()
    assert root.findtext("part-list/score-part/part-name") == "Trumpet in B♭"
    assert root.findtext("part-list/score-part/score-instrument/instrument-sound") == "brass.trumpet"
    attrs = root.find("part/measure/attributes")
    tags = [c.tag for c in attrs]
    assert tags.index("transpose") > tags.index("clef")  # schema order
    assert attrs.findtext("transpose/diatonic") == "-1"
    assert attrs.findtext("transpose/chromatic") == "-2"

    # music21 understands it: written B♭4 sounds as A♭4.
    part = parse_score(out).parts[0]
    assert part.getInstrument().transposition.semitones == -2
    first = part.recurse().notes[0]
    assert first.pitch.nameWithOctave == "B-4"
    assert part.toSoundingPitch().recurse().notes[0].pitch.nameWithOctave == "A-4"


def test_retagging_replaces_old_transpose(melody):
    tree = read_tree(melody)
    tag_instrument(tree, INSTRUMENTS["bb-trumpet"])
    tag_instrument(tree, INSTRUMENTS["eb-alto-sax"])
    transposes = list(tree.getroot().iter("transpose"))
    assert len(transposes) == 1
    assert transposes[0].findtext("chromatic") == "-9"


def test_concert_instrument_has_no_transpose(melody):
    tree = read_tree(melody)
    tag_instrument(tree, INSTRUMENTS["bb-trumpet"])
    tag_instrument(tree, INSTRUMENTS["flute"])
    assert list(tree.getroot().iter("transpose")) == []


def test_mxl_roundtrip(tmp_path, melody):
    mxl = write_tree(read_tree(melody), tmp_path / "x.mxl")
    def canon(path):
        return ET.canonicalize(ET.tostring(read_tree(path).getroot()), strip_text=True)

    assert canon(mxl) == canon(melody)
    assert len(parse_score(mxl).parts[0].recurse().notes) == 8
