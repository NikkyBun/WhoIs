#!/usr/bin/env bash
# rips out a per user whois nameservers install, the kind that install.sh sets up.
set -euo pipefail

SLUG="whois-nameservers"
APP_DIR="$HOME/.local/share/$SLUG"
DESKTOP_FILE="$HOME/.local/share/applications/$SLUG.desktop"
ICON="$HOME/.local/share/icons/hicolor/256x256/apps/$SLUG.png"

printf '\033[1;34m==>\033[0m Removing WHOIS Nameservers ...\n'
rm -rf "$APP_DIR"
rm -f  "$DESKTOP_FILE" "$ICON"

if command -v xdg-user-dir >/dev/null 2>&1; then
    DESK="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
    [ -n "$DESK" ] && rm -f "$DESK/$SLUG.desktop"
fi

command -v update-desktop-database >/dev/null 2>&1 && \
    update-desktop-database -q "$HOME/.local/share/applications" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    gtk-update-icon-cache -q -t -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

printf '\033[1;32m OK\033[0m Uninstalled.\n'
