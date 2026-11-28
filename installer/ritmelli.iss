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

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; the _internal\ and bin\ of the version before go whole, so none of its files stays
; behind. microfone\, atualizacao\ and vozes\ stay: the audio service holds the filter DLL,
; the update task runs this setup from atualizacao\, and the voices are 325 MB
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\bin"

[Files]
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

#ifdef TestBuild
[Code]
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
