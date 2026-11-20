"""Tag a recognised part with its (transposing) instrument.

OMR engines don't know which instrument a part is for, so MuseScore imports the
notes as concert pitch. For a B♭ trumpet part that is wrong by a major 2nd, and
"Change instrument → Alto Saxophone" then gives a wrong result.

Writing a MusicXML ``<transpose>`` element (plus the instrument's name and sound)
tells MuseScore that the written notes belong to a B♭ trumpet. Changing the
instrument afterwards then transposes correctly.
"""

from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class Instrument:
    key: str
    name: str
    abbreviation: str
    sound: str  # MusicXML standard sound ID, used by MuseScore to pick the instrument
    diatonic: int  # written → sounding, in diatonic steps
    chromatic: int  # written → sounding, in semitones

    @property
    def transposing(self) -> bool:
        return self.chromatic != 0 or self.diatonic != 0


INSTRUMENTS: dict[str, Instrument] = {
    i.key: i
    for i in (
        Instrument("bb-trumpet", "Trumpet in B♭", "B♭ Tpt.", "brass.trumpet", -1, -2),
        Instrument("eb-alto-sax", "Alto Saxophone", "A. Sax.", "wind.reed.saxophone.alto", -5, -9),
        Instrument("bb-clarinet", "Clarinet in B♭", "B♭ Cl.", "wind.reed.clarinet.bflat", -1, -2),
        Instrument("bb-tenor-sax", "Tenor Saxophone", "T. Sax.", "wind.reed.saxophone.tenor", -8, -14),
        Instrument("f-horn", "Horn in F", "Hn.", "brass.french-horn", -4, -7),
        Instrument("c-trumpet", "Trumpet in C", "C Tpt.", "brass.trumpet.c", 0, 0),
        Instrument("flute", "Flute", "Fl.", "wind.flutes.flute", 0, 0),
    )
}

# Order of children inside <attributes>, as defined by the MusicXML schema.
_ATTRIBUTES_ORDER = [
    "footnote", "level", "divisions", "key", "time", "staves", "part-symbol",
    "instruments", "clef", "staff-details", "transpose", "for-part", "directive",
    "measure-style",
]
# Order of children inside <score-part>.
_SCORE_PART_ORDER = [
    "identification", "part-link", "part-name", "part-name-display", "part-abbreviation",
    "part-abbreviation-display", "group", "score-instrument", "player", "midi-device",
    "midi-instrument",
]


def _insert_ordered(parent: ET.Element, child: ET.Element, order: list[str]) -> None:
    """Insert ``child`` at the schema-correct position among ``parent``'s children."""
    rank = order.index(child.tag)
    pos = len(parent)
    for i, existing in enumerate(parent):
        if existing.tag in order and order.index(existing.tag) > rank:
            pos = i
            break
    parent.insert(pos, child)


def _set_text(parent: ET.Element, tag: str, text: str, order: list[str]) -> ET.Element:
    el = parent.find(tag)
    if el is None:
        el = ET.Element(tag)
        _insert_ordered(parent, el, order)
    el.text = text
    return el


def tag_instrument(tree: ET.ElementTree, instrument: Instrument, part_ids: list[str] | None = None) -> None:
    """Mark the parts of a score (default: all) as written for ``instrument``, in place."""
    root = tree.getroot()
    part_list = root.find("part-list")
    if part_list is None:
        raise ValueError("Not a partwise MusicXML score (no <part-list>)")

    for score_part in part_list.findall("score-part"):
        pid = score_part.get("id")
        if part_ids is not None and pid not in part_ids:
            continue
        _tag_score_part(score_part, instrument)
        part = root.find(f"part[@id='{pid}']")
        if part is not None:
            _tag_part(part, instrument)


def _tag_score_part(score_part: ET.Element, instrument: Instrument) -> None:
    pid = score_part.get("id") or "P1"
    _set_text(score_part, "part-name", instrument.name, _SCORE_PART_ORDER)
    _set_text(score_part, "part-abbreviation", instrument.abbreviation, _SCORE_PART_ORDER)

    score_instrument = score_part.find("score-instrument")
    if score_instrument is None:
        score_instrument = ET.Element("score-instrument", id=f"{pid}-I1")
        _insert_ordered(score_part, score_instrument, _SCORE_PART_ORDER)
        # Keep MIDI instruments pointing at an existing score-instrument.
        for midi in score_part.findall("midi-instrument"):
            midi.set("id", score_instrument.get("id"))
    order = ["instrument-name", "instrument-abbreviation", "instrument-sound", "solo", "ensemble", "virtual-instrument"]
    _set_text(score_instrument, "instrument-name", instrument.name, order)
    _set_text(score_instrument, "instrument-sound", instrument.sound, order)


def _tag_part(part: ET.Element, instrument: Instrument) -> None:
    # Remove any transposition the engine may have guessed.
    for attributes in part.iter("attributes"):
        for old in attributes.findall("transpose"):
            attributes.remove(old)
    if not instrument.transposing:
        return

    first_measure = part.find("measure")
    if first_measure is None:
        return
    attributes = first_measure.find("attributes")
    if attributes is None:
        attributes = ET.Element("attributes")
        first_measure.insert(0, attributes)

    transpose = ET.Element("transpose")
    ET.SubElement(transpose, "diatonic").text = str(instrument.diatonic)
    ET.SubElement(transpose, "chromatic").text = str(instrument.chromatic)
    _insert_ordered(attributes, transpose, _ATTRIBUTES_ORDER)
