---
name: deploy
description: Use when the user says "deploy", asks to deploy the app, or wants to run cloud_deploy.bat.
---

Run `cloud_deploy.bat` via the Bash tool using:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Set-Location 'G:\projects\Expenses'; .\cloud_deploy.bat"
```
