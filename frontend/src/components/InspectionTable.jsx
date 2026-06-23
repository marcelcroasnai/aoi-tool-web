// AOI Tool - Inspection Table
import { useState } from "react";
import { SummaryBar, Spinner, Th } from "./shared.jsx";
import { BaugrupeRow } from "./BaugrupeRow.jsx";

export function InspectionTable({
  currentData, loading, error, inspMode,
  t, tr, onOpenViewer,
}) {
  const [filterColor, setFilterColor] = useState("all");
  const [expandAllBg, setExpandAllBg] = useState(false);
  const [expandAllPp, setExpandAllPp] = useState(false);
  const [search,      setSearch]      = useState("");

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
      </div>

      {/* Table */}
      <div style={{ overflowX: "auto", borderRadius: 10, border: `1px solid ${t.border}` }}>
        <table style={{ width: "100%", borderCollapse: "collapse", background: t.bgTable }}>
          <thead>
            <tr>
              <Th label={tr.colNr}          width={52}  t={t} />
              <Th label={tr.colSmdLine}     width={100} t={t} />
              <Th label={tr.colBg}          width={220} t={t} />
              <Th label={tr.colKunde}       width={120} t={t} />
              <Th label="Project"           width={160} t={t} />
              <Th label="Components (I | C)"    width={180} t={t} />
              <Th label={tr.colFlags}       width={110} t={t} />
              <Th label="Info"              width={140} t={t} />
            </tr>
          </thead>
          <tbody>
            {filteredData.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 40, color: t.textMuted, fontSize: 14 }}>
                  {tr.noResults}
                </td>
              </tr>
            ) : (
              filteredData.flatMap((bg, i) => {
                const prev = filteredData[i - 1];
                const lineChanged = i > 0 && bg.smd_line && prev.smd_line !== bg.smd_line;
                const spacer = lineChanged ? (
                  <tr key={`spacer-${i}`}>
                    <td colSpan={8} style={{ height: 12, background: "transparent", borderBottom: `1px solid ${t.border}20` }} />
                  </tr>
                ) : null;
                return [
                  spacer,
                  <BaugrupeRow
                    key={bg.name}
                    bg={bg}
                    index={i}
                    inspType={inspMode}
                    t={t} tr={tr}
                    onOpenViewer={onOpenViewer}
                    forceExpandBg={expandAllBg}
                    forceExpandPp={expandAllPp}
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
