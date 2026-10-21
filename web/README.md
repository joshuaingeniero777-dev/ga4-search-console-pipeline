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

Every page is behind Google sign-in, which the API handles (`/backend/auth/...`). The real API
refuses everything until its sign-in settings are in the repo root's `.env` (see
`.env.example` and `docs/ROADMAP.md`, item 4). The pretend-sheet dev API counts everyone as
signed in, so it works with the panel straight away.
