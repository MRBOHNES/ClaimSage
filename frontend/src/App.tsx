import { useCallback, useEffect, useRef, useState } from "react";
import "./App.css";
import {
  askQuestion,
  checkHealth,
  createSession,
  getDocumentStatus,
  uploadDocuments,
  type DocumentStatus,
  type OcrMode,
} from "./api";
import Sidebar from "./components/Sidebar";
import Chat, { type Message } from "./components/Chat";

export default function App() {
  const [healthy, setHealthy] = useState<boolean | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [documents, setDocuments] = useState<DocumentStatus[]>([]);
  const [ocrMode, setOcrMode] = useState<OcrMode>("auto");
  const [uploading, setUploading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [asking, setAsking] = useState(false);

  // Backend health indicator (mirrors the "Backend unreachable" banner).
  useEffect(() => {
    let alive = true;
    const ping = () => checkHealth().then((h) => alive && setHealthy(h));
    ping();
    const id = setInterval(ping, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const newSession = useCallback(async () => {
    try {
      const id = await createSession();
      setSessionId(id);
      setDocuments([]);
      setMessages([]);
      setHealthy(true);
    } catch (e) {
      setHealthy(false);
      alert(`Could not start a session: ${(e as Error).message}`);
    }
  }, []);

  const onFiles = useCallback(
    async (files: File[]) => {
      if (!sessionId) return;
      setUploading(true);
      try {
        const created = await uploadDocuments(sessionId, files, ocrMode);
        setDocuments((prev) => [...prev, ...created]);
      } catch (e) {
        alert(`Upload failed: ${(e as Error).message}`);
      } finally {
        setUploading(false);
      }
    },
    [sessionId, ocrMode],
  );

  // Poll status of any documents still processing until they settle.
  const pollRef = useRef<number | null>(null);
  useEffect(() => {
    const pending = documents.filter((d) => d.status === "processing");
    if (pending.length === 0) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    if (pollRef.current) return; // already polling
    pollRef.current = window.setInterval(async () => {
      const updates = await Promise.all(
        documents
          .filter((d) => d.status === "processing")
          .map((d) => getDocumentStatus(d.doc_id).catch(() => null)),
      );
      setDocuments((prev) =>
        prev.map((d) => {
          const u = updates.find((x) => x && x.doc_id === d.doc_id);
          return u ?? d;
        }),
      );
    }, 2000);
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, [documents]);

  const onAsk = useCallback(
    async (question: string) => {
      if (!sessionId) return;
      setMessages((m) => [...m, { role: "user", text: question }]);
      setAsking(true);
      try {
        const res = await askQuestion(sessionId, question);
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: res.answer,
            citations: res.citations,
            confidence: res.confidence,
          },
        ]);
      } catch (e) {
        setMessages((m) => [
          ...m,
          { role: "assistant", text: (e as Error).message, error: true },
        ]);
      } finally {
        setAsking(false);
      }
    },
    [sessionId],
  );

  const canAsk = !!sessionId && documents.some((d) => d.status === "ready");

  return (
    <div className="app">
      <Sidebar
        healthy={healthy}
        sessionId={sessionId}
        documents={documents}
        ocrMode={ocrMode}
        uploading={uploading}
        setOcrMode={setOcrMode}
        onNewSession={newSession}
        onFiles={onFiles}
      />
      <Chat
        sessionId={sessionId}
        canAsk={canAsk}
        messages={messages}
        asking={asking}
        onAsk={onAsk}
      />
    </div>
  );
}
