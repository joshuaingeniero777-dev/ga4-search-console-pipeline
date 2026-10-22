---
name: add-metric
description: Start pulling a new number (metric) from Google Analytics or Search Console. Uses the Settings page if the metric is already supported; otherwise adds it to the code safely, on a branch with tests and a pull request. Only when the owner types /add-metric.
disable-model-invocation: true
---

# Add a metric

The person asking is usually **Marisol, the owner. She isn't technical.** Talk in plain English.
Read `CLAUDE.md` first and follow its rules, especially "How work moves".

## 1. Find out what she wants, in her words

For example: "how many people came for the first time" or "page views". Work out which
source it comes from (Google Analytics or Search Console) and its Google name, e.g.
`newUsers` or `screenPageViews`. If you aren't sure, ask; don't guess.

## 2. Is it already supported?

The supported metrics are in `src/pipeline/settings.py` (`GA4_METRICS`, `SEARCH_CONSOLE_METRICS`).
Search Console only has four (clicks, impressions, click-through rate, position), and all four
are already supported.

**If it's already there:** no code change is needed. Tell her:
- Open the control panel, go to **Settings**, tick the number, and save.
- If she wants alerts on it, enter an alert level next to it. Alerts only check counts
  (sessions, users, page views...), not rates or averages (decision 23).

Stop here.

## 3. Not supported yet: check it really exists (read-only)

Try it with the read-only preview. It writes nothing:

```powershell
.\.venv\Scripts\python.exe -m pipeline.extract --ga4-metrics sessions NEWNAME
```

- If it says Google didn't accept the request, the name is wrong. Find the right one; don't add
  an unrecognised name.
- Show her a couple of the numbers it printed and check they look like what she meant.

## 4. Add it to the code, on a branch

Follow `CLAUDE.md`: never work on `main`, one change per branch.

1. `git switch main; git pull; git switch -c feat/metric-NEWNAME`
2. In `src/pipeline/settings.py`:
   - Add the Google name to `GA4_METRICS` (or `SEARCH_CONSOLE_METRICS`).
   - Add a plain-English label to `METRIC_LABELS`.
   - If it's a **count** (adding up a week makes sense), also add it to `COUNT_METRICS`. If it's
     a rate or an average, don't; alerts won't check it.
3. Add a test in `tests/test_settings.py` that the metric is offered with its label.
4. Run all the checks: `.\.venv\Scripts\python.exe -m pytest` and the panel's
   (`cd web; npm test`). The panel gets metric names from the API, so it needs no change.
5. Commit, push, open a PR, wait for the `Tests` check, and merge. This is a code-only change,
   so it doesn't need her OK to merge (`CLAUDE.md`).

## 5. Tell her what's next

In plain English: the new number is now available. To start pulling it, she opens
**Settings** in the control panel, ticks it, and saves. From the next run it gets its own
column in the sheet. Earlier days stay blank unless she uses `/rerun` for them.
