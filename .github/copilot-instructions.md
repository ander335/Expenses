# GitHub Copilot Suggestions for Expenses Bot

## Instructions
- To deploy bot in cloud use `.\cloud_deploy.bat` command.
- Do not run bot locally, it is designed to run in cloud environment only.
- Don't use pylance MCP. Compile and run .py files locally.

## Writing code
- When writing new code, add detailed logging using the `logger` object from `logger_config.py`.
- Writing code, make sure there is no similar logic, functions or blocks. If there is any, try to generalize it and use in both places.
- Keep function docstrings concise: use single-line comments only, no multi-line docstrings with Args/Returns sections.
- Do not test bot functionality by writing simple scripts. Deploy it to cloud right away instead.
- Important! Do not create any diagrams, not README files, not documentation, unless explicitly instructed to do so. This only consumes time and LLM tokens without adding value.

## Troubleshooting
- Extract logs using gcloud run services logs read expenses-bot --project gen-lang-client-0006062814 --region europe-central2 --limit 50