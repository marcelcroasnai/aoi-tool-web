// AOI Tool - Shared UI components
import { useState } from "react";

export function StatusBar({ status, t, tr }) {
  const ok = status?.status === "ok";
  const s  = ok ? t.statusOk : t.statusErr;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "4px 14px", borderRadius: 20,
      background: s.bg, border: `1px solid ${s.border}`,
      fontSize: 12, color: s.color,
    }}>
      <span style={{
        width: 7, height: 7, borderRadius: "50%",
        background: ok ? "#22c55e" : "#ef4444",
        boxShadow: ok ? "0 0 6px #22c55e" : "0 0 6px #ef4444",
      }} />
      {status ? (ok ? tr.driveOk : status.message || tr.driveErr) : tr.driveChecking}
    </div>
  );
}

export function Spinner({ t, tr }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 16, padding: 60 }}>
      <div style={{
        width: 40, height: 40, borderRadius: "50%",
        border: `3px solid ${t.border}`, borderTopColor: "#38bdf8",
        animation: "spin 0.8s linear infinite",
      }} />
      <span style={{ color: t.textMuted, fontSize: 13 }}>{tr.btnRunning}</span>
    </div>
  );
}

export function ErrorBadge({ error, t }) {
  // Map error_type string to color theme key
  const typeToColor = { "Critical": "red", "Suggestion": "orange", "Info": "yellow" };
  const colorKey    = typeToColor[error.error_type] || "orange";
  const c           = t.rowColors[colorKey] || t.rowColors.orange;


  return (
    <div style={{
      padding: "5px 10px", borderRadius: 6, marginBottom: 4,
      background: c.bg, border: `1px solid ${c.border}40`,
      lineHeight: 1.5,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: error.long_desc ? 3 : 0 }}>
        <span style={{ fontWeight: 700, fontFamily: "monospace", fontSize: 11, color: c.border, flexShrink: 0 }}>
          {error.error_code}
        </span>
        {error.short_desc && error.short_desc !== error.error_code && (
          <span style={{ fontSize: 12, fontWeight: 600, color: c.text }}>
            {error.short_desc}
          </span>
        )}
        <span style={{
          marginLeft: "auto", fontSize: 10, padding: "1px 6px",
          borderRadius: 8, background: c.border + "20",
          color: c.border, fontWeight: 600, flexShrink: 0,
        }}>{error.error_type}</span>
      </div>
      {error.long_desc && (
        <div style={{ fontSize: 11, color: c.text, opacity: 0.85, paddingLeft: 4 }}>
          {error.long_desc}
          {error.affected_rows?.length > 0 && (
            <span style={{ marginLeft: 8, fontFamily: "monospace", opacity: 0.7 }}>
              rows: {error.affected_rows.join(", ")}
            </span>
          )}
        </div>
      )}
      {error.open_file && (
        <div style={{ fontSize: 10, fontFamily: "monospace", color: c.text, opacity: 0.6, marginTop: 2, paddingLeft: 4 }}>
          📄 {error.open_file}
        </div>
      )}
    </div>
  );
  
}

export function HinweisBlock({ hinweis, t, tr }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(o => !o)} style={{
        background: t.hinweisBtn.bg, border: `1px solid ${t.hinweisBtn.border}`,
        color: t.hinweisBtn.color, borderRadius: 6, padding: "2px 8px",
        fontSize: 11, cursor: "pointer", marginBottom: 3,
      }}>
        📋 {tr.hinweisBtn} {open ? "▲" : "▼"}
      </button>
      {open && (
        <pre style={{
          fontSize: 10, color: t.hinweisPre.color, background: t.hinweisPre.bg,
          padding: 8, borderRadius: 6, maxHeight: 120, overflow: "auto",
          whiteSpace: "pre-wrap", margin: 0,
        }}>{hinweis}</pre>
      )}
    </div>
  );
}

export function Flag({ label, color }) {
  return (
    <span style={{
      padding: "1px 5px", borderRadius: 6,
      background: color + "20", color, border: `1px solid ${color}40`,
      fontSize: 10, fontWeight: 700,
    }}>{label}</span>
  );
}

export function Th({ label, width, align = "left", t }) {
  return (
    <th style={{
      padding: "9px 12px", textAlign: align,
      fontSize: 10, fontWeight: 700, letterSpacing: "0.08em",
      color: t.thHead.color, textTransform: "uppercase",
      borderBottom: `2px solid ${t.thHead.border}`,
      background: t.thHead.bg, width: width || "auto",
      whiteSpace: "nowrap", position: "sticky", top: 0, zIndex: 2,
    }}>{label}</th>
  );
}

// ─── Inspection-table primitives (Direction A) ─────────────────────────────────

const SEV_ICON = { green: "✓", yellow: "ℹ", orange: "⚠", red: "✗" };

// One status object per row: icon + (count when not green).
export function StatusPill({ rowColor, count = 0, t }) {
  const c    = t.rowColors[rowColor] || t.rowColors.green;
  const icon = SEV_ICON[rowColor] || "✓";
  const showCount = rowColor !== "green" && count > 0;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 10px", borderRadius: 999, fontSize: 12, fontWeight: 700,
      background: c.bg, color: c.text, border: `1px solid ${c.border}40`,
      fontVariantNumeric: "tabular-nums",
    }}>
      <span>{icon}</span>{showCount && <span>{count}</span>}
    </span>
  );
}

