// AOI Tool - PP Sub Row — no rowspan, stable layout
// Receives nrCell from BaugrupeRow (rendered empty cell with group background)
import { useState, useEffect } from "react";
import { API_BASE } from "../api.js";
import { ErrorBadge, HinweisBlock } from "./shared.jsx";

const CELL = {
  padding: "8px 12px",
  verticalAlign: "middle",
  fontSize: 13,
  borderRight: "1px solid rgba(128,128,128,0.12)",
};

// ─── PP Detail Panel ───────────────────────────────────────────────────────────
function PpDetailPanel({ pp, t, tr, onClose }) {
  useEffect(() => {
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const hasPm      = pp.pm_dict && Object.keys(pp.pm_dict).length > 0;
  const hasErrors  = pp.errors?.length > 0;
  const hasHinweis = !!pp.hinweis;
  const sideColor  = pp.side === "BOT" ? "#f97316" : "#38bdf8";
  const colors     = t.rowColors[pp.row_color] || t.rowColors.green;

  return (
    <>
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, zIndex: 900,
        background: "rgba(0,0,0,0.45)",
        animation: "fadeIn 0.2s ease",
      }} />

      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0,
        width: 540, zIndex: 901,
        background: t.bgHeader,
        borderLeft: `2px solid ${t.border}`,
        display: "flex", flexDirection: "column",
        boxShadow: "-8px 0 32px rgba(0,0,0,0.35)",
        animation: "slideInRight 0.25s ease",
      }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "14px 20px",
          borderBottom: `1px solid ${t.border}`,
          flexShrink: 0,
        }}>
          <span style={{
            padding: "3px 10px", borderRadius: 6, fontSize: 12, fontWeight: 700,
            background: sideColor + "20", color: sideColor,
            border: `1px solid ${sideColor}40`, fontFamily: "monospace",
          }}>{pp.side}</span>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 14, color: t.text }}>
              {pp.name}
            </div>
            {pp.cli && (
              <span style={{
                padding: "1px 7px", borderRadius: 8, fontSize: 11, marginTop: 3,
                background: t.cliChip.bg, color: t.cliChip.color,
                fontFamily: "monospace", display: "inline-block",
              }}>{pp.cli}</span>
            )}
          </div>

          <div style={{ textAlign: "right" }}>
            {hasErrors && (
              <div style={{
                padding: "2px 9px", borderRadius: 10,
                background: colors.bg, border: `1px solid ${colors.border}60`,
                color: colors.text, fontSize: 12, fontWeight: 700,
              }}>
                {pp.errors.length} {pp.errors.length === 1 ? "Error" : "Errors"}
              </div>
            )}
            {pp.pm_count > 0 && (
              <div style={{ fontSize: 11, color: t.textMuted, marginTop: 2 }}>
                {pp.pm_count} PM
              </div>
            )}
          </div>

          <button onClick={onClose} style={{
            width: 32, height: 32, borderRadius: 8,
            border: `1px solid ${t.border}`, background: "transparent",
            color: t.textMuted, fontSize: 16, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            flexShrink: 0,
          }}>✕</button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>
          {hasErrors && (
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", color: t.textMuted, textTransform: "uppercase", marginBottom: 8 }}>
                Errors
              </div>
              {pp.errors.map((err, i) => <ErrorBadge key={i} error={err} t={t} />)}
            </div>
          )}

          {hasHinweis && (
            <div style={{ marginBottom: 20 }}>
              <HinweisBlock hinweis={pp.hinweis} t={t} tr={tr} />
            </div>
          )}

          {hasPm && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", color: t.textMuted, textTransform: "uppercase", marginBottom: 12 }}>
                {tr.pmTitle}
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {Object.entries(pp.pm_dict).sort(([a],[b]) => a.localeCompare(b)).map(([pmName, partNrs]) => (
                  <div key={pmName} style={{ borderRadius: 8, border: `1px solid ${t.border}`, overflow: "hidden" }}>
                    <div style={{
                      padding: "8px 14px",
                      background: t.tabActive.bg,
                      borderBottom: `1px solid ${t.border}`,
                      fontFamily: "monospace", fontWeight: 700, fontSize: 13,
                      color: t.tabActive.color,
                      textTransform: "uppercase",
                    }}>{pmName}</div>
                    <div style={{ padding: "8px 14px", display: "flex", flexDirection: "column", gap: 5 }}>
                      {typeof partNrs === "object" && !Array.isArray(partNrs)
                        ? Object.entries(partNrs).sort(([a],[b]) => a.localeCompare(b)).map(([partNr, refs]) => (
                            <div key={partNr} style={{ display: "flex", alignItems: "baseline", gap: 8, fontSize: 12 }}>
                              <span style={{ color: t.textMuted, flexShrink: 0 }}>•</span>
                              <span style={{ fontFamily: "monospace", fontWeight: 600, color: t.textSub, minWidth: 110, flexShrink: 0 }}>
                                {partNr}:
                              </span>
                              <span style={{ color: t.text, fontFamily: "monospace" }}>
                                {Array.isArray(refs)
                                  ? `${refs.length} refs`
                                  : String(refs).replace(/^\(|\)$/g, "")}
                              </span>
                            </div>
                          ))
                        : <div style={{ color: t.text, fontFamily: "monospace", fontSize: 12 }}>
                            {Array.isArray(partNrs) ? `${partNrs.length} refs` : String(partNrs).replace(/^\(|\)$/g, "")}
                          </div>
                      }
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!hasPm && !hasErrors && !hasHinweis && (
            <div style={{ textAlign: "center", padding: 40, color: "#22c55e", fontSize: 32 }}>✓</div>
          )}
        </div>

        <div style={{
          padding: "10px 20px", borderTop: `1px solid ${t.border}`,
          fontSize: 10, color: t.textMuted, textAlign: "center", flexShrink: 0,
        }}>
          ESC or click outside to close
        </div>
      </div>

      <style>{`
        @keyframes fadeIn       { from { opacity: 0 }          to { opacity: 1 } }
        @keyframes slideInRight { from { transform: translateX(100%) } to { transform: translateX(0) } }
      `}</style>
    </>
  );
}

// ─── PpThumbnail ──────────────────────────────────────────────────────────────
export function PpThumbnail({ ppName, customSrc, onClick, t, tr }) {
  const [loaded,   setLoaded]   = useState(false);
  const [imgError, setImgError] = useState(false);
  const src = customSrc ?? `${API_BASE}/api/image/${encodeURIComponent(ppName)}?type=hr`;

  if (imgError) return (
    <div style={{
      width: 120, height: 80, borderRadius: 6,
      background: t.border, border: `1px solid ${t.borderInput}`,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 20, color: t.textMuted, cursor: "default", flexShrink: 0,
    }}>📷</div>
  );

  return (
    <div onClick={onClick} style={{
      width: 120, height: 80, borderRadius: 6,
      border: `1px solid ${t.borderInput}`,
      overflow: "hidden", cursor: "pointer",
      background: t.bgInput, flexShrink: 0,
      display: "flex", alignItems: "center", justifyContent: "center",
      transition: "transform 0.15s, box-shadow 0.15s",
    }}
      onMouseEnter={e => { e.currentTarget.style.transform = "scale(1.05)"; e.currentTarget.style.boxShadow = "0 0 10px #38bdf860"; }}
      onMouseLeave={e => { e.currentTarget.style.transform = "scale(1)"; e.currentTarget.style.boxShadow = "none"; }}
    >
      {!loaded && <span style={{ fontSize: 11, color: t.textMuted }}>...</span>}
      <img
        src={src} alt={ppName || "image"} draggable={false}
        style={{ width: "100%", height: "100%", objectFit: "cover", display: loaded ? "block" : "none" }}
        onLoad={() => setLoaded(true)}
        onError={() => setImgError(true)}
      />
    </div>
  );
}

// ─── PpSubRow ─────────────────────────────────────────────────────────────────
export function PpSubRow({ pp, isLast, nrCell, t, tr, onOpenViewer, isUrgent, accent, lpImageSrc }) {
  const [panelOpen, setPanelOpen] = useState(false);

  const colors     = t.rowColors[pp.row_color] || t.rowColors.green;
  const hasErrors  = pp.errors?.length > 0;
  const hasPm      = pp.pm_dict && Object.keys(pp.pm_dict).length > 0;
  const hasHinweis = !!pp.hinweis;
  const hasDetails = hasPm || hasHinweis || hasErrors;
  const sideColor  = pp.side === "BOT" ? "#f97316" : "#38bdf8";

  const PP_BG = {
    green:  "rgba(34,197,94,0.04)",
    yellow: "rgba(234,179,8,0.05)",
    orange: "rgba(249,115,22,0.05)",
    red:    "rgba(239,68,68,0.05)",
  };
  const ppBg = PP_BG[pp.row_color] || PP_BG.green;

  const haranSrc   = `${API_BASE}/api/image/${encodeURIComponent(pp.name)}?type=hr`;
  const lpSrc      = lpImageSrc ?? null;
  const canCompare = !!lpSrc;

  return (
    <>
      {panelOpen && (
        <PpDetailPanel pp={pp} t={t} tr={tr} onClose={() => setPanelOpen(false)} />
      )}

      {/* PP main row */}
      <tr
        onClick={() => hasDetails && setPanelOpen(true)}
        style={{
          background: ppBg,
          borderBottom: isLast
            ? `1px solid ${accent}30`
            : `1px solid rgba(128,128,128,0.08)`,
          borderLeft: `4px solid ${sideColor}40`,
          cursor: hasDetails ? "pointer" : "default",
        }}
        onMouseEnter={e => e.currentTarget.style.filter = "brightness(0.94)"}
        onMouseLeave={e => e.currentTarget.style.filter = ""}
      >
        {/* Nr — empty cell with group background */}
        {nrCell}

        {/* SMD Line → side badge */}
        <td style={{ ...CELL, width: 100, textAlign: "center" }}>
          <span style={{
            padding: "3px 10px", borderRadius: 6, fontSize: 12, fontWeight: 700,
            background: sideColor + "15", color: sideColor,
            border: `1px solid ${sideColor}35`, fontFamily: "monospace",
          }}>{pp.side}</span>
        </td>

        {/* Assembly → PP name + CLI */}
        <td style={{ ...CELL }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, paddingLeft: 8 }}>
            <div style={{ fontFamily: "monospace", fontWeight: 600, fontSize: 13, color: t.text }}>
              {pp.name}
            </div>
            {pp.cli && (
              <span style={{
                padding: "2px 8px", borderRadius: 8, fontSize: 11,
                background: t.cliChip.bg, color: t.cliChip.color,
                fontFamily: "monospace", display: "inline-block", width: "fit-content",
              }}>{pp.cli}</span>
            )}
          </div>
        </td>

        {/* Customer + Project → LP image, Compare, Haran (merged) */}
        <td colSpan={2} style={{ ...CELL, width: 280, borderRight: "1px solid rgba(128,128,128,0.12)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {lpSrc ? (
              <PpThumbnail customSrc={lpSrc} t={t} tr={tr}
                onClick={e => { e.stopPropagation(); onOpenViewer("single", [{ src: lpSrc, label: tr.viewerLp }]); }}
              />
            ) : (
              <div style={{
                width: 120, height: 80, borderRadius: 6, flexShrink: 0,
                background: t.border + "25", border: `1px solid ${t.border}`,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <span style={{ fontSize: 11, color: t.textMuted }}>LP</span>
              </div>
            )}

            {canCompare && (
              <button
                onClick={e => { e.stopPropagation(); onOpenViewer("compare", [{ src: lpSrc, label: tr.viewerLp }, { src: haranSrc, label: `${tr.viewerHaran} — ${pp.name}` }]); }}
                style={{
                  padding: "5px 9px", borderRadius: 6, border: `1px solid ${t.border}`,
                  background: "transparent", color: t.textMuted, fontSize: 14,
                  cursor: "pointer", flexShrink: 0, transition: "all 0.15s",
                }}
                onMouseEnter={e => { e.currentTarget.style.background = t.tabActive.bg; e.currentTarget.style.color = t.tabActive.color; }}
                onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = t.textMuted; }}
              >⇔</button>
            )}

            <PpThumbnail ppName={pp.name} t={t} tr={tr}
              onClick={e => { e.stopPropagation(); onOpenViewer("single", [{ src: haranSrc, label: `${tr.viewerHaran} — ${pp.name}` }]); }}
            />
          </div>
        </td>

        {/* Col 6: Components — show only relevant side */}
        <td style={{ ...CELL, width: 270 }}>
          <div style={{ fontFamily: "monospace", fontSize: 12 }}>
            {pp.side === "BOT" ? (
              <span>
                <span style={{ color: "#f97316", fontWeight: 700 }}>B: </span>
                <span style={{ color: t.textSub }}>{pp.cad_bot_count ?? "—"}</span>
              </span>
            ) : (
              <span>
                <span style={{ color: "#38bdf8", fontWeight: 700 }}>T: </span>
                <span style={{ color: t.textSub }}>{pp.cad_top_count ?? "—"}</span>
              </span>
            )}
          </div>
        </td>

        {/* Flags — hinweis indicator */}
        <td style={{ ...CELL, width: 110, textAlign: "center" }}>
          {pp.hinweis && <span style={{ fontSize: 13 }}>📋</span>}
        </td>

        {/* Info */}
        <td style={{ ...CELL, width: 130, textAlign: "center", borderRight: "none" }}>
          <div style={{ fontFamily: "'IBM Plex Sans'", fontSize: 13, lineHeight: 1.8 }}>
            {hasErrors && (
              <div style={{
                padding: "2px 8px", borderRadius: 10, display: "inline-block",
                background: colors.bg, border: `1px solid ${colors.border}60`,
                color: colors.text, fontWeight: 700, marginBottom: 2,
              }}>
                {pp.errors.length} {pp.errors.length === 1 ? "Error" : "Errors"}
              </div>
            )}
            {pp.pm_count > 0 && (
              <div style={{ color: t.textMuted }}>{pp.pm_count} PM</div>
            )}
            {hasDetails && (
              <div style={{ color: t.textMuted, fontSize: 11, marginTop: 2 }}>› details</div>
            )}
            {!hasErrors && !pp.pm_count && !hasDetails && (
              <span style={{ color: "#22c55e", fontSize: 15 }}>✓</span>
            )}
          </div>
        </td>
      </tr>

      {/* PP error rows — start at Assembly col, span 6 cols */}
      {hasErrors && pp.errors.map((err, i) => (
        <tr key={`pp-err-${i}`} style={{
          background: t.expandBg,
          borderBottom: `1px solid ${colors.border}15`,
          borderLeft: `4px solid ${colors.border}60`,
        }}>
          {nrCell}
          <td style={{ ...CELL, width: 100 }} />
          <td colSpan={6} style={{ padding: "4px 16px 4px 24px", borderRight: "none", verticalAlign: "middle" }}>
            <ErrorBadge error={err} t={t} />
          </td>
        </tr>
      ))}
    </>
  );
}
