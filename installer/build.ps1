# Freezes ritmelli.exe into dist\ritmelli with ritmelli.spec, by the PyInstaller of the
# build group, with our bootloaders in place of the ones it ships: the ready-made ones
# are the start of many malware files, and antivirus marks the app with them. First it
# builds the filter with the same version and writes its sources digest next to it. Last,
# it compiles ritmelli.iss into dist\Ritmelli-<version>-setup.exe.
# Usage: build.ps1 -Version 0.900.N [-Channel test]
#   -Channel test makes a test build, whose setup refuses a PC without the hook
param(
  [Parameter(Mandatory)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version,
  [ValidateSet('test')][string]$Channel
)
$ErrorActionPreference = 'Stop'
# build_info.py names the channel by the version: the setup must do what it says
if ($Channel -eq 'test' -and $Version -notmatch '^0\.900\.\d+$') { throw "a test build is 0.900.N, not $Version" }

# PowerShell 5 makes each stderr line of a program an error: only the exit code counts
function Run($name, [scriptblock]$cmd) {
  $before = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
  try { & $cmd 2>&1 | ForEach-Object { "$_" } } finally { $ErrorActionPreference = $before }
  if ($LASTEXITCODE -ne 0) { throw "$name exited with $LASTEXITCODE" }
}

# a short path: inside a long one, a package path goes past the 260 characters of Windows
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:LOCALAPPDATA 'ritmelli-next-build'
$env:RITMELLI_VERSION = $Version
Push-Location (Split-Path $PSScriptRoot)
try {
  Run 'uv sync' { uv sync --locked --group build }
  Run 'compila.bat' { cmd /c filter\apo\compila.bat $Version }
  Run 'sources digest' { uv run --no-sync python installer\build_info.py sources filter\apo\saida\micfx.sources }
  $ours = Join-Path $PSScriptRoot 'bootloader\bin'
  $venv = Join-Path $env:UV_PROJECT_ENVIRONMENT 'Lib\site-packages\PyInstaller\bootloader\Windows-64bit-intel'
  # uv links these files to its cache: a copy over the link would change the cache too
  Remove-Item (Join-Path $venv '*.exe')
  Copy-Item (Join-Path $ours '*.exe') $venv
  $runw = (Select-String (Join-Path $ours 'FONTE.txt') -Pattern '^([0-9a-f]{64})  runw\.exe$').Matches[0].Groups[1].Value
  $got = (Get-FileHash (Join-Path $venv 'runw.exe') -Algorithm SHA256).Hash
  if ($got -ne $runw) { throw "runw.exe in the venv has hash $got, not the $runw of FONTE.txt" }
  Run 'pyinstaller' { uv run --no-sync pyinstaller --noconfirm --log-level ERROR installer\ritmelli.spec }
  & filter\apo\check_version.ps1 -Folder dist\ritmelli\_internal\microfone -Version $Version
  # the user folder first: .github/actions/inno-setup puts 6.7.3 there, and an older Inno
  # may not append to the uninstall log v0.7.0 left
  $iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" |
    Where-Object { Test-Path $_ } | Select-Object -First 1
  if (-not $iscc) { throw 'Inno Setup 6 is missing: winget install -e --id JRSoftware.InnoSetup' }
  $options = "/DVersion=$Version", "/DApp=$((Resolve-Path dist\ritmelli).Path)", "/O$((Resolve-Path dist).Path)"
  if ($Channel -eq 'test') { $options += '/DTestBuild' }
  Run 'ISCC' { & $iscc /Q @options installer\ritmelli.iss }
} finally { Pop-Location }
