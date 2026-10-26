# ClaimSage frontend

React + Vite + TypeScript UI for ClaimSage: start a session, upload documents (or take a photo), watch ingestion
progress, and ask questions with page-level citations. Deployed on Vercel.

## Run it

```bash
cp .env.example .env.local    # VITE_API_URL=http://localhost:8000
npm install
npm run dev                   # http://localhost:5173
```

The backend must be running (see the [root README](../README.md)); the sidebar shows "Backend connected" or an
unreachable banner by polling `/api/health` every 15 seconds.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server with hot reload |
| `npm run build` | Type-check (`tsc -b`) and production build |
| `npm run lint` | Oxlint (`.oxlintrc.json`) |
| `npm run preview` | Serve the production build locally |

## Configuration

| Variable | Purpose |
|---|---|
| `VITE_API_URL` | Base URL of the backend (no trailing slash). Falls back to `http://localhost:8000` when empty. In production, set it on Vercel to the Render backend URL. |

## Layout

```
src/
├── api.ts                 # typed client for the backend (sessions, upload, status, query, health)
├── App.tsx                # state: session, documents, messages, OCR mode, health polling
└── components/
    ├── Sidebar.tsx        # session + document list with ingestion status
    ├── Uploader.tsx       # drag-and-drop, camera capture, OCR mode (auto / always / off)
    └── Chat.tsx           # landing hero, messages, citations and confidence
```

The backend's CORS list (`CORS_ORIGINS`) must include the URL this app is served from. See
[`../docs/DEPLOY.md`](../docs/DEPLOY.md).
