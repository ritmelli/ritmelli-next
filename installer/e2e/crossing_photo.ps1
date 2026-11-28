# The photo of a PC on Ritmelli 0.7.0 before the crossing, and the finish that puts the PC back as the photo saw it.
# Run as administrator, in the 64-bit PowerShell, with a new proof folder outside the app folder (such as C:\<name>):
#   crossing_photo.ps1 -Step photo -Proof <folder> -Setup <published Ritmelli-0.7.0-setup.exe>
#   crossing_photo.ps1 -Step before-uninstall -Proof <folder>   (right before the uninstall of the crossing)
#   crossing_photo.ps1 -Step finish -Proof <folder>             (also alone, when the crossing died halfway)
# Dot-sourced without -Step, it only defines the functions. The crossing keeps the pid of its local server in
# server.pid, the served folder in served\ and the throwaway public key in public.txt, all in the proof folder.
#Requires -RunAsAdministrator
param([string]$Step, [string]$Proof, [string]$Setup)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$PublishedSha = 'F0AEE549CCA67359B09E2B404AD864C34E4E9F834FA3FAC1BB108E93992E5A1E'
$Is1 = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{320EB2BD-48BC-420D-8F52-C22F644E47D4}_is1'
$RitmelliKey = 'HKLM:\SOFTWARE\Ritmelli'
$HookKey = 'HKLM:\SOFTWARE\Ritmelli\Atualizador'
$TreeKey = 'HKLM:\SOFTWARE\Ritmelli\Microfone'
$CaptureKey = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Capture'
$NoEnhancements = '{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},5'
$Hosts = '{D6EB08E6-2DDA-44F3-88C8-2D0EA00C6C8E}', '{9FEF5C33-9ED4-4CC6-8624-4F017BB71678}',
  '{ED59B560-1ECA-4491-9179-EC121791159D}', '{1663A464-C189-435F-89BD-9C9E9BAF1C23}'
$Tasks = '\Ritmelli Atualiza', '\Ritmelli\Microfone'
$Links = (Join-Path ([Environment]::GetFolderPath('CommonPrograms')) 'Ritmelli.lnk'),
  (Join-Path ([Environment]::GetFolderPath('CommonDesktopDirectory')) 'Ritmelli.lnk')
$Rule = 'Ritmelli'
$LocalRoot = $env:LOCALAPPDATA
$Local = Join-Path $LocalRoot 'Ritmelli'
$Kind = '^[A-Za-z]+:'
# A host takes another slot when the setup runs again, and the silent devices depend on the moment of the check.
$NotCompared = '^tree\|_(hospede\d|mudos)$'
$RoundDone = 'no new version \(installed 0\.7\.0, published 0\.7\.0\)|installer for 0\.7\.\d+ started'

# Windows PowerShell turns the stderr of a tool into errors that stop the script: the exit code says it instead.
function Invoke-Tool([string]$Exe, [string[]]$Argv) {
  $ErrorActionPreference = 'Continue'
  $out = (& (Join-Path ([Environment]::SystemDirectory) $Exe) @Argv 2>&1 | ForEach-Object { "$_" }) -join "`n"
  [pscustomobject]@{ Code = $LASTEXITCODE; Out = $out }
}

function Wait-Until([int]$Seconds, [scriptblock]$Done) {
  $end = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $end) {
    $r = & $Done
    if ($r) { return $r }
    Start-Sleep 1
  }
}

function Get-Values([string]$Path, [string[]]$Only) {
  $m = [ordered]@{}
  $k = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
  if (-not $k) { return $m }
  foreach ($n in $k.GetValueNames()) {
    if ($Only -and $n -notin $Only) { continue }
    $v = $k.GetValue($n, $null, 'DoNotExpandEnvironmentNames')
    if ($v -is [byte[]]) { $v = [BitConverter]::ToString($v) } elseif ($v -is [string[]]) { $v = $v -join '|' }
    $m[$n] = "$($k.GetValueKind($n)):$v"
  }
  $m
}

function Add-Values($Map, [string]$Prefix, [string]$Path, [string[]]$Only) {
  $v = Get-Values $Path $Only
  foreach ($n in $v.Keys) { $Map[$Prefix + $n] = $v[$n] }
}

