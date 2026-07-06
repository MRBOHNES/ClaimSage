# ClaimSage

**Document-grounded Q&A over insurance claims.** Upload large documents in any
format (PDF, Word, Excel, email, text, or a **photo of a document**), ask
natural-language questions, and get fast, accurate answers grounded in your
documents **with page-level citations**.

Built to demonstrate a real **RAG (Retrieval-Augmented Generation)** system:
embeddings, a vector store, semantic search, chunking strategy, multi-format
ingestion, OCR for scanned documents, a React frontend, and a full cloud
deployment — all running on **free tiers**.

### 🔗 Live demo → **https://claim-sage-six.vercel.app**

> First load may take ~50s — the free backend cold-starts after inactivity, then
> it's instant.

**New here?**
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — how RAG works and how each part
  of this system fits together.
- [`docs/LEARNING_GUIDE.md`](docs/LEARNING_GUIDE.md) — a from-scratch guide to
  building an app like this, **including every bug we hit and how we fixed it**.
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — how the live deployment is wired up.

---

## Stack

| Layer | Choice |
|---|---|
| Frontend | React · Vite · TypeScript (deployed on **Vercel**) |
| Backend | Python 3.12 · FastAPI (Docker, deployed on **Render**) |
| RAG framework | LlamaIndex |
| Vector store | Qdrant (local Docker in dev · **Qdrant Cloud** in prod) |
| OCR | Tesseract (scanned PDFs + image/camera uploads) |
| Registry | SQLite |
| Chat model | `google/gemma-4-26b-a4b-it:free` (OpenRouter) |
| Embeddings | `nvidia/llama-nemotron-embed-vl-1b-v2:free` (OpenRouter, 2048-dim) |

Everything runs on **free tiers**: OpenRouter free models + Qdrant Cloud free
cluster + Render/Vercel free hosting.

### Architecture

```
 Browser ──HTTPS──▶ Vercel (React/Vite frontend)
                        │  fetch(VITE_API_URL)
                        ▼
                   Render (FastAPI + Tesseract, Docker)
                    │            │
                    ▼            ▼
              Qdrant Cloud   OpenRouter
              (vectors)      (LLM + embeddings)
```

---

## Quick start

### 1. Prerequisites
- Docker Desktop (for Qdrant)
- Python 3.12
- A free [OpenRouter](https://openrouter.ai) API key
- **Tesseract** for OCR of scanned PDFs / image uploads — `brew install tesseract`
  (macOS) or `apt-get install tesseract-ocr` (Linux). Already bundled in the
  Docker image; only needed for local `uvicorn` runs.

### 2. Configure secrets
```bash
cd backend
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY=sk-or-v1-...
```

### 3. Start Qdrant
```bash
docker compose up -d qdrant
```

### 4. Run the backend
```bash
cd backend
python3.12 -m venv ../backend_venv           # first time only
../backend_venv/bin/pip install -r requirements.txt   # first time only
../backend_venv/bin/uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs for interactive API docs.

### Or run everything in Docker
```bash
docker compose up --build     # backend + qdrant together
```

---

## Try it (curl)

```bash
# 1. start a session
SID=$(curl -s -X POST localhost:8000/api/sessions | python3 -c "import sys,json;print(json.load(sys.stdin)['session_id'])")

# 2. upload a document
curl -s -X POST "localhost:8000/api/documents?session_id=$SID" -F "files=@policy.pdf"

# 3. (poll GET /api/documents/{doc_id}/status until "ready")

# 4. ask a question
curl -s -X POST localhost:8000/api/query \
  -H 'Content-Type: application/json' \
  -d "{\"session_id\":\"$SID\",\"question\":\"Is knee surgery covered and what is the waiting period?\"}"
```

---

## Project layout

```
ClaimSage/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app + startup
│   │   ├── config.py               # settings from .env
│   │   ├── api/                    # HTTP routes (health, upload, query)
│   │   ├── models/                 # SQLite registry + Pydantic schemas
│   │   └── services/               # the RAG pipeline
│   │       ├── parsers.py          # multi-format → LlamaIndex Documents
│   │       ├── indexing.py         # chunking + Qdrant wiring
│   │       ├── ingestion.py        # orchestrates parse→chunk→embed→store
│   │       ├── query_engine.py     # retrieval + grounded answer + citations
│   │       ├── llm_provider.py     # OpenRouter abstraction (chat + embeddings)
│   │       └── openrouter_embedding.py  # custom embedding (encoding_format fix)
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── docker-compose.yml
└── docs/ARCHITECTURE.md            # start here to learn the system
```

Supported formats: PDF, .docx, .xlsx, .txt, .eml, and images
(.jpg/.jpeg/.png/.tiff/.bmp) (50 MB max).
Legacy binary `.doc` / `.msg` are rejected with a clear message.

**OCR:** scanned PDF pages (no text layer) and image uploads are read via
Tesseract OCR. For PDFs, OCR runs *only* on pages that lack extractable text
(per-page character threshold), so digital pages stay fast and accurate. Control
it per upload with `?ocr_mode=auto|always|off` on `POST /api/documents`
(`auto` is the default).

---

## Status

**Phase 1 (done):** working end-to-end RAG — multi-format ingestion, async
processing, scoped retrieval, grounded answers with citations.

**Phase 2 (planned):** agentic query routing (LangChain), hybrid search
(BM25 + vector), and an evaluation harness comparing chunking strategies.
