// AOI Tool - Image Viewer (single + compare mode)
import { useState, useEffect } from "react";

export function ViewerPanel({ src, label, tr }) {
  const [zoom,      setZoom]      = useState(1);
  const [rotation,  setRotation]  = useState(0);
  const [offset,    setOffset]    = useState({ x: 0, y: 0 });
  const [dragging,  setDragging]  = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 8;

  const handleWheel = (e) => {
    e.preventDefault();
    setZoom(z => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z - e.deltaY * 0.001)));
  };

  const handleMouseDown = (e) => {
    if (zoom <= 1) return;
    e.preventDefault();
    setDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e) => {
    if (!dragging) return;
    setOffset({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
  };

  const handleMouseUp = () => setDragging(false);

  const reset = () => { setZoom(1); setRotation(0); setOffset({ x: 0, y: 0 }); };

  const btn = (title, onClick, content) => (
    <button title={title} onClick={onClick} style={{
      padding: "5px 10px", borderRadius: 6, border: "none",
      background: "#1e293b", color: "#94a3b8",
      fontSize: 12, cursor: "pointer",
      fontFamily: "'IBM Plex Sans'", fontWeight: 600,
    }}>{content}</button>
  );

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, height: "100%" }}>
      {/* Controls */}
      <div style={{
        display: "flex", alignItems: "center", gap: 6,
        padding: "8px 12px", background: "#0a0f1a",
        borderBottom: "1px solid #1e293b", flexShrink: 0,
      }}>
        <span style={{ fontSize: 11, color: "#64748b", fontFamily: "monospace", flex: 1 }}>
          {label}
        </span>
        {btn(tr.viewerZoomIn,  () => setZoom(z => Math.min(MAX_ZOOM, z + 0.25)), "＋")}
        {btn(tr.viewerZoomOut, () => setZoom(z => Math.max(MIN_ZOOM, z - 0.25)), "－")}
        <span style={{ fontSize: 11, color: "#475569", minWidth: 36, textAlign: "center" }}>
          {Math.round(zoom * 100)}%
        </span>
        {btn(tr.viewerRotate, () => setRotation(r => (r + 90) % 360), "↻")}
        {btn(tr.viewerReset,  reset, "⊡")}
      </div>

      {/* Image area */}
      <div
        style={{
          flex: 1, overflow: "hidden", position: "relative",
          background: "#000",
          cursor: zoom > 1 ? (dragging ? "grabbing" : "grab") : "default",
          userSelect: "none",
        }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <img
          src={src}
          alt={label}
          draggable={false}
          style={{
            position: "absolute", top: "50%", left: "50%",
            transform: `translate(-50%, -50%) translate(${offset.x}px, ${offset.y}px) scale(${zoom}) rotate(${rotation}deg)`,
            transformOrigin: "center center",
            maxWidth: "100%", maxHeight: "100%",
            transition: dragging ? "none" : "transform 0.1s",
          }}
          onError={e => { e.target.alt = tr.imgUnavailable; }}
        />
      </div>
    </div>
  );
}

export function ImageViewer({ mode, images, onClose, t, tr }) {
  useEffect(() => {
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 1000,
        background: "rgba(0,0,0,0.95)",
        display: "flex", flexDirection: "column",
      }}
    >
      {/* Header */}
      <div
        onClick={e => e.stopPropagation()}
        style={{
          display: "flex", alignItems: "center", justifyContent: "flex-end",
          padding: "8px 16px", background: "#0a0f1a",
          borderBottom: "1px solid #1e293b", flexShrink: 0,
        }}
      >
        <span style={{ fontSize: 10, color: "#334155", marginRight: "auto" }}>
          {tr.lightboxEsc}
        </span>
        <button
          onClick={onClose}
          style={{
            padding: "4px 14px", borderRadius: 8,
            border: "1px solid #334155", background: "transparent",
            color: "#94a3b8", fontSize: 12, cursor: "pointer",
          }}
        >
          {tr.lightboxClose}
        </button>
      </div>

      {/* Panels */}
      <div
        onClick={e => e.stopPropagation()}
        style={{ flex: 1, display: "flex", minHeight: 0 }}
      >
        {images.map((img, i) => (
          <div
            key={i}
            style={{
              flex: 1, display: "flex", minWidth: 0,
              borderLeft: i > 0 ? "2px solid #1e3a5f" : "none",
            }}
          >
            <ViewerPanel src={img.src} label={img.label} tr={tr} />
          </div>
        ))}
      </div>
    </div>
  );
}
