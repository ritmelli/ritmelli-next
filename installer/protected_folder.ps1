# The protected folder rule of the setup, the same as src/ritmelli/machine/protected_folder.py,
# run by the system PowerShell before the setup uses the app folder. Both SYSTEM tasks run
# ritmelli.exe from it, and the update task runs the downloaded setup from it: only a folder
# that the system and the administrators alone can change will do.
#
# - the path, normalized, is inside the root, and neither it, nor a parent, nor anything in it
#   is a reparse point;
# - the owner of the folder and of everything in it is SYSTEM, Administrators or
#   TrustedInstaller;
# - no allow ACE gives another principal write (of the data, the attributes or the extended
#   attributes), append or create, delete (of children too), WRITE_DAC or WRITE_OWNER (of the
#   inherit-only ones, only that of CREATOR OWNER is left out); the same holds for each folder
#   from the root (included) to the parent of the destination. A null or unreadable DACL fails,
#   and so does a name Windows does not open as it is (ending in a dot or a space);
# - in microfone\log, LocalService (audiodg.exe writes the filter log) may write, create and
#   delete, never WRITE_DAC or WRITE_OWNER on the folder, and may own the files (with full
#   control of its own), never the folder.
# A destination that does not exist yet is checked by the parents that exist.
#
# The setup runs this file as text (a scriptblock), whatever the script execution policy:
#   & ([scriptblock]::Create([IO.File]::ReadAllText('protected_folder.ps1'))) -Folder <destination> -Root <root> -Answer <file>
# It writes "OK" to -Answer, or the reason it refuses (ASCII only, for the Inno log).
param([Parameter(Mandatory = $true)][string]$Folder, [Parameter(Mandatory = $true)][string]$Root,
      [Parameter(Mandatory = $true)][string]$Answer)

$owners = @('S-1-5-18', 'S-1-5-32-544', 'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464')
$localService = 'S-1-5-19'
# inherit-only, it becomes the ACE of whoever creates (that of CREATOR GROUP would become the
# one of their primary group, None)
$creatorOwner = 'S-1-3-0'
# FILE_WRITE_DATA, FILE_APPEND_DATA, FILE_WRITE_EA, FILE_DELETE_CHILD, FILE_WRITE_ATTRIBUTES
# (enough to turn an empty folder into a junction), DELETE, WRITE_DAC, WRITE_OWNER,
# GENERIC_WRITE, GENERIC_ALL
$write = 0x2 -bor 0x4 -bor 0x10 -bor 0x40 -bor 0x100 -bor 0x10000 -bor 0x40000 -bor 0x80000 -bor 0x40000000 -bor 0x10000000
$changeAcl = 0x40000 -bor 0x80000 -bor 0x10000000
$reparse = [int][IO.FileAttributes]::ReparsePoint
$directory = [int][IO.FileAttributes]::Directory

# The object as the rule reads it: $null if it does not exist; else its attributes, without
# following a reparse point, and, when it is not one, its security descriptor (owner and DACL).
function Read-Entry($path) {
  try { $a = [int][IO.File]::GetAttributes($path) }
  catch [IO.FileNotFoundException], [IO.DirectoryNotFoundException] { return $null }
  $o = @{ Path = $path; Folder = ($a -band $directory) -ne 0; Reparse = ($a -band $reparse) -ne 0 }
  if (-not $o.Reparse) {
    $sections = [Security.AccessControl.AccessControlSections]'Owner, Access'
    $acl = if ($o.Folder) { [IO.Directory]::GetAccessControl($path, $sections) } else { [IO.File]::GetAccessControl($path, $sections) }
    [byte[]]$binary = $acl.GetSecurityDescriptorBinaryForm()
    $o.Sd = [Security.AccessControl.RawSecurityDescriptor]::new($binary, 0)
  }
  $o
}

# Why the owner or the DACL fails, or $null.
function Get-ObjectReason($o, [bool]$inLog) {
  $owner = if ($o.Sd.Owner) { $o.Sd.Owner.Value } else { $null }
  if (-not ($owners -contains $owner) -and -not ($inLog -and -not $o.Folder -and $owner -eq $localService)) {
    return "$($o.Path) is owned by $owner"
  }
  $dacl = $o.Sd.DiscretionaryAcl
  if ($null -eq $dacl) { return "$($o.Path) has a null DACL" }
  foreach ($ace in $dacl) {
    $inheritOnly = ([int]$ace.AceFlags -band 0x08) -ne 0
    # on a file, an inherit-only ACE applies to nothing and has no one to pass to
    if (-not $o.Folder -and $inheritOnly) { continue }
    $type = [int]$ace.AceType
    if (@(1, 6, 10, 12) -contains $type) { continue }  # deny: it only takes access away
    if (@(0, 9) -notcontains $type) { return "$($o.Path) has an ACE of type $type" }
    $sid = $ace.SecurityIdentifier.Value
    $mask = [int]$ace.AccessMask
    if (($owners -contains $sid) -or (($mask -band $write) -eq 0)) { continue }
    if ($inheritOnly -and $sid -eq $creatorOwner) { continue }
    # full control only on a log file LocalService owns (the micfx.log audiodg.exe makes when it rotates)
    if ($inLog -and $sid -eq $localService -and ((($mask -band $changeAcl) -eq 0) -or (-not $o.Folder -and $owner -eq $localService))) { continue }
    return "$($o.Path) lets $sid write or change it (access 0x$('{0:x8}' -f $mask))"
  }
  $null
}

