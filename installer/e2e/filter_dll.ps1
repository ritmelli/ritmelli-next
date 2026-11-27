# The filter DLL placed twice by machine/filter_dll.py, as the mic setup does, in a
# proof folder, on Windows as an administrator, with the audio service on. The second
# DLL has other bytes, as the next version's does, and the same sources digest: the
# installed one keeps its sha256 and its date, the audio service keeps its process, and
# place exits with 0. It registers the DLL of the proof folder, and refuses a PC
# that has the key already, as a PC with Ritmelli does.
# Usage: filter_dll.ps1 -Dll <micfx.dll, with micfx.sources next to it> [-Proof <folder>] [-Key <path in HKLM>]
param(
  [Parameter(Mandatory)][string]$Dll,
  [string]$Proof = "$env:RUNNER_TEMP\filter-dll",
  [string]$Key = 'SOFTWARE\Ritmelli\Microfone'
)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path "$PSScriptRoot\..\.."
$Dll = (Resolve-Path $Dll).Path
$sources = Join-Path (Split-Path $Dll) 'micfx.sources'
if (Test-Path "HKLM:\$Key") { throw "HKLM\$Key is there already: run this on a PC without Ritmelli" }
if (Test-Path $Proof) { throw "$Proof is there already" }
if ((Get-Service audiosrv).Status -ne 'Running') {
  Set-Service audiosrv -StartupType Manual
  Start-Service audiosrv
}
$folder, $next = (Join-Path $Proof 'microfone'), (Join-Path $Proof 'next')
$installed = Join-Path $folder 'micfx.dll'

# Exits with 1 when it stopped the audio service to replace the DLL.
function Place($dll) {
  $out = uv run --project $root python -c 'import sys; from ritmelli.machine import filter_dll; sys.exit(filter_dll.place(*sys.argv[1:]))' $dll $folder $Key
  if ($LASTEXITCODE -ne 0) { throw "filter_dll.place exited with $LASTEXITCODE`: $out" }
}
function Audio { (Get-CimInstance Win32_Service -Filter "Name='audiosrv'").ProcessId }
function Installed { "$((Get-FileHash $installed).Hash) $((Get-Item $installed).LastWriteTimeUtc.ToString('o'))" }

try {
  $audio = Audio
  Place $Dll
  $first = Installed
  $null = New-Item -ItemType Directory $next
  Copy-Item $Dll, $sources $next
  $tail = [IO.File]::Open("$next\micfx.dll", 'Append'); $tail.WriteByte(0); $tail.Close()
  Place "$next\micfx.dll"
  if ((Installed) -ne $first) { throw "the installed DLL was $first, and is $(Installed)" }
  if ((Audio) -ne $audio) { throw "the audio service ran as process $audio, and runs as $(Audio)" }
  "placed twice: the DLL kept $first, and the audio service its process $audio"
} finally {
  if (Test-Path "HKLM:\$Key") { Remove-Item "HKLM:\$Key" -Recurse -Force }
  if (Test-Path $Proof) { Remove-Item $Proof -Recurse -Force }
}
