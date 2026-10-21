# Roadmap

Everything left to build, in order. One item at a time, each on its own branch
with its own pull request, and tests passing before the PR is opened.

**Status key:** ✅ done (merged) · 🔄 in progress · ⏳ waiting on a person · ⬜ not started

**How work moves:** Claude builds an item, opens the PR, and summarises it in
plain English. A person reviews and merges. Claude then pulls `main` and starts
the next item.

**When Claude stops and asks:**
- before writing to a real Google Sheet, sending a real email, or deploying anything
- when something only a person can do is needed (accounts, Cloud Console clicks, OAuth setup, answers from Marisol)
- when a decision isn't covered by `CLAUDE.md` or `docs/decisions.md`
- when a test fails and the cause isn't clear

| # | Item | Branch | Status |
|---|---|---|---|
| 1 | Settings and run-history store, plus runner stub | `feat/pipeline-store` | 🔄 PR #5 open, waiting to be merged |
| 2 | API: the five endpoints | `feat/api-backend` | ⬜ |
| 3 | Control panel pages | `feat/web-panel` | ⬜ |
| 4 | Google sign-in for the panel | `feat/panel-sign-in` | ⬜ |
| 5 | Real data: GA4 + Search Console into the sheet | `feat/extract-load` | ⬜ |
| 6 | Alerts | `feat/alerts` | ⬜ |
| 7 | Deployment | `feat/deploy` | ⬜ |
| 8 | Claude Code skills for the owner | `feat/owner-skills` | ⬜ |
| 9 | Owner's guide | `docs/owners-guide` | ⬜ |

---

## 1. Settings and run-history store 🔄

Sheet-backed `_settings` and `_runs` tabs, settings validation with TBD
placeholder defaults, the runner stub (`python -m pipeline.runner`) and the
6 AM New York schedule.

- [x] Sheet confirmed with a person ("GA4 Search Console Pipeline")
- [x] One real run: both tabs created and protected, one `success` row in `_runs`
- [x] PR opened: #5
- [x] Security review fix: tabs are re-checked and re-locked if their protection was removed or made by hand
- [ ] Merged

## 2. API: the five endpoints ⬜

FastAPI app in `api/`: `GET /status`, `GET /runs`, `POST /runs`, `GET /settings`,
`PUT /settings`, as specified in the backend plan. It's a thin layer over
`pipeline.store`, `pipeline.runner` and `pipeline.schedule`.

- Every endpoint requires a verified Google sign-in token from one of the two
  allowed domains (rule 7). Token checking is built and tested here with fake
  tokens; the real sign-in setup is item 4.
- "Run now" hands the run to a **dispatcher**. Locally it starts
  `python -m pipeline.runner` as a separate process. The Cloud Run Job version is
  added in item 7 (decision 15).
- `/status` includes the TBD placeholder warnings, and a warning when a tab was
  found unlocked and re-locked ("please check your settings"). Settings aren't
  wiped in that case, since the owner may have unlocked it on purpose.
- New dependencies, explained in the PR (rule 5): `fastapi`, `uvicorn`, `httpx` (tests only).
- **Done when:** endpoint tests cover success, 401, 403, 409 and 422 for each
  route; no test touches Google; the API runs locally with `uvicorn`.

## 3. Control panel pages ⬜

Next.js app in `web/` with four pages: **Status**, **Run History**, **Settings**, **Run now**.
Plain English throughout; it talks only to the API, never to Google (rule 6).

- **First:** fix `.gitignore`. Its `*.json` rule (a safety net for key files)
  would also hide `web/package.json`'s siblings (`package-lock.json`, `tsconfig.json`).
  The fix allows JSON under `web/` while keeping key files ignored everywhere.
- Settings page shows each rule's plain-English error next to the field, and the
  "still a placeholder" warnings.
- Run now: optional start/end dates, the same limits the API enforces, and a clear
  message if a run is already going.
- **Done when:** component tests pass, `npm run build` succeeds, all four pages
  work against the local API.
- **Needs a person:** Node.js LTS installed (checked at the start of this item).

## 4. Google sign-in for the panel ⬜

Sign in with Google, limited to **starrwellnesscollective.org** and **joinswc.org**
accounts (decision 13). The panel sends the sign-in token to the API, which
already checks it (item 2).

- **Needs a person:** create the OAuth client and consent screen in Google Cloud
  Console, and confirm whether both domains are in the same Google Workspace
  (this decides whether the consent screen can be "Internal").
- **Done when:** an allowed account gets in; any other Google account is turned
  away with a plain message; the panel is never reachable signed-out.

## 5. Real data: GA4 + Search Console into the sheet ⬜

Replace the runner stub with real extract, transform and load steps: pull the
metrics chosen in settings, one row per day (CLAUDE.md), re-pulling a rolling
7-day window (decision 3) so late Search Console data corrects itself.

- Re-pulled days overwrite their existing rows, never duplicate them.
- **Needs a person:** GA4 property ID plus read access, and Search Console
  access (both still pending in `docs/decisions.md`).
- **Will ask:** the layout of the data tab(s), e.g. one tab per source or one
  combined tab. Not decided yet; it shapes the Looker Studio setup.
- **Will ask before:** the first real write of data to the master sheet.

## 6. Alerts ⬜

Compare each day against the thresholds in settings and alert the recipients.
**Switched off automatically** while any of metrics, thresholds or recipients
are still TBD placeholders (decision 17), and the panel says so.

- **Will ask:** how alerts are sent. Settings hold email recipients, but the
  only alerting library installed so far is for a Slack webhook. Sending email
  needs a chosen mail service.
- **Will ask before:** sending any real alert.
- **Needs Marisol:** real metrics, thresholds and recipients, and whether
  recipients must be on the business's own domains. That would block alerts going
  to outside addresses; a security review suggested it, but it's a business rule.

## 7. Deployment ⬜

- Pipeline as a **Cloud Run Job**, triggered by Cloud Scheduler at **6:00 AM
  America/New_York** (decisions 14, 15).
- API on **Cloud Run**; control panel on **Vercel** (decision 18).
- "Run now" in the cloud starts the Cloud Run Job.
- Secrets live in each host's secret settings, never in the repo.
- **Blocker:** Cloud Run needs billing turned on, which conflicts with
  decision 9 (billing off). Someone has to decide this before deployment starts.
- **Needs a person:** a Vercel account, the billing decision, Cloud Console setup.
- **Will ask before:** every deploy.

## 8. Claude Code skills for the owner ⬜

Plain-English slash commands in `.claude/skills/`:
- **`/health-check`**: is everything working? Last run, next run, access to Google, placeholder warnings.
- **`/rerun`**: re-pull a date range, with the same date rules as the panel.
- **`/add-metric`**: add a metric to the pipeline safely, on a branch with tests and a PR.

**Done when:** each skill has been tried end-to-end. Any step that writes to the
real sheet is confirmed with a person first.

## 9. Owner's guide ⬜

`docs/owners-guide.md`: one page for Marisol, no jargon. It covers what the
pipeline does, how to check it's working, what to do when something fails, how to
change settings, and who to ask.

---

## Housekeeping

- `chore/claude-plugins` (shared Claude Code plugin settings) is committed locally
  but was never pushed. Decide whether to push it and open a PR.
- Old local branches `backend-plan` and `chore/editable-install` can be deleted
  once nothing else needs them.
