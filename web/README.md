# Control panel

The pipeline's web control panel: **Status**, **Run history**, **Run now** and **Settings**.
It is not a dashboard; charts live in Looker Studio.

It talks only to the pipeline API (`api/` in this repo), through its own `/backend/...`
paths, which Next.js forwards to `API_URL`. It never calls Google (`CLAUDE.md` rule 6).

## Working on it locally

From the repo root, start the API with a pretend sheet (nothing touches Google):

```powershell
python -m scripts.dev_api
```

Then, in another terminal:

```powershell
cd web
npm install
npm run dev
```

Open http://localhost:3000.

## Checks (the same ones GitHub runs on every PR)

```powershell
npm run lint
npm run typecheck
npm test
npm run build
```

## Settings

Copy `.env.example` to `.env.local`. `API_URL` is where the API runs (default `http://127.0.0.1:8000`).

Sign-in is roadmap item 4. Until it's added, the real API refuses every request; only the
pretend-sheet dev API works with the panel.
