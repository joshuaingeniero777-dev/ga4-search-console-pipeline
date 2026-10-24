# Running the control panel on this computer

Everything to copy, in order. Uses the **real** sheet and **real** sign-in. **Run now**
writes to the sheet, and posts to Slack if a number dropped 25% or more.

## 1. Check everything is working (optional, read-only)

PowerShell, in the project folder:

```powershell
cd C:\Users\joshu\projects\ga4-search-console-pipeline
.\.venv\Scripts\python.exe -m scripts.health_check
```

## 2. Start the API (terminal 1, leave it open)

```powershell
cd C:\Users\joshu\projects\ga4-search-console-pipeline
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Ready when it says `Uvicorn running on http://127.0.0.1:8000`.

## 3. Start the control panel (terminal 2, leave it open)

```powershell
cd C:\Users\joshu\projects\ga4-search-console-pipeline\web
npm run build
npm run start
```

Ready when it says `Ready`. `npm run build` is only needed after the panel's code changes, but it's
harmless to run every time (about a minute).

## 4. Open it

Go to **http://localhost:3000**. Type `localhost`, not `127.0.0.1`, because sign-in only works on
that address. Sign in with a work account (`@joinswc.org` or `@starrwellnesscollective.org`).

## 5. Stop

Press `Ctrl+C` in each terminal.

## If something's off

| What you see | Fix |
|---|---|
| "The pipeline server isn't responding" | Terminal 1 isn't running, or stopped. Start step 2 again. |
| "Sign-in isn't set up yet" | `.env` is missing the sign-in lines (see `.env.example`). |
| "Sign-in didn't work" | Make sure the address is `localhost:3000`, then sign in again. |
| A port is already in use | An old copy is still running. Close the old terminals, or restart the computer. |
