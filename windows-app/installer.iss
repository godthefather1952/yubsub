#ifndef AppVersion
  #define AppVersion "0.5.1"
#endif

[Setup]
SourceDir=..
AppId={{C27D48CF-B8ED-4A0C-ADAF-30623ACD25AF}
AppName=YUBSUB
AppVersion={#AppVersion}
AppVerName=YUBSUB {#AppVersion}
AppPublisher=2.wav
AppPublisherURL=https://github.com/godthefather1952/yubsub
AppSupportURL=https://github.com/godthefather1952/yubsub/issues
DefaultDirName={localappdata}\Programs\YUBSUB
DefaultGroupName=YUBSUB
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\YUBSUB.exe
DisableProgramGroupPage=yes
WizardStyle=modern
OutputDir=dist\installer
OutputBaseFilename=YUBSUB-Setup-v{#AppVersion}
SetupIconFile=build\YUBSUB.ico
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=yes
ChangesAssociations=no

[Files]
Source: "dist\YUBSUB\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "build\MicrosoftEdgeWebView2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{autoprograms}\YUBSUB"; Filename: "{app}\YUBSUB.exe"
Name: "{autodesktop}\YUBSUB"; Filename: "{app}\YUBSUB.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{tmp}\MicrosoftEdgeWebView2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installing Microsoft Edge WebView2 Runtime..."; Flags: waituntilterminated; Check: NeedsWebView2
Filename: "{app}\YUBSUB.exe"; Description: "Launch YUBSUB"; Flags: nowait postinstall skipifsilent

[Code]
function HasWebView2(): Boolean;
var
  Ver: String;
begin
  Result :=
    (RegQueryStringValue(HKCU, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Ver) and (Ver <> '')) or
    (RegQueryStringValue(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Ver) and (Ver <> '')) or
    (RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Ver) and (Ver <> ''));
end;

function NeedsWebView2(): Boolean;
begin
  Result := not HasWebView2();
end;
