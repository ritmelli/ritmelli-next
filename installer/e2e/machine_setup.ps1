# The machine part of the setup on a clean machine, as an administrator, with the hook. It
# refuses a PC where Ritmelli is. The setup makes both SYSTEM tasks as v0.7.0 made them,
# read back field by field, and puts the result of the mic setup in its log. Run again as
# SYSTEM by a temporary task, as the update task runs it, each line of [Run] exits as it did
# for the person who installed. Last, a setup built without the filter DLL exits with 9.
# Usage: machine_setup.ps1 -Build <the folder with build-info.json and the setup> -NoDll <the setup without micfx.dll>
#Requires -RunAsAdministrator
param([Parameter(Mandatory)][string]$Build, [Parameter(Mandatory)][string]$NoDll)
$ErrorActionPreference = 'Stop'
# Wait-Until and the names v0.7.0 left
. "$PSScriptRoot\crossing_photo.ps1"
if ((Test-Path -LiteralPath $Is1) -or (Test-Path -LiteralPath $RitmelliKey) -or (Test-Path "$env:ProgramFiles\Ritmelli*")) {
  throw 'Ritmelli is on this PC: run this on a clean machine'
}

$info = Get-Content -LiteralPath (Join-Path $Build 'build-info.json') -Raw | ConvertFrom-Json
$name = "Ritmelli-$($info.version)-setup.exe"
$setup = Join-Path $Build $name
if ((Get-FileHash -LiteralPath $setup).Hash -ne $info.artifacts.$name.sha256) { throw "$name is not the one in build-info.json" }
$exe = "$env:ProgramFiles\Ritmelli\ritmelli.exe"
$logs = New-Item -ItemType Directory -Force (Join-Path $env:TEMP 'machine-setup')
$silent = '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'

