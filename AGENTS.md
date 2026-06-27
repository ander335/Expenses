# Expenses
Read `./.github/copilot-instractions.md`
These instructions apply to Codex, Claude Code, GitHub Copilot, and any other coding agent working in this repository.

## Repository Skills
- Before starting a task, inspect the repo-local `skills/` folder for a skill that matches the user's request.
- Also inspect the common skills folder at `..\Common\AI\skills`. Use a common skill when it matches the user's request and no more specific repo-local skill applies.

## Available Common Skills
- Common skills are stored one repo level above this repository in `..\Common\AI\skills`.

## Running deploy from bash
To run `cloud_deploy.bat` via the Bash tool, use:
`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Set-Location 'G:\projects\Expenses'; .\cloud_deploy.bat"`