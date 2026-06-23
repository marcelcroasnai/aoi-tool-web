// AOI Tool - Ideas Panel
// Slide-in panel from right: add new ideas + view existing list
import { useState, useEffect, useCallback } from "react";
import { API_BASE } from "../api.js";

export function IdeasPanel({ t, tr, onClose }) {
  const [ideas,     setIdeas]     = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [saving,    setSaving]    = useState(false);
  const [error,     setError]     = useState(null);
  const [saveOk,    setSaveOk]    = useState(false);

  // Form state
  const [user,       setUser]       = useState("");
  const [shortDesc,  setShortDesc]  = useState("");
  const [longDesc,   setLongDesc]   = useState("");
  const [formError,  setFormError]  = useState(null);

  useEffect(() => {
    const h = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const fetchIdeas = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/ideas`);
      const d   = await res.json();
      setIdeas(d.ideas || []);
    } catch (e) {
      setError("Could not load ideas.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchIdeas(); }, [fetchIdeas]);

  const handleSubmit = async () => {
    if (!user.trim())       { setFormError("User name is required."); return; }
    if (!shortDesc.trim())  { setFormError("Short description is required."); return; }
    setFormError(null);
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/ideas`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user, short_desc: shortDesc, long_desc: longDesc }),
      });
      if (!res.ok) throw new Error("Save failed");
      setUser(""); setShortDesc(""); setLongDesc("");
      setSaveOk(true);
      setTimeout(() => setSaveOk(false), 2500);
      await fetchIdeas();
    } catch (e) {
      setFormError("Could not save idea. Try again.");
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = {
    width: "100%", padding: "8px 12px", borderRadius: 8,
    border: `1px solid ${t.borderInput}`,
    background: t.bgInput, color: t.text,
    fontFamily: "'IBM Plex Sans'", fontSize: 13,
    outline: "none", boxSizing: "border-box",
  };

  const labelStyle = {
    display: "block", fontSize: 10, fontWeight: 700,
    letterSpacing: "0.08em", color: t.textMuted,
    textTransform: "uppercase", marginBottom: 5,
  };

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose} style={{
        position: "fixed", inset: 0, zIndex: 900,
        background: "rgba(0,0,0,0.45)",
        animation: "fadeIn 0.2s ease",
      }} />

      {/* Panel */}
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0,
        width: 560, zIndex: 901,
        background: t.bgHeader,
        borderLeft: `2px solid ${t.border}`,
        display: "flex", flexDirection: "column",
        boxShadow: "-8px 0 32px rgba(0,0,0,0.35)",
        animation: "slideInRight 0.25s ease",
      }}>

        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", gap: 12,
          padding: "14px 20px", borderBottom: `1px solid ${t.border}`,
          flexShrink: 0,
        }}>
          <span style={{ fontSize: 20 }}>💡</span>
          <span style={{ fontFamily: "'IBM Plex Sans'", fontWeight: 700, fontSize: 16, color: t.text, flex: 1 }}>
            Improvement Ideas
          </span>
          <button onClick={onClose} style={{
            width: 32, height: 32, borderRadius: 8,
            border: `1px solid ${t.border}`, background: "transparent",
            color: t.textMuted, fontSize: 16, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>✕</button>
        </div>

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px" }}>

          {/* ── Add form ── */}
          <div style={{
            borderRadius: 10, border: `1px solid ${t.border}`,
            padding: "16px 18px", marginBottom: 24,
            background: t.bg,
          }}>
            <div style={{
              fontFamily: "'IBM Plex Sans'", fontWeight: 700, fontSize: 13,
              color: t.tabActive.color, marginBottom: 14,
            }}>+ Add new idea</div>

            {/* User */}
            <div style={{ marginBottom: 12 }}>
              <label style={labelStyle}>Your name</label>
              <input
                value={user}
                onChange={e => { setUser(e.target.value); setFormError(null); }}
                placeholder="John Doe"
                style={inputStyle}
              />
            </div>

            {/* Short description */}
            <div style={{ marginBottom: 12 }}>
              <label style={labelStyle}>Short description</label>
              <input
                value={shortDesc}
                onChange={e => { setShortDesc(e.target.value); setFormError(null); }}
                placeholder="One line summary"
                style={inputStyle}
              />
            </div>

            {/* Long description */}
            <div style={{ marginBottom: 16 }}>
              <label style={labelStyle}>Long description <span style={{ color: t.border }}>(optional)</span></label>
              <textarea
                value={longDesc}
                onChange={e => setLongDesc(e.target.value)}
                placeholder="Detailed explanation, steps to reproduce, expected benefit..."
                rows={4}
                style={{ ...inputStyle, resize: "vertical", lineHeight: 1.6 }}
              />
            </div>

            {/* Error / success */}
            {formError && (
              <div style={{ fontSize: 12, color: "#ef4444", marginBottom: 10 }}>⚠ {formError}</div>
            )}
            {saveOk && (
              <div style={{ fontSize: 12, color: "#22c55e", marginBottom: 10 }}>✓ Idea saved!</div>
            )}

            {/* Submit */}
            <button
              onClick={handleSubmit}
              disabled={saving}
              style={{
                padding: "8px 20px", borderRadius: 8, border: "none",
                background: saving ? t.border : "linear-gradient(135deg,#0ea5e9,#6366f1)",
                color: saving ? t.textMuted : "#fff",
                fontFamily: "'IBM Plex Sans'", fontSize: 13, fontWeight: 600,
                cursor: saving ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", gap: 6,
              }}
            >
              {saving
                ? <><span style={{ animation: "spin 0.8s linear infinite", display: "inline-block" }}>⟳</span> Saving...</>
                : "💾 Save idea"
              }
            </button>
          </div>

          {/* ── Ideas list ── */}
          <div>
            <div style={{
              fontSize: 10, fontWeight: 700, letterSpacing: "0.1em",
              color: t.textMuted, textTransform: "uppercase", marginBottom: 12,
            }}>
              Existing ideas ({ideas.length})
            </div>

            {loading && (
              <div style={{ color: t.textMuted, fontSize: 13, textAlign: "center", padding: 20 }}>
                Loading...
              </div>
            )}

            {!loading && error && (
              <div style={{ color: "#ef4444", fontSize: 13 }}>⚠ {error}</div>
            )}

            {!loading && !error && ideas.length === 0 && (
              <div style={{ color: t.textMuted, fontSize: 13, textAlign: "center", padding: 20 }}>
                No ideas yet. Be the first!
              </div>
            )}

            {!loading && ideas.map((idea) => (
              <div key={idea.id} style={{
                borderRadius: 8, border: `1px solid ${t.border}`,
                padding: "12px 16px", marginBottom: 10,
                background: t.bgTable,
              }}>
                {/* Meta */}
                <div style={{
                  display: "flex", alignItems: "center", gap: 10,
                  marginBottom: 8,
                }}>
                  <span style={{
                    padding: "2px 8px", borderRadius: 10,
                    background: t.tabActive.bg, color: t.tabActive.color,
                    fontSize: 11, fontWeight: 600, fontFamily: "monospace",
                  }}>{idea.user}</span>
                  <span style={{ fontSize: 11, color: t.textMuted, marginLeft: "auto" }}>
                    {idea.added_at}
                  </span>
                </div>

                {/* Short desc */}
                <div style={{
                  fontFamily: "'IBM Plex Sans'", fontWeight: 600,
                  fontSize: 14, color: t.text, marginBottom: 6,
                }}>
                  {idea.short_desc}
                </div>

                {/* Long desc */}
                {idea.long_desc && (
                  <div style={{
                    fontSize: 12, color: t.textSub, lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                  }}>
                    {idea.long_desc}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: "10px 20px", borderTop: `1px solid ${t.border}`,
          fontSize: 10, color: t.textMuted, textAlign: "center", flexShrink: 0,
        }}>
          ESC or click outside to close
        </div>
      </div>

      <style>{`
        @keyframes fadeIn       { from { opacity: 0 }                to { opacity: 1 }            }
        @keyframes slideInRight { from { transform: translateX(100%) } to { transform: translateX(0) } }
      `}</style>
    </>
  );
}
