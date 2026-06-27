---
name: troubleshooting
description: >
  Troubleshoot the Expenses bot. Use this skill when the user says "troubleshoot",
  "troubleshoot the bot", or asks to investigate why the bot isn't working.
---

# Troubleshooting the Expenses Bot

Fetch recent logs and report findings to the user.

## Fetch logs

```bash
gcloud run services logs read expenses-bot \
  --project gen-lang-client-0006062814 \
  --region europe-central2 \
  --limit 50
```

## Report

Summarize errors and warnings. Cross-reference with the codebase to trace the root cause. Present findings — error, relevant code, and diagnosis — clearly to the user. Do not make code changes.
