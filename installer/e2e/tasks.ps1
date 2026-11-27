# The two SYSTEM tasks of machine/tasks.py, on Windows as an administrator: created,
# read back from the Task Scheduler field by field, and deleted. It refuses a PC that
# already has either task.
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
  if ($LASTEXITCODE -ne 0) { throw "machine/tasks.py exited with $LASTEXITCODE" }
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
