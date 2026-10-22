# Owner's guide: the website data pipeline

*For Marisol. One page: what it does, how to tell it's working, and what to do when it isn't.*

*Still being finished: the daily run in the cloud, and Slack alerts. Until they're done, nothing
runs by itself. `docs/ROADMAP.md` tracks them.*

## What it does

Every morning at **6:00 AM (New York time)** it:

1. **Collects** the last 7 days of website numbers: **sessions** and **total users** from Google Analytics, and **clicks** and **impressions** from Google Search.
2. **Saves** them in the master Google Sheet, one row per day: the **GA4** tab and the **Search Console** tab. Looker Studio reports read from there.
3. **Checks for drops.** If a number's latest week is **25% or more below** the week before, it posts an alert to the Slack channel.

It re-collects the whole last week every morning on purpose. Google keeps adjusting recent days, so older rows correct themselves. Search Console is always 2–3 days behind, so its newest days fill in a little later.

## Is it working?

- **Control panel → Status.** "Working" in green means the last run went fine. If not, it says why in plain words.
- **Or ask Claude Code:** type `/health-check`. It checks everything and tells you what, if anything, needs attention. It can't change anything.

## When an alert arrives in Slack

It names the number, how much it dropped, and which two weeks were compared. Small numbers swing a lot week to week, so **an alert is a nudge to take a look, not an emergency.** Check the GA4 or Search Console tab or Looker Studio. If something real changed (the site was down, a page was removed), that's your answer.

You won't get another alert about the same number for 7 days. Weeks where the earlier total was under 20 are never alerted on, because they're too small to mean anything.

## When something goes wrong

The Status page and `/health-check` always say **what** went wrong in plain English. The common ones:

| It says… | What to do |
|---|---|
| A run **failed** with a reason | Often temporary. Once the reason is fixed, re-collect the missed days (below). |
| "The saved settings are still the old placeholders" | Open **Settings**, check the numbers and alert levels, and **Save**. |
| "Slack refused the alert… make a new Slack link" | The Slack link was removed. See "Changing where alerts go" below. |
| "Google said no (403)" / "can't read" Analytics or Search Console | Someone changed access in Google Analytics or Search Console. Ask for help. |
| "Sign-in didn't work" | Try again with your **work** Google account. Personal Gmail accounts are always refused. |

## Changing things

- **Which numbers, and alert levels:** Control panel → **Settings**. Tick numbers, set the "% drop" for alerts (leave empty for no alert), then **Save**. Alerts only look at counts like sessions or clicks, not rates.
- **Re-collecting days** (to fill a gap, or re-pull a month): Control panel → **Run now**, or type `/rerun` in Claude Code. It shows the days and asks before writing.
- **A number that isn't offered yet:** type `/add-metric` in Claude Code and describe it in your own words.
- **Changing where alerts go:** alerts go to whichever channel the pipeline's **Slack link** points at.
  1. Go to **api.slack.com/apps** (signed in to Slack) and open the pipeline's app.
  2. Open **Incoming Webhooks** → **Add New Webhook to Workspace**, pick the channel, then copy the new link.
  3. Have it put in the pipeline's secret settings as `SLACK_WEBHOOK_URL`.
  4. On the same page, remove the old link.

  Treat the link like a password: anyone who has it can post in that channel.

## Where things are

- **Master Google Sheet:**
  - **GA4** and **Search Console** tabs: the daily numbers.
  - **_settings**, **_runs** and **_alerts** tabs: the pipeline's own records.
  - All of these are **locked** on purpose. Don't edit them by hand; use the control panel.
- **Looker Studio:** the charts and reports.
- **Control panel:** Status, Run history, Run now and Settings. Only Starr Wellness Collective Google accounts can sign in.
- **The code and its records:** the GitHub repository. `docs/decisions.md` lists every decision and why it was made.

## Costs

The Google services it uses are expected to cost nothing at this size. To run in the cloud, Google Cloud needs billing switched on. You approved a **$5 a month maximum**. The plan, once it's set up:
- A warning at **$3**.
- At **$5**, billing switches itself off, and the pipeline **stops** until someone switches billing back on.
- The sheet and Looker Studio keep everything already collected.

## Who to ask

- **Something's broken and `/health-check` doesn't explain it:** *[name and contact of the developer or support person, to be filled in at handover]*.
- **Accounts and access** (Google Workspace, Google Cloud, Slack): *[the Workspace administrator, to be filled in at handover]*.
