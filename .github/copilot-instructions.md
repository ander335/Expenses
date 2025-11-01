# GitHub Copilot Suggestions for Expenses Bot

## Instructions
- To run the bot locally use .\run_bot.bat file
- To deploy bot in cloud use .\cloud_deploy.bat service

## Writing code
- When writing new code, add detailed logging using the `logger` object from `logger_config.py`.

## Troubleshooting
- Extract logs using gcloud run services logs read expenses-bot --project gen-lang-client-0006062814 --region europe-central2 --limit 50