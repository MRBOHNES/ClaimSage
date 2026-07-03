// Typed client for the ClaimSage backend. Base URL comes from VITE_API_URL
// (set on Vercel to the deployed backend); falls back to local dev.

const BASE_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/$/, "");

export type OcrMode = "auto" | "always" | "off";

export interface DocumentStatus {
  doc_id: string;
  filename: string;
  status: "processing" | "ready" | "failed";
  error: string;
  chunks_indexed: number;
}

export interface Citation {
  filename: string;
  location: string | null;
  snippet: string;
  score: number;
}

export interface QueryResponse {
  answer: string;
  citations: Citation[];
  confidence: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export async function checkHealth(): Promise<boolean> {
  try {
    await request("/api/health");
    return true;
  } catch {
    return false;
  }
}

export async function createSession(): Promise<string> {
  const data = await request<{ session_id: string }>("/api/sessions", {
    method: "POST",
  });
  return data.session_id;
}

export async function uploadDocuments(
  sessionId: string,
  files: File[],
  ocrMode: OcrMode,
): Promise<DocumentStatus[]> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const data = await request<{ documents: DocumentStatus[] }>(
    `/api/documents?session_id=${encodeURIComponent(sessionId)}&ocr_mode=${ocrMode}`,
    { method: "POST", body: form },
  );
  return data.documents;
}

export async function getDocumentStatus(docId: string): Promise<DocumentStatus> {
  return request<DocumentStatus>(`/api/documents/${docId}/status`);
}

export async function askQuestion(
  sessionId: string,
  question: string,
): Promise<QueryResponse> {
  return request<QueryResponse>("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, question }),
  });
}
