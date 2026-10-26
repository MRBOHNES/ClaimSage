# Deploying ClaimSage live

> 📥 **Download as PDF:** [`ClaimSage-Deploy.pdf`](pdf/ClaimSage-Deploy.pdf)
> · [all docs as PDF](pdf/)

This gets you a **public demo**: the React frontend on Vercel talking to the
FastAPI backend on Render, with vectors in managed Qdrant Cloud. All three have
free tiers.

```
[ Vercel: frontend ]  --HTTPS-->  [ Render: FastAPI backend ]  -->  [ Qdrant Cloud ]
                                            |
                                            +--> OpenRouter (LLM + embeddings)
```

Steps marked **(you)** need your own accounts/logins; the code and config are
already in the repo.

---

## 1. Qdrant Cloud (vector store) — (you)

1. Sign up at <https://cloud.qdrant.io> and create a **free cluster**.
2. Copy the **cluster URL** (looks like `https://xxxx.cloud.qdrant.io:6333`) and
   create an **API key**.
3. Keep both handy for step 2.

## 2. Backend on Render — (you)

1. Push this repo to GitHub (see bottom).
2. In Render: **New → Blueprint**, select this repo. Render reads
   [`render.yaml`](../render.yaml) and creates the `claimsage-api` web service
   (Docker, from `backend/Dockerfile` — Tesseract for OCR is baked in).
3. Set the service's environment variables (dashboard → Environment):
   - `OPENROUTER_API_KEY` = your `sk-or-v1-...` key
   - `QDRANT_URL` = the Qdrant Cloud URL from step 1
   - `QDRANT_API_KEY` = the Qdrant Cloud API key from step 1
   - `CORS_ORIGINS` = your Vercel URL once you have it (step 3), e.g.
     `https://claimsage.vercel.app,http://localhost:5173`
4. Deploy. When it's live, verify:
   `curl https://<your-service>.onrender.com/api/health` → `{"status":"ok"}`.
   (First request after idle can take ~50s on the free plan — a cold start.)

## 3. Frontend on Vercel — (you)

1. In Vercel: **Add New → Project**, import this repo.
2. Set **Root Directory** to `frontend`. Framework preset: **Vite**.
3. Add an environment variable:
   - `VITE_API_URL` = your Render backend URL (e.g.
     `https://claimsage-api.onrender.com`)
4. Deploy. Vercel gives you the public link — this is the one for your resume.
5. Go back to Render and make sure `CORS_ORIGINS` includes this exact Vercel URL,
   then redeploy the backend. The frontend's "Backend unreachable" banner clears.

---

## Notes & limitations

- **Cold starts:** Render's free web service sleeps after ~15 min idle; the first
  request wakes it (~50s). Fine for a demo; upgrade the plan to remove it.
- **Ephemeral storage:** the SQLite session/document registry and uploaded files
  live on the instance's disk, which resets on redeploy/sleep. Each visitor just
  starts a fresh session — vectors themselves persist in Qdrant Cloud while the
  cluster is active. For durable multi-visit history, move the registry to
  Postgres (future work).
- **Qdrant Cloud inactivity:** the free cluster deactivates after a period of
  inactivity. Then `GET /api/health` returns `{"status": "ok", "qdrant":
  "unreachable"}` and uploads and questions fail. Reactivate the cluster in the
  Qdrant Cloud console (or create a new one, update `QDRANT_URL` /
  `QDRANT_API_KEY` on Render, and re-upload documents: a new cluster is empty).
  Check Qdrant's current free-tier policy for the exact window.
- **Never commit secrets** — all keys are set in the Render/Vercel dashboards.

## Pushing this repo to GitHub

```bash
git remote add origin https://github.com/<you>/ClaimSage.git   # first time
git push -u origin main
```
