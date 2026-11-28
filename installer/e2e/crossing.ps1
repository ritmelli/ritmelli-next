# The crossing on the owner's PC, R2 to R14, between the photo (R1) and the finish (R15) of crossing_photo.ps1. It
# serves two test builds of main and their test manifests on 127.0.0.1:8765, and points the hook at them. Each step
# waits for the state, with a ceiling. The first one that fails goes to the finish, and so does R14 when it passes.
# As administrator, in the 64-bit PowerShell, with Ritmelli closed and no program using the microphone:
#   crossing.ps1 -Proof <new folder> -Setup <published Ritmelli-0.7.0-setup.exe> -Builds <folder with build-0.900.N\>
# The log is %TEMP%\crossing.log until the photo, then crossing.log in the proof folder. For each V<n> it asks,
# whoever follows the log creates V<n>.ok, or V<n>.fail with what went wrong, in the proof folder, within 30 min.
#Requires -RunAsAdministrator
param([Parameter(Mandatory)][string]$Proof, [Parameter(Mandatory)][string]$Setup, [Parameter(Mandatory)][string]$Builds)
$ErrorActionPreference = 'Stop'
if (-not [Environment]::Is64BitProcess) { throw 'run it in the 64-bit PowerShell' }
$Proof = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Proof)
# the photo, the finish, Read-State, Compare-State, Wait-Until, Get-Busy and the names v0.7.0 left
. "$PSScriptRoot\crossing_photo.ps1" -Proof $Proof -Setup $Setup
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$Url = 'http://127.0.0.1:8765'
$Api = 'http://127.0.0.1:8799/api'
$Filter = '{C17A1D48-D473-40D9-9ED3-D024AA46EBE2}'
$Fx = '{d04e05a6-594b-4fb6-a80d-01af5eed7d1d}'
$Apo = 'HKLM:\SOFTWARE\Classes\AudioEngine\AudioProcessingObjects'
$SystemAdminsCreatorTrustedInstaller = 'S-1-5-18', 'S-1-5-32-544', 'S-1-3-0',
  'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464'
$Write = 0x50000116
$ProcessCreation = '{0CCE922B-69AE-11D9-BED3-505054503030}'
$AuditKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\Audit'
$CommandLine = 'ProcessCreationIncludeCmdLine_Enabled'
$svc = New-Object -ComObject Schedule.Service
$svc.Connect()

function Wait-Owner([string]$Name, [string]$Ask) {
  "${Name}: check with the owner that $Ask. Then create $Name.ok in $Proof, or $Name.fail with what went wrong."
  $answer = Wait-Until 1800 {
    Get-ChildItem -LiteralPath $Proof -File | Where-Object Name -in "$Name.ok", "$Name.fail" | Select-Object -First 1
  }
  if (-not $answer) { throw "$Name got no answer in 30 min" }
  if ($answer.Extension -eq '.fail') { throw "$Name failed: $(Get-Content -LiteralPath $answer.FullName -Raw)" }
  "${Name}: ok"
}

function Get-RunState {
  try { Get-Content -LiteralPath "$app\atualizacao\estado.json" -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $null }
}

function Get-UpdateLog([string]$Since) {
  @(Get-Content -LiteralPath "$app\atualizacao\atualizador.log" | Where-Object { [string]::CompareOrdinal($_, $Since) -ge 0 })
}

function Get-Dll([string]$Folder = 'microfone') {
  $f = Get-Item -LiteralPath "$app\$Folder\micfx.dll"
  "$((Get-FileHash -LiteralPath $f.FullName).Hash) $($f.LastWriteTimeUtc.ToString('o'))"
}

function Get-Audio {
  $dg = @(Get-Process audiodg -ErrorAction SilentlyContinue).Id
  if (-not $dg) { throw 'no audiodg.exe runs: is a sound playing?' }
  "audiosrv $((Get-CimInstance Win32_Service -Filter "Name = 'audiosrv'").ProcessId), audiodg $($dg -join ' ')"
}

