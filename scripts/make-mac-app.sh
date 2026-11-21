#!/usr/bin/env bash
# Build TransNote.app: double-click → choose images → choose where to save → MuseScore.
# You can also drop images onto the app icon (or onto it in the Dock).
#
#   ./scripts/make-mac-app.sh                 # installs into ~/Applications
#   ./scripts/make-mac-app.sh /Applications   # or somewhere else
#
# Run it again after moving the repo or reinstalling transnote.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST_DIR="${1:-$HOME/Applications}"
APP="$DEST_DIR/TransNote.app"

if [ "$(uname -s)" != "Darwin" ]; then
    echo "TransNote.app can only be built on macOS." >&2
    exit 1
fi

TRANSNOTE="$(command -v transnote || true)"
[ -z "$TRANSNOTE" ] && [ -x "$HOME/.local/bin/transnote" ] && TRANSNOTE="$HOME/.local/bin/transnote"
if [ -z "$TRANSNOTE" ]; then
    echo "transnote not found. Run ./scripts/setup-mac.sh first." >&2
    exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
sed "s|__TRANSNOTE__|$TRANSNOTE|" "$REPO_DIR/app/TransNote.applescript" > "$TMP/TransNote.applescript"

mkdir -p "$DEST_DIR"
rm -rf "$APP"
osacompile -o "$APP" "$TMP/TransNote.applescript"

PLIST="$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName TransNote" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string de.kayser.transnote" "$PLIST" 2>/dev/null \
    || /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier de.kayser.transnote" "$PLIST"
# Accept only images and PDFs when files are dropped on the icon.
/usr/libexec/PlistBuddy -c "Delete :CFBundleDocumentTypes" "$PLIST" 2>/dev/null || true
/usr/libexec/PlistBuddy \
    -c "Add :CFBundleDocumentTypes array" \
    -c "Add :CFBundleDocumentTypes:0 dict" \
    -c "Add :CFBundleDocumentTypes:0:CFBundleTypeRole string Viewer" \
    -c "Add :CFBundleDocumentTypes:0:LSItemContentTypes array" \
    -c "Add :CFBundleDocumentTypes:0:LSItemContentTypes:0 string public.image" \
    -c "Add :CFBundleDocumentTypes:0:LSItemContentTypes:1 string com.adobe.pdf" \
    "$PLIST"
# Editing Info.plist invalidates osacompile's ad-hoc signature; sign again so macOS opens it.
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
touch "$APP"   # make Finder pick up the changes

echo "✓ Built $APP"
echo "  (uses $TRANSNOTE)"
echo "  Open it from Finder/Spotlight, or drag it into the Dock and drop images onto it."
