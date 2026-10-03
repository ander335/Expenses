---
name: deploy
description: Use when the user says "deploy", asks to deploy the app, or wants to run cloud_deploy.bat.
---

1. Never try to start or run Docker Desktop yourself. If Docker is not running, always ask the user to start it.
2. Run `cloud_deploy.bat` using:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Set-Location 'G:\projects\Expenses'; .\cloud_deploy.bat"
```
