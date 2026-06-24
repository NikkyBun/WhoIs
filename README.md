# WHOIS Nameservers

A small desktop GUI (Python + tkinter, standard library only) that looks up
domain nameservers for many domains at once via WHOIS and DNS.

```
python3 whois_nameservers.py
```

## Downloads / installers

Grab a ready-to-run build from the [**Releases**](../../releases/latest) page:

| Platform | How |
|----------|-----|
| **Windows** | Download `WHOIS-Nameservers.exe` from the latest release and run it — no install needed. (Each build is also attached to its [Actions](../../actions) **Build Windows EXE** run.) |
| **Linux (Debian/Ubuntu/Mint)** | Download `whois-nameservers_2.23626_amd64.deb` from the latest release, then double-click it — or `sudo apt install ./whois-nameservers_2.23626_amd64.deb`. |
| **Linux (any distro)** | Clone the repo and run `packaging/src/whois-nameservers-2.23626/install.sh` to build + install for the local machine. |

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

## License

MIT — see [LICENSE](LICENSE). Use it however you like.
