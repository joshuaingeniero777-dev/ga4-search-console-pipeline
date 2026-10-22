---
name: rerun
description: Re-pull GA4 and Search Console data for chosen days into the master sheet, e.g. to fill a gap after a failed run. Writes to the real sheet, so it always confirms first. Only when the owner types /rerun.
disable-model-invocation: true
---

# Re-pull days of data

The person asking is usually **Marisol, the owner. She isn't technical.** Talk in plain English.

This **writes to the real master sheet**. Never run it without her clear "yes" in this
conversation, after she has seen exactly which days will be pulled.

## Steps

1. **Work out the days.**
   - If she gave days ("last week", "September", "the 3rd to the 10th"), turn them into a first
     and last date (YYYY-MM-DD).
   - If she didn't, the usual choice is the last 7 days ending yesterday. Offer that.
   - Use **New York time** for "today" and "yesterday".

2. **Check the dates against the pipeline's own rules** before asking her to confirm:

   ```powershell
   .\.venv\Scripts\python.exe -c "from datetime import date; from pipeline.runner import resolve_range; from pipeline import schedule; print(resolve_range(date.fromisoformat('FIRST'), date.fromisoformat('LAST'), schedule.today()))"
   ```

   - If it prints an error, it's already in plain English (e.g. "The end date can be yesterday
     at the latest"). Tell her, and suggest days that work.
   - The rules: up to yesterday, back at most 16 months, and no more than 366 days in one go.

3. **Confirm with her in one plain sentence**, for example:
   "I'll re-pull Google Analytics and Search Console for Sep 1 – Sep 30, 2026 into the master
   sheet. Days already there are replaced with fresh numbers; nothing is deleted. OK?"
   Wait for a clear yes.

4. **Run it.** Use her name or email for `--triggered-by`, so the run history shows who started it:

   ```powershell
   .\.venv\Scripts\python.exe -m pipeline.runner --start FIRST --end LAST --trigger manual --triggered-by "Marisol (via Claude Code)"
   ```

   - If it says a run is already in progress, wait a few minutes and offer to try again. Never
     work around that check.

5. **Tell her what happened** in a sentence or two, using the run's own message: how many days
   were updated for each source, and anything that failed and why. Search Console runs 2–3
   days behind, so its newest days may be missing; later runs fill them in.

Never edit the sheet by hand, and never change code as part of this skill.
