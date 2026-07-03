import type { DocumentStatus, OcrMode } from "../api";
import Uploader from "./Uploader";

interface Props {
  healthy: boolean | null;
  sessionId: string | null;
  documents: DocumentStatus[];
  ocrMode: OcrMode;
  uploading: boolean;
  setOcrMode: (m: OcrMode) => void;
  onNewSession: () => void;
  onFiles: (files: File[]) => void;
}

const STATUS_LABEL: Record<DocumentStatus["status"], string> = {
  processing: "processing…",
  ready: "ready",
  failed: "failed",
};

export default function Sidebar({
  healthy,
  sessionId,
  documents,
  ocrMode,
  uploading,
  setOcrMode,
  onNewSession,
  onFiles,
}: Props) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">◆</div>
        <div>
          <div className="brand-name">ClaimSage</div>
          <div className="brand-sub">AI Document Intelligence</div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-label">Current session</div>
        <div className="session-box">
          <span
            className={`dot ${sessionId ? "on" : "off"}`}
            title={sessionId ? "Active" : "No session"}
          />
          <span className="session-id">
            {sessionId ? sessionId.slice(0, 8) + "…" : "No active session"}
          </span>
        </div>
        <button className="btn primary" onClick={onNewSession}>
          + New session
        </button>
      </div>

      <div className="panel grow">
        <div className="panel-label">Documents</div>
        {documents.length === 0 ? (
          <div className="empty-docs">
            <div className="empty-docs-icon">▢</div>
            No documents yet
          </div>
        ) : (
          <ul className="doc-list">
            {documents.map((d) => (
              <li key={d.doc_id} className={`doc ${d.status}`}>
                <span className="doc-name" title={d.filename}>
                  {d.filename}
                </span>
                <span className={`doc-status ${d.status}`}>
                  {d.status === "ready" && "✓ "}
                  {STATUS_LABEL[d.status]}
                </span>
                {d.status === "failed" && d.error && (
                  <span className="doc-error" title={d.error}>
                    {d.error}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <Uploader
        disabled={!sessionId}
        uploading={uploading}
        ocrMode={ocrMode}
        setOcrMode={setOcrMode}
        onFiles={onFiles}
      />

      <div className="health">
        <span className={`dot ${healthy ? "on" : "off"}`} />
        {healthy === null
          ? "Checking backend…"
          : healthy
            ? "Backend connected"
            : "Backend unreachable"}
      </div>
    </aside>
  );
}
