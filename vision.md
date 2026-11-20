# TransNote — Vision

> **Status:** v0.3. Phase 0 tooling is built; waiting for real sample pages. Open questions are marked **❓**.

## 1. The problem

I have printed sheet music (books, handouts, old copies) that I want to **edit
and transpose** in MuseScore Studio. Re-typing it by hand is slow and boring.
I want to point a camera at a page and get an editable score that is correct
enough that fixing the remaining mistakes in MuseScore takes minutes, not an hour.

## 2. The goal

**Photo (or scan) of sheet music → editable MusicXML → MuseScore Studio.**

The result should preserve everything that matters musically:

- pitches, including accidentals
- durations: notes, dots, ties ("holding")
- rests ("pauses")
- key signature and time signature (and changes of either)
- bar lines, repeats, and voltas where possible
- multiple pages combined into one score

### Typical input (decided)

- **Printed** sheet music (no handwriting)
- **Single-line melodies**, one staff, mostly **B♭ trumpet parts**
- Usual target: **E♭ alto sax**

### Transposition happens in MuseScore (decided)

TransNote does not transpose. But it should **tag the part as a B♭ trumpet**
(the MusicXML `<transpose>` element: diatonic −1, chromatic −2). Without that,
MuseScore treats the notes on the page as concert pitch. Then "Change
instrument → Alto Saxophone" comes out a major 2nd off. With the tag, changing
the instrument gives the correct alto part (written trumpet + perfect 5th).

## 3. Guiding principles

1. **Mac first, phone later.** All processing runs on the Mac, in Python. The
   iPhone/iPad is only a camera for now. A native iOS app (TestFlight) is a
   possible later phase, not a starting point.
2. **Don't reinvent OMR.** Optical Music Recognition is a hard research
   problem. We build on existing open-source engines and put our effort into
   the parts around them: image cleanup, picking the best result, checking it,
   and the workflow.
3. **MusicXML is the format between steps.** It's an open standard, MuseScore
   imports it directly, and Python (`music21`) can read, check, and change it.
4. **Expect mistakes, and make them easy to find.** No OMR engine is perfect.
   TransNote should *flag* doubtful measures (e.g. a bar whose durations don't
   add up to the time signature) rather than pretend the result is clean.
5. **Measure progress.** Keep a small set of my own real photos with corrected
   "ground truth" scores, so engine choices and tweaks are judged on data.

## 4. How it works (proposed pipeline)

```
 iPad/iPhone photo ─┐
 PDF scan ──────────┤
                    ▼
        ┌───────────────────────┐
        │ 1. Ingest             │  images / PDF pages, page order
        ├───────────────────────┤
        │ 2. Preprocess         │  flatten perspective, deskew, even out
        │    (OpenCV)           │  lighting, black/white, upscale
        ├───────────────────────┤
        │ 3. Recognize (OMR)    │  pluggable engine → MusicXML per page
        │    homr / Audiveris   │
        ├───────────────────────┤
        │ 4. Merge & check      │  join pages, check bar lengths, key,
        │    (music21)          │  clefs; mark doubtful bars
        ├───────────────────────┤
        │ 5. Tag instrument     │  mark as B♭ trumpet (MuseScore transposes)
        ├───────────────────────┤
        │ 6. Export             │  .mxl → open in MuseScore Studio
        └───────────────────────┘
```

### Capture tip (no app needed)

Apple already ships a good document scanner: **Files / Notes → "Scan
Documents"** on iPhone/iPad, or **Continuity Camera** on the Mac
(*File → Insert from iPhone/iPad → Scan Documents*). It corrects perspective
and crops the page, and the result lands on the Mac as a PDF. That covers most
of step 2 for free and is the recommended way to capture in phase 1.

### OMR engine candidates

