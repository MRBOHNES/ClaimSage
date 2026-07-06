# ClaimSage — The Build-It-Yourself Learning Guide

A from-scratch guide to building a production-shaped **RAG (Retrieval-Augmented
Generation)** application — and, just as important, **every bug we actually hit
while building and deploying this one**, with the symptom, the root cause, the
fix, and the lesson.

This is written to be **revised before an interview**. If someone asks *"walk me
through a RAG system you built and what broke,"* everything you need is here.

- Part 1 explains the **concepts** (what RAG is and why each piece exists).
- Part 2 is a **step-by-step build order** you could repeat on a new project.
- Part 3 is the **deployment** story (going from localhost to a public URL).
- Part 4 is the **bug journal** — the most valuable part for interviews.
- Part 5 is a **rapid-fire interview Q&A** cheat sheet.

For how *this* codebase is wired, read [`ARCHITECTURE.md`](ARCHITECTURE.md)
alongside this. For the deploy runbook, see [`DEPLOY.md`](DEPLOY.md).

---

# Part 1 — The concepts

## 1.1 The problem RAG solves

You have large documents (a 100-page insurance policy, an Excel schedule of
benefits, a folder of claim emails) and you want plain-English answers grounded
in them: *"Is knee surgery covered, and what's the waiting period?"*

The naive approach — paste the whole policy into an LLM and ask — fails for three
reasons:

1. **Context window limits.** The document is too big to fit in the prompt.
2. **Cost & latency.** Sending everything on every question is slow and expensive.
3. **Hallucination.** With no grounding, the model invents plausible-sounding
   answers.

**RAG fixes all three:** instead of sending the whole document, you *retrieve*
only the handful of relevant passages and send those. The model reads a page, not
a book.

## 1.2 RAG in two phases

```
INGESTION (once per document)
  file → parse to text → chunk into pieces → embed each chunk → store vectors

QUERY (every question)
  question → embed → find nearest chunks → LLM writes answer from those chunks
```

**The key mental model:** the LLM never reads the whole document. Retrieval does
the hard part (finding the right 5 chunks); the LLM does the easy part (summarize
those 5 chunks). That's why a small, free model is "good enough" here.

## 1.3 The two model types (don't confuse them)

Beginners conflate these. They are different models doing different jobs:

- **Embedding model** — turns text into a vector (a list of numbers, e.g. 2048 of
  them). Similar meanings land at nearby points in space. Used to *find* relevant
  chunks by measuring distance. Runs on **every chunk at ingestion** and **every
  question at query time**.
- **Chat / LLM model** — writes the natural-language answer. Runs **once per
  question**, over the retrieved chunks only.

## 1.4 Why a vector store (Qdrant) *and* a relational DB (SQLite)?

- **Qdrant** answers one question extremely fast: *"which stored vectors are
  nearest to this one?"* That's approximate-nearest-neighbour search. It is not
  the right tool for bookkeeping.
- **SQLite** tracks the relational bookkeeping: which sessions exist, which
  documents belong to them, and whether each document has finished processing
  (`processing` / `ready` / `failed`).

Different jobs, different databases. A common interview question is *"why not just
use one?"* — because "find similar vectors" and "track upload status" are
different access patterns, and forcing one store to do both makes both worse.

## 1.5 What makes answers trustworthy: grounding + structural citations

Two design decisions separate a toy from something you'd demo:

1. **Grounding.** The system prompt tells the LLM to answer *using only the
   provided context.* If the answer isn't in the retrieved chunks, it should say
   so rather than invent one.
2. **Structural citations.** We do **not** ask the LLM to cite itself (models lie
   about their sources). Instead, citations are read from the **metadata of the
   retrieved chunks** — filename, page label, similarity score. That metadata was
   attached at parse time. This is honest: the citation literally *is* the chunk
   that was fed to the model.

---

# Part 2 — Build order (how to recreate this)

Build in this order. Each step is independently testable, which is the whole
point — you never debug ten things at once.