# Why the folder or something in it fails, or $null. It never enters a reparse point: one fails.
function Get-TreeReason($o) {
  $stack = New-Object System.Collections.Stack
  $stack.Push(@($o, ''))
  $ordinal = [StringComparison]::OrdinalIgnoreCase
  while ($stack.Count) {
    $o, $rel = $stack.Pop()
    if ($o.Reparse) { return "$($o.Path) is a reparse point" }
    $parts = @($rel -split '\\' | Where-Object { $_ })
    # microfone\log itself only as a folder: a file of that name is not the filter log. Ordinal,
    # as the lower() of the exe: -eq compares by culture, and would find 'log' equal to 'log'
    # with an invisible character at the end
    $inLog = $parts.Count -ge 2 -and [string]::Equals($parts[0], 'microfone', $ordinal) -and
             [string]::Equals($parts[1], 'log', $ordinal) -and ($parts.Count -gt 2 -or $o.Folder)
    $reason = Get-ObjectReason $o $inLog
    if ($reason) { return $reason }
    if ($o.Folder) {
      foreach ($child in [IO.Directory]::EnumerateFileSystemEntries($o.Path)) {
        # Windows drops a trailing dot or space when it opens a name: the read would find another object
        if ($child -match '[. ]$') { return "$child has a name Windows can't open" }
        # MAX_PATH: without \\?\, Windows would say it does not exist, and it would pass unchecked
        if ($child.Length -ge 260) { return "$child is too long to check" }
        $entry = Read-Entry $child
        if ($entry) { $stack.Push(@($entry, "$rel\$([IO.Path]::GetFileName($child))")) }
      }
    }
  }
  $null
}

function Get-Reason {
  # GetFullPath of the .NET Framework expands a short name (C:\PROGRA~1 becomes C:\Program Files),
  # and the exe, by sys.executable, does not: the same folder would pass here and fail there. An
  # alias is a part of up to 8 characters with a ~ and a digit, and an extension of up to 3; a long
  # name with a ~ (Ritmelli~2026) is not one
  foreach ($part in ($Folder -split '[\\/]' | Select-Object -Skip 1)) {
    $name = $part.TrimEnd('. ')  # Windows drops a trailing dot or space
    if ($name -match '^[^.]{1,8}(\.[^.]{1,3})?$' -and $name.Split('.')[0] -match '~[0-9]') {
      return "$Folder has a short (8.3) name"
    }
  }
  # before GetFullPath: Windows drops a trailing dot or space, and the read of a parent (a prefix of
  # the path) would find another object, or none, and the walk would stop there before the real one
  foreach ($part in @($Folder -split '[\\/]' | Select-Object -Skip 1) + @($Root -split '[\\/]' | Select-Object -Skip 1)) {
    if ($part -ne '.' -and $part -ne '..' -and $part -match '[. ]$') { return "$Folder has a name Windows can't open" }
  }
  $f = [IO.Path]::GetFullPath($Folder).TrimEnd('\')
  $r = [IO.Path]::GetFullPath($Root).TrimEnd('\')
  if (-not $f.StartsWith("$r\", [StringComparison]::OrdinalIgnoreCase)) { return "$f is outside $r" }
  # before the walk: a parent that does not exist yet would stop it before the end
  if ($f.Length -ge 260) { return "$f is too long to check" }
  $inRoot = @($r.Substring(3) -split '\\' | Where-Object { $_ }).Count
  $parts = @($f.Substring(3) -split '\\' | Where-Object { $_ })
  $path = $f.Substring(0, 3)
  for ($i = 0; $i -le $parts.Count; $i++) {
    if ($i) { $path = Join-Path $path $parts[$i - 1] }
    $o = Read-Entry $path
    if (-not $o) {
      # the destination, or a parent of it, does not exist yet: the parents that exist count, the root too
      if ($i -le $inRoot) { return "$r doesn't exist" }
      return $null
    }
    if ($o.Reparse) { return "$path is a reparse point" }
    if (-not $o.Folder) { return "$path is not a folder" }
    if ($i -eq $parts.Count) { return Get-TreeReason $o }
    if ($i -ge $inRoot) {
      $reason = Get-ObjectReason $o $false
      if ($reason) { return $reason }
    }
  }
  $null
}

try {
  if ($Folder -notmatch '^[A-Za-z]:\\' -or $Root -notmatch '^[A-Za-z]:\\') { $text = "$Folder is not an absolute path" }
  else { $text = Get-Reason }
} catch {
  $text = "couldn't check ${Folder}: $($_.Exception.Message)"
}
if (-not $text) { $text = 'OK' }
$ascii = -join ($text.ToCharArray() | ForEach-Object { if ([int]$_ -lt 128) { $_ } else { '?' } })
[IO.File]::WriteAllText($Answer, $ascii)
