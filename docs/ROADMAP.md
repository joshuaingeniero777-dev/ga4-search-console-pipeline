# Roadmap

Everything left to build, in order. One item at a time, each on its own branch
with its own pull request, and tests passing before the PR is opened.

**Status key:** ✅ done (merged) · 🔄 in progress · ⏳ waiting on a person · ⬜ not started

**How work moves** (also in `CLAUDE.md`, "How work moves"):
1. Claude builds an item on its own branch and opens a PR.
2. The `Tests` check runs on the PR (pytest, Python 3.14, no credentials). If it fails, Claude fixes it on the same branch.
3. When it passes, Claude squash-merges the PR, deletes the branch, pulls `main`, marks the item done here, gives a short plain-English summary, and starts the next item.

**Claude stops and asks before merging** any PR that touches:
- deployment
- secrets handling
- alerts that send real email

Code that *can* write to the real sheet merges without asking; tests never touch the real sheet.

**Claude also stops and asks:**
- before writing to a real Google Sheet, sending a real email, or deploying anything
- when something only a person can do is needed (accounts, Cloud Console clicks, OAuth setup, answers from Marisol)
- when a decision isn't covered by `CLAUDE.md` or `docs/decisions.md`
- when a test fails and the cause isn't clear

| # | Item | Branch | Status |
|---|---|---|---|
| 0 | Tests run on every PR (GitHub Actions) | `chore/ci` | ✅ PR #6 |
| 1 | Settings and run-history store, plus runner stub | `feat/pipeline-store` | ✅ PR #5 |
| 2 | API: the five endpoints | `feat/api-backend` | ✅ PR #7 |
| 3 | Control panel pages | `feat/web-panel` | ✅ PR #9 |
| 4 | Google sign-in for the panel | `feat/panel-sign-in` | ⏳ built; needs the sign-in client from a person |
| 5 | Real data: GA4 + Search Console into the sheet | `feat/extract-load` | ⬜ |
| 6 | Alerts | `feat/alerts` | ⬜ |
| 7 | Deployment | `feat/deploy` | ⬜ |
| 8 | Claude Code skills for the owner | `feat/owner-skills` | ⬜ |
| 9 | Owner's guide | `docs/owners-guide` | ⬜ |

---

## 1. Settings and run-history store ✅

Sheet-backed `_settings` and `_runs` tabs, settings validation with TBD
placeholder defaults, the runner stub (`python -m pipeline.runner`) and the
6 AM New York schedule.