function Get-TaskErrors {
  foreach ($t in $Tasks) { try { $null = $svc.GetFolder('\').GetTask($t) } catch { "the task $t is gone" } }
}

function Invoke-Task([string]$Name, [int]$Seconds) {
  if (-not (Wait-Until 900 { $svc.GetFolder('\').GetTask($Name).State -ne 4 })) { throw "$Name still runs after 15 min" }
  $since = (Get-Date).AddSeconds(-1)
  $r = Invoke-Tool schtasks.exe /run, /tn, $Name
  if ($r.Code) { throw "schtasks /run $Name`: $($r.Out)" }
  $ran = Wait-Until $Seconds {
    $t = $svc.GetFolder('\').GetTask($Name)
    if ($t.LastRunTime -ge $since -and $t.State -ne 4) { $t }
  }
  if (-not $ran) { throw "$Name did not end in $Seconds s" }
  $ran.LastTaskResult
}

# The setup a round started, to its end. A copy of its log goes to the proof folder, for the proof card.
function Wait-Setup([string]$Version) {
  $s = Wait-Until 180 { $e = Get-RunState; if ($e.estado -eq 'instalando' -and $e.versao -eq $Version) { $e } }
  if (-not $s) { throw "no setup of $Version started; the update log ends: $((Get-UpdateLog '' | Select-Object -Last 3) -join ' | ')" }
  if (-not (Wait-Until 900 { -not (Get-Process -Id $s.pid -ErrorAction SilentlyContinue) })) {
    throw "the setup of $Version still runs after 15 min"
  }
  $script:installed = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  $copy = Join-Path $Proof "$at-$($s.log)"
  Copy-Item -LiteralPath "$app\atualizacao\$($s.log)" $copy
  $product = (Get-Item -LiteralPath "$app\ritmelli.exe").VersionInfo.ProductVersion
  if (-not (Select-String -LiteralPath $copy -Pattern 'Installation process succeeded' -Quiet) -or
    -not (Select-String -LiteralPath $copy -Pattern ' mic filter: ok$' -Quiet) -or $product -ne $Version) {
    throw "the setup of $Version did not succeed (see $copy), and ritmelli.exe is $product"
  }
  $copy
}

function Start-Server {
  $served = Join-Path $Proof 'served'
  foreach ($b in $testBuilds) { Copy-Item -LiteralPath $b.Setup (New-Item -ItemType Directory -Force "$served\v$($b.Version)") }
  $infos = @($testBuilds | ForEach-Object { Join-Path $_.Dir 'build-info.json' })
  $script:public = uv run --project $root python "$PSScriptRoot\test_manifest.py" $Url $served @infos | Select-Object -Last 1
  if ($LASTEXITCODE -or -not $public) { throw "test_manifest.py exited with $LASTEXITCODE" }
  Set-Content -LiteralPath (Join-Path $Proof 'public.txt') $public
  $python = uv run --project $root python -c 'import sys; print(sys._base_executable)'
  $argv = '-I', '-m', 'http.server', '8765', '--bind', '127.0.0.1', '--directory', "`"$served`""
  $server = Start-Process -FilePath $python -ArgumentList $argv -WindowStyle Hidden -PassThru
  Set-Content -LiteralPath (Join-Path $Proof 'server.pid') $server.Id
  $want = @('latest/manifest.json', 'latest/manifest.json.sig') + @($testBuilds | ForEach-Object {
    "v$($_.Version)/manifest.json", "v$($_.Version)/manifest.json.sig", "v$($_.Version)/Ritmelli-$($_.Version)-setup.exe" })
  if (@(Get-ChildItem -LiteralPath $served -Recurse -File).Count -ne $want.Count) { throw "$served holds more than $want" }
  if (-not (Wait-Until 30 { try { Invoke-WebRequest "$Url/latest/manifest.json" -UseBasicParsing -TimeoutSec 2 } catch { $null } })) {
    throw 'the local server did not come up in 30 s'
  }
  foreach ($path in $want) {
    $size = (Invoke-WebRequest "$Url/$path" -Method Head -UseBasicParsing -TimeoutSec 5).Headers['Content-Length']
    if ($size -ne (Get-Item -LiteralPath "$served\$path").Length) { throw "$Url/$path answers $size bytes" }
  }
}

function Set-Hook([string]$Manifest) {
  if (-not (Test-Path -LiteralPath $HookKey)) { New-Item -Path $HookKey | Out-Null }
  New-ItemProperty -LiteralPath $HookKey -Name Manifesto -Value $Manifest -PropertyType String -Force | Out-Null
  New-ItemProperty -LiteralPath $HookKey -Name Chave -Value $public -PropertyType String -Force | Out-Null
  New-ItemProperty -LiteralPath $HookKey -Name SoHttps -Value 0 -PropertyType DWord -Force | Out-Null
  $hook = Get-Values $HookKey 'Manifesto', 'Chave', 'SoHttps'
  if ((@($hook.Values) -join ' ') -ne "String:$Manifest String:$public DWord:0") { throw "the hook reads back $($hook.Values -join ', ')" }
}

# A capture open on each device by confere loads the filter into audiodg.exe, which writes to micfx.log.
function Test-Loaded {
  $log = "$app\microfone\log\micfx.log"
  $before = (Get-Item -LiteralPath $log -ErrorAction SilentlyContinue).LastWriteTimeUtc
  $checked = & "$app\ritmelli.exe" --microfone confere | Out-String | ConvertFrom-Json
  $on = @(& "$app\ritmelli.exe" --microfone estado | ForEach-Object { "$_" })
  $after = (Get-Item -LiteralPath $log -ErrorAction SilentlyContinue).LastWriteTimeUtc
  Write-Host "confere: $($checked | ConvertTo-Json -Compress)`n$($on -join "`n")`n$((Invoke-Tool tasklist.exe /m, micfx.dll).Out)"
  if ($checked.silent) { "silent: $($checked.silent -join '; ')" }
  if (-not $on -or ($on -notmatch ': filter$')) { 'not every active microphone has the filter' }
  if (-not $after -or $after -le $before) { 'micfx.log got no line while confere had each microphone open' }
}

function Test-Machine($Info, [string]$SetupLog) {
  $cur = Read-State $app
  $ids = Get-MicIds $photo 'saved'
  $bad = @(Compare-State $photo $cur (@('task|', 'firewall', 'link|', 'vozes|', 'reg|') + @($ids | ForEach-Object { "saved|$_|", "fx|$_|", "props|$_|" })))
  $dll = "$app\microfone\micfx.dll"
  $sha = (Get-FileHash -LiteralPath $dll).Hash
  if ($sha -ne (Get-FileHash -LiteralPath "$app\_internal\microfone\micfx.dll").Hash) { $bad += 'microfone\micfx.dll is not the one of _internal\' }
  $tree = Get-Values $TreeKey '_sources', '_dll_sha256'
  if ($tree['_sources'] -ne "String:$($Info.filter_sources)" -or $tree['_dll_sha256'] -ne "String:$sha") {
    $bad += "_sources and _dll_sha256 are $($tree.Values -join ', ')"
  }
  foreach ($c in @($Filter) + $Hosts) {
    $com = Get-Values "HKLM:\SOFTWARE\Classes\CLSID\$c\InprocServer32"
    if ($com[''] -ne "String:$dll" -or $com['ThreadingModel'] -ne 'String:Both' -or -not (Test-Path -LiteralPath "$Apo\$c")) {
      $bad += "$c is $($com.Values -join ', ')"
    }
  }
  $writers = (Get-Acl -LiteralPath "$app\microfone\log").Access |
    Where-Object { $_.AccessControlType -eq 'Allow' -and [int]$_.FileSystemRights -band $Write } |
    ForEach-Object { $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value } |
    Where-Object { $_ -notin $SystemAdminsCreatorTrustedInstaller } | Sort-Object -Unique
  if ("$writers" -ne 'S-1-5-19') { $bad += "microfone\log is written by $writers" }
  if (-not (Select-String -LiteralPath $SetupLog -Pattern ' aparelhos: ' -Quiet)) { $bad += "$SetupLog has no 'aparelhos:'" }
  foreach ($id in $ids) {
    if ($cur["fx|$id|$Fx,1"] -ne "String:$Filter" -or $cur["fx|$id|$Fx,15"] -notlike "*$Filter") {
      $bad += "$id has not the filter on the LFX and last on the EFX list"
    }
  }
  $bad += @(Test-Loaded)
  if ($bad) { throw ($bad -join '; ') }
}

function Test-Settled([string]$Version) {
  $code = Invoke-Task $Tasks[0] 300
  $s = Get-RunState
  $gold = Get-Content -LiteralPath "$root\src\ritmelli\update\fixtures\state\idle.json" -Raw | ConvertFrom-Json
  $type = { param($v) if ($null -eq $v) { 'null' } else { $v.GetType().Name } }
  $bad = @(Get-TaskErrors) + @(if ($code) { "the round exited with $code" })
  if ($s.estado -ne 'parado' -or $s.instalada -ne $Version -or $s.nova -or $s.erro -or $s.falhas.PSObject.Properties.Name) {
    $bad += "estado.json is $($s | ConvertTo-Json -Compress)"
  }
  foreach ($p in $gold.PSObject.Properties) {
    if ((& $type $s.($p.Name)) -ne (& $type $p.Value)) { $bad += "$($p.Name) is $(& $type $s.($p.Name)), not $(& $type $p.Value)" }
  }
  if ($photo['estado']) {
    $keys = @($s.PSObject.Properties.Name)
    $names = @(($photo['estado'] | ConvertFrom-Json).PSObject.Properties.Name)
    $bad += @($names | Where-Object { $_ -ne 'erro' -and $_ -notin $keys } | ForEach-Object { "the key $_ of R1 is gone from estado.json" })
  }
  $lines = Get-UpdateLog $installed
  foreach ($want in "previous install: done ($Version)", 'no new version') {
    if (-not ($lines | Where-Object { $_.Contains($want) })) { $bad += "the update log has no '$want': $($lines -join ' | ')" }
  }
  if ($bad) { throw ($bad -join '; ') }
  $lines
}

# The audit of process creation, with the command line: a 0.3 s process is gone before WMI can read its path.
function Start-Trace {
  $csv = Join-Path $Proof 'audit.csv'
  $r = Invoke-Tool auditpol.exe /backup, "/file:$csv"
  if ($r.Code) { throw "auditpol /backup: $($r.Out)" }
  $row = Import-Csv -LiteralPath $csv | Where-Object { $_.PSObject.Properties.Value -contains $ProcessCreation }
  $line = (Get-Values $AuditKey $CommandLine)[$CommandLine]
  $script:audit = @{ Value = [int]@($row.PSObject.Properties.Value)[-1]; Key = Test-Path -LiteralPath $AuditKey; Line = $line }
  "the process creation audit is on until the end of R12; before, $($audit | ConvertTo-Json -Compress)"
  if (-not $audit.Key) { New-Item -Path $AuditKey | Out-Null }
  New-ItemProperty -LiteralPath $AuditKey -Name $CommandLine -Value 1 -PropertyType DWord -Force | Out-Null
  $r = Invoke-Tool auditpol.exe /set, "/subcategory:$ProcessCreation", /success:enable
  if ($r.Code) { throw "auditpol /set: $($r.Out)" }
}

# Not auditpol /restore: it leaves empty global SACLs that were not there.
function Stop-Trace {
  if (-not $audit) { return }
  $set = @{ $true = 'enable'; $false = 'disable' }
  $r = Invoke-Tool auditpol.exe /set, "/subcategory:$ProcessCreation", "/success:$($set[[bool]($audit.Value -band 1)])"
  if ($audit.Line) { New-ItemProperty -LiteralPath $AuditKey -Name $CommandLine -Value ($audit.Line -replace $Kind) -PropertyType DWord -Force | Out-Null }
  else { Remove-ItemProperty -LiteralPath $AuditKey -Name $CommandLine }
  if (-not $audit.Key) { Remove-Item -LiteralPath $AuditKey }
  $script:audit = $null
  if ($r.Code) { throw "auditpol /set back: $($r.Out)" }
}

function Get-Started([datetime]$Since) {
  foreach ($e in Get-WinEvent -FilterHashtable @{ LogName = 'Security'; Id = 4688; StartTime = $Since } -ErrorAction SilentlyContinue) {
    $d = @{}
    foreach ($x in ([xml]$e.ToXml()).Event.EventData.Data) { $d[$x.Name] = "$($x.'#text')".Trim() }
    if ($d.NewProcessName -ne "$app\ritmelli.exe") { continue }
    $d.Account = @($d.TargetUserSid, $d.SubjectUserSid) | Where-Object { $_ -notin '', '-', 'S-1-0-0' } | Select-Object -First 1
    [pscustomobject]$d
  }
}

$early = Join-Path $env:TEMP 'crossing.log'
Start-Transcript -LiteralPath $early | Out-Null
try {
  $testBuilds = foreach ($v in '0.900.1', '0.900.2') {
    $dir, $name = "$Builds\build-$v", "Ritmelli-$v-setup.exe"
    $info = Get-Content -LiteralPath "$dir\build-info.json" -Raw | ConvertFrom-Json
    if ($info.version -ne $v -or (Get-FileHash -LiteralPath "$dir\$name").Hash -ne $info.artifacts.$name.sha256) { throw "$dir is not the test build $v" }
    [pscustomobject]@{ Version = $v; Dir = $dir; Info = $info; Setup = "$dir\$name" }
  }
  if ($testBuilds[0].Info.commit -ne $testBuilds[1].Info.commit) { throw 'the two test builds are not of one commit' }
  Invoke-Photo $Setup
} catch {
  "R1: FAIL: $_"
  Stop-Transcript | Out-Null
  exit 1
}
Stop-Transcript | Out-Null
Move-Item -LiteralPath $early (Join-Path $Proof 'crossing.log')
Start-Transcript -LiteralPath (Join-Path $Proof 'crossing.log') -Append | Out-Null
$photo = Read-Map 'photo.json'
$app = $photo['app|Inno Setup: App Path'] -replace $Kind
'R1: PASS'
$failed = $null
try {
  $at = 'R2'
  $log = Join-Path $Proof 'R2-instalador-0.900.1.log'
  $p = Start-Process -FilePath $testBuilds[0].Setup -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$log`"" -PassThru
  $null = $p.Handle
  if (-not $p.WaitForExit(600000)) { throw 'the setup still runs after 10 min' }
  $diff = @(Compare-State $photo (Read-State $app) '')
  if ($p.ExitCode -ne 1 -or $diff) { throw "without the hook the setup exited with $($p.ExitCode), and changed: $($diff -join '; ')" }
  'R2: PASS: without the hook, the setup exited with 1 and changed nothing'

  $at = 'R3'
  Start-Server
  Set-Hook "$Url/v0.900.1/manifest.json"
  "R3: PASS: the hook points to $Url/v0.900.1/manifest.json, with the throwaway public key $public"

  $at = 'R4'
  $null = Invoke-Task $Tasks[0] 600
  $log4 = Wait-Setup '0.900.1'
  $entry = Get-ItemProperty -LiteralPath $Is1
  if ($entry.DisplayVersion -ne '0.900.1' -or $entry.InstallLocation -ne "$app\" -or $entry.UninstallString -ne "`"$app\unins000.exe`"") {
    throw "the uninstall entry says $($entry.DisplayVersion), $($entry.InstallLocation), $($entry.UninstallString)"
  }
  'R4: PASS: v0.7.0 took the test manifest and installed 0.900.1'

  $at = 'R5'
  Test-Machine $testBuilds[0].Info $log4
  $r5 = Get-Dll
  'R5: PASS: the tasks, the rule, the shortcut, the filter and the microphones are as the plan says'

  $at = 'R6'
  Test-Settled '0.900.1'
  'R6: PASS: the first round of the skeleton settled the install'

  $at = 'R7'
  $mics = [ordered]@{}
  Add-Mics $mics
  $code = Invoke-Task $Tasks[1] 300
  $now = [ordered]@{}
  Add-Mics $now
  $bad = @(Compare-State $mics $now '') + @(Get-TaskErrors)
  if ($code -or $bad -or (Get-Dll) -ne $r5) { throw "the mic task exited with $code; $($bad -join '; '); the DLL is $(Get-Dll), was $r5" }
  'R7: PASS: the mic task changed nothing'

  $at = 'R8'
  Wait-Owner 'V1-sound' 'a sound plays on this PC outside Ritmelli, such as a video in the browser, and stays on until V1'
  $audio, $internal = (Get-Audio), (Get-Dll '_internal\microfone')
  Set-Hook "$Url/v0.900.2/manifest.json"
  $null = Invoke-Task $Tasks[0] 600
  $log8 = Wait-Setup '0.900.2'
  Test-Settled '0.900.2'
  'R8: PASS: 0.900.1 took 0.900.2, and its first round settled it'

  $at = 'R9'
  $bad = @(if ((Get-Audio) -ne $audio) { "the audio restarted: $audio, now $(Get-Audio)" })
  if ((Get-Dll) -ne $r5 -or (Get-Dll '_internal\microfone') -eq $internal) { $bad += "microfone\micfx.dll is $(Get-Dll), was $r5" }
  if (-not (Select-String -LiteralPath $log8 -Pattern ' aparelhos: devices: not checked' -Quiet)) { $bad += "$log8 says the audio restarted" }
  $bad += @(Test-Loaded)
  if ($bad) { throw ($bad -join '; ') }
  'R9: PASS: the filter DLL stayed, and the audio did not restart'
  Wait-Owner 'V1' 'the sound played on with no cut through the jump to 0.900.2'
  Wait-Owner 'V2' 'the old clone (python) plays music to the microphone through ring 5 with the filter 0.900.2 left, and runs the new mic task to the end with a new microphone plugged in'

  $at = 'R10'
  Set-Hook "$Url/latest/manifest.json"
  $since = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  $code = Invoke-Task $Tasks[0] 300
  $line = Get-UpdateLog $since | Select-Object -Last 1
  if ($code -or $line -notlike '*no new version (installed 0.900.2, published 0.900.2)' -or (Get-RunState).erro) {
    throw "the round said '$line', with the error '$((Get-RunState).erro)'"
  }
  'R10: PASS: no new version on latest'

  $at = 'R11'
  Remove-ItemProperty -LiteralPath $HookKey -Name Manifesto, Chave, SoHttps
  foreach ($t in $Tasks) { Invoke-Tool schtasks.exe /end, /tn, $t | Out-Null }
  if (-not (Wait-Until 1800 { -not (Get-Busy $app) })) {
    throw "still running after 30 min, not stopped: $((Get-Busy $app).Name -join ', '). Call the owner."
  }
  $out = @(Install-Published $photo)
  Move-Item -LiteralPath (Join-Path $Proof 'setup-0.7.0.log') (Join-Path $Proof 'R11-setup-0.7.0.log')
  $diff = @(Compare-State $photo (Read-State $app) 'app|DisplayVersion', 'dll', 'task|')
  if ($out -or $diff) { throw "$out $($diff -join '; ')" }
  'R11: PASS: back on 0.7.0, with its filter DLL and its tasks'

  $at = 'R12'
  Wait-Owner 'V3' 'Ritmelli 0.7.0 is open from the Start menu, without Run as administrator, as every day'
  if (-not (Wait-Until 120 { try { (Invoke-RestMethod "$Api/atualizacao" -TimeoutSec 2).automatica } catch { $null } })) {
    throw 'the API of 0.7.0 did not answer with the update task in 2 min'
  }
  $main = (Get-NetTCPConnection -LocalPort 8799 -State Listen | Select-Object -First 1).OwningProcess
  $opened = Get-CimInstance Win32_Process -Filter "ProcessId = $main"
  $owner = (Invoke-CimMethod -InputObject $opened -MethodName GetOwnerSid).Sid
  if ($opened.ExecutablePath -ne "$app\ritmelli.exe") { throw "the API is of $($opened.ExecutablePath)" }
  Set-Hook "$Url/v0.900.2/manifest.json"
  $since = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  $null = Invoke-Task $Tasks[0] 600
  $s = Get-RunState
  $product = (Get-Item -LiteralPath "$app\ritmelli.exe").VersionInfo.ProductVersion
  if ($s.estado -ne 'pronta' -or $s.nova.versao -ne '0.900.2' -or $product -ne '0.7.0' -or -not ((Get-UpdateLog $since) -match 'Ritmelli is open')) {
    throw "with 0.7.0 open, ritmelli.exe is $product and estado.json $($s | ConvertTo-Json -Compress)"
  }
  Start-Trace
  $posted = Get-Date
  try { Invoke-RestMethod "$Api/atualizacao/instalar" -Method Post -ContentType 'application/json' -Body '{}' | Out-Null }
  catch { "install now answered: $($_.Exception.Message)" }
  if (-not (Wait-Until 60 { -not (Get-Process -Id $main -ErrorAction SilentlyContinue) })) { throw '0.7.0 did not close in 60 s after install now' }
  $null = Wait-Setup '0.900.2'
  $exe = "$app\ritmelli.exe"
  $reopened = Wait-Until 120 {
    Get-Started $posted | Where-Object { $_.Account -eq $owner -and $_.CommandLine -in "`"$exe`"", $exe -and $_.MandatoryLabel -eq 'S-1-16-8192' }
  }
  Get-Started $posted | ForEach-Object { "started: $($_.CommandLine) as $($_.Account) at $($_.MandatoryLabel)" }
  $wrong = @(Get-Started $posted | Where-Object { $_.CommandLine -in "`"$exe`"", $exe -and ($_.Account -ne $owner -or $_.MandatoryLabel -ne 'S-1-16-8192') })
  Stop-Trace
  $dll = (Get-FileHash -LiteralPath "$app\microfone\micfx.dll").Hash
  if (-not $reopened -or $wrong -or $dll -eq $photo['dll'] -or $dll -ne (Get-FileHash -LiteralPath "$app\_internal\microfone\micfx.dll").Hash) {
    throw "ritmelli.exe with no argument did not start only as $owner at Medium, or microfone\micfx.dll is still $dll"
  }
  'R12: PASS: install now took 0.7.0 to 0.900.2, reopened as the owner, and the filter DLL changed'

  $at = 'R13'
  Invoke-BeforeUninstall
  $before = Read-Map 'before-uninstall.json'
  $log = Join-Path $Proof 'uninstall.log'
  Start-Process -FilePath "$app\unins000.exe" -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$log`""
  if (-not (Wait-Until 300 { -not ((Get-Busy $app) -or (Test-Path -LiteralPath $app)) })) { throw 'the uninstall did not end in 5 min' }
  $sys = [Environment]::SystemDirectory
  $five = "$app\ritmelli.exe --atualizador remove", "$sys\taskkill.exe /F /IM ritmelli.exe", "$app\ritmelli.exe --microfone remove",
    "$sys\netsh.exe advfirewall firewall delete rule name=`"Ritmelli`"", "$sys\netsh.exe advfirewall firewall delete rule name=`"Vitrola`""
  $exec = @(Get-Content -LiteralPath $log) -match 'Running Exec (filename|parameters): ' -replace '.*Running Exec (filename|parameters): '
  $ran = for ($i = 0; $i -lt $exec.Count; $i += 2) { "$($exec[$i]) $($exec[$i + 1])" }
  $cur = Read-State $app
  $saved = Get-MicIds $photo 'saved'
  $new = @(Get-MicIds $before 'saved' | Where-Object { $_ -notin $saved })
  $bad = @(Compare-State $before $cur 'local|' | Where-Object { $_ -notlike 'local|metricas.json:*' })
  $bad += @(@($cur.Keys) -match '^(task\||saved\||tree\|_(hospede\d|mudos|sources|dll_sha256)$)')
  $bad += @(@($Is1) + @(@($Filter) + $Hosts | ForEach-Object { "HKLM:\SOFTWARE\Classes\CLSID\$_", "$Apo\$_" }) | Where-Object { Test-Path -LiteralPath $_ })
  $bad += @(@(Find-NotAtOriginal $photo $cur $saved) + @(Find-NotAtOriginal $before $cur $new) | ForEach-Object { "$_ is not on its original" })
  if ((@($ran) -join '|') -ne ($five -join '|')) { $bad += "the uninstaller ran: $(@($ran) -join '; ')" }
  if (-not (Invoke-Tool netsh.exe advfirewall, firewall, show, rule, "name=$Rule").Code) { $bad += 'the firewall rule is there' }
  if (-not $cur['hook']) { $bad += "$HookKey is gone" }
  if ($bad) { throw "the uninstall left: $($bad -join '; ')" }
  'R13: PASS: the uninstaller ran the five lines once each and gave each microphone back'
  Wait-Owner 'V4' 'each real microphone is back on the effects of its maker'

  $at = 'R14'
  $net = @(Select-String -Path (Join-Path $Proof 'R*-instalador-*.log') -Pattern 'Downloading|https?://')
  if ($net) { throw "a setup of the skeleton used the network: $($net.Line -join ' | ')" }
  'R14: PASS: no setup of the skeleton downloaded anything'
} catch {
  $failed = "${at}: $_ (line $($_.InvocationInfo.ScriptLineNumber))"
  "${at}: FAIL: $_"
} finally {
  try { Stop-Trace } catch { if (-not $failed) { $failed = "R12: $_" }; "R12: FAIL: the audit did not go back: $_" }
  try {
    $at = 'R15'
    Invoke-Finish
    'R15: PASS'
    $at = 'V5'
    Wait-Owner 'V5' 'Ritmelli 0.7.0 opens from the Start menu and plays music to the microphone, as before the proof'
  } catch {
    if (-not $failed) { $failed = "${at}: $_" }
    "${at}: FAIL: $_"
  }
}
if ($failed) { "crossing: FAIL at $failed" } else { 'crossing: PASS, R1 to R15 and V1 to V5' }
Stop-Transcript | Out-Null
exit ([int][bool]$failed)
