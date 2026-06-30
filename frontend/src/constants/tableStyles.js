// AOI Tool - Shared table style layer
// Central place for the inspection-table look so row components stay small.
// makeTableStyles(theme, dense) returns reusable style fragments + helpers,
// all derived from the active theme tokens (themes.js).

// Convert "#rrggbb" / "#rgb" to "rgba(...)". Non-hex input is returned as-is.
export function withAlpha(hex, a) {
  if (!hex || typeof hex !== "string" || hex[0] !== "#") return hex;
  let h = hex.slice(1);
  if (h.length === 3) h = h.split("").map(c => c + c).join("");
  const n = parseInt(h, 16);
  const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  return `rgba(${r},${g},${b},${a})`;
}

// Fixed side colors (consistent across the app): BOT = orange, TOP = blue.
export const SIDE_COLOR = { BOT: "#f97316", TOP: "#38bdf8" };

export function makeTableStyles(t, dense) {
  const padY = dense ? 6 : 10;
  const padX = dense ? 10 : 12;
  const divider = withAlpha(t.border, 0.5);
  const accent = t.tabActive.color;   // sky (dark) / blue (light) — SMD band accent

  return {
    dense,
    railWidth: 3,
    padX, padY,
    divider,

    wrap:  { overflowX: "auto", borderRadius: 12, border: `1px solid ${t.border}` },
    table: { width: "100%", borderCollapse: "collapse", background: t.bgTable,
             fontFamily: "'IBM Plex Sans'" },

    cell: {
      padding: `${padY}px ${padX}px`,
      verticalAlign: "middle",
      fontSize: dense ? 13 : 14,
      color: t.text,
    },

    // SMD-line section header — clearly marks where a new line's BGs begin.
    smdBand: {
      padding: `${dense ? 5 : 7}px 14px`,
      background: withAlpha(accent, 0.16),
      color: accent,
      fontSize: 12, fontWeight: 800, letterSpacing: "0.12em",
      textTransform: "uppercase",
      borderTop:    `1px solid ${withAlpha(accent, 0.45)}`,
      borderBottom: `1px solid ${withAlpha(accent, 0.45)}`,
      borderLeft:   `4px solid ${accent}`,
    },

    num:  { fontVariantNumeric: "tabular-nums" },
    mono: { fontFamily: "'IBM Plex Mono', monospace" },

    // subtle zebra so adjacent BG groups read apart without row tinting
    zebra(i) { return i % 2 === 1 ? withAlpha(t.textMuted, 0.04) : "transparent"; },

    // severity accent (hex) + full token object for a given row_color
    sevColor(rowColor) { return (t.rowColors[rowColor] || t.rowColors.green).border; },
    sev(rowColor)      { return t.rowColors[rowColor] || t.rowColors.green; },
  };
}