| Engine | Language | Strengths | Weaknesses |
|---|---|---|---|
| [homr](https://github.com/liebharc/homr) | Python | Built for **camera photos**; deep learning (oemer segmentation + transformer); outputs MusicXML | Small project; slow on CPU; quality varies with notation complexity |
| [oemer](https://github.com/BreezeWhite/oemer) | Python | End-to-end deep learning; handles skewed phone photos | Older; weaker on dense or polyphonic scores |
| [Audiveris](https://github.com/Audiveris/audiveris) | Java (Mac .dmg, CLI batch mode) | Mature, actively maintained, very good on **clean printed scans**, rich MusicXML | Struggles with photos (perspective, shadows); separate Java install |
| Vision LLM (e.g. Claude) | API | Can read a page "like a musician": good for key/time-signature checks or second opinions on single bars | Not reliable for full note-by-note transcription; costs money; needs internet |

**Both have a command-line interface**, so either fits an automated workflow:

```bash
# Audiveris (no GUI, export MusicXML)
/Applications/Audiveris.app/Contents/MacOS/Audiveris -batch -export -output out/ -- page.pdf
# homr (writes page.musicxml next to the image)
homr page.jpg
```

- **Audiveris** reads PDFs and multi-page books natively. It's a separate
  Java app (signed .dmg not provided, so Gatekeeper needs a one-time override).
- **homr** is a Python package, so it lives in the same environment as
  TransNote. It takes images only (PDF pages must be rendered first), one page
  per run. It ignores dynamics and articulations.

**Plan:** wrap both behind one interface and pick the winner with the
benchmark below. Keep the loser available as a fallback.

### Engine benchmark (phase 0)

1. Collect **5–10 real pages** from my trumpet parts, in two versions each:
   phone **photo** and Apple **"Scan Documents" PDF**.
2. Make **ground truth**: run either engine, fix the result by hand in
   MuseScore, export MusicXML.
3. `transnote compare samples/` runs every engine on every page and scores the
   output against ground truth with `music21`:
   - note accuracy (pitch + duration, aligned per measure)
   - rests, ties, key and time signature correct?
   - bars whose durations don't fit the time signature
   - run time
4. Result: a table showing which engine wins for photos vs. scans.

## 5. Phases

| Phase | What I get | Status |
|---|---|---|
| **0 — Setup & benchmark** | Python project (`uv`), setup scripts for Mac and cloud, `transnote compare`, 5–10 real test pages with ground truth | Tooling done; real pages missing |
| **1 — MVP** | `transnote scan page.jpg --open` → MusicXML opens in MuseScore | Done (both engines, multi-page) |
| **2 — Quality** | Preprocessing, doubtful bars *marked in the score*, cross-checking the two engines against each other | Bar check prints doubtful bars |
| **3 — Instrument tag** | `--instrument bb-trumpet` writes the transposition into the MusicXML so MuseScore's "Change instrument" is correct | Done (default) |
| **4 — Comfort** | Drop photos into a watched folder (e.g. iCloud Drive), or a small drag-and-drop window on the Mac |
| **5 — Mobile (maybe)** | iPad app via TestFlight that captures pages and sends them to the Mac, or runs OMR on-device |

### First results (synthetic pages only)

Two made-up melodies, engraved with LilyPond (`scripts/make_synthetic_samples.py`),
each as a clean 300 dpi "scan" and a fake phone photo (perspective, shadow, blur):

| Engine | Notes+rests | Pitch | Rhythm | Time per page |
|---|---|---|---|---|
| homr | 100 % | 100 % | 100 % | ~5 s |
| Audiveris | 95 % | 97 % | 96 % | ~7 s |

Audiveris dropped one whole bar of the waltz (on both scan and photo). The bar
check did **not** catch this, because the remaining bars were all complete. A
missing bar can only be found by comparing with something else, e.g. the other
engine's result. That's an idea for phase 2.

These pages are much cleaner than real printed parts, so this proves the
pipeline works but does **not** pick the winner yet.

## 6. Open questions ❓

1. **Chord symbols / dynamics / articulations:** needed, or are notes and
   rhythm enough? (homr ignores dynamics and articulations.)
2. **Interface:** a terminal command is enough to start. A window can come later.
3. **Which Mac?** Apple Silicon is assumed (fast enough for homr on CPU/MPS).

## 7. Out of scope (for now)

- Writing our own OMR model
- Audio playback or MIDI-only output (MuseScore does this)
- A full in-app score editor (MuseScore *is* the editor)
- App Store release
