# Expenses
Read `./.github/copilot-instractions.md`
These instructions apply to Codex, Claude Code, GitHub Copilot, and any other coding agent working in this repository.

## Repository Skills
- Before starting a task, inspect the repo-local `skills/` folder for a skill that matches the user's request.
- Also inspect the common skills folder at `..\Common\AI\skills`. Use a common skill when it matches the user's request and no more specific repo-local skill applies.

## Available Common Skills
- Common skills are stored one repo level above this repository in `..\Common\AI\skills`.

## Instructions
- Do not run bot locally, it is designed to run in cloud environment only.
- Don't use pylance MCP. Compile and run .py files locally.

## Writing code
- When writing new code, add detailed logging using the `logger` object from `logger_config.py`.
- Writing code, make sure there is no similar logic, functions or blocks. If there is any, try to generalize it and use in both places.
- Keep function docstrings concise: use single-line comments only, no multi-line docstrings with Args/Returns sections.
- Do not test bot functionality by writing simple scripts. Deploy it to cloud right away instead.
- Important! Do not create any diagrams, not README files, not documentation, unless explicitly instructed to do so. This only consumes time and LLM tokens without adding value.