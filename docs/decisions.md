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

## Open questions

- Who maintains this after handover? Nobody has been named yet.
- Should the repo move to a company GitHub organization? Currently personal.
- Who else should have Owner access on the Cloud project, so it isn't only me?
- Which shared inbox or Slack channel should alerts go to? Must not be my personal email.
- GA4 property ID and read access — requested, not yet granted.
- Search Console access — requested. Usually needs a property Owner specifically, which may be a different person.

## Known risks

- The service account key is a file on disk. If this moves to GCP hosting, Workload Identity Federation removes the file entirely and is the better long-term answer.
- Nobody has confirmed which metrics matter (decision 3 assumes a general set). The first version may need reshaping once someone actually uses the dashboard.