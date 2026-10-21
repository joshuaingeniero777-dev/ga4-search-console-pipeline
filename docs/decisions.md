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
| 9 | Billing left disabled on the Cloud project | GA4 Data, Search Console, and Sheets APIs are free within quota. Avoids tying the project to a card or a 90-day trial | My call — revisit if Phase 10 lands on Cloud Scheduler |
| 10 | APIs enabled: GA4 Data, Search Console, Sheets only | Least privilege. GA4 Admin API deliberately left off since we read reports, not configuration | My call |
| 11 | Config via .env + python-dotenv | Keeps environment-specific values out of code. .env.example documents what settings exist without exposing real ones | My call |
| 12 | Control panel settings and run history stored as protected `_settings` and `_runs` tabs in the master Google Sheet | No new service or billing, survives redeploys on any host, and the owner can see it. Secrets stay in env vars, never in the sheet | Yes — confirmed 2026-10-21 |
| 13 | Control panel login allowed for starrwellnesscollective.org and joinswc.org Google Workspace accounts | Both domains belong to the business | Yes — confirmed 2026-10-21 |
| 14 | Daily scheduled run at 6:00 AM, America/New_York | Business timezone; early enough that the sheet is fresh at the start of the workday | Yes — confirmed 2026-10-21 |
| 15 | Runs (scheduled and "Run now") execute as a Cloud Run Job, not FastAPI background tasks | A Job runs to completion on its own, so a long run isn't cut off when the API finishes responding | Yes — confirmed 2026-10-21. See open question on billing |
| 16 | "Run now" re-pulls capped at 366 days per run | Keeps a single run inside API quotas and time limits | Yes — confirmed 2026-10-21 |
| 17 | Metrics, alert thresholds, and alert recipients ship with placeholder defaults marked TBD | Waiting on Marisol. Code is built so the real values are a settings change, not a code change | Pending — owner to supply values |
| 18 | API hosted on Cloud Run; control panel hosted on Vercel | Vercel is built for Next.js. The API stays in Google Cloud, next to the pipeline and the service account | Yes — confirmed 2026-10-21. Cloud Run is subject to the billing open question |
| 19 | Google sign-in happens in the API (Authlib), not the panel. The API keeps a signed, HttpOnly session cookie on the panel's own address (the panel forwards `/backend/*` to the API), sessions last 8 hours, and saves and runs are only accepted from the panel's address | Keeps rule 6 literally true: only `api/` talks to Google. No sign-in tokens in the browser | Yes — confirmed 2026-10-21 |
| 20 | Data goes in one tab per source: a GA4 tab and a Search Console tab, each one row per day | The two sources have different columns | Yes — confirmed 2026-10-21 |

## Open questions

- **Cloud Run vs. billing off (decisions 9 and 15 conflict). Waiting on Marisol (asked 2026-10-21); deployment (roadmap item 7) is on hold until then.** Cloud Run requires a billing account linked to the project, even when usage stays inside the free tier. Either billing gets enabled (likely $0/month at this volume, ideally with a budget alert), or runs need a host that doesn't require billing.
- Metrics to pull, alert threshold values, and alert recipients: waiting on Marisol (decision 17).

- Who maintains this after handover? Nobody has been named yet.
- Should the repo move to a company GitHub organization? Currently personal.
- Who else should have Owner access on the Cloud project, so it isn't only me?
- Which shared inbox or Slack channel should alerts go to? Must not be my personal email.
- GA4 property ID and read access — requested, not yet granted.
- Search Console access — requested. Usually needs a property Owner specifically, which may be a different person.

## Known risks

- The service account key is a file on disk. If this moves to GCP hosting, Workload Identity Federation removes the file entirely and is the better long-term answer.
- Nobody has confirmed which metrics matter (decision 3 assumes a general set). The first version may need reshaping once someone actually uses the dashboard.