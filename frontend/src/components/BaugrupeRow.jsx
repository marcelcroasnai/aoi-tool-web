// AOI Tool - BG Row — Direction A (severity rail, neutral rows, status pill)
import { useState } from "react";
import { API_BASE } from "../api.js";
import { Chip, CompCell, StatusPill, ErrorBadge } from "./shared.jsx";
import { withAlpha } from "../constants/tableStyles.js";
import { PpSubRow } from "./PpSubRow.jsx";

export function BaugrupeRow({ bg, index, t, tr, onOpenViewer, forceExpandBg, styles }) {
  const [expanded, setExpanded] = useState(false);
  const isExpanded  = forceExpandBg || expanded;

  const ppList      = bg.pp_list_detail || [];
  const hasPpData   = ppList.length > 0;
  const hasBgErrors = bg.bg_errors?.length > 0;
  const isUrgent    = bg.auftragsmenge?.includes(" ");
  const totalPpErr  = ppList.reduce((s, pp) => s + (pp.errors?.length || 0), 0);
  const totalErr    = (bg.bg_errors?.length || 0) + totalPpErr;

  const iBot = bg.intranet_bot_count ?? 0;
  const iTop = bg.intranet_top_count ?? 0;
  const cBot = bg.cad_bot_count      ?? 0;
  const cTop = bg.cad_top_count      ?? 0;

  const sevColor = styles.sevColor(bg.row_color);
  const dot      = bg.bg_color || sevColor;          // keep AP color as a marker dot
  const rowBg    = styles.zebra(index);

  // Rail + Nr cell, shared by every row in this BG group (BG, errors, PP rows)
  const railCell = (showNum) => (
    <td style={{
      ...styles.cell, ...styles.num,
      width: 52, textAlign: "right",
      borderLeft: `${styles.railWidth}px solid ${sevColor}`,
      color: showNum ? t.textSub : "transparent",
      fontWeight: 700, userSelect: "none",
    }}>
      {showNum ? index + 1 : ""}
    </td>
  );

  const errPad = styles.dense ? "3px 14px 3px 18px" : "4px 16px 4px 22px";

  return (
    <>
      {/* ── BG header row ── */}
      <tr
        onClick={() => hasPpData && setExpanded(e => !e)}
        style={{
          background: rowBg,
          borderTop: `1px solid ${t.border}`,
          cursor: hasPpData ? "pointer" : "default",
        }}
        onMouseEnter={e => (e.currentTarget.style.background = t.expandBg)}
        onMouseLeave={e => (e.currentTarget.style.background = rowBg)}
      >
        {railCell(true)}

        {/* Assembly + project subtitle */}
        <td style={styles.cell}>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", flexShrink: 0, background: dot }} />
            <span style={{ ...styles.mono, fontWeight: 700, fontSize: styles.dense ? 14 : 15, color: t.text }}>
              {bg.name}
            </span>
            {bg.smd_line && <Chip label={`SMD ${bg.smd_line}`} t={t} />}
            {hasPpData    && <Chip label={`${ppList.length} PP`} t={t} />}
            {isUrgent     && <Chip label="⏱" color="#f59e0b" t={t} title="eilig" />}
            {hasPpData && (
              <span style={{ marginLeft: "auto", color: t.textMuted, fontSize: 12 }}>
                {isExpanded ? "▲" : "▼"}
              </span>
            )}
          </div>
          {bg.project_name && (
            <div style={{ color: t.textMuted, fontSize: 11, marginTop: 3, marginLeft: 17 }}>
              {bg.project_name}
            </div>
          )}
        </td>

        {/* Customer */}
        <td style={{ ...styles.cell, width: 110 }}>
          <span style={{ color: t.textSub, fontSize: 13 }}>{bg.kunde || "—"}</span>
        </td>

        {/* Components */}
        <td style={{ ...styles.cell, width: 170 }}>
          <CompCell iBot={iBot} iTop={iTop} cBot={cBot} cTop={cTop} t={t} />
        </td>

        {/* Flags */}
        <td style={{ ...styles.cell, width: 110 }}>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {bg.dmc              && <Chip label="DMC"  color="#38bdf8" t={t} />}
            {bg.medi             && <Chip label="MEDI" color="#a78bfa" t={t} />}
            {bg.locked === "yes" && <Chip label="🔒"   color="#ef4444" t={t} />}
          </div>
        </td>

        {/* Status */}
        <td style={{ ...styles.cell, width: 90, textAlign: "right" }}>
          <StatusPill rowColor={bg.row_color} count={totalErr} t={t} />
        </td>
      </tr>

      {/* ── BG error rows ── */}
      {hasBgErrors && bg.bg_errors.map((err, i) => (
        <tr key={`bgerr-${i}`} style={{ background: withAlpha(sevColor, 0.06) }}>
          {railCell(false)}
          <td colSpan={5} style={{ padding: errPad }}>
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
          railCell={railCell(false)}
          sevColor={sevColor}
          t={t} tr={tr} styles={styles}
          onOpenViewer={onOpenViewer}
          lpImageSrc={
            pp.side === "BOT"
              ? (bg.lp_image_bot ? `${API_BASE}/api/lp-image/?path=${encodeURIComponent(bg.lp_image_bot)}` : null)
              : (bg.lp_image_top ? `${API_BASE}/api/lp-image/?path=${encodeURIComponent(bg.lp_image_top)}` : null)
          }
        />
      ))}
    </>
  );
}
