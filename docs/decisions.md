# Decisions and assumptions

Running log of choices made on this project, why they were made, and whether
anyone has confirmed them. Anything marked "My call" was an engineering decision
made without stakeholder input and is open to correction.

| # | Decision | Why | Confirmed? |
|---|---|---|---|
| 1 | Service account, not user OAuth | A scheduled job can't depend on a human clicking through a browser login, and it must keep working after my internship ends | Yes — sponsor confirmed the pipeline should outlive the internship |
| 2 | Write output to Google Sheets | Looker Studio needs a data source regardless. Sheets keeps the pipeline simple and leaves the dashboard swappable without touching code | My call |
| 3 | Daily run, re-pulling a rolling 7-day window | Search Console data isn't final for 2–3 days after the fact. A rolling window self-corrects instead of permanently under-reporting | My call |
| 4 | Feature branches merged to main via PR | Produces a reviewable history. Git workflow is a graded skill on this project | My call |
| 5 | Runs in the cloud, not on my laptop | Sponsor confirmed it should keep running post-internship. Rules out Windows Task Scheduler | Yes |
| 6 | pandas pinned at 3.0.5 | pip installed 3.x, not 2.x. Major version, so some behavior differs from most examples online. Pinned exactly so it can't drift | My call |
| 7 | Cloud project under the starrwellnesscollective.org organization | Project belongs to the org rather than to me personally, so it survives my account being deactivated | Yes — org was available at project creation |
| 8 | Service account key has no expiry | Google JSON keys don't rotate automatically. Should be regenerated periodically; consider Workload Identity Federation if this moves to GCP hosting | Open |
| 9 | ~~Billing left disabled on the Cloud project~~ **Superseded 2026-10-22:** Marisol approved billing with a $5/month maximum. Proposed setup: a budget that warns at $3 and automatically switches billing off at $5 (a Google budget on its own only warns). Not built until the user approves the setup | Cloud Run (decisions 15, 18) needs billing on | Marisol approved the $5 cap; the cap setup awaits the user's OK |
| 10 | APIs enabled: GA4 Data, Search Console, Sheets only | Least privilege. GA4 Admin API deliberately left off since we read reports, not configuration | My call |
| 11 | Config via .env + python-dotenv | Keeps environment-specific values out of code. .env.example documents what settings exist without exposing real ones | My call |
| 12 | Control panel settings and run history stored as protected `_settings` and `_runs` tabs in the master Google Sheet | No new service or billing, survives redeploys on any host, and the owner can see it. Secrets stay in env vars, never in the sheet | Yes — confirmed 2026-10-21 |
| 13 | Control panel login allowed for starrwellnesscollective.org and joinswc.org Google Workspace accounts | Both domains belong to the business | Yes — confirmed 2026-10-21 |
| 14 | Daily scheduled run at 6:00 AM, America/New_York | Business timezone; early enough that the sheet is fresh at the start of the workday | Yes — confirmed 2026-10-21, and by Marisol 2026-10-22 |
| 15 | Runs (scheduled and "Run now") execute as a Cloud Run Job, not FastAPI background tasks | A Job runs to completion on its own, so a long run isn't cut off when the API finishes responding | Yes — confirmed 2026-10-21. See open question on billing |
| 16 | "Run now" re-pulls capped at 366 days per run | Keeps a single run inside API quotas and time limits | Yes — confirmed 2026-10-21 |
| 17 | ~~Metrics, alert thresholds, and alert recipients ship with placeholder defaults marked TBD~~ **Superseded by decisions 25–26 (2026-10-22)** | Was waiting on Marisol | Done |
| 18 | API hosted on Cloud Run; control panel hosted on Vercel | Vercel is built for Next.js. The API stays in Google Cloud, next to the pipeline and the service account | Yes — confirmed 2026-10-21. Cloud Run is subject to the billing open question |
| 19 | Google sign-in happens in the API (Authlib), not the panel. The API keeps a signed, HttpOnly session cookie on the panel's own address (the panel forwards `/backend/*` to the API), sessions last 8 hours, and saves and runs are only accepted from the panel's address | Keeps rule 6 literally true: only `api/` talks to Google. No sign-in tokens in the browser | Yes — confirmed 2026-10-21 |
| 20 | Data goes in one tab per source: a GA4 tab and a Search Console tab, each one row per day | The two sources have different columns | Yes — confirmed 2026-10-21 |
| 21 | Alerts compare the latest 7 days' total with the 7 days before (each source's weeks end on its newest reported day) | Daily numbers are tiny (0–2 clicks a day), so single-day comparisons would fire constantly | Yes — confirmed 2026-10-21 |
| 22 | No alert for a metric unless the earlier week's total is at least 20 | Going from 2 clicks to 0 counts as a 100% drop but means nothing | Yes — confirmed 2026-10-21 |
| 23 | Alerts only check counts (sessions, users, page views, clicks, impressions...), not rates or averages (click-through rate, position, engagement/bounce rate, session length). The Settings page says so next to those | Adding up a week of rates means nothing; what a "bad" rate change is hasn't been decided | Yes — confirmed 2026-10-21. Revisit with Marisol |
| 24 | The same metric is emailed at most once per 7 days (again after that if it's still down). Sent alerts are logged in a locked `_alerts` tab | Avoids a near-identical email every morning while a drop is in the comparison | Yes — confirmed 2026-10-21 |
| 25 | Metrics: GA4 sessions and total users; Search Console clicks and impressions. Alert level: 25% week-over-week drop for all four | Marisol's choice | Yes — Marisol, 2026-10-22 |
| 26 | Alerts go to a Slack channel Marisol is in, through a Slack incoming webhook (a secret, kept in `.env` / the host's secret settings). The channel is set by the webhook, so the control panel says so instead of offering a recipients list. Any email sender is kept in the code but unused | Marisol's choice | Yes — Marisol, 2026-10-22 |
| 27 | joinswc.org and starrwellnesscollective.org are in the same Google Workspace, so the sign-in app can be "Internal" (only that Workspace's accounts can reach it) | Confirmed by the user | Yes — 2026-10-22 |

## Open questions

- **Billing cap setup (decision 9):** proposed to the user 2026-10-22; not built until approved. Deployment (roadmap item 7) waits on it.
- Who maintains this after handover? Nobody has been named yet.
- Should the repo move to a company GitHub organization? Currently personal.
- Who else should have Owner access on the Cloud project, so it isn't only me?
- ~~Which shared inbox or Slack channel should alerts go to?~~ A Slack channel Marisol is in (decision 26).
- ~~GA4 property ID and read access~~ and ~~Search Console access~~: granted; confirmed by `scripts/access_check.py` and the first real run (2026-10-21).

## Known risks

- The service account key is a file on disk. If this moves to GCP hosting, Workload Identity Federation removes the file entirely and is the better long-term answer.
- Nobody has confirmed which metrics matter (decision 3 assumes a general set). The first version may need reshaping once someone actually uses the dashboard.