import { useRef, useState } from "react";
import type { OcrMode } from "../api";

interface Props {
  disabled: boolean;
  uploading: boolean;
  ocrMode: OcrMode;
  setOcrMode: (m: OcrMode) => void;
  onFiles: (files: File[]) => void;
}

const ACCEPT =
  ".pdf,.docx,.xlsx,.txt,.eml,.jpg,.jpeg,.png,.tiff,.bmp,image/*";

export default function Uploader({
  disabled,
  uploading,
  ocrMode,
  setOcrMode,
  onFiles,
}: Props) {
  const fileInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    onFiles(Array.from(list));
  }

  return (
    <div className="uploader">
      <div
        className={`dropzone${dragging ? " dragging" : ""}${disabled ? " disabled" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (!disabled) handleFiles(e.dataTransfer.files);
        }}
        onClick={() => !disabled && fileInput.current?.click()}
        role="button"
        tabIndex={0}
      >
        <div className="dropzone-icon">↑</div>
        <div className="dropzone-text">
          {uploading ? (
            "Uploading…"
          ) : (
            <>
              Drop files here or <span className="link">browse</span>
            </>
          )}
        </div>
        <div className="dropzone-hint">
          PDF, DOCX, XLSX, TXT, EML, images — up to 50 MB
        </div>
      </div>

      <div className="upload-actions">
        <button
          className="btn ghost"
          disabled={disabled}
          onClick={() => cameraInput.current?.click()}
        >
          📷 Take photo
        </button>
        <label className="ocr-select" title="When to run OCR on scanned pages">
          OCR
          <select
            value={ocrMode}
            disabled={disabled}
            onChange={(e) => setOcrMode(e.target.value as OcrMode)}
          >
            <option value="auto">auto</option>
            <option value="always">always</option>
            <option value="off">off</option>
          </select>
        </label>
      </div>

      <input
        ref={fileInput}
        type="file"
        multiple
        accept={ACCEPT}
        hidden
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <input
        ref={cameraInput}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
    </div>
  );
}
