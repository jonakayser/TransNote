# /// script
# requires-python = ">=3.11"
# dependencies = ["music21>=9.1", "numpy", "opencv-python-headless"]
# ///
"""Generate synthetic benchmark samples with a known ground truth.

For each made-up melody this writes, into ``samples/synthetic-<name>/``:

* ``truth.musicxml`` — the exact notes
* ``scan.png``      — the page engraved by LilyPond at 300 dpi (a perfect "scan")
* ``photo.jpg``     — the same page made to look like a phone photo
                      (perspective, rotation, uneven light, blur, JPEG)

Needs LilyPond (``brew install lilypond`` / ``apt install lilypond``). Run with:

    uv run scripts/make_synthetic_samples.py

These are only a smoke test. Real pages from your own music are what count.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np
from music21 import key, meter, metadata, note, stream, tie

ROOT = Path(__file__).resolve().parent.parent / "samples"

# (pitch or "r", quarter length, tied to next?)
# Written pitch for B♭ trumpet.
MARCH = """
Bb4 1 | C5 1 | D5 1 | Eb5 1 |
F5 2 | D5 2 |
Eb5 .5 | D5 .5 | C5 1 | r 1 | F4 1 |
Bb4 3 ~ | Bb4 1 |
G5 1.5 | F5 .5 | Eb5 1 | D5 1 |
C5 2 | r 2 |
A4 1 | Bb4 1 | C5 1 | D5 1 |
Eb5 1 | C5 1 | A4 2 |
Bb4 .5 | C5 .5 | D5 .5 | Eb5 .5 | F5 1 | F5 1 |
G5 2 ~ | G5 .5 | F5 .5 | Eb5 .5 | D5 .5 |
C5 1 | r .5 | C5 .5 | F5 1 | E5 1 |
F5 4 |
D5 1.5 | Eb5 .5 | F5 1 | Bb4 1 |
Eb5 2 | C5 2 |
Bb4 1 | D5 1 | C5 1 | A4 1 |
Bb4 3 | r 1
"""

WALTZ = """
C5 2 | A4 1 |
F5 2 | E5 1 |
D5 1 | C5 1 | Bb4 1 |
A4 3 ~ |
A4 1 | r 1 | C5 1 |
D5 .5 | E5 .5 | F5 1 | G5 1 |
A5 2 | F5 1 |
C6 1.5 | Bb5 .5 | A5 1 |
G5 3 |
r 1 | G5 1 | Bb5 1 |
A5 1 | F5 1 | D5 1 |
C5 2 | F#5 1 |
G5 .5 | F5 .5 | E5 1 | D5 1 |
C5 1 | Bb4 1 | G4 1 |
F4 2 ~ | F4 .5 | r .5 |
F4 2 | r 1
"""

PIECES = {
    # name: (melody, time signature, sharps(+)/flats(−), title)
    "march": (MARCH, "4/4", -2, "Synthetic March"),
    "waltz": (WALTZ, "3/4", -1, "Synthetic Waltz"),
}


def build_score(melody: str, time_sig: str, sharps: int, title: str) -> stream.Score:
    part = stream.Part()
    part.append(meter.TimeSignature(time_sig))
    part.append(key.KeySignature(sharps))
    tokens = [t.strip() for t in melody.replace("\n", " ").split("|") if t.strip()]
    previous_tied = False
    for token in tokens:
        bits = token.split()
        pitch, ql = bits[0], float(bits[1])
        tied = len(bits) > 2 and bits[2] == "~"
        if pitch == "r":
            el = note.Rest(quarterLength=ql)
        else:
            el = note.Note(re.sub(r"^([A-G])b", r"\1-", pitch), quarterLength=ql)  # Bb4 → B-4
            if tied or previous_tied:
                el.tie = tie.Tie("continue" if tied and previous_tied else "start" if tied else "stop")
        previous_tied = tied and pitch != "r"
        part.append(el)
    score = stream.Score([part])
    score.insert(0, metadata.Metadata(title=title))
    return score.makeNotation()


def to_lilypond(score: stream.Score, title: str, out_dir: Path) -> Path:
    """Engrave with LilyPond on a full A4 page and return the 300 dpi PNG."""
    ly = out_dir / "page.ly"
    score.write("lilypond", fp=str(ly))
    text = ly.read_text()
    text = text.replace('\\include "lilypond-book-preamble.ly"', "")
    text += f'\n\\header {{ title = "{title}" tagline = ##f }}\n'
    text = re.sub(r"\\paper \{ *\}", lambda _: '\\paper { #(set-paper-size "a4") }', text)
    ly.write_text(text)
    subprocess.run(
        ["lilypond", "--png", "-dresolution=300", "-o", str(out_dir / "page"), str(ly)],
        check=True, capture_output=True,
    )
    pngs = sorted(out_dir.glob("page*.png"))
    if not pngs:
        raise RuntimeError("LilyPond produced no PNG")
    return pngs[0]


def fake_photo(scan: np.ndarray, seed: int) -> np.ndarray:
    """Make a clean page look like a hand-held phone photo of it."""
    rng = np.random.default_rng(seed)
    h, w = scan.shape[:2]
    # Put the page on a darker "table" with margin, then warp it.
    margin = int(0.08 * w)
    canvas = np.full((h + 2 * margin, w + 2 * margin, 3), (70, 80, 95), np.uint8)
    canvas[margin:margin + h, margin:margin + w] = cv2.cvtColor(scan, cv2.COLOR_GRAY2BGR)
    H, W = canvas.shape[:2]
    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    jitter = 0.04 * W
    dst = src + rng.uniform(-jitter, jitter, src.shape).astype(np.float32)
    photo = cv2.warpPerspective(canvas, cv2.getPerspectiveTransform(src, dst), (W, H),
                                borderValue=(60, 70, 80))
    # Uneven lighting: a soft shadow from one corner.
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    shade = 0.75 + 0.25 * (xx / W * 0.6 + yy / H * 0.4)
    photo = np.clip(photo.astype(np.float32) * shade[..., None], 0, 255)
    # Warm paper tint, sensor noise, slight blur, phone resolution, JPEG.
    photo *= np.array([0.92, 0.97, 1.0], np.float32)
    photo += rng.normal(0, 4, photo.shape)
    photo = cv2.GaussianBlur(np.clip(photo, 0, 255).astype(np.uint8), (3, 3), 0.8)
    scale = 3024 / max(H, W)
    photo = cv2.resize(photo, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_AREA)
    return photo


def main() -> int:
    if not shutil.which("lilypond"):
        print("LilyPond is not installed (brew install lilypond / apt install lilypond).", file=sys.stderr)
        return 1
    for i, (name, (melody, time_sig, sharps, title)) in enumerate(PIECES.items()):
        dest = ROOT / f"synthetic-{name}"
        dest.mkdir(parents=True, exist_ok=True)
        score = build_score(melody, time_sig, sharps, title)
        score.write("musicxml", fp=str(dest / "truth.musicxml"))
        with tempfile.TemporaryDirectory() as tmp:
            png = to_lilypond(score, title, Path(tmp))
            scan = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
        cv2.imwrite(str(dest / "scan.png"), scan)
        cv2.imwrite(str(dest / "photo.jpg"), fake_photo(scan, seed=i), [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
