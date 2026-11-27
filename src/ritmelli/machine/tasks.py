"""The two Windows tasks that run ritmelli.exe as SYSTEM.

The setup creates them. A user can read and start them, not change them. The XML is the
one of v0.7.0, byte for byte, descriptions in Portuguese included: it is what the PCs
with v0.7.0 have, and the crossing compares them field by field.
"""

import os
import tempfile
from xml.sax.saxutils import escape

from ritmelli.machine.installed import MIC_TASK, UPDATE_TASK, system32
from ritmelli.ports.process.run import run

TIMEOUT_S = 30.0

UPDATE_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Ritmelli: baixa e instala as atualizações quando o Ritmelli está fechado.</Description>
    <SecurityDescriptor>D:(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGX;;;AU)</SecurityDescriptor>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled><Delay>PT2M</Delay></LogonTrigger>
    <TimeTrigger>
      <Repetition><Interval>PT4H</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <StartBoundary>2026-01-01T00:00:00</StartBoundary><Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Sistema"><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <ExecutionTimeLimit>PT2H</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Sistema">
    <Exec><Command>{exe}</Command><Arguments>--atualizador</Arguments></Exec>
  </Actions>
</Task>
"""

MIC_XML = """<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Ritmelli: adiciona o filtro de microfone aos microfones que ainda não o têm.</Description>
    <SecurityDescriptor>D:(A;;FA;;;SY)(A;;FA;;;BA)(A;;GRGX;;;AU)</SecurityDescriptor>
  </RegistrationInfo>
  <Principals>
    <Principal id="Sistema"><UserId>S-1-5-18</UserId><RunLevel>HighestAvailable</RunLevel></Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Sistema">
    <Exec><Command>{exe}</Command><Arguments>--microfone instala-todos</Arguments></Exec>
  </Actions>
</Task>
"""


def definition(xml: str, exe: str) -> bytes:
    """The file schtasks reads, with exe as the program: UTF-16 with CRLF, as v0.7.0
    writes it."""
    return xml.replace("{exe}", escape(exe)).replace("\n", "\r\n").encode("utf-16")


def _schtasks(*args: str) -> int:
    return run([system32("schtasks.exe"), *args], TIMEOUT_S)[0]


def create(name: str, xml: str, exe: str) -> tuple[int, str]:
    """Creates or replaces the task. The exit code and the output of schtasks."""
    fd, path = tempfile.mkstemp(suffix=".xml")
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(definition(xml, exe))
        command = [system32("schtasks.exe"), "/create", "/tn", name, "/xml", path, "/f"]
        return run(command, TIMEOUT_S)
    finally:
        os.remove(path)


def delete(name: str, *, end: bool = False) -> None:
    """end first stops a run in the middle. Inside that run, it would stop this process
    before the delete."""
    if end:
        _schtasks("/end", "/tn", name)
    _schtasks("/delete", "/tn", name, "/f")


def exists(name: str) -> bool:
    return _schtasks("/query", "/tn", name) == 0


def start(name: str) -> bool:
    """Runs the task now, which a user may do. False when it is missing or did not run."""
    return _schtasks("/run", "/tn", name) == 0


def disarm(running: str) -> list[str]:
    """The app folder failed the protected folder rule in the run of one task. Both go:
    the other one first, each even if the other fails, and both are checked after. Only
    the update task is ended first, when the mic task disarms: a round that waits for the
    app to close would run a setup later. The errors, empty when both are gone."""
    other = UPDATE_TASK if running == MIC_TASK else MIC_TASK
    errors: list[str] = []
    for name, end in ((other, other == UPDATE_TASK), (running, False)):
        try:
            delete(name, end=end)
        except OSError as error:
            errors.append(f"{name}: {error}")
    for name in (other, running):
        try:
            if exists(name):
                errors.append(f"the task {name} is still there")
        except OSError as error:
            errors.append(f"{name}: {error}")
    return errors
