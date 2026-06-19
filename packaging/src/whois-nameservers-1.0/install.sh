#!/usr/bin/env bash
#
# WHOIS Nameservers - per-user installer (no root required).
#
# Default mode BUILDS a standalone binary for THIS machine with PyInstaller,
# then installs it under ~/.local with a menu entry + icon. If the build tools
# are missing or the build fails, it automatically falls back to installing a
# lightweight launcher that runs the app with the system python3 (the app is
# pure standard library).
#
# Usage:
#   ./install.sh              # build a standalone binary, then install
#   ./install.sh --no-build   # skip building; install a python3 launcher
#   ./install.sh --uninstall  # remove an existing installation
#   ./install.sh --help
#
set -euo pipefail

APP_NAME="WHOIS Nameservers"
SLUG="whois-nameservers"
BIN_NAME="WHOIS-Nameservers"

# Resolve the directory this script lives in (so CWD does not matter).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

APP_DIR="$HOME/.local/share/$SLUG"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
DESKTOP_FILE="$DESKTOP_DIR/$SLUG.desktop"
BUILD_DIR="$SCRIPT_DIR/.installbuild"

c_info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
c_ok()   { printf '\033[1;32m OK\033[0m %s\n' "$*"; }
c_warn() { printf '\033[1;33m  !\033[0m %s\n' "$*"; }
c_err()  { printf '\033[1;31mERR\033[0m %s\n' "$*" >&2; }

pkg_hint() {
    # Best-effort, distro-aware install hint for missing prerequisites.
    if   command -v apt    >/dev/null 2>&1; then echo "sudo apt install $1"
    elif command -v dnf    >/dev/null 2>&1; then echo "sudo dnf install $2"
    elif command -v pacman >/dev/null 2>&1; then echo "sudo pacman -S $3"
    else echo "install the equivalent of: $1"
    fi
}

refresh_caches() {
    command -v update-desktop-database >/dev/null 2>&1 && \
        update-desktop-database -q "$DESKTOP_DIR" 2>/dev/null || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 && \
        gtk-update-icon-cache -q -t -f "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
}

uninstall() {
    c_info "Removing $APP_NAME ..."
    rm -rf "$APP_DIR"
    rm -f  "$DESKTOP_FILE"
    rm -f  "$ICON_DIR/$SLUG.png"
    # Desktop shortcut, if any (locale-aware path).
    if command -v xdg-user-dir >/dev/null 2>&1; then
        local d; d="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
        [ -n "$d" ] && rm -f "$d/$SLUG.desktop"
    fi
    refresh_caches
    c_ok "Uninstalled."
    exit 0
}

# ---- argument parsing ------------------------------------------------------
MODE="build"
for arg in "$@"; do
    case "$arg" in
        --no-build) MODE="nobuild" ;;
        --uninstall|--remove) uninstall ;;
        -h|--help)
            awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"
            exit 0 ;;
        *) c_err "Unknown option: $arg"; exit 2 ;;
    esac
done

# ---- prerequisite checks ---------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    c_err "python3 is not installed."
    c_err "Install it first: $(pkg_hint 'python3' 'python3' 'python')"
    exit 1
fi

if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
    c_err "Python's tkinter module is missing (needed to run the GUI)."
    c_err "Install it first: $(pkg_hint 'python3-tk' 'python3-tkinter' 'tk')"
    exit 1
fi
c_ok "python3 and tkinter present."

# ---- build (optional) ------------------------------------------------------
BUILT_BINARY=""
if [ "$MODE" = "build" ]; then
    c_info "Building a standalone binary for this machine (PyInstaller)..."
    build_ok=1
    rm -rf "$BUILD_DIR"
    if python3 -m venv "$BUILD_DIR/venv" >/dev/null 2>&1; then
        # shellcheck disable=SC1091
        VENV_PY="$BUILD_DIR/venv/bin/python"
        "$VENV_PY" -m pip install --upgrade pip >/dev/null 2>&1 || true
        if "$VENV_PY" -m pip install pyinstaller >/dev/null 2>&1; then
            if "$VENV_PY" -m PyInstaller --onefile --windowed \
                    --name "$BIN_NAME" --icon "$SCRIPT_DIR/whois_icon.png" \
                    --distpath "$BUILD_DIR/dist" \
                    --workpath "$BUILD_DIR/work" \
                    --specpath "$BUILD_DIR" \
                    "$SCRIPT_DIR/whois_nameservers.py" >/dev/null 2>&1; then
                BUILT_BINARY="$BUILD_DIR/dist/$BIN_NAME"
            else
                c_warn "PyInstaller build failed."; build_ok=0
            fi
        else
            c_warn "Could not install PyInstaller (no internet / no pip?)."; build_ok=0
        fi
    else
        c_warn "Could not create a build venv (is python3-venv installed?)."; build_ok=0
    fi

    if [ "$build_ok" -eq 1 ] && [ -x "$BUILT_BINARY" ]; then
        c_ok "Built standalone binary."
    else
        c_warn "Falling back to a python3 launcher (no build needed)."
        MODE="nobuild"
        BUILT_BINARY=""
    fi
fi

# ---- install files ---------------------------------------------------------
c_info "Installing into $APP_DIR ..."
mkdir -p "$APP_DIR" "$DESKTOP_DIR" "$ICON_DIR"
cp -f "$SCRIPT_DIR/whois_icon.png" "$APP_DIR/whois_icon.png"
cp -f "$SCRIPT_DIR/whois_icon.png" "$ICON_DIR/$SLUG.png"

if [ -n "$BUILT_BINARY" ]; then
    cp -f "$BUILT_BINARY" "$APP_DIR/$BIN_NAME"
    chmod +x "$APP_DIR/$BIN_NAME"
    EXEC_LINE="$APP_DIR/$BIN_NAME"
    KIND="standalone binary"
else
    cp -f "$SCRIPT_DIR/whois_nameservers.py" "$APP_DIR/whois_nameservers.py"
    EXEC_LINE="$(command -v python3) $APP_DIR/whois_nameservers.py"
    KIND="python3 launcher"
fi

# ---- desktop entry ---------------------------------------------------------
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=$APP_NAME
GenericName=Domain Nameserver Lookup
Comment=Look up domain nameservers via WHOIS/DNS
Exec=$EXEC_LINE
Icon=$APP_DIR/whois_icon.png
Terminal=false
Categories=Network;Utility;
Keywords=whois;dns;nameserver;domain;lookup;
StartupNotify=true
EOF
chmod +x "$DESKTOP_FILE"

# ---- optional Desktop shortcut --------------------------------------------
if command -v xdg-user-dir >/dev/null 2>&1; then
    DESK="$(xdg-user-dir DESKTOP 2>/dev/null || true)"
    if [ -n "$DESK" ] && [ -d "$DESK" ]; then
        cp -f "$DESKTOP_FILE" "$DESK/$SLUG.desktop"
        chmod +x "$DESK/$SLUG.desktop"
        command -v gio >/dev/null 2>&1 && \
            gio set "$DESK/$SLUG.desktop" metadata::trusted true 2>/dev/null || true
        c_ok "Placed a launcher on your Desktop."
    fi
fi

refresh_caches

# ---- clean up build artifacts ---------------------------------------------
rm -rf "$BUILD_DIR"

echo
c_ok "$APP_NAME installed as a $KIND."
echo "    Launch it from your applications menu (search \"WHOIS\"),"
echo "    the Desktop icon, or run: $EXEC_LINE"
echo "    To remove it later:  \"$SCRIPT_DIR/install.sh\" --uninstall"
