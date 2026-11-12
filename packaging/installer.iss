; Inno Setup script for the Windows setup program. Built by `python3 tasks.py package`.
; Per-user install (no administrator rights). The library itself lives in
; %LOCALAPPDATA%\OldschoolCSDemos and is kept on uninstall unless the user says otherwise.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6E2D8B1C-41F0-4C5A-9A7E-0D3B5F18C2A4}
AppName=Oldschool CS Demos Library Replayer
AppVersion={#AppVersion}
AppVerName=Oldschool CS Demos {#AppVersion}
AppPublisher=KabaL
AppPublisherURL=https://github.com/k4b4l74/oldschool-cs-demo-library-replayer
DefaultDirName={localappdata}\Programs\Oldschool CS Demos
DefaultGroupName=Oldschool CS Demos
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=OldschoolCSDemos-Setup-{#AppVersion}
SetupIconFile=build\app.ico
UninstallDisplayIcon={app}\OldschoolCSDemos.exe
UninstallDisplayName=Oldschool CS Demos Library Replayer
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AppMutex=OldschoolCSDemosLibraryReplayer
CloseApplications=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[CustomMessages]
english.StartApp=Start Oldschool CS Demos
french.StartApp=Lancer Oldschool CS Demos
english.DeleteLibrary=Also delete your demo library (database, imported files and demo copies) in %1?%n%nChoose No to keep it for a later install.
french.DeleteLibrary=Supprimer aussi votre bibliothèque de démos (base de données, fichiers importés et copies des démos) dans %1 ?%n%nChoisissez Non pour la garder pour une prochaine installation.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\OldschoolCSDemos\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Oldschool CS Demos"; Filename: "{app}\OldschoolCSDemos.exe"
Name: "{autodesktop}\Oldschool CS Demos"; Filename: "{app}\OldschoolCSDemos.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\OldschoolCSDemos.exe"; Description: "{cm:StartApp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Data: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    Data := ExpandConstant('{localappdata}\OldschoolCSDemos');
    if DirExists(Data) and not UninstallSilent() then
      if MsgBox(FmtMessage(CustomMessage('DeleteLibrary'), [Data]), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(Data, True, True, True);
  end;
end;
