# The setup of a build on a clean machine, as an administrator. It refuses a PC where
# Ritmelli is. Without the hook, the setup exits with 1 and changes nothing. With it, a
# folder outside Program Files fails the protected folder rule: the setup exits with 7 and
# changes nothing. Then it installs in silence into a folder that is not the default, and
# again over itself, as an update does: it must find that folder alone. The uninstaller then
# takes it all out, and of the lines both setups left in its log, each RunOnceId runs once.
# Last, it installs once more with no folder given: it must go to the default.
# Usage: clean_machine.ps1 -Build <the folder with build-info.json and the setup>
#Requires -RunAsAdministrator
param([Parameter(Mandatory)][string]$Build)
$ErrorActionPreference = 'Stop'
# Read-State, Compare-State, Wait-Until, Get-Busy and the names v0.7.0 left
. "$PSScriptRoot\crossing_photo.ps1"
if ((Test-Path -LiteralPath $Is1) -or (Test-Path -LiteralPath $RitmelliKey) -or (Test-Path "$env:ProgramFiles\Ritmelli*")) {
  throw 'Ritmelli is on this PC: run this on a clean machine'
}

$info = Get-Content -LiteralPath (Join-Path $Build 'build-info.json') -Raw | ConvertFrom-Json
$name = "Ritmelli-$($info.version)-setup.exe"
$setup = Join-Path $Build $name
if ((Get-FileHash -LiteralPath $setup).Hash -ne $info.artifacts.$name.sha256) { throw "$name is not the one in build-info.json" }
$app = Join-Path $env:ProgramFiles 'Ritmelli-2'
$logs = New-Item -ItemType Directory -Force (Join-Path $env:TEMP 'clean-machine')