function Add-Hashes($Map, [string]$Prefix, [string]$Root) {
  if (-not (Test-Path -LiteralPath $Root)) { return }
  $full = (Get-Item -LiteralPath $Root).FullName.TrimEnd('\')
  foreach ($f in Get-ChildItem -LiteralPath $Root -Recurse -File -Force) {
    $Map[$Prefix + $f.FullName.Substring($full.Length + 1)] = (Get-FileHash -LiteralPath $f.FullName).Hash
  }
}

# The effect chain of a microphone by the vendor CLSID each host slot carries, not by the slot number.
function Add-Mics($Map) {
  $tree = Get-Values $TreeKey
  foreach ($n in $tree.Keys) { $Map["tree|$n"] = $tree[$n] }
  foreach ($k in Get-ChildItem -LiteralPath $TreeKey -ErrorAction SilentlyContinue) {
    Add-Values $Map "saved|$($k.PSChildName)|" $k.PSPath
  }
  foreach ($k in Get-ChildItem -LiteralPath $CaptureKey -ErrorAction SilentlyContinue) {
    $fx = Get-Values "$($k.PSPath)\FxProperties"
    foreach ($n in $fx.Keys) {
      $v = $fx[$n]
      for ($h = 0; $h -lt $Hosts.Count; $h++) {
        $v = $v -ireplace [regex]::Escape($Hosts[$h]), "host($($tree["_hospede$h"]))"
      }
      $Map["fx|$($k.PSChildName)|$n"] = $v
    }
    Add-Values $Map "props|$($k.PSChildName)|" "$($k.PSPath)\Properties" $NoEnhancements
  }
}

function Read-State([string]$App) {
  $s = [ordered]@{}
  $names = 'DisplayVersion', 'Inno Setup: App Path', 'Inno Setup: Language', 'Inno Setup: Selected Tasks'
  Add-Values $s 'app|' $Is1 $names
  $exe = Join-Path $App 'ritmelli.exe'
  if (Test-Path -LiteralPath $exe) { $s['exe'] = (Get-Item -LiteralPath $exe).VersionInfo.ProductVersion }
  Add-Values $s 'reg|' $RitmelliKey 'Metricas', 'MetricasVersao'
  if (Test-Path -LiteralPath $HookKey) { $s['hook'] = 'present' }
  Add-Values $s 'hook|' $HookKey
  $svc = New-Object -ComObject Schedule.Service
  $svc.Connect()
  foreach ($t in $Tasks) {
    try { $task = $svc.GetFolder('\').GetTask($t) } catch { continue }
    $s["task|$t"] = $task.Xml + $task.GetSecurityDescriptor(4)
  }
  $s['firewall'] = (Invoke-Tool netsh.exe advfirewall, firewall, show, rule, "name=$Rule", verbose).Out
  $shell = New-Object -ComObject WScript.Shell
  foreach ($l in $Links) {
    if (-not (Test-Path -LiteralPath $l)) { continue }
    $k = $shell.CreateShortcut($l)
    $s["link|$l"] = "$($k.TargetPath) $($k.Arguments)"
  }
  $dll = Join-Path $App 'microfone\micfx.dll'
  if (Test-Path -LiteralPath $dll) {
    $s['dll'] = (Get-FileHash -LiteralPath $dll).Hash
    $s['dll|signature'] = "$((Get-AuthenticodeSignature -LiteralPath $dll).Status)"
  }
  $state = Join-Path $App 'atualizacao\estado.json'
  if (Test-Path -LiteralPath $state) { $s['estado'] = Get-Content -LiteralPath $state -Raw }
  Add-Hashes $s 'local|' $Local
  Add-Hashes $s 'vozes|' (Join-Path $App 'vozes')
  Add-Mics $s
  $s
}

function Save-Map($Map, [string]$Name) {
  $Map | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $Proof $Name) -Encoding UTF8
}

function Read-Map([string]$Name) {
  $f = Join-Path $Proof $Name
  if (-not (Test-Path -LiteralPath $f)) { throw "$f is missing: the finish runs only after a photo" }
  $m = @{}
  (Get-Content -LiteralPath $f -Raw -Encoding UTF8 | ConvertFrom-Json).PSObject.Properties |
    ForEach-Object { $m[$_.Name] = $_.Value }
  $m
}

function Compare-State($Ref, $Cur, [string[]]$Prefixes) {
  $wanted = '^(' + (($Prefixes | ForEach-Object { [regex]::Escape($_) }) -join '|') + ')'
  foreach ($k in @($Ref.Keys) + @($Cur.Keys) | Sort-Object -Unique) {
    if ($k -notmatch $wanted -or $k -match $NotCompared) { continue }
    if ("$($Ref[$k])" -ne "$($Cur[$k])") { "${k}: [$($Ref[$k])] -> [$($Cur[$k])]" }
  }
}

function Get-MicIds($Map, [string]$Kinds = 'fx|props|saved') {
  @(@($Map.Keys) -match "^($Kinds)\|" | ForEach-Object { $_.Split('|')[1] } | Sort-Object -Unique)
}

# The microphones whose effects are not the saved original of $Ref: its values, _ausentes and _sem_melhorias.
function Find-NotAtOriginal($Ref, $Cur, [string[]]$Ids) {
  $saved = @($Ref.Keys) -like 'saved|*'
  foreach ($id in $Ids) {
    $p = "saved|$id|"
    $off = @($saved | Where-Object { $_.StartsWith($p) -and $_[$p.Length] -ne '_' } |
      Where-Object { $Cur["fx|$id|$($_.Substring($p.Length))"] -ne $Ref[$_] })
    $absent = "$($Ref["${p}_ausentes"])" -replace $Kind -split '\|'
    $gone = @($absent | Where-Object { $_ -and $Cur.Contains("fx|$id|$_") })
    $muted = $Ref["${p}_sem_melhorias"] -eq 'DWord:1' -and $Cur["props|$id|$NoEnhancements"] -ne 'DWord:1'
    if ($off -or $gone -or $muted) { $id }
  }
}

function Get-Busy([string]$App) {
  Get-CimInstance Win32_Process | Where-Object {
    $_.Name -like 'Ritmelli-*-setup*' -or $_.Name -like 'unins000*' -or $_.Name -eq '_unins.tmp' -or
    ($_.Name -eq 'ritmelli.exe' -and $_.ExecutablePath -like "$App\*") }
}

# reg import cannot write the keys of a microphone: Administrators only set values there, as the mic setup does.
# So the tree goes to a .reg file, and the values of each microphone, with their kinds, to mics.xml.
function Save-Registry {
  $reg = (New-Item -ItemType Directory (Join-Path $Proof 'reg')).FullName
  $tree = Get-Item -LiteralPath $TreeKey -ErrorAction SilentlyContinue
  if ($tree) {
    $r = Invoke-Tool reg.exe export, $tree.Name, (Join-Path $reg 'tree.reg'), /y
    if ($r.Code) { throw "reg export $($tree.Name): $($r.Out)" }
  }
  $values = @()
  foreach ($k in Get-ChildItem -LiteralPath $CaptureKey -ErrorAction SilentlyContinue) {
    $fx = Get-Item -LiteralPath "$($k.PSPath)\FxProperties" -ErrorAction SilentlyContinue
    foreach ($n in @(if ($fx) { $fx.GetValueNames() })) {
      $values += [pscustomobject]@{ Key = $fx.Name; Name = $n; Kind = "$($fx.GetValueKind($n))"
        Value = $fx.GetValue($n, $null, 'DoNotExpandEnvironmentNames') }
    }
    $p = Get-Item -LiteralPath "$($k.PSPath)\Properties" -ErrorAction SilentlyContinue
    if (-not $p) { continue }
    $v = $p.GetValue($NoEnhancements)
    if ($null -ne $v -and $p.GetValueKind($NoEnhancements) -ne 'DWord') {
      throw "$($p.Name): $NoEnhancements is not a DWORD"
    }
    $values += [pscustomobject]@{ Key = $p.Name; Name = $NoEnhancements; Kind = 'DWord'; Value = $v }
  }
  $values | Export-Clixml -LiteralPath (Join-Path $reg 'mics.xml')
}

function Invoke-Photo([string]$Setup) {
  if (-not $Setup -or (Get-FileHash -LiteralPath $Setup).Hash -ne $PublishedSha) {
    throw 'give the published 0.7.0 setup: -Setup <file>'
  }
  $app = (Get-Values $Is1 'Inno Setup: App Path')['Inno Setup: App Path'] -replace $Kind
  if (-not $app) { throw 'Ritmelli is not installed' }
  $s = Read-State $app
  if ($s['app|DisplayVersion'] -ne 'String:0.7.0' -or $s['exe'] -ne '0.7.0') {
    throw "this is not Ritmelli 0.7.0: $($s['app|DisplayVersion']), ritmelli.exe $($s['exe'])"
  }
  if (@($s.Keys) -match '^hook\|(Manifesto|Chave|SoHttps)$') { throw 'the hook has a value: finish that crossing first' }
  if (Get-Busy $app) { throw 'Ritmelli, its setup or its uninstaller is running: close it, or wait for it' }
  if (Test-Path -LiteralPath $Proof) { throw "$Proof already exists: give a new proof folder" }
  New-Item -ItemType Directory $Proof | Out-Null
  $owner = Invoke-Tool icacls.exe $Proof, /setowner, '*S-1-5-32-544'
  $acl = Invoke-Tool icacls.exe $Proof, /inheritance:r, /grant:r, '*S-1-5-32-544:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F'
  if ($owner.Code -or $acl.Code -or (Get-ChildItem -LiteralPath $Proof -Force)) {
    throw "$Proof is not for administrators only: $($owner.Out) $($acl.Out)"
  }
  $copy = Join-Path $Proof 'Ritmelli-0.7.0-setup.exe'
  Copy-Item -LiteralPath $Setup $copy
  if ((Get-FileHash -LiteralPath $copy).Hash -ne $PublishedSha) { throw "the copy of $Setup changed" }
  Save-Registry
  $vozes = Join-Path $app 'vozes'
  if (Test-Path -LiteralPath $vozes) {
    $r = Invoke-Tool robocopy.exe $vozes, (Join-Path $Proof 'vozes'), /MIR, /R:2, /W:1, /NJH, /NJS, /NP
    if ($r.Code -ge 8) { throw "the copy of the voices failed: $($r.Out)" }
  }
  $voices = [ordered]@{}
  Add-Hashes $voices 'vozes|' (Join-Path $Proof 'vozes')
  $diff = @(Compare-State $s $voices 'vozes|')
  if ($diff) { throw "the copy of the voices differs: $($diff -join '; ')" }
  Save-Map $s 'photo.json'
  "photo of Ritmelli 0.7.0 in $app, $((Get-MicIds $s).Count) microphones, micfx.dll $($s['dll|signature']): $Proof"
}

function Invoke-BeforeUninstall {
  $photo = Read-Map 'photo.json'
  foreach ($n in 'Ritmelli', 'Vitrola') {
    $f = Join-Path $LocalRoot "$n\metricas.json"
    if (Test-Path -LiteralPath $f) { Copy-Item -LiteralPath $f (Join-Path $Proof "metricas-$n.json") -Force }
  }
  Save-Map (Read-State ($photo['app|Inno Setup: App Path'] -replace $Kind)) 'before-uninstall.json'
}

# The registry goes back only when a microphone is not on the original that 0.7.0 saved, or that original changed:
# after a full uninstall the microphones are on the vendor effects, and the photo has the filter of 0.7.0 on them.
function Restore-Registry($Photo) {
  $cur = [ordered]@{}
  Add-Mics $cur
  $ids = Get-MicIds $Photo 'saved'
  $both = @(Get-MicIds $cur 'saved' | Where-Object { $ids -contains $_ })
  $changed = $both -and (Compare-State $Photo $cur @($both | ForEach-Object { "saved|$_|" }))
  if (-not ((Test-Path -LiteralPath $Is1) -or (Find-NotAtOriginal $Photo $cur $ids) -or $changed)) { return }
  $tree = Join-Path $Proof 'reg\tree.reg'
  if (Test-Path -LiteralPath $tree) {
    $r = Invoke-Tool reg.exe import, $tree
    if ($r.Code) { throw "reg import tree.reg: $($r.Out)" }
  }
  foreach ($v in Import-Clixml -LiteralPath (Join-Path $Proof 'reg\mics.xml')) {
    $sub = $v.Key -replace '^HKEY_LOCAL_MACHINE\\'
    $k = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($sub, 'ReadWriteSubTree', 'SetValue, ReadKey')
    if (-not $k) { continue }
    if ($null -eq $v.Value) { $k.DeleteValue($v.Name, $false) }
    elseif ($v.Kind -eq 'MultiString') { $k.SetValue($v.Name, [string[]]$v.Value, $v.Kind) }
    else { $k.SetValue($v.Name, $v.Value, $v.Kind) }
    $k.Close()
  }
  'the microphones and their saved originals are back from the photo'
}

function Install-Published($Photo) {
  $setup = Join-Path $Proof 'Ritmelli-0.7.0-setup.exe'
  if ((Get-FileHash -LiteralPath $setup).Hash -ne $PublishedSha) { throw "$setup is not the published 0.7.0 setup" }
  $argv = '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/LOG=`"$(Join-Path $Proof 'setup-0.7.0.log')`""
  if ($Photo['app|Inno Setup: Language']) { $argv += '/LANG=' + ($Photo['app|Inno Setup: Language'] -replace $Kind) }
  if ($Photo['reg|Metricas']) { $argv += '/metricas=' + ($Photo['reg|Metricas'] -replace $Kind) }
  if ($Photo['app|Inno Setup: Selected Tasks'] -match 'desktopicon') { $argv += '/MERGETASKS="desktopicon"' }
  $p = Start-Process -FilePath $setup -ArgumentList $argv -PassThru
  $null = $p.Handle
  if (-not $p.WaitForExit(900000)) { throw 'the 0.7.0 setup still runs after 15 min: run the finish again later' }
  if ($p.ExitCode) { "the 0.7.0 setup exited with $($p.ExitCode): see setup-0.7.0.log" }
}

function Test-Round([string]$App) {
  $since = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  $r = Invoke-Tool schtasks.exe /run, /tn, $Tasks[0]
  if ($r.Code) { return "the update task did not run: $($r.Out)" }
  $log = Join-Path $App 'atualizacao\atualizador.log'
  $done = Wait-Until 300 {
    Get-Content -LiteralPath $log -ErrorAction SilentlyContinue |
      Where-Object { [string]::CompareOrdinal($_, $since) -ge 0 -and $_ -match $RoundDone }
  }
  if (-not $done) { "the update round did not say 'no new version (installed 0.7.0, published 0.7.0)' in 5 min" }
}

function Invoke-Finish {
  $photo = Read-Map 'photo.json'
  $app = $photo['app|Inno Setup: App Path'] -replace $Kind
  Remove-ItemProperty -LiteralPath $HookKey -Name Manifesto, Chave, SoHttps -ErrorAction SilentlyContinue
  foreach ($t in $Tasks) { Invoke-Tool schtasks.exe /end, /tn, $t | Out-Null }
  if (-not (Wait-Until 1800 { -not (Get-Busy $app) })) {
    throw "still running after 30 min, not stopped: $((Get-Busy $app).Name -join ', '). Run the finish again later."
  }
  $pidFile = Join-Path $Proof 'server.pid'
  if (Test-Path -LiteralPath $pidFile) {
    Get-CimInstance Win32_Process -Filter "ProcessId = $([int](Get-Content -LiteralPath $pidFile))" |
      Where-Object CommandLine -like '*http.server*' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  }
  $served = $pidFile, (Join-Path $Proof 'served'), (Join-Path $Proof 'public.txt')
  Remove-Item -LiteralPath $served -Recurse -Force -ErrorAction SilentlyContinue
  Restore-Registry $photo
  $voices = Join-Path $Proof 'vozes'
  if (Test-Path -LiteralPath $voices) {
    $r = Invoke-Tool robocopy.exe $voices, (Join-Path $app 'vozes'), /MIR, /R:2, /W:1, /NJH, /NJS, /NP
    if ($r.Code -ge 8) { throw "the voices did not go back: $($r.Out)" }
  }
  $diff = @(Install-Published $photo)
  foreach ($n in 'Ritmelli', 'Vitrola') {
    $copy = Join-Path $Proof "metricas-$n.json"
    if (Test-Path -LiteralPath $copy) {
      $dir = New-Item -ItemType Directory -Force (Join-Path $LocalRoot $n)
      Copy-Item -LiteralPath $copy (Join-Path $dir.FullName 'metricas.json') -Force
    }
  }
  Remove-Item -Path (Join-Path $app 'atualizacao\Ritmelli-0.900.*-setup.exe') -Force -ErrorAction SilentlyContinue
  Remove-ItemProperty -LiteralPath $TreeKey -Name _sources, _dll_sha256 -ErrorAction SilentlyContinue
  if (-not $photo['hook']) { Remove-Item -LiteralPath $HookKey -Recurse -ErrorAction SilentlyContinue }
  $cur = Read-State $app
  $prefixes = @('app|', 'exe', 'reg|', 'hook', 'task|', 'firewall', 'link|', 'dll', 'vozes|', 'tree|', 'local|library\')
  $prefixes += @(Get-MicIds $photo | ForEach-Object { "fx|$_|", "props|$_|", "saved|$_|" })
  $diff += @(Compare-State $photo $cur $prefixes)
  if (Test-Path -LiteralPath (Join-Path $Proof 'before-uninstall.json')) {
    $diff += @(Compare-State (Read-Map 'before-uninstall.json') $cur 'local|')
  }
  $diff += @(Test-Round $app)
  if ($diff) { $diff; throw 'the lines above are not as in the photo: put them back by hand' }
  'the PC is back on Ritmelli 0.7.0 as in the photo: open it from the Start menu and play music to the microphone'
}

if ($Step) {
  if (-not [Environment]::Is64BitProcess) { throw 'run it in the 64-bit PowerShell' }
  if (-not $Proof) { throw 'give the proof folder: -Proof <folder>' }
  $Proof = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Proof)
  switch ($Step) {
    'photo' { Invoke-Photo $Setup }
    'before-uninstall' { Invoke-BeforeUninstall }
    'finish' { Invoke-Finish }
    default { throw "unknown step '$Step': photo, before-uninstall or finish" }
  }
}
