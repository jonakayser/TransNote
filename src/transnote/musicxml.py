"""Reading and writing MusicXML files (plain ``.musicxml``/``.xml`` and compressed ``.mxl``).

We work on the raw XML (ElementTree) wherever possible so that we don't lose
anything the OMR engine wrote. ``music21`` is only used for analysis and merging.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

MUSICXML_SUFFIXES = (".musicxml", ".xml", ".mxl")

_DOCTYPE = (
    '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
    '"http://www.musicxml.org/dtds/partwise.dtd">'
)


def is_musicxml(path: Path) -> bool:
    return path.suffix.lower() in MUSICXML_SUFFIXES


def read_xml_bytes(path: Path) -> bytes:
    """Return the score XML of a ``.musicxml``/``.xml`` or ``.mxl`` file."""
    path = Path(path)
    if path.suffix.lower() != ".mxl":
        return path.read_bytes()
    with zipfile.ZipFile(path) as zf:
        rootfile = _mxl_rootfile(zf)
        return zf.read(rootfile)


def _mxl_rootfile(zf: zipfile.ZipFile) -> str:
    try:
        container = ET.fromstring(zf.read("META-INF/container.xml"))
        for el in container.iter():
            if el.tag.endswith("rootfile") and el.get("full-path"):
                return el.get("full-path")  # type: ignore[return-value]
    except KeyError:
        pass
    # Fallback: first XML file that is not in META-INF
    for name in zf.namelist():
        if not name.startswith("META-INF") and name.lower().endswith((".xml", ".musicxml")):
            return name
    raise ValueError("No score found inside the .mxl file")


def read_tree(path: Path) -> ET.ElementTree:
    root = ET.fromstring(read_xml_bytes(path))
    return ET.ElementTree(root)


def write_tree(tree: ET.ElementTree, path: Path) -> Path:
    """Write a score as ``.musicxml`` (plain) or ``.mxl`` (compressed), by suffix."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree)
    buf = io.BytesIO()
    tree.write(buf, encoding="UTF-8", xml_declaration=False)
    xml = b'<?xml version="1.0" encoding="UTF-8"?>\n' + _DOCTYPE.encode() + b"\n" + buf.getvalue()
    if path.suffix.lower() == ".mxl":
        inner = path.with_suffix(".musicxml").name
        container = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<container><rootfiles>'
            f'<rootfile full-path="{inner}" media-type="application/vnd.recordare.musicxml+xml"/>'
            "</rootfiles></container>"
        )
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("mimetype", "application/vnd.recordare.musicxml", compress_type=zipfile.ZIP_STORED)
            zf.writestr("META-INF/container.xml", container)
            zf.writestr(inner, xml)
    else:
        path.write_bytes(xml)
    return path


def parse_score(path: Path):
    """Parse a MusicXML file with music21 (works for .mxl too)."""
    from music21 import converter

    return converter.parse(str(path), format="musicxml", forceSource=True)
