WHOIS Nameservers — installer (any Linux)
=========================================

This installs a desktop app that looks up domain nameservers via WHOIS/DNS.
It installs for the current user only — NO root/password required.

HOW TO INSTALL
--------------
1. Extract this archive (double-click the .tar.gz, or:  tar -xzf <file>.tar.gz).
2. Open the extracted folder in a terminal and run:

       bash install.sh

   (Or in your file manager: right-click install.sh -> "Run as a Program".
    Running in a terminal is recommended so you can see the progress.)

3. When it finishes, find "WHOIS Nameservers" in your applications menu,
   or use the icon placed on your Desktop.

WHAT install.sh DOES
--------------------
By default it BUILDS a standalone binary tailored to your computer
(using Python's PyInstaller) and installs it under ~/.local. This needs:
  * python3 with tkinter   (Debian/Ubuntu/Mint: sudo apt install python3-tk)
  * python3-venv + pip     (Debian/Ubuntu/Mint: sudo apt install python3-venv python3-pip)
  * an internet connection (to download PyInstaller, one time, ~1 minute)

If those build tools are not available, install.sh AUTOMATICALLY falls back to
installing a lightweight launcher that simply runs the app with your system
python3 (the app uses only the Python standard library). You can force this
fast, no-build mode yourself:

       bash install.sh --no-build

REQUIREMENTS EITHER WAY
-----------------------
You need python3 + tkinter installed (almost always already present on Linux
desktops). The app also needs internet access to perform WHOIS/DNS lookups.

UNINSTALL
---------
       bash install.sh --uninstall      (or: bash uninstall.sh)

FILES IN THIS ARCHIVE
---------------------
  whois_nameservers.py   the application (pure standard library)
  whois_icon.png         the app icon
  build_icon.py          regenerates the icon (needs Pillow; optional)
  install.sh             the installer
  uninstall.sh           the uninstaller
