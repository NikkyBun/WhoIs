@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Building WHOIS Nameservers for Windows
echo ============================================================
echo.

rem --- go find python 3, wherever it is hiding on this pc ---
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo ERROR: Python 3 was not found on this PC.
    echo.
    echo   1. Install it from  https://www.python.org/downloads/
    echo   2. During setup, TICK "Add python.exe to PATH".
    echo   3. Re-run this file.
    echo.
    pause
    exit /b 1
)
echo Using Python: %PY%
echo.

rem --- the build environment, kept off on its own, all isolated ---
echo [1/3] Creating an isolated build environment...
%PY% -m venv .buildenv
if errorlevel 1 ( echo ERROR: could not create the build venv. & pause & exit /b 1 )
call ".buildenv\Scripts\activate.bat"

rem --- now go and grab pyinstaller ---
echo [2/3] Installing PyInstaller ^(needs internet, one time^)...
python -m pip install --upgrade pip >nul
python -m pip install pyinstaller
if errorlevel 1 ( echo ERROR: pip could not install PyInstaller. & pause & exit /b 1 )

rem --- build the exe, windowed, all one single file, the icon baked right in ---
echo [3/3] Building WHOIS-Nameservers.exe...
pyinstaller --onefile --windowed --name "WHOIS-Nameservers" --icon "whois_icon.ico" whois_nameservers.py
if errorlevel 1 ( echo ERROR: the PyInstaller build failed. & pause & exit /b 1 )

echo.
echo ============================================================
echo   DONE
echo.
echo   Your app:  "%~dp0dist\WHOIS-Nameservers.exe"
echo   Double-click it to run. The icon is embedded in the .exe.
echo ============================================================
echo.
echo Optional: to make a real setup installer (Start Menu entry +
echo uninstaller), install Inno Setup from https://jrsoftware.org/isdl.php
echo then right-click installer.iss -^> Compile.
echo.
echo You may delete the .buildenv and build folders and the .spec file;
echo only the dist folder is needed.
echo.
pause
