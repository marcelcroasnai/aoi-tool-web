// AOI Tool - PP Sub Row — Direction A (tree detail row, shared rail)
// Receives railCell (the empty rail/Nr <td>) from BaugrupeRow.
import { useState, useEffect } from "react";
import { API_BASE } from "../api.js";
import { ErrorBadge, HinweisBlock, StatusPill } from "./shared.jsx";
import { withAlpha, SIDE_COLOR } from "../constants/tableStyles.js";

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
export function PpThumbnail({ ppName, customSrc, onClick, t, tr, w = 120, h = 80 }) {
  const [loaded,   setLoaded]   = useState(false);
  const [imgError, setImgError] = useState(false);
  const src = customSrc ?? `${API_BASE}/api/image/${encodeURIComponent(ppName)}?type=hr`;

  if (imgError) return (
    <div style={{
      width: w, height: h, borderRadius: 6,
      background: t.border, border: `1px solid ${t.borderInput}`,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 20, color: t.textMuted, cursor: "default", flexShrink: 0,
    }}>📷</div>
  );

  return (
    <div onClick={onClick} style={{
      width: w, height: h, borderRadius: 6,
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
export function PpSubRow({ pp, isLast, railCell, sevColor, t, tr, onOpenViewer, styles, lpImageSrc }) {
  const [panelOpen, setPanelOpen] = useState(false);

  const hasErrors  = pp.errors?.length > 0;
  const hasPm      = pp.pm_dict && Object.keys(pp.pm_dict).length > 0;
  const hasHinweis = !!pp.hinweis;
  const hasDetails = hasPm || hasHinweis || hasErrors;
  const sideColor  = SIDE_COLOR[pp.side] || SIDE_COLOR.TOP;
  const sideCount  = pp.side === "BOT" ? pp.cad_bot_count : pp.cad_top_count;

  const haranSrc   = `${API_BASE}/api/image/${encodeURIComponent(pp.name)}?type=hr`;
  const lpSrc      = lpImageSrc ?? null;
  const canCompare = !!lpSrc;

  const thumbW  = styles.dense ? 92 : 120;
  const thumbH  = styles.dense ? 62 : 80;
  const clusterGap = styles.dense ? 18 : 28;          // space between badge / name / images
  const padY    = styles.dense ? 5 : 7;
  const stop    = (fn) => (e) => { e.stopPropagation(); fn(e); };

  return (
    <>
      {panelOpen && (
        <PpDetailPanel pp={pp} t={t} tr={tr} onClose={() => setPanelOpen(false)} />
      )}

      {/* ── PP detail row (real column cells so values align with the BG row) ── */}
      <tr
        onClick={() => hasDetails && setPanelOpen(true)}
        style={{
          background: "transparent",
          borderBottom: `1px solid ${styles.divider}`,
          cursor: hasDetails ? "pointer" : "default",
        }}
        onMouseEnter={e => (e.currentTarget.style.background = t.expandBg)}
        onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
      >
        {railCell}

        {/* Baugruppe + Kunde span: connector · side badge · name/CLI · images */}
        <td colSpan={2} style={{ ...styles.cell, paddingTop: padY, paddingBottom: padY }}>
          <div style={{ display: "flex", alignItems: "center", gap: clusterGap, borderLeft: `1.5px solid ${t.border}`, paddingLeft: 14 }}>

            <span style={{
              padding: "2px 9px", borderRadius: 6, fontSize: 12, fontWeight: 700, flexShrink: 0,
              background: sideColor + "1f", color: sideColor,
              border: `1px solid ${sideColor}45`, fontFamily: "'IBM Plex Mono', monospace",
            }}>{pp.side}</span>

            <div style={{ display: "flex", flexDirection: "column", gap: 3, minWidth: 170, flexShrink: 0 }}>
              <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontWeight: 600, fontSize: 13, color: t.text }}>
                {pp.name}
              </span>
              {pp.cli && (
                <span style={{
                  padding: "1px 7px", borderRadius: 8, fontSize: 11, width: "fit-content",
                  background: t.cliChip.bg, color: t.cliChip.color,
                  fontFamily: "'IBM Plex Mono', monospace",
                }}>{pp.cli}</span>
              )}
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: 8 }} onClick={e => e.stopPropagation()}>
              {lpSrc ? (
                <PpThumbnail customSrc={lpSrc} t={t} tr={tr} w={thumbW} h={thumbH}
                  onClick={stop(() => onOpenViewer("single", [{ src: lpSrc, label: tr.viewerLp }]))}
                />
              ) : (
                <div style={{
                  width: thumbW, height: thumbH, borderRadius: 6, flexShrink: 0,
                  background: withAlpha(t.border, 0.25), border: `1px solid ${t.border}`,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <span style={{ fontSize: 11, color: t.textMuted }}>LP</span>
                </div>
              )}

              {canCompare && (
                <button
                  onClick={stop(() => onOpenViewer("compare", [{ src: lpSrc, label: tr.viewerLp }, { src: haranSrc, label: `${tr.viewerHaran} — ${pp.name}` }]))}
                  style={{
                    padding: "6px 9px", borderRadius: 6, border: `1px solid ${t.border}`,
                    background: "transparent", color: t.textMuted, fontSize: 14,
                    cursor: "pointer", flexShrink: 0, transition: "all 0.15s",
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = t.tabActive.bg; e.currentTarget.style.color = t.tabActive.color; }}
                  onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = t.textMuted; }}
                >⇔</button>
              )}

              <PpThumbnail ppName={pp.name} t={t} tr={tr} w={thumbW} h={thumbH}
                onClick={stop(() => onOpenViewer("single", [{ src: haranSrc, label: `${tr.viewerHaran} — ${pp.name}` }]))}
              />
            </div>
          </div>
        </td>

        {/* Components — same column as the BG B · T */}
        <td style={{ ...styles.cell, width: 170 }}>
          <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
            <span style={{ color: sideColor, fontWeight: 700 }}>{pp.side === "BOT" ? "B" : "T"}</span>
            <span style={{ color: t.textSub }}> {sideCount ?? "—"}</span>
          </span>
        </td>

        {/* Flags */}
        <td style={{ ...styles.cell, width: 110 }}>
          {hasHinweis && <span title="Hinweis" style={{ fontSize: 13 }}>📋</span>}
        </td>

        {/* Status */}
        <td style={{ ...styles.cell, width: 90, textAlign: "right" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8 }}>
            {pp.pm_count > 0 && <span style={{ color: t.textMuted, fontSize: 11 }}>{pp.pm_count} PM</span>}
            <StatusPill rowColor={pp.row_color} count={pp.errors?.length || 0} t={t} />
            {hasDetails && <span style={{ color: t.textMuted, fontSize: 12 }}>›</span>}
          </div>
        </td>
      </tr>

      {/* ── PP error rows ── */}
      {hasErrors && pp.errors.map((err, i) => (
        <tr key={`pp-err-${i}`} style={{ background: t.expandBg, borderBottom: `1px solid ${styles.divider}` }}>
          {railCell}
          <td colSpan={5} style={{ padding: styles.dense ? "3px 14px 3px 30px" : "4px 16px 4px 34px" }}>
            <div style={{ borderLeft: `1.5px solid ${t.border}`, paddingLeft: 14 }}>
              <ErrorBadge error={err} t={t} />
            </div>
          </td>
        </tr>
      ))}
    </>
  );
}
