---
name: health-check
description: Check whether the data pipeline is working - Google access, the master sheet, settings, the last run, Slack alerts and sign-in - and explain the answer in plain English. Read-only; changes nothing. Use when the owner asks "is everything working?", "did it run?", or types /health-check.
---

# Health check

The person asking is usually **Marisol, the owner. She isn't technical.** Everything you say
must be plain English: no code, file paths, stack traces or jargon unless she asks.

## Steps

1. From the repo root, run the read-only checklist:

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.health_check
   ```

   It only ever reads (its Google permissions are read-only). It never posts to Slack. It is
   always safe to run, without asking first.

2. Explain the result in a few short sentences:
   - Start with the answer: "Everything's working" or "Two things need attention".
   - For each line marked `NO`, say what it means and what to do, using the table below.
   - Mention when the last run happened and what it updated, in words.
   - Don't paste the raw checklist unless she asks for it.

3. Don't fix anything as part of this skill. If something needs fixing, say what you'd do and
   ask. Anything that writes to the real sheet, posts to Slack, or deploys needs her OK
   (see `CLAUDE.md`, "How work moves").

## What the `NO` lines mean

| Line | What to tell her | What to suggest |
|---|---|---|
| Google key | The pipeline's key to Google isn't working. | A developer may need to make a new key (`docs/owners-guide.md`, "Who to ask"). |
| Master sheet | The pipeline can't open the sheet. | Check the sheet still exists and is shared with the pipeline's Google account. |
| Settings: old placeholders | The saved settings are from before her choices. | Open the control panel, go to Settings, check the numbers and alert levels, and save. |
| Settings: a problem | Someone edited the settings tab by hand and broke a rule. | Fix it on the control panel's Settings page; the message says what's wrong. |
| Last run: failed | The last run didn't work; the line says why in plain English. | Often temporary. `/rerun` the same days once the cause is fixed. |
| Last run: hasn't run yet | Normal before the first run. | Nothing. |
| Locked tabs | Someone unlocked one of the pipeline's tabs. | Nothing needed: the next run locks it again. Ask whether it was on purpose. |
| GA4 / Search Console | The pipeline can't read that source; the line says why. | Usually an access change in Google Analytics or Search Console. |
| Slack alerts | No Slack link is set up, so alerts are off. | `docs/owners-guide.md`, "Changing where alerts go". |
| Control panel sign-in | Sign-in isn't set up on this computer. | Only matters for running the panel on this computer. |

"Next scheduled run" is information, not a problem. Until the pipeline runs in the cloud
(`docs/ROADMAP.md`, item 7), nothing runs by itself.