- [x] Sheet confirmed with a person ("GA4 Search Console Pipeline")
- [x] One real run: both tabs created and protected, one `success` row in `_runs`
- [x] PR opened: #5
- [x] Security review fix: tabs are re-checked and re-locked if their protection was removed or made by hand
- [x] Merged (PR #5, with the user's OK since it writes to the real sheet)

## 2. API: the five endpoints ✅

FastAPI app in `api/`: `GET /status`, `GET /runs`, `POST /runs`, `GET /settings`,
`PUT /settings`, as specified in the backend plan. It's a thin layer over
`pipeline.store`, `pipeline.runner` and `pipeline.schedule`.

- Every endpoint requires a verified Google sign-in token from one of the two
  allowed domains (rule 7). Token checking is built and tested here with fake
  tokens; the real sign-in setup is item 4.
- "Run now" hands the run to a **dispatcher**. Locally it starts
  `python -m pipeline.runner` as a separate process. The Cloud Run Job version is
  added in item 7 (decision 15).
- `/status` includes the TBD placeholder warnings, and a warning when the API
  found a tab unlocked and re-locked it ("please check your settings"). The warning
  lasts until the API restarts. Settings aren't wiped in that case, since the owner
  may have unlocked it on purpose. Re-locks done by the scheduled job go to its log.
- New dependencies, explained in the PR (rule 5): `fastapi`, `uvicorn`, `httpx2` (tests only).
- Without `GOOGLE_OAUTH_CLIENT_ID` set, the API refuses everyone (fails closed).
- The panel should poll `/status` no faster than every 15 seconds (Sheets read quota).
- **Done when:** endpoint tests cover success, 401, 403, 409 and 422 for each
  route; no test touches Google; the API runs locally with `uvicorn`.

## 3. Control panel pages ✅

Next.js app in `web/` with four pages: **Status**, **Run History**, **Settings**, **Run now**.
Plain English throughout; it talks only to the API, never to Google (rule 6).

- [x] `.gitignore` fixed: `web/package-lock.json` and `web/tsconfig.json` are allowed
  by name. Any other JSON, including a Google key file with a random name, stays
  ignored everywhere.
- [x] Settings page checks each rule next to its field before saving, shows the
  API's plain-English reason for anything else, and shows the "still a placeholder" warnings.
- [x] Run now: the usual 7 days, or chosen dates; a clear message if a run is already going.
- [x] `GET /settings` now also returns the metric choices and limits, so the panel never
  keeps its own copy of the rules.
- [x] `python -m scripts.dev_api`: the API with a pretend sheet and pretend sign-in, for
  working on the panel without touching Google.
- [x] Tests: 29 panel tests; lint, type-check and build pass; GitHub runs them on every PR.
- [x] Tried end to end: the panel's production build plus the dev API; all four pages
  load, Run now works and refuses a second click, bad settings are explained.
- Node.js 24 was already installed.

## 4. Google sign-in for the panel ⏳

Sign in with Google, limited to **starrwellnesscollective.org** and **joinswc.org**
accounts (decision 13). Sign-in happens in the API (decision 19).

- [x] `/auth/login`, `/auth/callback`, `/auth/me`, `/auth/logout` in the API (Authlib, PKCE).
  Session cookie: signed, HttpOnly, SameSite=Lax, HTTPS-only once the panel is on HTTPS, 8 hours.
- [x] Turned away: personal Gmail, other companies' Workspaces, unverified emails,
  emails that don't match their domain. People are only ever sent back to a page on
  the panel itself.
- [x] Saves, runs and sign-out are refused unless they come from the panel's own address.
- [x] Locked (nobody gets in) until the client ID, client secret and a long session
  secret are all set.
- [x] Panel: every page is behind a sign-in gate; it explains a refused or cancelled
  sign-in, and returns to sign-in if a session runs out mid-visit.
- [x] Checked live with placeholder settings: the panel forwards the sign-in to Google
  and the cookie lands on the panel's own address.
- [ ] **Needs a person:** the steps below.
- [ ] Real sign-in tried with an allowed account and with a personal Gmail account.

**Steps for a person (Google Cloud Console, project `ga4-search-console-pipeline`):**
1. **Check the Workspace question:** in https://admin.google.com go to *Account > Domains >
   Manage domains*. If both joinswc.org and starrwellnesscollective.org are listed, they're
   one Workspace.
2. **Google Auth Platform > Branding:** app name "SWC pipeline control panel", a support
   email, and the developer contact email.
3. **Audience:** *Internal* if both domains are one Workspace; otherwise *External*, then
   **Publish app** so it's "In production". Either way, the API's domain check turns everyone
   else away.
4. **Data access:** only `openid`, `email` and `profile`. These are basic scopes, so Google
   needs no app review.
5. **Clients > Create client > Web application**, named "Control panel (local)":
   - Authorized JavaScript origins: `http://localhost:3000`
   - Authorized redirect URIs: `http://localhost:3000/backend/auth/callback`
   - The live address (Vercel) is added in item 7.
6. Put the client ID and secret in `.env` at the repo root, as in `.env.example`, and
   generate `SESSION_SECRET`. **Never paste the secret into chat or commit it.**
7. Tell Claude it's done. Trying a real sign-in reads the real sheet, so it happens with
   your OK.

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
- ~~Old local branches `backend-plan` and `chore/editable-install`~~: deleted (both were already in `main`).
- `npm audit` reports 5 "high" issues, all in the lint tooling (`eslint-config-next` → `fast-glob` →
  `micromatch` → `braces`). They only run on a developer's computer, never in the panel itself.
  npm's suggested fix is a downgrade to Next.js 14, so it was not applied. Revisit when
  `eslint-config-next` updates.
