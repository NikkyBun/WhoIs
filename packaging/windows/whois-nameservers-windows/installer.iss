; Inno Setup script for WHOIS Nameservers
; ---------------------------------------------------------------------------
; HOW TO USE:
;   1. First build the .exe:  double-click build_windows.bat
;      (this creates  dist\WHOIS-Nameservers.exe)
;   2. Install Inno Setup:    https://jrsoftware.org/isdl.php
;   3. Right-click this file -> "Compile"  (or open it in Inno Setup and press F9)
;   4. The finished installer appears in:  installer-output\WHOIS-Nameservers-Setup.exe
;
; The installer is per-user (no administrator rights required).
; ---------------------------------------------------------------------------

[Setup]
AppName=WHOIS Nameservers
AppVersion=1.0
AppPublisher=Galaxynet
DefaultDirName={localappdata}\Programs\WHOIS Nameservers
DefaultGroupName=WHOIS Nameservers
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\WHOIS-Nameservers.exe
OutputDir=installer-output
OutputBaseFilename=WHOIS-Nameservers-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
SetupIconFile=whois_icon.ico
WizardStyle=modern

[Files]
Source: "dist\WHOIS-Nameservers.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\WHOIS Nameservers"; Filename: "{app}\WHOIS-Nameservers.exe"
Name: "{group}\Uninstall WHOIS Nameservers"; Filename: "{uninstallexe}"
Name: "{userdesktop}\WHOIS Nameservers"; Filename: "{app}\WHOIS-Nameservers.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\WHOIS-Nameservers.exe"; Description: "Launch WHOIS Nameservers now"; Flags: nowait postinstall skipifsilent
