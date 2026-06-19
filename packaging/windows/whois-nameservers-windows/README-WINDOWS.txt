WHOIS Nameservers — Windows build kit
=====================================

A Windows .exe must be built ON a Windows PC (PyInstaller cannot build a
Windows program from Linux/Mac). This kit makes that a one-click job.

You need this kit on a Windows 10/11 PC.


THE EASY WAY — get a double-clickable .exe
------------------------------------------
1. Install Python 3 (once) from:  https://www.python.org/downloads/
   IMPORTANT: on the first setup screen, tick "Add python.exe to PATH".
   (Python's installer already includes tkinter — nothing else to add.)

2. Double-click  build_windows.bat
   It builds everything in an isolated environment and produces:

        dist\WHOIS-Nameservers.exe

3. Double-click  dist\WHOIS-Nameservers.exe  to run the app.
   The icon is embedded in the .exe. You can copy that single .exe
   anywhere, or send it to other Windows users — it is self-contained
   (no Python needed to RUN it; Python is only needed to BUILD it).


OPTIONAL — make a proper setup installer
----------------------------------------
If you want a classic "Setup.exe" wizard (Start Menu entry, Desktop
shortcut, and an uninstaller in Add/Remove Programs):

1. Build the .exe first (steps above).
2. Install Inno Setup (free):  https://jrsoftware.org/isdl.php
3. Right-click  installer.iss  ->  Compile.
   The result appears in:  installer-output\WHOIS-Nameservers-Setup.exe

That Setup.exe is what you hand to other people: they double-click it and
the app installs per-user (no administrator rights required).


NOTES
-----
* Needs an internet connection the first time (to download PyInstaller),
  and to perform WHOIS/DNS lookups when running.
* After building you may delete the .buildenv and build folders and the
  WHOIS-Nameservers.spec file; only the dist folder matters.
* 64-bit Windows recommended. The .exe matches the Python you build with
  (install 64-bit Python for a 64-bit .exe).


FILES IN THIS KIT
-----------------
  whois_nameservers.py   the application (pure standard library)
  whois_icon.ico         the Windows app icon (embedded into the .exe)
  whois_icon.png         the icon as PNG (reference)
  build_windows.bat      one-click builder -> dist\WHOIS-Nameservers.exe
  installer.iss          Inno Setup script -> WHOIS-Nameservers-Setup.exe
  README-WINDOWS.txt     this file
