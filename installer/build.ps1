# Freezes ritmelli.exe into dist\ritmelli with ritmelli.spec, by the PyInstaller of the
# build group, with our bootloaders in place of the ones it ships: the ready-made ones
# are the start of many malware files, and antivirus marks the app with them.
# Usage: build.ps1 -Version 0.900.N
param([Parameter(Mandatory)][ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version)
$ErrorActionPreference = 'Stop'

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
  $ours = Join-Path $PSScriptRoot 'bootloader\bin'
  $venv = Join-Path $env:UV_PROJECT_ENVIRONMENT 'Lib\site-packages\PyInstaller\bootloader\Windows-64bit-intel'
  $hashes = @(Get-Content (Join-Path $ours 'FONTE.txt') | Where-Object { $_ -match '^[0-9a-f]{64}  \S+\.exe$' })
  if ($hashes.Count -ne 4) { throw "FONTE.txt lists $($hashes.Count) bootloaders, not 4" }
  foreach ($line in $hashes) {
    $hash, $name = $line -split '  '
    Copy-Item (Join-Path $ours $name) $venv -Force
    $got = (Get-FileHash (Join-Path $venv $name) -Algorithm SHA256).Hash
    if ($got -ne $hash) { throw "$name in the venv has hash $got, not the $hash of FONTE.txt" }
  }
  Run 'pyinstaller' { uv run --no-sync pyinstaller --noconfirm --log-level ERROR installer\ritmelli.spec }
} finally { Pop-Location }
