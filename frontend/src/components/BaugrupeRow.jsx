// AOI Tool - BG Row — no rowspan, stable layout
import { useState } from "react";
import { API_BASE } from "../api.js";
import { Flag, ErrorBadge } from "./shared.jsx";
import { PpSubRow } from "./PpSubRow.jsx";

const CELL = {
  padding: "10px 12px",
  verticalAlign: "middle",
  fontSize: 14,
  borderRight: "1px solid rgba(128,128,128,0.12)",
};


function CompRow({ t, label, bot, top }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontFamily: "monospace", fontSize: 12, lineHeight: 1.9 }}>
      {label && <span style={{ color: t.textMuted, minWidth: 28 }}>{label}:</span>}
      <span style={{ color: "#f97316", fontWeight: 700 }}>B:</span>
      <span style={{ color: t.textSub, minWidth: 30 }}>{bot}</span>
      <span style={{ color: t.border }}>|</span>
      <span style={{ color: "#38bdf8", fontWeight: 700 }}>T:</span>
      <span style={{ color: t.textSub, minWidth: 30 }}>{top}</span>
      <span style={{ color: t.border }}>|</span>
      <span style={{ color: t.textMuted, fontWeight: 700 }}>Σ:</span>
      <span style={{ color: t.textSub }}>{bot + top}</span>
    </div>
  );
}


