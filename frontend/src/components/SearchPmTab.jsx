// AOI Tool - Search PM Tab
// Results grouped by PM name: each PM shows CLI + expandable PP list
import { useState, useEffect } from "react";
import { fetchCliList, fetchSearchPm } from "../api.js";

// ─── PM result group ──────────────────────────────────────────────────────────
function PmGroup({ pmName, cli, ppList, t }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      borderRadius: 8, border: `1px solid ${t.border}`,
      overflow: "hidden", marginBottom: 6,
    }}>
      {/* Header row */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "8px 14px", cursor: "pointer",
          background: t.bgHeader,
          borderBottom: open ? `1px solid ${t.border}` : "none",
        }}
      >
        {/* PM name */}
        <span style={{
          fontFamily: "monospace", fontWeight: 700, fontSize: 13,
          color: t.text, flex: 1,
        }}>
          {pmName}
        </span>

        {/* CLI badge */}
        <span style={{
          fontFamily: "monospace", fontSize: 11, color: t.textMuted,
          background: t.bgInput, border: `1px solid ${t.border}`,
          borderRadius: 6, padding: "1px 8px",
        }}>
          {cli || "—"}
        </span>

        {/* PP count badge */}
        <span style={{
          fontSize: 11, fontWeight: 700,
          background: "#1e3a5f", color: "#7dd3fc",
          borderRadius: 10, padding: "1px 8px",
        }}>
          {ppList.length} PP
        </span>

        {/* Chevron */}
        <span style={{ color: t.textMuted, fontSize: 11 }}>
          {open ? "▲" : "▼"}
        </span>
      </div>

      {/* PP list */}
      {open && (
        <div style={{ padding: "8px 14px", background: t.bgTable }}>
          {ppList.map(pp => (
            <div key={pp} style={{
              fontFamily: "monospace", fontSize: 12,
              color: t.textSub, padding: "3px 0",
              borderBottom: `1px solid ${t.border}20`,
            }}>
              {pp}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export function SearchPmTab({ t, tr }) {
  const [query,      setQuery]      = useState("");
  const [searchType, setSearchType] = useState("contains");
  const [cli,        setCli]        = useState("all");
  const [cliList,    setCliList]    = useState([]);
  const [results,    setResults]    = useState(null);
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState(null);

  // Load CLI list on mount
  useEffect(() => {
    fetchCliList()
      .then(d => setCliList(d.cli_list || []))
      .catch(() => {});
  }, []);

  const runSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      setResults(await fetchSearchPm(query, searchType, cli));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const searchTypeOptions = [
    ["contains",    tr.stContains],
    ["exact",       tr.stExact],
    ["starts_with", tr.stStarts],
    ["ends_with",   tr.stEnds],
  ];

  // Group results by (PM name + CLI) combination
  const pmGroups = results
    ? Object.values(
        results.results.reduce((acc, r) => {
          const key = `${r.pm}||${r.cli}`;
          if (!acc[key]) {
            acc[key] = { pmName: r.pm, cli: r.cli, ppList: [] };
          }
          acc[key].ppList.push(r.pp);
          return acc;
        }, {})
      ).sort((a, b) => a.pmName.localeCompare(b.pmName) || a.cli.localeCompare(b.cli))
    : [];

  const inputStyle = {
    width: "100%", padding: "8px 12px", borderRadius: 8,
    border: `1px solid ${t.borderInput}`,
    background: t.bgInput, color: t.text, outline: "none",
  };

  return (
    <div style={{ maxWidth: 1700, margin: "0 auto", padding: "20px 24px" }}>

      {/* Search bar */}
      <div style={{
        display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end",
        padding: "16px 20px", borderRadius: 12,
        background: t.bgHeader, border: `1px solid ${t.border}`,
        marginBottom: 20,
      }}>

        {/* Query input */}
        <div style={{ flex: "1 1 220px" }}>
          <label style={{
            display: "block", fontSize: 10, color: t.textMuted,
            marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.08em",
          }}>
            {tr.searchPmInput.replace("...", "")}
          </label>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && runSearch()}
            placeholder={tr.searchPmInput}
            autoFocus
            style={{ ...inputStyle, fontFamily: "'IBM Plex Mono'", fontSize: 13 }}
          />
        </div>

        {/* Search type */}
        <div style={{ flex: "0 0 160px" }}>
          <label style={{
            display: "block", fontSize: 10, color: t.textMuted,
            marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.08em",
          }}>
            {tr.searchPmType}
          </label>
          <select
            value={searchType}
            onChange={e => setSearchType(e.target.value)}
            style={{ ...inputStyle, fontSize: 12 }}
          >
            {searchTypeOptions.map(([val, label]) => (
              <option key={val} value={val}>{label}</option>
            ))}
          </select>
        </div>

        {/* CLI filter */}
        <div style={{ flex: "0 0 220px" }}>
          <label style={{
            display: "block", fontSize: 10, color: t.textMuted,
            marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.08em",
          }}>
            {tr.searchPmCli}
          </label>
          <select
            value={cli}
            onChange={e => setCli(e.target.value)}
            style={{ ...inputStyle, fontFamily: "'IBM Plex Mono'", fontSize: 12 }}
          >
            <option value="all">{tr.searchPmAll}</option>
            {cliList.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>

        {/* Search button */}
        <button
          onClick={runSearch}
          disabled={loading || !query.trim()}
          style={{
            padding: "8px 24px", borderRadius: 8, border: "none", height: 38,
            background: (!loading && query.trim())
              ? "linear-gradient(135deg,#0ea5e9,#6366f1)"
              : t.border,
            color: (!loading && query.trim()) ? "#fff" : t.textMuted,
            fontFamily: "'IBM Plex Sans'", fontSize: 13, fontWeight: 700,
            cursor: (!loading && query.trim()) ? "pointer" : "not-allowed",
            display: "flex", alignItems: "center", gap: 6, alignSelf: "flex-end",
          }}
        >
          {loading
            ? <><span style={{ animation: "spin 0.8s linear infinite", display: "inline-block" }}>⟳</span> {tr.searchPmBtn}</>
            : <>🔍 {tr.searchPmBtn}</>
          }
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          padding: "10px 16px", borderRadius: 8, marginBottom: 16,
          background: t.errorBanner?.bg || "#2d1a1a",
          border: `1px solid ${t.errorBanner?.border || "#ef4444"}`,
          color: t.errorBanner?.color || "#fca5a5", fontSize: 13,
        }}>
          ⚠ {error}
        </div>
      )}

      {/* Results summary */}
      {results && (
        <>
          <div style={{
            display: "flex", alignItems: "center", gap: 12,
            marginBottom: 14, fontSize: 12, color: t.textMuted,
          }}>
            <span style={{
              padding: "3px 12px", borderRadius: 20, fontSize: 12, fontWeight: 700,
              background: results.count > 0 ? "#1e3a5f" : t.border,
              color: results.count > 0 ? "#7dd3fc" : t.textMuted,
            }}>
              {pmGroups.length} PM/CLI · {results.count} {tr.searchPmResults}
            </span>
            <span>
              PM: <strong style={{ color: t.text, fontFamily: "monospace" }}>
                {results.query}
              </strong>
            </span>
            <span>·</span>
            <span>{searchTypeOptions.find(([v]) => v === results.search_type)?.[1]}</span>
            {results.cli_filter !== "all" && (
              <>
                <span>·</span>
                <span style={{ fontFamily: "monospace" }}>{results.cli_filter}</span>
              </>
            )}
          </div>

          {/* PM groups */}
          {pmGroups.length === 0 ? (
            <div style={{ textAlign: "center", padding: 60, color: t.textMuted }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>🔍</div>
              <div>{tr.searchPmNone}</div>
            </div>
          ) : (
            pmGroups.map(({ pmName, cli: pmCli, ppList }) => (
              <PmGroup
                key={`${pmName}||${pmCli}`}
                pmName={pmName}
                cli={pmCli}
                ppList={ppList}
                t={t}
              />
            ))
          )}
        </>
      )}
    </div>
  );
}
