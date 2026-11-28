# Security

Report a flaw in private, so it is not public before the fix.

## How to report

Use [Report a vulnerability](../../security/advisories/new), the private channel of this repository on GitHub.
Do not open a public issue for it.

## What counts

- The updater: the signature of the manifest, and the download of the setup.
- The setup and the uninstaller.
- The tasks that run as SYSTEM, for the update and the mic setup.
- The filter on the microphone, which runs inside the Windows audio service.

## What to send

- The version of Ritmelli.
- The steps, one by one.
- What happens, and what should happen.

## What not to do

Do not test on the PC of another person.
