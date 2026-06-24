# WHOIS Nameservers

A small desktop GUI (Python + tkinter, standard library only) that looks up
domain nameservers for many domains at once via WHOIS and DNS.

```
python3 whois_nameservers.py
```

## Downloads / installers

| Platform | How |
|----------|-----|
| **Windows** | Built automatically in the cloud — see [Actions](../../actions) → latest **Build Windows EXE** run → download the `WHOIS-Nameservers-windows` artifact. Tagged releases also attach the `.exe`. |
| **Linux (Debian/Ubuntu/Mint)** | `packaging/` build of `whois-nameservers_2.23626_amd64.deb` (double-click to install). |
| **Linux (any distro)** | `packaging/src/` — run `install.sh` to build + install for the local machine. |

## Building the Windows .exe yourself

PyInstaller cannot cross-compile, so a Windows `.exe` must be built on Windows.
Either let the GitHub Actions workflow (`.github/workflows/build-windows.yml`)
do it in the cloud, or use the local kit in `packaging/windows/`
(`build_windows.bat`).

## Repo layout

```
whois_nameservers.py          the application (pure standard library)
whois_icon.png / .ico         app icon
build_icon.py                 regenerates the icon (needs Pillow)
packaging/deb/                Debian package source
packaging/src/                universal Linux source installer
packaging/windows/            Windows build kit (.bat + Inno Setup script)
.github/workflows/            cloud build of the Windows .exe
```
