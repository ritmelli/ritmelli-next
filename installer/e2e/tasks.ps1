# The two SYSTEM tasks of machine/tasks.py, on Windows as an administrator: created,
# read back from the Task Scheduler field by field, and deleted. Then --atualizador
# remove on the update task, and the hook, written in HKLM and read by
# machine/update_hook.py. It refuses a PC that already has either task or
# HKLM\SOFTWARE\Ritmelli.
# Usage: tasks.ps1 [-UpdateTask <name>] [-MicTask <name>] [-Exe <path>]
param(
  [string]$UpdateTask = 'Ritmelli Atualiza',
  [string]$MicTask = '\Ritmelli\Microfone',
  [string]$Exe = "$env:ProgramFiles\Ritmelli\ritmelli.exe"
)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path "$PSScriptRoot\..\.."

function Tasks([string]$code, [string[]]$arguments) {
  uv run --project $root python -c "import sys; from ritmelli.machine import tasks; $code" @arguments
  if ($LASTEXITCODE -ne 0) { throw "python exited with $LASTEXITCODE" }
}

# What users may do with the task, from the ACL Windows enforces: as in v0.7.0's check,
# nothing that writes, deletes or changes the ACL, and run it.
function Users($sddl) {
  $write = 0x2 -bor 0x4 -bor 0x10 -bor 0x100 -bor 0x10000 -bor 0x40000 -bor 0x80000 -bor 0x10000000 -bor 0x40000000
  $run = $false
  foreach ($ace in (New-Object Security.AccessControl.RawSecurityDescriptor $sddl).DiscretionaryAcl) {
    if ($ace.AceType -ne 'AccessAllowed' -or $ace.SecurityIdentifier.Value -notin 'S-1-5-11', 'S-1-5-32-545', 'S-1-1-0', 'S-1-5-4') { continue }
    if ($ace.AccessMask -band $write) { return 'write' }
    if ($ace.AccessMask -band (0x20000000 -bor 0x20)) { $run = $true }
  }
  if ($run) { 'read and run' } else { 'read' }
}

function Check($name, $arguments, $limit, $triggers) {
  [xml]$xml = & "$env:SystemRoot\System32\schtasks.exe" /query /tn $name /xml | Out-String
  $task = $xml.Task
  $service = New-Object -ComObject Schedule.Service
  $service.Connect()
  $found = [ordered]@{
    account   = $task.Principals.Principal.UserId
    level     = $task.Principals.Principal.RunLevel
    sddl      = $task.RegistrationInfo.SecurityDescriptor
    users     = Users $service.GetFolder('\').GetTask($name).GetSecurityDescriptor(4)
    triggers  = @(foreach ($t in $task.Triggers.ChildNodes) { "$($t.LocalName) $($t.Delay)$($t.Repetition.Interval)" }) -join ', '
    limit     = $task.Settings.ExecutionTimeLimit
    instances = $task.Settings.MultipleInstancesPolicy
    command   = $task.Actions.Exec.Command
    arguments = $task.Actions.Exec.Arguments
  }
  $want = [ordered]@{
    account = 'S-1-5-18'; level = 'HighestAvailable'; sddl = 'D:(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGX;;;AU)'; users = 'read and run'
    triggers = $triggers; limit = $limit; instances = 'IgnoreNew'; command = $Exe; arguments = $arguments
  }
  foreach ($field in $want.Keys) {
    if ("$($found[$field])" -ne $want[$field]) { throw "$name`: $field is '$($found[$field])', not '$($want[$field])'" }
  }
  "$name`: " + (($want.Keys | ForEach-Object { "$_ $($found[$_])" }) -join '; ')
}

$either = '(tasks.exists(sys.argv[1]) or tasks.exists(sys.argv[2]))'
Tasks "sys.exit($either and 'a task is there already: run this on a PC without them')" $UpdateTask, $MicTask
try {
  Tasks 'code, out = tasks.create(sys.argv[1], tasks.UPDATE_XML, sys.argv[2]); sys.exit(code and out)' $UpdateTask, $Exe
  Tasks 'code, out = tasks.create(sys.argv[1], tasks.MIC_XML, sys.argv[2]); sys.exit(code and out)' $MicTask, $Exe
  Check $UpdateTask '--atualizador' 'PT2H' 'LogonTrigger PT2M, TimeTrigger PT4H'
  Check $MicTask '--microfone instala-todos' 'PT5M' ''
} finally {
  Tasks "tasks.delete(sys.argv[1], end=True); tasks.delete(sys.argv[2]); sys.exit($either and 'a task is still there')" $UpdateTask, $MicTask
}
'both tasks were created as in v0.7.0, and deleted'

# --atualizador remove, as the uninstaller runs it, on the update task by its real name.
Tasks "sys.exit(tasks.exists(tasks.UPDATE_TASK) and 'the update task is there already')"
try {
  Tasks 'code, out = tasks.create(tasks.UPDATE_TASK, tasks.UPDATE_XML, sys.argv[1]); sys.exit(code and out)' $Exe
  uv run --project $root python -m ritmelli.app --atualizador remove
  if ($LASTEXITCODE -ne 0) { throw "--atualizador remove exited with $LASTEXITCODE" }
  Tasks "sys.exit(tasks.exists(tasks.UPDATE_TASK) and '--atualizador remove left the task')"
} finally {
  Tasks 'tasks.delete(tasks.UPDATE_TASK)'
}
'--atualizador remove deleted the update task, outside the frozen exe'

# The hook in its real key. pytest leaves it alone: a SYSTEM update task would read it.
$ritmelli = 'HKLM:\SOFTWARE\Ritmelli'
if (Test-Path $ritmelli) { throw "$ritmelli is there already: run this on a PC without Ritmelli" }
$url, $public = 'http://127.0.0.1:8765/v0.900.1/manifest.json', 'a test public key'
try {
  New-Item "$ritmelli\Atualizador" -Force | Out-Null
  New-ItemProperty "$ritmelli\Atualizador" Manifesto -PropertyType String -Value $url | Out-Null
  New-ItemProperty "$ritmelli\Atualizador" Chave -PropertyType String -Value $public | Out-Null
  New-ItemProperty "$ritmelli\Atualizador" SoHttps -PropertyType DWord -Value 0 | Out-Null
  Tasks 'from ritmelli.machine import update_hook; sys.exit(update_hook.read() != (sys.argv[1], {1: sys.argv[2]}, False))' $url, $public
} finally {
  if (Test-Path $ritmelli) { Remove-Item $ritmelli -Recurse -Force }
}
'the hook was read from HKLM: the test manifest, the test key alone, http allowed'
