#!/usr/bin/env bash
# Setup for the Claude Code cloud environment (Ubuntu 24.04, x86_64) — or any
# Ubuntu machine. Installs both OMR engines and LilyPond.
#
# Paste the contents of this file into the environment's "Setup script"
# (cloud environment menu → Edit), or run it by hand:  sudo ./scripts/setup-cloud.sh
#
# Network: needs PyPI, the Ubuntu package mirrors and GitHub release downloads
# (github.com/…/releases/download → release-assets.githubusercontent.com).
set -euo pipefail

AUDIVERIS_FALLBACK_VERSION="5.11.0"
SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"
export DEBIAN_FRONTEND=noninteractive

echo "== System packages (LilyPond for synthetic test pages)"
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq --no-install-recommends lilypond curl ca-certificates >/dev/null

echo "== Audiveris"
if [ -x /opt/audiveris/bin/Audiveris ]; then
    echo "   already installed"
else
    AUD_VERSION="$(curl -fsSL https://api.github.com/repos/Audiveris/audiveris/releases/latest 2>/dev/null \
        | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -1 || true)"
    AUD_VERSION="${AUD_VERSION:-$AUDIVERIS_FALLBACK_VERSION}"
    . /etc/os-release
    DEB="Audiveris-${AUD_VERSION}-ubuntu${VERSION_ID}-x86_64.deb"
    TMP="$(mktemp -d)"
    curl -fsSL -o "$TMP/$DEB" "https://github.com/Audiveris/audiveris/releases/download/${AUD_VERSION}/${DEB}"
    # The package registers a desktop menu entry; headless containers lack the folders for it.
    $SUDO mkdir -p /usr/share/desktop-directories /usr/share/applications
    $SUDO apt-get install -y -qq "$TMP/$DEB" >/dev/null || $SUDO dpkg --configure -a
    rm -rf "$TMP"
    echo "   installed Audiveris ${AUD_VERSION}"
fi

echo "== uv + homr"
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi
uv tool install 'homr[cpu]' >/dev/null 2>&1 || uv tool upgrade homr >/dev/null
"$HOME/.local/bin/homr" --init   # downloads the models once

echo "== Done. In the repository run:  uv run transnote doctor"