function Install([string]$File, [int]$Expected, [string]$Log) {
  $p = Start-Process -FilePath $File -ArgumentList ($silent + "/LOG=`"$Log`"") -PassThru
  $null = $p.Handle
  if (-not $p.WaitForExit(600000)) { throw "the setup still runs after 10 min: $Log" }
  if ($p.ExitCode -ne $Expected) { Get-Content -LiteralPath $Log -Tail 30; throw "the setup exited with $($p.ExitCode), not $Expected" }
}

# The update task runs the setup as SYSTEM. Here a temporary task does, and gives its exit code.
function Install-AsSystem([string]$File, [string]$Log) {
  $task = "RitmelliSetupAsSystem-$PID"
  $action = New-ScheduledTaskAction -Execute $File -Argument (($silent + "/LOG=`"$Log`"") -join ' ')
  $principal = New-ScheduledTaskPrincipal -UserId 'S-1-5-18' -LogonType ServiceAccount -RunLevel Highest
  Register-ScheduledTask -TaskName $task -Action $action -Principal $principal | Out-Null
  try {
    Start-ScheduledTask -TaskName $task
    # 267011 before the task ran, 267009 while it runs
    $done = Wait-Until 600 { Get-ScheduledTaskInfo -TaskName $task | Where-Object { $_.LastTaskResult -notin 267009, 267011 } }
    if (-not $done) { throw "the setup as SYSTEM still runs after 10 min: $Log" }
    $done.LastTaskResult
  } finally {
    Unregister-ScheduledTask -TaskName $task -Confirm:$false
  }
}

# The exit code of each line of [Run] in a setup log, by its parameters.
function Get-Exits([string]$Log) {
  $exits = [ordered]@{}
  $parameters = $null
  foreach ($line in Get-Content -LiteralPath $Log) {
    if ($line -match 'Parameters: (.*)$') { $parameters = $Matches[1] -replace ' --saida "[^"]*"' }
    elseif ($line -match 'Process exit code: (\d+)' -and $parameters) { $exits[$parameters] = [int]$Matches[1]; $parameters = $null }
  }
  $exits
}

# Each field of a task, as tasks.ps1 reads it: what users may do comes from the ACL Windows enforces.
function Test-Task([string]$Name, [string]$Arguments, [string]$Limit, [string]$Triggers) {
  $task = ([xml](& "$env:SystemRoot\System32\schtasks.exe" /query /tn $Name /xml | Out-String)).Task
  $service = New-Object -ComObject Schedule.Service
  $service.Connect()
  $enforced = $service.GetFolder('\').GetTask($Name).GetSecurityDescriptor(4)
  $users = @((New-Object Security.AccessControl.RawSecurityDescriptor $enforced).DiscretionaryAcl | Where-Object {
    $_.AceType -eq 'AccessAllowed' -and $_.SecurityIdentifier.Value -in 'S-1-5-11', 'S-1-5-32-545', 'S-1-1-0', 'S-1-5-4' })
  $write = 0x2 -bor 0x4 -bor 0x10 -bor 0x100 -bor 0x10000 -bor 0x40000 -bor 0x80000 -bor 0x10000000 -bor 0x40000000
  $found = [ordered]@{
    account = $task.Principals.Principal.UserId; level = $task.Principals.Principal.RunLevel
    sddl = $task.RegistrationInfo.SecurityDescriptor
    'users write' = [bool]($users | Where-Object { $_.AccessMask -band $write })
    'users run' = [bool]($users | Where-Object { $_.AccessMask -band (0x20000000 -bor 0x20) })
    triggers = @(foreach ($t in $task.Triggers.ChildNodes) { "$($t.LocalName) $($t.Delay)$($t.Repetition.Interval)" }) -join ', '
    limit = $task.Settings.ExecutionTimeLimit; instances = $task.Settings.MultipleInstancesPolicy
    command = $task.Actions.Exec.Command; arguments = $task.Actions.Exec.Arguments
  }
  $want = [ordered]@{
    account = 'S-1-5-18'; level = 'HighestAvailable'; sddl = 'D:(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGX;;;AU)'
    'users write' = 'False'; 'users run' = 'True'; triggers = $Triggers; limit = $Limit; instances = 'IgnoreNew'
    command = $exe; arguments = $Arguments
  }
  foreach ($field in $want.Keys) {
    if ("$($found[$field])" -ne $want[$field]) { throw "$Name`: $field is '$($found[$field])', not '$($want[$field])'" }
  }
  "$Name`: " + (($want.Keys | ForEach-Object { "$_ $($found[$_])" }) -join '; ')
}

function Test-Tasks {
  Test-Task $Tasks[0] '--atualizador' 'PT2H' 'LogonTrigger PT2M, TimeTrigger PT4H'
  Test-Task $Tasks[1] '--microfone instala-todos' 'PT5M' ''
}

New-Item -Path $HookKey -Force | Out-Null
New-ItemProperty -LiteralPath $HookKey -Name Manifesto -Value 'http://127.0.0.1:8765/v0.900.1/manifest.json' | Out-Null
try {
  $user = Join-Path $logs 'user.log'
  Install $setup 0 $user
  $lines = @(Select-String -LiteralPath $user -Pattern ' (devices|mic filter): ' | ForEach-Object Line)
  if (-not ($lines -match ' mic filter: ok$') -or -not ($lines -match ' devices: ')) { $lines; throw "the setup log has no 'mic filter: ok' or no 'devices:' line" }
  $lines
  Test-Tasks
  'for the user, the setup logged the mic setup and made both tasks as v0.7.0 did'

  $system = Join-Path $logs 'system.log'
  $code = Install-AsSystem $setup $system
  if ($code -ne 0) { Get-Content -LiteralPath $system -Tail 30; throw "as SYSTEM, the setup exited with $code" }
  $before, $after = (Get-Exits $user), (Get-Exits $system)
  if ((@($after.Keys) -join '|') -ne (@($before.Keys) -join '|')) {
    throw "as SYSTEM, [Run] ran '$(@($after.Keys) -join "', '")', not '$(@($before.Keys) -join "', '")'"
  }
  foreach ($k in $after.Keys) {
    "  $k -> $($after[$k]) as SYSTEM, $($before[$k]) for the user"
    if ($after[$k] -ne 0 -and $before[$k] -eq 0) { throw "as SYSTEM, $k exited with $($after[$k])" }
  }
  Test-Tasks
  'as SYSTEM, each line of [Run] exited as it did for the user, and both tasks stayed as v0.7.0 made them'

  $broken = Join-Path $logs 'no-filter-dll.log'
  Install $NoDll 9 $broken
  $why = Select-String -LiteralPath $broken -Pattern 'mic filter: failed: FileNotFoundError' | Select-Object -First 1
  if (-not $why) { Get-Content -LiteralPath $broken -Tail 30; throw 'without the filter DLL, the setup exited with 9 for another reason' }
  "without the filter DLL, the setup exited with 9: $($why.Line)"
} finally {
  Remove-Item -LiteralPath $RitmelliKey -Recurse -Force -ErrorAction SilentlyContinue
}
