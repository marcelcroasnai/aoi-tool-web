// AOI Tool - Inspection Table — Direction A (calm table + severity rail)
import { useState } from "react";
import { SummaryBar, Spinner, Th, SmdBand, DensityToggle } from "./shared.jsx";
import { BaugrupeRow } from "./BaugrupeRow.jsx";
import { makeTableStyles } from "../constants/tableStyles.js";

const COL_COUNT = 5;

export function InspectionTable({
  currentData, loading, error, inspMode,
  t, tr, onOpenViewer,
}) {
  const [filterColor, setFilterColor] = useState("all");
  const [expandAllBg, setExpandAllBg] = useState(false);
  const [expandAllPp, setExpandAllPp] = useState(false);
  const [search,      setSearch]      = useState("");
  const [dense,       setDense]       = useState(false);

  const styles = makeTableStyles(t, dense);

  const seen = new Set();
  const filteredData = currentData?.filter(bg => {
    if (seen.has(bg.name)) return false;
    seen.add(bg.name);
    const matchColor  = filterColor === "all" || bg.row_color === filterColor;
    const matchSearch = !search || bg.name.includes(search) ||
      (bg.pp_list_detail || []).some(pp =>
        pp.name?.toLowerCase().includes(search.toLowerCase())
      );
    return matchColor && matchSearch;
  });

  const filterLabels = [
    ["all",    tr.filterAll],
    ["red",    tr.filterError],
    ["orange", tr.filterWarning],
    ["yellow", tr.filterInfo],
    ["green",  tr.filterOk],
  ];

  if (loading) return <Spinner t={t} tr={tr} />;

  if (error) return (
    <div style={{
      padding: "10px 16px", borderRadius: 8, marginBottom: 16,
      background: t.errorBanner.bg, border: `1px solid ${t.errorBanner.border}`,
      color: t.errorBanner.color, fontSize: 14,
    }}>⚠ {error}</div>
  );

  if (!filteredData) return (
    <div style={{ textAlign: "center", padding: 80, color: t.textMuted }}>
      <div style={{ fontSize: 40, marginBottom: 12 }}>🔍</div>
      <div style={{ fontSize: 15, fontFamily: "'IBM Plex Sans'" }}>
        <strong style={{ color: t.tabActive.color }}>▶ {tr.btnInspect}</strong>
        {" — "}
        {inspMode === "ap" ? tr.emptyAp : inspMode === "vb" ? tr.emptyVb : tr.textInputLabel}
      </div>
    </div>
  );

  return (
    <>
      {/* Summary bar */}
      <div style={{ marginBottom: 12 }}>
        <SummaryBar results={currentData} t={t} tr={tr} />
      </div>

      {/* Toolbar */}
      <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder={tr.searchPlaceholder}
          style={{
            padding: "7px 14px", borderRadius: 8,
            border: `1px solid ${t.borderInput}`,
            background: t.bgInput, color: t.text,
            fontFamily: "'IBM Plex Mono'", fontSize: 13,
            outline: "none", width: 260,
          }}
        />

        <div style={{ width: 1, height: 28, background: t.border, margin: "0 2px" }} />

        {filterLabels.map(([color, label]) => {
          const c      = t.rowColors[color] || { border: t.border, text: t.textMuted, bg: "transparent" };
          const active = filterColor === color;
          const count  = color !== "all" && currentData
            ? currentData.filter(r => r.row_color === color).length : null;
          return (
            <button key={color} onClick={() => setFilterColor(color)} style={{
              padding: "6px 14px", borderRadius: 20,
              border: `1px solid ${active ? c.border : t.border}`,
              background: active ? c.bg : "transparent",
              color: active ? c.text : t.textMuted,
              fontSize: 12, fontWeight: 600, cursor: "pointer",
              fontFamily: "'IBM Plex Sans'",
              display: "flex", alignItems: "center", gap: 5,
              transition: "all 0.15s",
            }}>
              {label}
              {count !== null && <span style={{ opacity: 0.7 }}>{count}</span>}
            </button>
          );
        })}

        <div style={{ width: 1, height: 28, background: t.border, margin: "0 2px" }} />

        {/* Expand BG */}
        <button
          onClick={() => { setExpandAllBg(v => !v); if (expandAllBg) setExpandAllPp(false); }}
          style={{
            padding: "6px 14px", borderRadius: 20, cursor: "pointer",
            border: `1px solid ${expandAllBg ? t.tabActive.color : t.border}`,
            background: expandAllBg ? t.tabActive.bg : "transparent",
            color: expandAllBg ? t.tabActive.color : t.textMuted,
            fontSize: 12, fontWeight: 600, fontFamily: "'IBM Plex Sans'",
            display: "flex", alignItems: "center", gap: 5, transition: "all 0.15s",
          }}
        >
          {expandAllBg ? "▼" : "▶"} {tr.expandBg}
        </button>

        {/* Expand PP */}
        <button
          onClick={() => {
            const next = !expandAllPp;
            setExpandAllPp(next);
            setExpandAllBg(next ? true : false);
          }}
          style={{
            padding: "6px 14px", borderRadius: 20, cursor: "pointer",
            border: `1px solid ${expandAllPp ? "#a78bfa" : t.border}`,
            background: expandAllPp ? "#a78bfa20" : "transparent",
            color: expandAllPp ? "#a78bfa" : t.textMuted,
            fontSize: 12, fontWeight: 600, fontFamily: "'IBM Plex Sans'",
            display: "flex", alignItems: "center", gap: 5, transition: "all 0.15s",
          }}
        >
          {expandAllPp ? "▼▼" : "▶▶"} {tr.expandPp}
        </button>

        <div style={{ marginLeft: "auto" }} />
        <DensityToggle dense={dense} setDense={setDense} t={t} />
      </div>

      {/* Table */}
      <div style={styles.wrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              <Th label={tr.colNr}   width={52}  align="right" t={t} />
              <Th label={tr.colBg}                              t={t} />
              <Th label={tr.colKunde} width={110}              t={t} />
              <Th label="Components"  width={170}              t={t} />
              <Th label="Status"      width={90}  align="right" t={t} />
            </tr>
          </thead>
          <tbody>
            {filteredData.length === 0 ? (
              <tr>
                <td colSpan={COL_COUNT} style={{ textAlign: "center", padding: 40, color: t.textMuted, fontSize: 14 }}>
                  {tr.noResults}
                </td>
              </tr>
            ) : (
              filteredData.flatMap((bg, i) => {
                const prev = filteredData[i - 1];
                const lineChanged = bg.smd_line && (i === 0 || prev?.smd_line !== bg.smd_line);
                const band = lineChanged
                  ? <SmdBand key={`smd-${bg.smd_line}-${i}`} line={bg.smd_line} colSpan={COL_COUNT} styles={styles} />
                  : null;
                // pretty delimitation: a page-colored gap before every group (from the 2nd on)
                const gap = i > 0 ? (
                  <tr key={`gap-${i}`} aria-hidden="true">
                    <td colSpan={COL_COUNT} style={{ padding: 0, height: dense ? 7 : 12, background: t.bg, borderBottom: "none" }} />
                  </tr>
                ) : null;
                return [
                  gap,
                  band,
                  <BaugrupeRow
                    key={bg.name}
                    bg={bg}
                    index={i}
                    t={t} tr={tr}
                    onOpenViewer={onOpenViewer}
                    forceExpandBg={expandAllBg}
                    styles={styles}
                  />,
                ].filter(Boolean);
              })
            )}
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 10, fontSize: 12, color: t.textMuted, textAlign: "right" }}>
        {filteredData.length} {tr.shown} {currentData.length} {tr.totalBg} · {tr.footerHint}
      </div>
    </>
  );
}
