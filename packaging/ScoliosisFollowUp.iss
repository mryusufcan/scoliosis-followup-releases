#define AppName "Scoliosis Follow-Up"
#define AppVersion "1.1.0"
#define AppPublisher "Yusuf Can ÖZDEMİR"
#define AppURL "https://bio.link/yusufcanozdemir"
#define AppExeName "ScoliosisFollowUp.exe"

[Setup]
AppId={{F8B1A3C0-2A6B-4E12-BA64-1789D57E0B25}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={autopf}\Scoliosis Follow-Up
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\installer
OutputBaseFilename=ScoliosisFollowUp_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Kod dosyaları Program Files altında normal kullanıcılar tarafından
; değiştirilemez. Hasta verileri yine %LOCALAPPDATA% altında tutulur.
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Files]
Source: "..\dist\ScoliosisFollowUp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek seçenekler:"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{#AppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
# Hasta verileri ve lisans durumu %LOCALAPPDATA%\ScoliosisFollowUp altında
# tutulur; kaldırma işlemi onları kasıtlı olarak silmez.
