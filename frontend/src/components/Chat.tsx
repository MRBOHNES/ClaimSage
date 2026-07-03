import { useState } from "react";
import type { Citation } from "../api";

export interface Message {
  role: "user" | "assistant";
  text: string;
  citations?: Citation[];
  confidence?: number;
  error?: boolean;
}

interface Props {
  sessionId: string | null;
  canAsk: boolean;
  messages: Message[];
  asking: boolean;
  onAsk: (q: string) => void;
}

const STEPS = [
  { n: "01", title: "Create session", sub: "Start a new claim workflow" },
  { n: "02", title: "Upload documents", sub: "PDF, Word, Excel, or a photo" },
  { n: "03", title: "Ask questions", sub: "Get grounded, cited answers" },
];

function Hero() {
  return (
    <div className="hero">
      <div className="badge">◆ RAG PIPELINE · CITED ANSWERS</div>
      <h1>
        Ask your
        <br />
        <span className="accent">documents</span>
        <span className="cursor" />
      </h1>
      <p className="hero-sub">
        Upload insurance claims, policies, scans, or a photo — get grounded
        answers with page-level citations. Scanned pages are read via OCR.
      </p>
      <div className="steps">
        {STEPS.map((s) => (
          <div className="step" key={s.n}>
            <div className="step-n">{s.n}</div>
            <div className="step-title">{s.title}</div>
            <div className="step-sub">{s.sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Citations({ items }: { items: Citation[] }) {
  if (!items.length) return null;
  return (
    <div className="citations">
      <div className="citations-label">Sources</div>
      {items.map((c, i) => (
        <div className="citation" key={i}>
          <div className="citation-head">
            <span className="citation-file">{c.filename}</span>
            {c.location && <span className="citation-loc">{c.location}</span>}
            <span className="citation-score">{(c.score * 100).toFixed(0)}%</span>
          </div>
          <div className="citation-snippet">{c.snippet}</div>
        </div>
      ))}
    </div>
  );
}

export default function Chat({
  sessionId,
  canAsk,
  messages,
  asking,
  onAsk,
}: Props) {
  const [text, setText] = useState("");

  function submit() {
    const q = text.trim();
    if (!q || !canAsk || asking) return;
    onAsk(q);
    setText("");
  }

  return (
    <main className="main">
      <div className="thread">
        {messages.length === 0 ? (
          <Hero />
        ) : (
          messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}${m.error ? " error" : ""}`}>
              <div className="msg-role">
                {m.role === "user" ? "You" : "ClaimSage"}
              </div>
              <div className="msg-text">{m.text}</div>
              {m.role === "assistant" && typeof m.confidence === "number" && (
                <div className="confidence">
                  retrieval confidence: {(m.confidence * 100).toFixed(0)}%
                </div>
              )}
              {m.citations && <Citations items={m.citations} />}
            </div>
          ))
        )}
        {asking && (
          <div className="msg assistant">
            <div className="msg-role">ClaimSage</div>
            <div className="msg-text thinking">Searching your documents…</div>
          </div>
        )}
      </div>

      <div className="composer">
        <input
          className="composer-input"
          placeholder={
            !sessionId
              ? "Start a session to begin"
              : !canAsk
                ? "Upload a document first"
                : "Ask a question about your documents…"
          }
          value={text}
          disabled={!canAsk || asking}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <button
          className="btn primary send"
          disabled={!canAsk || asking || !text.trim()}
          onClick={submit}
        >
          →
        </button>
      </div>
    </main>
  );
}
