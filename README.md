# TransNote

Photos or scans of **printed sheet music → MusicXML** you can open and edit in
**MuseScore Studio**. Runs on the Mac; the iPhone/iPad is just the camera.

Built for single-line parts (mostly B♭ trumpet) that get transposed in MuseScore,
e.g. for E♭ alto sax. See [vision.md](vision.md) for the why and the plan.

## How it works

```
photo / PDF → OMR engine (homr or Audiveris) → mark as B♭ trumpet → check bars → .musicxml → MuseScore
```

TransNote doesn't read the notes itself. It drives two open-source optical
music recognition (OMR) engines through their command lines:

| Engine | Good at | Installed as |
|---|---|---|
| [homr](https://github.com/liebharc/homr) | phone photos | `uv tool install 'homr[cpu]'` |
| [Audiveris](https://github.com/Audiveris/audiveris) | clean scans | Mac app in `/Applications` |

## Setup on the Mac

```bash
git clone https://github.com/jonakayser/TransNote.git
```

```bash
cd TransNote && ./scripts/setup-mac.sh
```

The script installs `uv`, TransNote, homr (and its models) and Audiveris, asks
before each download, and finishes with `transnote doctor`.

## Everyday use

**Capture tip:** use *Files → ⋯ → Scan Documents* on the iPhone/iPad (or on the
Mac, *File → Insert from iPhone → Scan Documents*). It straightens and crops the
page, and the PDF lands on the Mac.

### The app

`./scripts/make-mac-app.sh` (also run by the setup script) builds
**`~/Applications/TransNote.app`**. Open it with Spotlight (⌘-Space, "TransNote"):

1. Pick the image(s) of one piece (⌘-click for several pages).
2. Pick where to save. By default this is the images' folder, with a name taken from
   the images (`Image.jpeg` + `Image 2.jpeg` → `Image.musicxml`).
3. Wait while it recognises the pages, then click **Open in MuseScore**.

You can also drag the app into the Dock and drop images onto it. Pages are put in
natural order (`Image`, `Image 2`, … `Image 10`), and the final dialog lists that order.
The app uses homr and marks the part as Trumpet in B♭.

### Command line

```bash
transnote scan trumpet-part.pdf --open
```

That writes `trumpet-part.musicxml` next to the PDF, marked as **Trumpet in B♭**,
prints key, time signature and any doubtful bars, and opens it in MuseScore.

More options:

```bash
transnote scan page-1.jpg page-2.jpg -e audiveris -o song.musicxml   # two photos, other engine
transnote scan page.jpg -i none                                      # don't mark an instrument
transnote check song.musicxml                                        # key, time, doubtful bars
transnote tag song.musicxml -i bb-trumpet                            # mark an existing file
transnote plan *.jpeg                                                # page order + suggested name
transnote doctor                                                     # what's installed?
```

### Transposing for alto sax in MuseScore

Because the file says it is a B♭ trumpet part, MuseScore knows the real
(concert) pitch. Then: right-click the staff → **Change instrument… → Alto
Saxophone**. MuseScore rewrites the part correctly (a perfect 5th up from the
trumpet part).

Without the B♭ trumpet mark (e.g. after `-i none`), MuseScore would treat the
written notes as concert pitch and the alto part would be a major 2nd off.
In that case use *Tools → Transpose* instead.

## Which engine is better? — `transnote compare`

Put real pages into `samples/` (layout: [samples/README.md](samples/README.md)),
then:

```bash
transnote compare
```

Every engine runs on every page. The results are scored against your
hand-corrected version. The table shows accuracy (notes + rests, pitch,
rhythm), key, time signature, bar count and timing. The full report, CSV and
all MusicXML outputs go to `results/<timestamp>/`.

`scripts/make_synthetic_samples.py` creates engraved test pages with a known
answer (needs LilyPond). They are only a smoke test; your real pages are what count.

## Development

```bash
uv run pytest
```

```bash
uv run transnote --help
```

In the Claude Code cloud environment, `scripts/setup-cloud.sh` installs both
engines and LilyPond on Ubuntu. Paste it into the environment's setup script so
every new session has them.

Code map (`src/transnote/`):

| File | Does |
|---|---|
| `cli.py` | the `transnote` command |
| `scan.py` | everyday pipeline, finding/opening MuseScore |
| `engines/` | `homr.py`, `audiveris.py`: run the engines, collect their MusicXML |
| `instrument.py` | mark a part as B♭ trumpet etc. (MusicXML `<transpose>`) |
| `analysis.py` | read notes/rests, key, time; find bars that don't add up |
| `evaluate.py` | compare a result with the ground truth |
| `compare.py` | benchmark runner and reports |
| `merge.py`, `musicxml.py` | join pages; read/write `.musicxml` / `.mxl` |

## Licences

TransNote calls homr and Audiveris as separate programs. Both are licensed
under the AGPL-3.0.