function Install([int]$Expected, [string]$Log, [string]$Dir) {
  $argv = '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$Log`""
  if ($Dir) { $argv += "/DIR=`"$Dir`"" }
  $p = Start-Process -FilePath $setup -ArgumentList $argv -PassThru
  $null = $p.Handle
  if (-not $p.WaitForExit(600000)) { throw "the setup still runs after 10 min: $Log" }
  if ($p.ExitCode -ne $Expected) { Get-Content -LiteralPath $Log -Tail 30; throw "the setup exited with $($p.ExitCode), not $Expected" }
}

$before = Read-State $app
$log = Join-Path $logs 'no-hook.log'
Install 1 $log
$diff = @(Compare-State $before (Read-State $app) '')
$refused = Select-String -LiteralPath $log -Pattern 'test build: no Manifesto' -Quiet
if ($diff -or (Test-Path "$env:ProgramFiles\Ritmelli*") -or -not $refused) {
  $diff; throw 'without the hook, the setup changed the lines above, made a folder, or did not say why it refused'
}
'without the hook, the setup exited with 1 and changed nothing'

New-Item -Path $HookKey -Force | Out-Null
New-ItemProperty -LiteralPath $HookKey -Name Manifesto -Value 'http://127.0.0.1:8765/v0.900.1/manifest.json' | Out-Null
try {
  $log = Join-Path $logs 'outside.log'
  Install 7 $log 'C:\Ritmelli'
  $diff = @(Compare-State $before (Read-State $app) '') -notmatch '^hook'
  $refused = Select-String -LiteralPath $log -Pattern 'unprotected folder: C:\\Ritmelli: .* is outside' -Quiet
  if ($diff -or (Test-Path 'C:\Ritmelli') -or (Test-Path "$env:ProgramFiles\Ritmelli*") -or -not $refused) {
    $diff; throw 'with /DIR=C:\Ritmelli, the setup changed the lines above, made a folder, or did not say why it refused'
  }
  'with /DIR=C:\Ritmelli, the setup exited with 7 and changed nothing'
  Install 0 (Join-Path $logs 'first.log') $app
  # of the version before, what the setup takes out and what it leaves
  $gone = "$app\_internal\old.pyd", "$app\bin\ffmpeg.exe"
  $kept = "$app\vozes\v1\voz.onnx", "$app\atualizacao\estado.json"
  foreach ($f in $gone + $kept) { New-Item -ItemType File -Force $f | Out-Null }
  Install 0 (Join-Path $logs 'second.log')
  $entry = Get-ItemProperty -LiteralPath $Is1
  $firewall = Get-NetFirewallRule -DisplayName $Rule -ErrorAction SilentlyContinue | ForEach-Object {
    "$($_.Direction) $($_.Action) $($_.Enabled) $($_.Profile) $(($_ | Get-NetFirewallApplicationFilter).Program)"
  }
  $there = @("$app\_internal\microfone\micfx.dll", "$app\microfone\micfx.dll", "$app\LICENSE.txt", "$app\TERCEIROS.txt") + $kept
  $left = @("$app\bin", $Links[1], "$env:ProgramFiles\Ritmelli") + $gone
  $found = [ordered]@{
    DisplayName = $entry.DisplayName; DisplayVersion = $entry.DisplayVersion
    InstallLocation = $entry.InstallLocation; UninstallString = $entry.UninstallString
    exe = (Get-Item -LiteralPath "$app\ritmelli.exe").VersionInfo.ProductVersion
    link = (New-Object -ComObject WScript.Shell).CreateShortcut($Links[0]).TargetPath
    rule = @($firewall) -join '; '
    'values in HKLM\SOFTWARE\Ritmelli' = @((Get-Item -LiteralPath $RitmelliKey).GetValueNames()) -join ' '
    missing = @($there | Where-Object { -not (Test-Path -LiteralPath $_) }) -join ', '
    left = @($left | Where-Object { Test-Path -LiteralPath $_ }) -join ', '
  }
  $want = [ordered]@{
    DisplayName = 'Ritmelli'; DisplayVersion = $info.version
    InstallLocation = "$app\"; UninstallString = "`"$app\unins000.exe`""
    exe = $info.version; link = "$app\ritmelli.exe"; rule = "Inbound Allow True Private, Public $app\ritmelli.exe"
    'values in HKLM\SOFTWARE\Ritmelli' = ''; missing = ''; left = ''
  }
  foreach ($k in $want.Keys) {
    if ("$($found[$k])" -ne $want[$k]) { throw "after the update, $k is '$($found[$k])', not '$($want[$k])'" }
  }
  'after the update: ' + (($want.Keys | ForEach-Object { "$_ $($found[$_])" }) -join '; ')

  $log = Join-Path $logs 'uninstall.log'
  Start-Process -FilePath "$app\unins000.exe" -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$log`""
  # its copy in the temporary folder, _unins.tmp in Inno 6.7.3, removes the folder after
  # unins000.exe exits: its end is the state
  $null = Wait-Until 300 { -not ((Get-Busy $app) -or (Test-Path -LiteralPath $app)) }
  if (Get-Busy $app) { throw 'the uninstaller still runs after 5 min' }
  $sys = [Environment]::SystemDirectory
  $five = "$app\ritmelli.exe --atualizador remove", "$sys\taskkill.exe /F /IM ritmelli.exe",
    "$app\ritmelli.exe --microfone remove", "$sys\netsh.exe advfirewall firewall delete rule name=`"Ritmelli`"",
    "$sys\netsh.exe advfirewall firewall delete rule name=`"Vitrola`""
  $lines = Get-Content -LiteralPath $log
  $exec = @($lines -match 'Running Exec (filename|parameters): ' -replace '.*Running Exec (filename|parameters): ')
  $ran = for ($i = 0; $i -lt $exec.Count; $i += 2) { "$($exec[$i]) $($exec[$i + 1])" }
  $skipped = @($lines -match 'Skipping RunOnceId ').Count
  if ((@($ran) -join '|') -ne ($five -join '|') -or $skipped -ne $five.Count) {
    $lines; throw 'the uninstaller did not run the five lines of v0.7.0 once each, in order'
  }
  $diff = @(Compare-State $before (Read-State $app) '') -notmatch '^hook'
  if ($diff -or (Test-Path "$env:ProgramFiles\Ritmelli*")) { $diff; throw 'the uninstaller left the lines above, or a folder' }
  "the uninstaller ran the five lines once each, skipped the $skipped of the first setup, and took it all out"

  Install 0 (Join-Path $logs 'default.log')
  $where = (Get-ItemProperty -LiteralPath $Is1).InstallLocation
  if ($where -ne "$env:ProgramFiles\Ritmelli\") { throw "with nothing installed before, the setup went to '$where'" }
  "with nothing installed before, the setup went to $where"
} finally {
  Remove-Item -LiteralPath $RitmelliKey -Recurse -Force -ErrorAction SilentlyContinue
}
# the netsh of the photo exits with 1 without the rule, and the step would end with it
exit 0
