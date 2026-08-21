; Blue Band - Windows installer (Inno Setup 6)
;
;   iscc packaging\blueband.iss
;
; Run *after* PyInstaller: it packs `dist\BlueBand\` as it stands.
;
; Two decisions worth knowing before changing anything here:
;
; 1. **Per-user install, not Program Files.** No administrator prompt on a
;    laptop the jury may not have the password for, and - the technical reason
;    - the program's own folder stays writable: Streamlit serves the last saved
;    comunicati out of `static\` inside the installation, which is what the
;    "Apri il PDF" link follows (see `core.paths.served`).
;
; 2. **The jury's work is not in here.** Competitions, results and comunicati
;    live in `Documenti\BlueBand` (`core.paths.data`). Nothing in this script
;    creates or removes that folder: an uninstall takes the program away and
;    leaves the championship alone.

#define AppName "Blue Band"
#define AppExe "BlueBand.exe"
#define AppPublisher "Nicola Borghi"
#define AppUrl "https://github.com/nicoborghi/BlueBand"
; overridden from the command line by CI: iscc /DAppVersion=1.2.3 ...
#ifndef AppVersion
  #define AppVersion "0.3.0"
#endif

[Setup]
; Never change AppId: it is how Windows recognises an installed Blue Band and
; upgrades it in place instead of leaving two of them in the program list.
AppId={{81735702-4049-45C8-A1E0-AE246498E364}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; per-user: `{autopf}` resolves to %LOCALAPPDATA%\Programs under `lowest`
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=BlueBand-{#AppVersion}-setup
SetupIconFile=blueband.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
; LZMA2/max on a tree that is mostly already-compressed wheels still takes the
; installer to about a third of the folder it installs
Compression=lzma2/max
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
    GroupDescription: "{cm:AdditionalIcons}"

[Files]
; the whole PyInstaller folder, as it was built
Source: "..\dist\BlueBand\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; what the program wrote inside its own folder while it ran: the served copies
; of the last comunicati, and Python's caches. The originals are in the output
; folder the jury chose, and the championship is in Documenti.
Type: filesandordirs; Name: "{app}\static"
Type: filesandordirs; Name: "{app}\_internal\static"