### Step 1 — Project skeleton
- FastAPI app, a health endpoint (`GET /api/health`), a Dockerfile, and a
  `docker-compose.yml` that runs Qdrant locally. Prove `/api/health` returns
  `{"status":"ok"}` before writing any RAG code.

### Step 2 — Config from environment
- One `Settings` object (pydantic-settings) that reads `.env`: API keys, Qdrant
  URL, model names, chunk size. **Never hard-code secrets or hosts.** Everything
  that differs between your laptop and prod must be an env var. (This bites you
  later if you skip it — see Bug #4 and #5.)

### Step 3 — The provider abstraction
- A single module (`llm_provider.py`) that is the *only* place that knows you use
  OpenRouter. Everything else asks it for "an LLM" or "an embedding model." When
  you later switch providers or add an agent layer, you edit one file.

### Step 4 — Parsing (multi-format → text + metadata)
- Turn each upload into text **plus location metadata** (this metadata is what
  makes citations possible):
  - PDF → one unit per **page** (PyMuPDF), tagged with the page number.
  - Excel → one unit per **row** (columns flattened), so a benefits-schedule row
    is never split in half.
  - Email → headers + body; parse attachments recursively.
- Reject formats you can't handle *clearly* (legacy `.doc`/`.msg`) rather than
  producing garbage.

### Step 5 — Chunking
- Split long text into ~512-token chunks with ~50-token **overlap**. Overlap
  stops a sentence's meaning from being cut across a boundary. Keep short units
  (Excel rows) whole.

### Step 6 — Embedding + storage
- Embed each chunk and upsert into a Qdrant collection, tagging every vector with
  `claim_id` (= the session id) so you can scope retrieval later.
- Discover the embedding dimension at runtime and create the collection with it —
  don't hard-code 1536/2048.

### Step 7 — Async ingestion
- Uploading returns **immediately** with status `processing`; the slow
  parse→chunk→embed work runs in a background task and flips the row to
  `ready`/`failed`. The client **polls** `GET /documents/{id}/status`. Doing the
  work inside the HTTP request would time out on a big PDF.

### Step 8 — Query
- Embed the question, ask Qdrant for the `top_k` nearest chunks **filtered to this
  `claim_id`**, feed them to the LLM with a grounding prompt, and return the
  answer plus citations built from chunk metadata.

### Step 9 — OCR fallback (scanned docs & photos)
- Some PDF pages are scans with **no text layer**, and users upload **photos** of
  documents. Add a per-page fallback: if a page yields fewer than N characters of
  real text, rasterize it (PyMuPDF) and run **Tesseract** OCR on the image.
  Crucially, OCR runs **only on pages that need it** — digital pages stay fast and
  accurate. Expose `?ocr_mode=auto|always|off`.

### Step 10 — Frontend
- A typed API client (base URL from an env var), a session/upload/chat UI, and
  status polling. Keep it dependency-light so you fully own and understand it.

### Step 11 — Tests, then deploy
- Test the pipeline locally (scoped retrieval, citation correctness) *before*
  touching the cloud. Then Part 3.

---

# Part 3 — Deployment (localhost → public URL)

The target topology:

```
[ Vercel: React frontend ]  --HTTPS-->  [ Render: FastAPI backend (Docker) ]
                                                 |
                                    +------------+------------+
                                    v                         v
                            [ Qdrant Cloud ]           [ OpenRouter ]
                            (vectors persist)          (LLM + embeddings)
```

Three services, all on free tiers. The full runbook is in
[`DEPLOY.md`](DEPLOY.md); the short version:

1. **Qdrant Cloud** — create a free cluster, copy its URL + API key.
2. **Render** — deploy the backend from `render.yaml` (Docker; Tesseract is baked
   into the image). Set `OPENROUTER_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`,
   `CORS_ORIGINS`.
3. **Vercel** — deploy `frontend/` with **Root Directory = `frontend`**, Vite
   preset, and `VITE_API_URL` = the Render URL.
4. Add the Vercel URL to the backend's `CORS_ORIGINS` and redeploy.

Two properties of free-tier hosting to understand (and mention in an interview as
*known trade-offs*, not surprises):

- **Cold starts.** Render's free web service sleeps after ~15 min idle; the first
  request wakes it (~50s). Acceptable for a demo.
- **Ephemeral disk.** The SQLite registry and uploaded files sit on the
  instance's disk, which resets on redeploy/sleep. Each visitor starts a fresh
  session. **Vectors persist in Qdrant Cloud regardless.** For durable history,
  move the registry to Postgres (noted as future work).

---

# Part 4 — The bug journal (the interview gold)

Every bug below is real, in the order it mattered. Format: **Symptom → Root cause
→ Fix → Lesson.** The lessons generalize far beyond this project.

---

## Bug #1 — OpenRouter embeddings crash on `null` data

**Symptom.** Embedding calls crashed. OpenRouter returned an embedding response
whose `data` was `null` instead of a list of floats.

**Root cause.** The standard OpenAI-compatible embedding client defaults to
`encoding_format="base64"`. OpenRouter doesn't return base64 the same way, so the
decoded payload came back null → crash.

**Fix.** A thin custom embedding class (`openrouter_embedding.py`) that forces
`encoding_format="float"`.

**Lesson.** "OpenAI-compatible" APIs are compatible *until they aren't.* When you
integrate a drop-in replacement provider, the defaults that worked for the
original may not hold. You only find these by actually calling the API and
reading the raw response — not by trusting the SDK's defaults.

---

## Bug #2 — Qdrant Cloud rejects filtered search: *"Index required but not found"*

**Symptom.** Every query worked perfectly on local Docker Qdrant, but on **Qdrant
Cloud** every question failed. The backend returned HTTP 500 in ~1.9s (fast — so
*not* a timeout). Qdrant's error was `400: Index required but not found for
"claim_id"`.

**Root cause.** Retrieval filters results to the current claim with a metadata
filter on `claim_id`. **Managed Qdrant Cloud refuses to filter on a field that
has no payload index** — it returns 400. Local Docker Qdrant is lenient and
filters an unindexed field anyway, so this bug was **invisible in development**
and only appeared in production.

**Fix.** Create a `claim_id` **KEYWORD payload index** on the collection. Done in
two places:
- immediately on the existing cloud collection (one-off), and
- durably in `ensure_collection()`, which now creates the index idempotently every
  startup so a fresh collection is always correct.

**Lesson.** *A managed service is not the same as the local dev version of the
same software.* Managed tiers enforce constraints (indexes, quotas, auth) that
your permissive local setup silently ignores. Test against something as close to
prod as you can — and when a feature works locally but 400s in the cloud, suspect
a constraint the cloud enforces that local doesn't.

---

## Bug #3 — The 500 that looked like a network failure ("NetworkError")

**Symptom.** The browser showed a generic **"NetworkError"** with no detail — it
*looked* like the backend was down or unreachable. It wasn't: the request reached
the server and came back as a 500 (this was the surfacing of Bug #2).

**Root cause.** A raw, unhandled 500 in FastAPI **bypasses the CORS middleware**,
so the error response carries **no `Access-Control-Allow-Origin` header**. The
browser then refuses to expose the response to JavaScript and reports it as an
opaque cross-origin "NetworkError" — hiding the real status and message.

**Fix.** Wrap the query handler so any unexpected exception becomes a proper
`HTTPException` (a clean 500 with a readable `detail`). Because it's now a
structured response, it flows **through** the CORS middleware and gets the CORS
header — so the browser actually shows the real error. Specific upstream failures
are mapped too: rate limit → 429, provider error → 502.

**Lesson.** In a cross-origin app, **an unhandled exception is worse than a
handled error** — it strips CORS headers and turns a debuggable 500 into a
mysterious "NetworkError." Always convert unexpected failures into structured
responses. And when you see "NetworkError" with a request that clearly *did* reach
the server, suspect a missing CORS header on an error path, not a dead server.

---

## Bug #4 — CORS list env var crashes pydantic on startup

**Symptom.** Setting `CORS_ORIGINS` as a comma-separated string in the
environment crashed the app at startup with a pydantic-settings `SettingsError`
about JSON-decoding.

**Root cause.** pydantic-settings tries to **JSON-decode** any field typed as a
`list`. `https://a.com,http://b.com` is not valid JSON, so it blew up before the
app even started.

**Fix.** Type the field as `Annotated[list[str], NoDecode]` to disable the JSON
decoding, and add a `@field_validator(mode="before")` that splits the string on
commas into a real list.

**Lesson.** Config parsing is a real source of production-only failures. The
value that works as a Python default (a list literal) is not the value the
environment provides (a string). Know how your settings library coerces env vars,
especially for lists and booleans.

---

## Bug #5 — The `QDRANT_URL=` paste slip

**Symptom.** After setting env vars on Render, Qdrant was "unreachable." The URL
looked right at a glance.

**Root cause.** The value pasted into Render's env var box was
`QDRANT_URL=https://...:6333` — i.e. the **`KEY=` prefix was included in the
value.** So the effective URL was `QDRANT_URL=https://...`, which is malformed.

**Fix.** Put only the value (`https://...:6333`) in the value box; the key is the
field name.

**Lesson.** Dashboard env vars are not `.env` files — you type the **value only**,
not `KEY=value`. A trivial slip, but it produces a confusing "unreachable" that
looks like a networking/auth problem. When a URL "looks right" but won't connect,
print/inspect the *exact* string the app received.

---

## Bug #6 — Health check said Qdrant was unreachable (but it wasn't)

**Symptom.** The main app talked to Qdrant Cloud fine, but the `/api/health`
endpoint reported `qdrant: "unreachable"`.

**Root cause.** The health check constructed its **own** `QdrantClient` for a
lightweight liveness ping and **forgot to pass the API key.** Qdrant Cloud
requires auth, so that unauthenticated client couldn't connect — even though the
real client (with the key) could.

**Fix.** Pass `api_key=settings.qdrant_api_key or None` (and a short timeout) when
building the health-check client too.

**Lesson.** Auth/config must be applied **consistently on every path** that talks
to a dependency, including the ones that feel trivial (health checks, scripts,
migrations). A second client that quietly skips the API key gives you a false
"unreachable" and sends you debugging the wrong thing.

---

## Bug #7 — Vercel tried to build the whole repo

**Symptom.** Vercel auto-detected multiple services (a frontend *and* a Python
backend) and wanted a `vercel.json`, failing to build cleanly.

**Root cause.** The repo root is a full-stack project. Vercel, pointed at the
root, saw both apps and got confused. Vercel is a **static/serverless** host — it
can't run the Dockerized, Tesseract-dependent Python backend anyway.

**Fix.** Set **Root Directory = `frontend`** in the Vercel project and use the
**Vite** preset. Vercel now builds only the frontend; the backend lives on Render.

**Lesson.** Match each part of a stack to a host that fits it. Frontends →
Vercel/Netlify (static). Containerized backends → Render/Railway/Fly. Point each
host at the *subdirectory* it owns, not the monorepo root.

---

## Bug #8 — Answers suddenly 429 (free-tier rate limit)

**Symptom.** After a burst of testing, every query started returning a
rate-limit error.

**Root cause.** OpenRouter's free tier caps requests per day, and **embeddings and
chat share that budget.** Each question costs at least one embedding call plus one
chat call, and each uploaded chunk costs an embedding call — so the quota drains
faster than it looks. It resets daily.

**Fix.** Handle it gracefully: catch the rate-limit error and return a clean
**429** with a "try again shortly" message instead of a scary 500 (see Bug #3).
Nothing to "fix" in the limit itself — it resets.

**Lesson.** Free tiers have quotas; know exactly what counts against them.
Surface rate limits as first-class, user-readable errors, not crashes. In an
interview: this is where you'd mention caching embeddings, batching, or a paid
tier as the scaling answer.

---

## Bug #9 — Cold starts look like a broken site

**Symptom.** The first visit to the live demo after it had been idle took ~50s and
felt broken.

**Root cause.** Render's free web service **sleeps after ~15 min idle**; the first
request has to cold-start the container.

**Fix.** No code fix — it's a free-tier property. We **document** it (in the README
and the app itself) so a visitor/interviewer expects the delay, and note that a
paid plan removes it.

**Lesson.** Know your hosting tier's behavior and set expectations rather than
pretending it doesn't exist. "The free tier cold-starts in ~50s; a paid plan or a
keep-alive ping removes it" is a *confident, informed* answer — much better than
being surprised by it live.

---

## Bug #10 — macOS blocked the tools from reading the project folder

**Symptom.** Mid-work, every file read/write and `git` command failed with
`Operation not permitted`, even with sandboxing disabled.

**Root cause.** macOS **TCC (Transparency, Consent & Control)** governs which apps
may read protected locations (Desktop, Documents). The terminal app's access to
the Desktop folder had been revoked, so nothing under it could be touched.

**Fix.** System Settings → Privacy & Security → Files and Folders / Full Disk
Access → re-enable the terminal app for the Desktop, then relaunch it.

**Lesson.** Not every "permission denied" is a code or git problem — the OS's own
privacy layer can be the wall. On macOS, when a whole directory suddenly becomes
unreadable across every tool at once, check TCC before you debug anything else.

---

## Design decisions that prevented bugs (worth mentioning too)

- **OCR only when needed.** Running OCR on every page would be slow and would
  *degrade* accuracy on clean digital text (OCR guesses; a text layer is exact).
  The per-page character-threshold fallback means digital pages use their real
  text and only true scans get OCR'd. Handling the mixed-content case (a PDF with
  both digital and scanned pages) fell out of this design for free.
