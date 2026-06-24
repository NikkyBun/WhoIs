; the inno setup script, for whois nameservers
; ---------------------------------------------------------------------------
; how you use it:
;   1. build the .exe first, just double click build_windows.bat
;      (that one gives you  dist\WHOIS-Nameservers.exe)
;   2. then go get inno setup, off  https://jrsoftware.org/isdl.php
;   3. right click this file, and hit "Compile" (or open it up inside inno setup, and press F9)
;   4. and the finished installer, it turns up in  installer-output\WHOIS-Nameservers-Setup.exe
;
; the installer is per user, so theres no admin rights needed, none at all.
; ---------------------------------------------------------------------------

[Setup]
AppName=WHOIS Nameservers
AppVersion=2.23626
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
