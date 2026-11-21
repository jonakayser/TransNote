#!/usr/bin/env bash
# One-time setup of TransNote on a Mac.
#
#   ./scripts/setup-mac.sh          # asks before each download
#   ./scripts/setup-mac.sh --yes    # no questions
#
# Installs: uv, TransNote (command `transnote`), homr (+ its models), Audiveris.
# Also builds ~/Applications/TransNote.app.
# Optional: LilyPond (only needed to generate synthetic test pages).
# Safe to run again: it skips what is already there.
#
# Note: macOS ships bash 3.2, so this script avoids newer bash features.
set -euo pipefail

AUDIVERIS_FALLBACK_VERSION="5.11.0"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ASSUME_YES=0
[ "${1:-}" = "--yes" ] && ASSUME_YES=1

bold() { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
ask() {
    [ "$ASSUME_YES" = 1 ] && return 0
    printf '  %s [y/N] ' "$1"
    read -r reply </dev/tty || return 1
    case "$reply" in [yY]*) return 0 ;; *) return 1 ;; esac
}

if [ "$(uname -s)" != "Darwin" ]; then
    echo "This script is for macOS. In the cloud/Linux use scripts/setup-cloud.sh." >&2
    exit 1
fi
ARCH="$(uname -m)"   # arm64 (Apple Silicon) or x86_64 (Intel)

# --- 1. uv ------------------------------------------------------------------------
bold "1/5  uv (Python project manager)"
if command -v uv >/dev/null 2>&1; then
    ok "uv $(uv --version | awk '{print $2}')"
elif command -v brew >/dev/null 2>&1; then
    brew install uv
else
    warn "Homebrew not found; using the official uv installer"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# --- 2. TransNote ----------------------------------------------------------------
bold "2/5  TransNote"
cd "$REPO_DIR"
uv sync
# Puts `transnote` on your PATH; code changes in this folder take effect immediately.
uv tool install --force --editable "$REPO_DIR" >/dev/null
ok "transnote installed ($(command -v transnote || echo "$HOME/.local/bin/transnote"))"
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) warn "Add ~/.local/bin to your PATH:  uv tool update-shell   (then open a new terminal)" ;;
esac

# --- 3. homr ----------------------------------------------------------------------
bold "3/5  homr (OMR for photos)"
if command -v homr >/dev/null 2>&1 || [ -x "$HOME/.local/bin/homr" ]; then
    ok "homr already installed (update: uv tool upgrade homr)"
else
    uv tool install 'homr[cpu]'
fi
echo "  Downloading homr's models if needed (only the first time, a few hundred MB) …"
HOMR="$(command -v homr || echo "$HOME/.local/bin/homr")"
"$HOMR" --init
ok "homr ready"

# --- 4. Audiveris -----------------------------------------------------------------
bold "4/5  Audiveris (OMR for scans)"
APP="/Applications/Audiveris.app"
if [ -d "$APP" ] || [ -d "$HOME/Applications/Audiveris.app" ]; then
    ok "Audiveris found"
else
    AUD_VERSION="$(curl -fsSL https://api.github.com/repos/Audiveris/audiveris/releases/latest 2>/dev/null \
        | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1 || true)"
    AUD_VERSION="${AUD_VERSION:-$AUDIVERIS_FALLBACK_VERSION}"
    DMG="Audiveris-${AUD_VERSION}-macosx-${ARCH}.dmg"
    URL="https://github.com/Audiveris/audiveris/releases/download/${AUD_VERSION}/${DMG}"
    if ask "Download and install Audiveris ${AUD_VERSION} (${ARCH}, ~100 MB) into /Applications?"; then
        TMP="$(mktemp -d)"
        trap 'hdiutil detach -quiet "$TMP/mnt" 2>/dev/null || true; rm -rf "$TMP"' EXIT
        curl -fL --progress-bar -o "$TMP/$DMG" "$URL"
        hdiutil attach -nobrowse -quiet -mountpoint "$TMP/mnt" "$TMP/$DMG"
        cp -R "$TMP/mnt/Audiveris.app" /Applications/
        hdiutil detach -quiet "$TMP/mnt"
        # The app is not signed by Apple. Files downloaded with curl are normally
        # not quarantined, but clear the flag in case macOS set it.
        xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
        ok "Audiveris ${AUD_VERSION} installed in /Applications"
    else
        warn "Skipped. Download the ${ARCH} .dmg manually from"
        warn "https://github.com/Audiveris/audiveris/releases and drag Audiveris into /Applications."
        warn "If macOS refuses to open it: right-click → Open (once)."
    fi
fi

# --- 5. Optional extras -------------------------------------------------------------
bold "5/5  Optional"
if ls -d /Applications/MuseScore*.app >/dev/null 2>&1; then
    ok "MuseScore Studio found"
else
    warn "MuseScore Studio not found (needed for --open):  brew install --cask musescore"
fi
if command -v lilypond >/dev/null 2>&1; then
    ok "LilyPond found (for synthetic test pages)"
elif command -v brew >/dev/null 2>&1 && ask "Install LilyPond (only needed for scripts/make_synthetic_samples.py)?"; then
    brew install lilypond
else
    warn "LilyPond not installed (optional)"
fi

bold "App"
"$REPO_DIR/scripts/make-mac-app.sh" || warn "Could not build TransNote.app (try ./scripts/make-mac-app.sh)"

bold "Check"
transnote doctor || "$HOME/.local/bin/transnote" doctor || true
echo
echo "Done. Open TransNote from Spotlight (⌘-Space, \"TransNote\"), or:  transnote scan my-page.jpg --open"
