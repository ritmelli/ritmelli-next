; The setup of Ritmelli, for Inno Setup 6.7.3. build.ps1 compiles it with /DVersion, /DApp
; (the frozen dist\ritmelli) and, for a test build, /DTestBuild.
; The AppId, the 64-bit mode, the folder, the language names, the task, the firewall rule,
; the shortcut and the five RunOnceId are those v0.7.0 left on each PC: with the same ones,
; this setup updates v0.7.0 in place and its uninstaller undoes both.

[Setup]
AppId={{320EB2BD-48BC-420D-8F52-C22F644E47D4}
AppName=Ritmelli
AppVersion={#Version}
AppVerName=Ritmelli {#Version}
AppPublisher=Behling Informática Ltda.
AppCopyright=Software livre sob a GPLv3 / Free software under the GPLv3
VersionInfoVersion={#Version}
; the folder of the installation before, which Inno reads from its uninstall key; no page
; to pick another
DefaultDirName={autopf}\Ritmelli
UsePreviousAppDir=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
; the firewall and the filter of the microphones need an administrator
PrivilegesRequired=admin
; x64 Windows only: the filter DLL is x64, and on ARM Windows audiodg.exe does not load it
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
OutputBaseFilename=Ritmelli-{#Version}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=auto
; the open app holds its files: the setup closes it, and never starts it again as the
; administrator
CloseApplications=force
CloseApplicationsFilter=*.exe,*.dll,*.pyd
RestartApplications=no
UninstallDisplayIcon={app}\ritmelli.exe
UninstallDisplayName=Ritmelli
SetupLogging=yes
SetupIconFile={#App}\_internal\icone\ritmelli.ico
; the images of v0.7.0, at 100% and 200%
WizardSmallImageFile=wizard-small-55.png,wizard-small-110.png
WizardImageFile=wizard-large-164.png,wizard-large-328.png
; Explorer keeps the icon of a shortcut by the path of the exe, which stays the same:
; without this, the shortcut kept the old icon after an update
ChangesAssociations=yes

[Languages]
; the license on an information page: the GPLv3 needs no accepting
Name: "en"; MessagesFile: "compiler:Default.isl"; InfoBeforeFile: "license-en.txt"
Name: "pt"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"; InfoBeforeFile: "license-pt.txt"

[CustomMessages]
pt.Open=Abrir o Ritmelli
en.Open=Open Ritmelli
pt.Firewall=Liberando o Ritmelli no firewall para que o celular possa se conectar ao computador...
en.Firewall=Allowing Ritmelli through the firewall so your phone can connect to the computer...
pt.UnprotectedFolder=O Ritmelli não pode ser instalado em %1, porque essa pasta não está protegida contra alterações de outros usuários e programas (%2).%n%nAs tarefas do Ritmelli rodam como sistema e só usam uma pasta que apenas os administradores podem alterar.
en.UnprotectedFolder=Ritmelli can't be installed in %1, because that folder isn't protected from changes by other users and programs (%2).%n%nRitmelli's tasks run as the system and only use a folder that only administrators can change.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; the _internal\ and bin\ of the version before go whole, so none of its files stays
; behind. microfone\, atualizacao\ and vozes\ stay: the audio service holds the filter DLL,
; the update task runs this setup from atualizacao\, and the voices are 325 MB
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\bin"

[Files]
; the protected folder rule, which [Code] runs from {tmp}. First in [Files]: with the solid
; compression, a file at the end would come out only after the whole app
Source: "protected_folder.ps1"; Flags: dontcopy
; the filter DLL comes only inside _internal\microfone: the mic setup copies it to
; {app}\microfone after it stops the audio service, and here the Restart Manager would try
; to close audiodg.exe
Source: "{#App}\*"; DestDir: "{app}"; Excludes: "\bin"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\Ritmelli"; Filename: "{app}\ritmelli.exe"
Name: "{autodesktop}\Ritmelli"; Filename: "{app}\ritmelli.exe"; Tasks: desktopicon

[Run]
; the phone reaches the PC on the home network. Private and public: many home Wi-Fi
; networks are public in Windows, and private alone left the phone out
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Ritmelli"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""Ritmelli"" dir=in action=allow program=""{app}\ritmelli.exe"" enable=yes profile=private,public"; StatusMsg: "{cm:Firewall}"; Flags: runhidden
; as the person who installed, not as the administrator
Filename: "{app}\ritmelli.exe"; Description: "{cm:Open}"; Flags: postinstall nowait skipifsilent runasoriginaluser

[UninstallRun]
; Of the lines with one RunOnceId in the uninstall log, only the newest runs: so the lines
; older setups left never run against this exe. The update task goes first: after the
; taskkill, a round waiting for Ritmelli to close would run the setup amid the uninstall.
Filename: "{app}\ritmelli.exe"; Parameters: "--atualizador remove"; Flags: runhidden; RunOnceId: "Atualizador"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM ritmelli.exe"; Flags: runhidden; RunOnceId: "Fecha"
Filename: "{app}\ritmelli.exe"; Parameters: "--microfone remove"; Flags: runhidden; RunOnceId: "Microfone"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Ritmelli"""; Flags: runhidden; RunOnceId: "Firewall"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Vitrola"""; Flags: runhidden; RunOnceId: "FirewallVitrola"

[UninstallDelete]
; what the update task downloaded: the setups, its state and its log
Type: filesandordirs; Name: "{app}\atualizacao"
; the voices v0.7.0 downloaded, which an install leaves in place
Type: filesandordirs; Name: "{app}\vozes"

[Code]
// The text in PowerShell single quotes: each single quote doubled, the typographic ones too,
// which PowerShell also reads as single quotes (U+2018 to U+201B)
function PsQuote(S: String): String;
begin
  StringChangeEx(S, '''', '''''', True);
  StringChangeEx(S, #$2018, #$2018#$2018, True);
  StringChangeEx(S, #$2019, #$2019#$2019, True);
  StringChangeEx(S, #$201A, #$201A#$201A, True);
  StringChangeEx(S, #$201B, #$201B#$201B, True);
  Result := '''' + S + '''';
end;

// Runs a .ps1 of the setup, extracted to {tmp}, as text by the system PowerShell: the script
// execution policy of the PC does not count. Args come quoted. The .ps1 answers in the file
// Answer; '' without an answer.
function RunPs(Script, Args, Answer: String): String;
var
  ResultCode: Integer;
  Content: AnsiString;
begin
  Result := '';
  // no Windows path has a double quote: with one, the command in double quotes would end midway
  if (Pos('"', Args) > 0) or (Pos('"', Answer) > 0) then begin
    Log(Script + ': argument with a double quote refused');
    Exit;
  end;
  ExtractTemporaryFile(Script);
  // the answer of a run before never counts for this one
  if FileExists(Answer) and not DeleteFile(Answer) then begin
    Log(Script + ': could not remove the previous answer ' + Answer);
    Exit;
  end;
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
              '-NoProfile -NonInteractive -Command "& ([scriptblock]::Create([IO.File]::ReadAllText(' +
              PsQuote(ExpandConstant('{tmp}\') + Script) + '))) ' + Args + ' -Answer ' + PsQuote(Answer) + '"',
              '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    Log(Script + ': PowerShell did not run (' + SysErrorMessage(ResultCode) + ')')
  else if ResultCode <> 0 then
    Log(Script + ': PowerShell exited with ' + IntToStr(ResultCode))
  else if LoadStringFromFile(Answer, Content) then
    Result := Trim(String(Content));
end;

// The protected folder rule (protected_folder.ps1) with the root {autopf}: '' if the folder
// passes; else, the reason
function UnprotectedReason(Folder: String): String;
begin
  Result := RunPs('protected_folder.ps1', '-Folder ' + PsQuote(Folder) + ' -Root ' + PsQuote(ExpandConstant('{autopf}')),
                  ExpandConstant('{tmp}\protected_folder.txt'));
  if Result = 'OK' then
    Result := ''
  else if Result = '' then
    Result := 'the check did not answer';
  if Result = '' then
    Log('protected folder: ' + Folder)
  else
    Log('unprotected folder: ' + Folder + ': ' + Result);
end;

// Before any file changes: the destination, a /DIR= too, passes the rule the exe checks
// before each task run, or the setup stops here, and in silence exits with 7
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Destination, Reason: String;
begin
  Result := '';
  Destination := WizardDirValue;
  Reason := UnprotectedReason(Destination);
  if Reason <> '' then
    Result := FmtMessage(CustomMessage('UnprotectedFolder'), [Destination, Reason]);
end;

#ifdef TestBuild
// A test build installs only on a PC with the hook, which points the update task at a test
// manifest. On any other PC it changes nothing and exits with 1: whoever runs it by hand
// keeps the version they have, and is never left on one above every 0.7.x.
function InitializeSetup: Boolean;
var
  Manifest: String;
begin
  Result := RegQueryStringValue(HKLM64, 'SOFTWARE\Ritmelli\Atualizador', 'Manifesto', Manifest) and (Manifest <> '');
  if not Result then
    Log('test build: no Manifesto in HKLM\SOFTWARE\Ritmelli\Atualizador, so nothing is installed');
end;
#endif
