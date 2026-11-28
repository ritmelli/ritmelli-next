# The protected folder rule on the disk, as an administrator. Each case runs the setup's side
# (protected_folder.ps1, by the system PowerShell as the setup runs it) and the exe's
# (machine/protected_folder.py), and both must give the verdict the case expects. The cases
# sit in a new Program Files\RitmelliTeste-<random>, which inherits the ACL of Program Files
# and is owned by Administrators, like the folder the setup makes. The finally removes it.
# With -Installed, the folder of an installed Ritmelli must pass on both sides too.
# Usage: protected_verdict.ps1 [-Installed <folder>]
#Requires -RunAsAdministrator
param([string]$Installed)
$ErrorActionPreference = 'Stop'
$repo = Resolve-Path "$PSScriptRoot\..\.."
$rule = (Resolve-Path "$PSScriptRoot\..\protected_folder.ps1").Path
$root = $env:ProgramW6432
$answer = Join-Path $env:TEMP "protected-verdict-$PID.txt"
$base = Join-Path $root "RitmelliTeste-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
$log = "$base\microfone\log"
$failed = @()

function Get-SetupVerdict([string]$Folder) {
  if (Test-Path -LiteralPath $answer) { Remove-Item -LiteralPath $answer }
  $quoted = $rule, $Folder, $root, $answer | ForEach-Object { "'" + $_.Replace("'", "''") + "'" }
  $command = "& ([scriptblock]::Create([IO.File]::ReadAllText($($quoted[0])))) -Folder $($quoted[1]) -Root $($quoted[2]) -Answer $($quoted[3])"
  & "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command $command | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "powershell exited with $LASTEXITCODE" }
  [IO.File]::ReadAllText($answer).Trim()
}

function Get-ExeVerdict([string]$Folder) {
  $code = 'import sys; from ritmelli.machine.protected_folder import unprotected_reason as r; print(r(*sys.argv[1:]) or ''OK'')'
  $out = uv run --project $repo python -c $code $Folder $root
  if ($LASTEXITCODE -ne 0) { throw "python exited with $LASTEXITCODE" }
  "$out"
}

function Assert-Verdict([string]$Name, [bool]$Passes, [string]$Folder = $base) {
  $exe, $setup = (Get-ExeVerdict $Folder), (Get-SetupVerdict $Folder)
  $ok = (($exe -eq 'OK') -eq $Passes) -and (($setup -eq 'OK') -eq $Passes)
  "[$(if ($ok) { 'ok' } else { 'FAILED' })] $(if ($Passes) { 'passes' } else { 'fails' }): $Name. exe: $exe; setup: $setup"
  if (-not $ok) { $script:failed += $Name }
}

function Invoke-Icacls {
  $out = & "$env:SystemRoot\System32\icacls.exe" @args
  if ($LASTEXITCODE -ne 0) { throw "icacls $args`: $out" }
}

function New-Junction([string]$Path, [string]$Target) {
  New-Item -ItemType Junction -Path $Path -Target $Target | Out-Null
  $script:junctions += $Path
}

$junctions = @()
try {
  New-Item -ItemType File -Force "$base\ritmelli.exe", "$base\_internal\python312.dll" | Out-Null
  New-Item -ItemType Directory $log | Out-Null
  Invoke-Icacls $log /grant '*S-1-5-19:(OI)(CI)M'
  New-Item -ItemType File "$log\micfx.log", "$log\micfx.log.1" | Out-Null
  # the log audiodg.exe makes when it rotates: LocalService owns it, with the full control of CREATOR OWNER
  Invoke-Icacls "$log\micfx.log.1" /setowner '*S-1-5-19'
  Invoke-Icacls "$log\micfx.log.1" /grant '*S-1-5-19:F'
  Assert-Verdict 'the folder as the setup makes it, with LocalService in microfone\log' $true

  Invoke-Icacls $base /grant '*S-1-5-32-545:(OI)(CI)M'
  Assert-Verdict 'Users write to the folder' $false
  Invoke-Icacls $base /remove:g '*S-1-5-32-545'
  Assert-Verdict 'the folder again, without the write of Users' $true

  New-Item -ItemType Directory "$base\atualizacao" | Out-Null
  Invoke-Icacls "$base\atualizacao" /grant '*S-1-5-32-545:(OI)(CI)M'
  Assert-Verdict 'Users write to atualizacao\' $false
  Remove-Item -LiteralPath "$base\atualizacao" -Recurse

  Invoke-Icacls "$base\_internal" /grant '*S-1-5-19:(OI)(CI)M'
  Assert-Verdict 'LocalService writes outside microfone\log' $false
  Invoke-Icacls "$base\_internal" /remove:g '*S-1-5-19'

  New-Junction "$base-j" $base
  Assert-Verdict 'a junction on the path' $false "$base-j"
  foreach ($inside in "$base\_internal\j", "$log\j") {
    New-Junction $inside "$base\microfone"
    Assert-Verdict "a junction at $($inside.Substring($base.Length + 1))" $false
    [IO.Directory]::Delete($inside)
  }
  Assert-Verdict 'the folder without the junctions inside' $true

  Invoke-Icacls $base /setowner ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
  Assert-Verdict 'owned by the account that runs this' $false
  Invoke-Icacls $base /setowner '*S-1-5-32-544'

  New-Item -ItemType Directory "$base\parent\app" | Out-Null
  Invoke-Icacls "$base\parent" /grant '*S-1-5-32-545:(DC)'
  Assert-Verdict 'in a parent that lets Users delete its children' $false "$base\parent\app"

  New-Item -ItemType Directory "$base\writable" | Out-Null
  Invoke-Icacls "$base\writable" /grant '*S-1-5-32-545:(OI)(CI)M'
  Assert-Verdict 'not there yet, in a parent Users write to' $false "$base\writable\new"

  if ($Installed) { Assert-Verdict "the installed Ritmelli in $Installed" $true $Installed }
} finally {
  foreach ($j in $junctions) {
    if (Test-Path -LiteralPath $j) { [IO.Directory]::Delete($j) }
  }
  & "$env:SystemRoot\System32\icacls.exe" $base /setowner '*S-1-5-32-544' /t /c /q | Out-Null
  Remove-Item -LiteralPath $base -Recurse -Force -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath $answer -ErrorAction SilentlyContinue
}
if (Test-Path -LiteralPath $base) { throw "$base is still there" }
if ($failed) { throw "the cases above that failed: $($failed -join '; ')" }
'each case got the verdict it expects, the same in the setup and in the exe'
