# GA4 + Search Console Pipeline

## What this project is

An automated pipeline for Starr Wellness Collective (joinswc.org). It pulls Google Analytics 4 and Google Search Console data into a Google Sheet on a schedule, sends alerts when numbers look wrong, and has a web control panel for managing it.

## Who uses it

- **The owner (Marisol) is non-technical.** She will maintain this after the original developer leaves. Anything she sees (the control panel, error messages, command output, summaries) must be plain English with no jargon or stack traces.
- Future developers or AI agents may also work on it. This file is their starting point.

## Architecture

```
ga4-search-console-pipeline/
├─ src/pipeline/     Python ETL: extract (GA4, Search Console), transform, load (Sheets), alerts
├─ api/              FastAPI backend. The only thing that talks to Google APIs and the pipeline.
├─ web/              Next.js control panel. Talks ONLY to the FastAPI backend, never to Google directly.
├─ config/           settings.example.toml (template, safe to commit)
├─ tests/            pytest tests for pipeline and api
└─ docs/             scoping notes, decision log, owner's guide
```

### Control panel scope

The control panel is NOT a dashboard. Charts and reporting live in Looker Studio. The panel has four jobs:

1. **Status**: did the last run succeed, when is the next one, plain-English reason if it failed
2. **Run history**: list of past runs with outcome
3. **Settings**: metrics pulled, alert thresholds, alert recipients
4. **Run now**: trigger a run, with an optional date range for re-pulls

### API endpoints (FastAPI)

- `GET /status`
- `GET /runs`
- `POST /runs` (body: optional start_date, end_date)
- `GET /settings`
- `PUT /settings` (validated; reject anything out of range)

## Decisions already made (do not change without asking)

- Auth to Google: service account, not user OAuth
- Data destination: Google Sheets, one master sheet per business
- Dashboards: Looker Studio
- Storage granularity: one row per day; reporting rolls up to weekly/monthly
- Hosting: cloud, because this must keep running after the internship ends
- Version control: feature branches and pull requests into `main`

## Rules for any agent working here

1. **Never commit secrets.** `service-account.json`, `.env`, and anything with keys stay gitignored. Never print their contents.
2. **Never work on `main`.** Create a branch first.
3. **Small changes.** One feature per branch. If a task touches more than one of `src/`, `api/`, `web/`, say so before starting.
4. **Run the tests before saying something is done.** If tests do not exist for what you changed, write them.
5. **Do not add dependencies** without explaining why in the PR description.
6. **The frontend never calls Google APIs.** All Google access goes through `api/`.
7. **The control panel must require login**, restricted to the business's Google Workspace accounts. It can trigger runs and change settings, so it is never public.
8. **Explain changes in plain English** at the end of every task: what changed, why, and how to undo it.
9. **When unsure, stop and ask.** Do not guess at business rules (thresholds, metrics, recipients).

## How work moves (pull requests and merging)

Work follows `docs/ROADMAP.md`, one item at a time, each on its own branch and PR.

1. **Every PR runs the `Tests` check** (`.github/workflows/tests.yml`: pytest on Python 3.14). Tests must pass with no `service-account.json`, no `.env` and no network access. Never add secrets to CI to make a test pass.
2. **After opening a PR, wait for the check:** `gh pr checks <number> --watch`. If it fails, fix it on the same branch and push again.
3. **When the check passes, the agent merges the PR itself:** `gh pr merge <number> --squash --delete-branch`, then `git switch main` and `git pull`. Then mark the item done in `docs/ROADMAP.md` and start the next one. Give the user a short plain-English summary of each merged PR.
4. **Exception: stop and ask the user before merging** any PR that touches:
   - deployment
   - secrets handling
   - alerts that send real email
   - anything that writes to a real Google Sheet outside of tests
5. **Also stop and ask** before writing to a real Google Sheet, sending a real email or deploying anything; when something needs a person (accounts, Cloud Console clicks, OAuth setup, answers from Marisol); when a decision isn't covered here or in `docs/decisions.md`; or when a test fails and the cause isn't clear.

## Commands

Python (from the repo root, venv active):

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock.txt
python -m pip install -e .   # makes `python -m pipeline.<module>` work
pytest
```

When regenerating the lock file, use `pip freeze --exclude-editable > requirements.lock.txt` so the local editable install isn't written into it.

Backend (once `api/` exists):

```powershell
uvicorn api.main:app --reload
```

Frontend (once `web/` exists):

```powershell
cd web
npm install
npm run dev
```

## Environment

- Windows 11, PowerShell, Python 3.14.6 (3.12/3.13 as fallback if a Google library breaks)
- Node.js LTS for the frontend
