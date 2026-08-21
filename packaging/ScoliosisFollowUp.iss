#define AppName "Scoliosis Follow-Up"
#ifndef AppVersion
  #define AppVersion Trim(FileRead(FileOpen(AddBackslash(SourcePath) + "..\VERSION")))
#endif
#define AppPublisher "Yusuf Can ÖZDEMİR"
#define AppURL "https://bio.link/yusufcanozdemir"
#define AppExeName "ScoliosisFollowUp.exe"

#ifdef AcceptanceBuild
  #define ConfiguredAppId "{{A6D3BC41-9F02-4C87-AF0E-6B8E8D6C11F4}"
  #define ConfiguredDefaultDirName "{localappdata}\ScoliosisFollowUp-Acceptance\app"
  #define ConfiguredPrivileges "lowest"
  #define ConfiguredOutputDir "..\build\acceptance-installer"
  #define ConfiguredOutputBaseFilename "ScoliosisFollowUp_Acceptance_Setup"
#else
  #define ConfiguredAppId "{{F8B1A3C0-2A6B-4E12-BA64-1789D57E0B25}"
  #define ConfiguredDefaultDirName "{autopf}\Scoliosis Follow-Up"
  #define ConfiguredPrivileges "admin"
  #define ConfiguredOutputDir "..\installer"
  #define ConfiguredOutputBaseFilename "ScoliosisFollowUp_Setup"
#endif

[Setup]
AppId={#ConfiguredAppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
DefaultDirName={#ConfiguredDefaultDirName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir={#ConfiguredOutputDir}
OutputBaseFilename={#ConfiguredOutputBaseFilename}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\resources\branding\ScoliosisFollowUp.ico
; Kod dosyaları Program Files altında normal kullanıcılar tarafından
; değiştirilemez. Hasta verileri yine %LOCALAPPDATA% altında tutulur.
PrivilegesRequired={#ConfiguredPrivileges}
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Files]
Source: "..\dist\ScoliosisFollowUp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Kısayol simgesini EXE'nin Windows simge önbelleğine bırakmak yerine ayrı
; ICO dosyasına bağla. Böylece masaüstü ve Başlat menüsünde boş simge oluşmaz.
Source: "..\resources\branding\ScoliosisFollowUp.ico"; DestDir: "{app}"; DestName: "ScoliosisFollowUp.ico"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\ScoliosisFollowUp.ico"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\ScoliosisFollowUp.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek seçenekler:"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{#AppName} uygulamasını başlat"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Hasta verileri ve lisans durumu %LOCALAPPDATA%\ScoliosisFollowUp altında
; tutulur; kaldırma işlemi onları kasıtlı olarak silmez.