- **Per-page / per-row parsing.** Choosing the parse *unit* deliberately (page for
  PDF, row for Excel) is what makes citations precise and stops a benefits row
  from being chopped in half by the chunker.
- **Structural, not model-generated, citations.** Reading citations from metadata
  (not asking the LLM) means they can't be hallucinated.

---

# Part 5 — Rapid-fire interview Q&A

**Q: What is RAG and why use it?**
Retrieve relevant chunks from your own documents and feed only those to an LLM.
Solves context-window limits, cost/latency, and hallucination in one move.

**Q: Embedding model vs. chat model?**
Embedding model turns text into vectors to *find* relevant chunks; chat model
*writes* the answer from them. Different models, different jobs.

**Q: Why both a vector DB and SQLite?**
Qdrant does nearest-vector search; SQLite tracks sessions and processing status.
Different access patterns — one store doing both makes both worse.

**Q: How do you keep answers grounded / avoid hallucination?**
A system prompt that says "answer only from this context," plus retrieval that
limits what the model sees, plus citations read structurally from chunk metadata.

**Q: How are citations trustworthy?**
They're built from the metadata of the exact chunks that were retrieved (filename,
page, similarity score) — not generated by the LLM, so they can't be faked.

**Q: Why chunk with overlap?**
So a sentence's meaning isn't severed at a chunk boundary; the overlap preserves
context across the cut.

**Q: Why is upload asynchronous?**
Embedding a large PDF takes seconds to minutes; doing it inside the HTTP request
would time out. Return `processing` immediately and let the client poll.

**Q: A feature worked locally but broke in production — example?**
Qdrant metadata filtering. Local Docker filters an unindexed field; managed
Qdrant Cloud requires a payload index and returns 400 without it (Bug #2).

**Q: You saw "NetworkError" in the browser — how did you debug it?**
Confirmed the request reached the server (fast 500, not a timeout), realized an
unhandled 500 skips CORS middleware and drops the CORS header, so the browser hid
the real error. Converted unhandled exceptions to structured HTTP errors (Bug #3).

**Q: Biggest lesson from deploying this?**
Managed/free-tier services enforce things local dev doesn't — indexes, auth on
every client, quotas, cold starts, ephemeral disk. Most of my bugs were the gap
between "works on my laptop" and "works in the cloud," not the RAG logic itself.

---

*Companion docs: [`ARCHITECTURE.md`](ARCHITECTURE.md) (how this codebase is
wired) · [`DEPLOY.md`](DEPLOY.md) (the deploy runbook).*
