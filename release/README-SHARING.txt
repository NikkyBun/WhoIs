WHOIS Nameservers — how to share it
===================================

This folder has TWO installers. Pick based on who you're giving it to.


1) whois-nameservers_1.0_amd64.deb
----------------------------------
Best for friends on Linux Mint / Ubuntu / Debian (64-bit Intel/AMD).

They just DOUBLE-CLICK the .deb -> the system installer opens -> "Install"
-> password. It adds "WHOIS Nameservers" to the applications menu with the
icon. No Python needed (the binary is self-contained).

  Install from a terminal instead:  sudo apt install ./whois-nameservers_1.0_amd64.deb
  Uninstall:                        sudo apt remove whois-nameservers

  Works on:  64-bit (amd64) Debian-family Linux, same or newer than the build
             machine's glibc.
  Won't run: Windows, macOS, ARM (Raspberry Pi etc.), or non-amd64 systems.


2) whois-nameservers-1.0-src.tar.gz
-----------------------------------
Best for ANY other Linux (Fedora, Arch, ARM, older or newer systems).

They extract it and run:  bash install.sh
This BUILDS a binary tailored to their machine, then installs it under their
home folder (no root/password needed) with a menu entry + icon. If they lack
the build tools, it automatically falls back to a python3 launcher, so it
still ends up working.

  Fast no-build install:  bash install.sh --no-build
  Uninstall:              bash install.sh --uninstall

  Needs:  python3 + tkinter (almost always already on Linux desktops);
          for the build, also python3-venv + pip + internet (one-time, ~1 min).


3) whois-nameservers-1.0-windows-buildkit.zip
---------------------------------------------
For Windows 10/11 users.

A Windows .exe must be built ON Windows (PyInstaller cannot cross-compile
from Linux). This kit makes that one-click: the recipient installs Python,
double-clicks build_windows.bat, and gets dist\WHOIS-Nameservers.exe (a
self-contained, double-clickable app with the icon embedded). An optional
Inno Setup script (installer.iss) turns it into a classic Setup.exe wizard
with a Start Menu entry and uninstaller. See README-WINDOWS.txt inside.

  Needs (on Windows): Python 3 from python.org ("Add to PATH"), internet
  once to fetch PyInstaller. The resulting .exe needs no Python to run.


For macOS users
---------------
No prebuilt option here. Either send them whois_nameservers.py (inside the
.tar.gz) to run with  python3 whois_nameservers.py  (pure standard library,
needs Python 3 + tkinter), or build a .app ON a Mac with PyInstaller.


Both installers register the same app: "WHOIS Nameservers" in the Network /
Utility menu category. The app needs an internet connection to do its
WHOIS/DNS lookups.