export function BaugrupeRow({ bg, index, t, tr, onOpenViewer, forceExpandBg }) {
  const [expanded, setExpanded] = useState(false);
  const isExpanded  = forceExpandBg || expanded;
  const colors      = t.rowColors[bg.row_color] || t.rowColors.green;
  const ppList      = bg.pp_list_detail || [];
  const hasPpData   = ppList.length > 0;
  const hasBgErrors = bg.bg_errors?.length > 0;
  const isUrgent    = bg.auftragsmenge?.includes(" ");
  const totalPpErr  = ppList.reduce((s, pp) => s + (pp.errors?.length || 0), 0);
  const iBot = bg.intranet_bot_count ?? 0;
  const iTop = bg.intranet_top_count ?? 0;
  const cBot = bg.cad_bot_count      ?? 0;
  const cTop = bg.cad_top_count      ?? 0;
  const compSame = iBot === cBot && iTop === cTop;

  // Group accent color
  const accent  = isUrgent ? "#f59e0b" : colors.border;
  // Use bg_color from AP if available, otherwise derive from row color
  const bgRowBg = bg.bg_color
    ? bg.bg_color + "55"          // AP color with transparency
    : accent + "22";
  const nrBg = bg.bg_color
    ? bg.bg_color + "33"
    : accent + "18";

  const borderGroup = `3px solid ${accent}60`;

  // Shared Nr cell style — same for BG row, error rows, PP rows
  const nrCell = (showNumber) => (
    <td style={{
      ...CELL,
      width: 52, textAlign: "center",
      background: nrBg,
      fontWeight: 800, fontSize: 16,
      color: showNumber ? accent : "transparent",
      borderRight: `1px solid ${accent}30`,
      userSelect: "none",
    }}>
      {showNumber ? index + 1 : "·"}
    </td>
  );

  return (
    <>
      {/* ── BG header row ── */}
      <tr
        onClick={() => hasPpData && setExpanded(e => !e)}
        style={{
          background: bgRowBg,
          borderTop: `2px solid ${accent}60`,
          borderBottom: isExpanded
            ? `1px solid ${accent}30`
            : `2px solid ${accent}60`,
          cursor: hasPpData ? "pointer" : "default",
        }}
        onMouseEnter={e => e.currentTarget.style.filter = "brightness(0.93)"}
        onMouseLeave={e => e.currentTarget.style.filter = ""}
      >
        {/* Nr */}
        {nrCell(true)}

        {/* SMD Line */}
        <td style={{ ...CELL, width: 100, textAlign: "center" }}>
          {bg.smd_line
            ? <span style={{ fontFamily: "monospace", color: t.textSub, fontSize: 13 }}>SMD {bg.smd_line}</span>
            : <span style={{ color: t.border }}>—</span>
          }
        </td>

        {/* Assembly */}
        <td style={{ ...CELL, minWidth: 240, textAlign: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{
              width: 9, height: 9, borderRadius: "50%", flexShrink: 0,
              background: accent, boxShadow: `0 0 7px ${accent}`,
            }} />
            <span style={{ fontFamily: "monospace", fontWeight: 700, fontSize: 15, color: t.text }}>
              {bg.name}
            </span>
            {hasPpData && (
              <span style={{
                padding: "1px 8px", borderRadius: 10, fontSize: 11,
                background: t.border + "60", color: t.textMuted,
              }}>
                {ppList.length} PP
              </span>
            )}
            {hasPpData && (
              <span style={{ color: t.textMuted, fontSize: 12, marginLeft: "auto" }}>
                {isExpanded ? "▲" : "▼"}
              </span>
            )}
          </div>
        </td>

        {/* Customer */}
        <td style={{ ...CELL, width: 120, textAlign: "center" }}>
          <span style={{ fontFamily: "monospace", color: t.textSub, fontSize: 13 }}>
            {bg.kunde || "—"}
          </span>
        </td>

        {/* Project */}
        <td style={{ ...CELL, width: 160, textAlign: "center" }}>
          <span style={{ color: t.textSub, fontSize: 13 }}>
            {bg.project_name || "—"}
          </span>
        </td>

        {/* Components */}
        <td style={{ ...CELL, width: 270 }}>
          {compSame ? (
            <CompRow t={t} label={null} bot={iBot} top={iTop} />
          ) : (
            <>
              <CompRow t={t} label="Int" bot={iBot} top={iTop} />
              <CompRow t={t} label="Cad" bot={cBot} top={cTop} />
            </>
          )}
        </td>

        {/* Flags */}
        <td style={{ ...CELL, width: 110, textAlign: "center" }}>
          <div style={{ display: "flex", gap: 4, justifyContent: "center", flexWrap: "wrap" }}>
            {bg.dmc           && <Flag label="DMC"  color="#38bdf8" />}
            {bg.medi          && <Flag label="MEDI" color="#a78bfa" />}
            {bg.locked === "yes" && <Flag label="🔒" color="#ef4444" />}
          </div>
        </td>

        {/* Info */}
        <td style={{ ...CELL, width: 130, textAlign: "center",
          borderRight: "none" }}>
          <div style={{ fontFamily: "'IBM Plex Sans'", fontSize: 13, lineHeight: 1.9 }}>
            {hasBgErrors && (
              <div style={{ color: colors.text, fontWeight: 600 }}>
                BG: {bg.bg_errors.length} err
              </div>
            )}
            {totalPpErr > 0 && (
              <div style={{ color: t.textMuted }}>
                PP: {totalPpErr} err
              </div>
            )}
            {!hasBgErrors && totalPpErr === 0 && (
              <span style={{ color: "#22c55e", fontSize: 16 }}>✓</span>
            )}
          </div>
        </td>
      </tr>

      {/* ── BG error rows ── */}
      {hasBgErrors && bg.bg_errors.map((err, i) => (
        <tr key={`bgerr-${i}`} style={{
          background: t.expandBg,
          borderBottom: `1px solid ${accent}20`,
          borderLeft: `4px solid ${accent}60`,
        }}>
          {nrCell(false)}
          <td colSpan={7} style={{ padding: "5px 16px 5px 24px", borderRight: "none" }}>
            <ErrorBadge error={err} t={t} />
          </td>
        </tr>
      ))}

      {/* ── PP sub-rows ── */}
      {isExpanded && ppList.map((pp, i) => (
        <PpSubRow
          key={pp.name}
          pp={pp}
          isLast={i === ppList.length - 1}
          nrCell={nrCell(false)}
          t={t} tr={tr}
          onOpenViewer={onOpenViewer}
          isUrgent={isUrgent}
          accent={accent}
          lpImageSrc={
            pp.side === "BOT"
              ? (bg.lp_image_bot ? `${API_BASE}/api/lp-image/?path=${encodeURIComponent(bg.lp_image_bot)}` : null)
              : (bg.lp_image_top ? `${API_BASE}/api/lp-image/?path=${encodeURIComponent(bg.lp_image_top)}` : null)
          }
        />
      ))}

      {/* ── Group bottom border ── */}
      <tr aria-hidden="true">
        <td colSpan={8} style={{
          padding: 0, height: 0,
          borderBottom: borderGroup,
        }} />
      </tr>
    </>
  );
}