// Outline chip; lights up in `color` when provided, otherwise muted neutral.
export function Chip({ label, color, t, mono, title }) {
  const lit = !!color;
  return (
    <span title={title} style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "1px 7px", borderRadius: 8, fontSize: 11, fontWeight: 600,
      whiteSpace: "nowrap",
      background: lit ? color + "1f" : "transparent",
      color: lit ? color : t.textMuted,
      border: `1px solid ${lit ? color + "55" : t.border}`,
      fontFamily: mono ? "'IBM Plex Mono', monospace" : "inherit",
    }}>{label}</span>
  );
}

// Components cell: B/T (intranet) + a Δ badge when Cad counts disagree.
export function CompCell({ iBot = 0, iTop = 0, cBot = 0, cTop = 0, t }) {
  const same = iBot === cBot && iTop === cTop;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}>
      <span style={{ fontFamily: "'IBM Plex Mono', monospace", fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
        <span style={{ color: "#f97316", fontWeight: 700 }}>B</span>
        <span style={{ color: t.textSub }}> {iBot}</span>
        <span style={{ color: t.border, margin: "0 5px" }}>·</span>
        <span style={{ color: "#38bdf8", fontWeight: 700 }}>T</span>
        <span style={{ color: t.textSub }}> {iTop}</span>
      </span>
      {!same && (
        <span title={`Intranet B${iBot}/T${iTop} ≠ Cad B${cBot}/T${cTop}`} style={{
          display: "inline-flex", alignItems: "center",
          padding: "1px 6px", borderRadius: 8, fontSize: 11, fontWeight: 700,
          background: "#ef444420", color: "#fca5a5", border: "1px solid #ef444455",
          cursor: "help",
        }}>Δ</span>
      )}
    </span>
  );
}

// SMD-line section band (replaces the old spacer row between lines).
export function SmdBand({ line, colSpan, styles }) {
  return (
    <tr>
      <td colSpan={colSpan} style={styles.smdBand}>SMD {line}</td>
    </tr>
  );
}

export function DensityToggle({ dense, setDense, t }) {
  return (
    <button
      onClick={() => setDense(d => !d)}
      title={dense ? "Compact" : "Comfortable"}
      style={{
        padding: "6px 12px", borderRadius: 20, cursor: "pointer",
        border: `1px solid ${t.border}`, background: "transparent",
        color: t.textMuted, fontSize: 13, fontWeight: 600,
        fontFamily: "'IBM Plex Sans'", display: "flex", alignItems: "center", gap: 5,
        transition: "all 0.15s",
      }}
    >
      {dense ? "▤" : "▦"}
    </button>
  );
}

export function Td({ children, align = "left", width, t, style: extra = {} }) {
  return (
    <td style={{
      padding: "7px 8px", textAlign: align,
      verticalAlign: "middle", width, maxWidth: width,
      fontSize: 12, borderRight: `1px solid ${t.border}20`,
      color: t.text, ...extra,
    }}>{children}</td>
  );
}

export function SummaryBar({ results, t, tr }) {
  const byColor = { green: 0, yellow: 0, orange: 0, red: 0 };
  results.forEach(r => { byColor[r.row_color] = (byColor[r.row_color] || 0) + 1; });
  const items = [
    ["green",  "✓", tr.summaryOk],
    ["yellow", "ℹ", tr.summaryInfo],
    ["orange", "⚠", tr.summaryWarning],
    ["red",    "✗", tr.summaryError],
  ];
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
      {items.map(([key, icon, label]) => {
        const c = t.rowColors[key];
        return (
          <div key={key} style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "4px 12px", borderRadius: 20,
            background: c.bg, border: `1px solid ${c.border}40`,
            color: c.text, fontSize: 12,
          }}>
            <span style={{ fontWeight: 700 }}>{icon}</span>
            <span>{byColor[key]}</span>
            <span style={{ color: t.textMuted }}>{label}</span>
          </div>
        );
      })}
      <span style={{ color: t.textMuted, fontSize: 12, marginLeft: "auto" }}>
        Total: <strong style={{ color: t.textSub }}>{results.length}</strong> {tr.totalBg}
      </span>
    </div>
  );
}

export function LangToggle({ lang, setLang, t }) {
  const labels = { de: "🇩🇪 DE", en: "🇬🇧 EN", ro: "🇷🇴 RO" };
  return (
    <div style={{ display: "flex", borderRadius: 8, overflow: "hidden", border: `1px solid ${t.border}` }}>
      {["de", "en", "ro"].map(l => (
        <button key={l} onClick={() => setLang(l)} style={{
          padding: "5px 10px", border: "none", cursor: "pointer",
          background: lang === l ? t.tabActive.bg : "transparent",
          color: lang === l ? t.tabActive.color : t.textMuted,
          fontSize: 12, fontWeight: 700, fontFamily: "'IBM Plex Sans'",
          letterSpacing: "0.04em",
        }}>
          {labels[l]}
        </button>
      ))}
    </div>
  );
}
