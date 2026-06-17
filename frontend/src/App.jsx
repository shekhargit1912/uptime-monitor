import { useEffect, useState } from "react";
import { addMonitor, deleteMonitor, listMonitors } from "./api.js";

const POLL_MS = 5000;

function StatusBadge({ check }) {
  if (!check) {
    return <span style={{ ...badge, background: "#9ca3af" }}>PENDING</span>;
  }
  const up = check.is_up;
  return (
    <span style={{ ...badge, background: up ? "#16a34a" : "#dc2626" }}>
      {up ? "UP" : "DOWN"}
    </span>
  );
}

function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString();
}

export default function App() {
  const [monitors, setMonitors] = useState([]);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    try {
      setMonitors(await listMonitors());
    } catch (err) {
      setError(`Failed to load monitors: ${err.message}`);
    }
  }

  // Poll the API every few seconds so the dashboard reflects live state.
  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, []);

  async function handleAdd(e) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await addMonitor(url.trim());
      setUrl("");
      await refresh();
    } catch (err) {
      setError(`Could not add URL: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id) {
    try {
      await deleteMonitor(id);
      await refresh();
    } catch (err) {
      setError(`Could not delete: ${err.message}`);
    }
  }

  return (
    <div style={page}>
      <h1 style={{ marginBottom: 4 }}>⏱️ Uptime Monitor</h1>
      <p style={{ color: "#6b7280", marginTop: 0 }}>
        Auto-refreshing every {POLL_MS / 1000}s.
      </p>

      <form onSubmit={handleAdd} style={form}>
        <input
          type="url"
          required
          placeholder="https://example.com"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          style={input}
        />
        <button type="submit" disabled={submitting} style={button}>
          {submitting ? "Adding…" : "Add URL"}
        </button>
      </form>

      {error && <div style={errorBox}>{error}</div>}

      <table style={table}>
        <thead>
          <tr>
            <th style={th}>Status</th>
            <th style={th}>URL</th>
            <th style={th}>HTTP</th>
            <th style={th}>Response</th>
            <th style={th}>Last checked</th>
            <th style={th}></th>
          </tr>
        </thead>
        <tbody>
          {monitors.length === 0 && (
            <tr>
              <td style={td} colSpan={6}>
                No monitors yet — add a URL above.
              </td>
            </tr>
          )}
          {monitors.map((m) => {
            const c = m.latest_check;
            return (
              <tr key={m.id}>
                <td style={td}>
                  <StatusBadge check={c} />
                </td>
                <td style={td}>
                  <a href={m.url} target="_blank" rel="noreferrer">
                    {m.url}
                  </a>
                  {c?.error && (
                    <div style={{ color: "#dc2626", fontSize: 12 }}>{c.error}</div>
                  )}
                </td>
                <td style={td}>{c?.status_code ?? "—"}</td>
                <td style={td}>
                  {c?.response_time_ms != null ? `${c.response_time_ms} ms` : "—"}
                </td>
                <td style={td}>{formatTime(c?.checked_at)}</td>
                <td style={td}>
                  <button onClick={() => handleDelete(m.id)} style={deleteBtn}>
                    Delete
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const page = {
  maxWidth: 900,
  margin: "40px auto",
  padding: "0 16px",
  fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
  color: "#111827",
};
const form = { display: "flex", gap: 8, margin: "16px 0" };
const input = {
  flex: 1,
  padding: "8px 12px",
  border: "1px solid #d1d5db",
  borderRadius: 6,
  fontSize: 14,
};
const button = {
  padding: "8px 16px",
  border: "none",
  borderRadius: 6,
  background: "#2563eb",
  color: "white",
  fontSize: 14,
  cursor: "pointer",
};
const deleteBtn = {
  padding: "4px 10px",
  border: "1px solid #d1d5db",
  borderRadius: 6,
  background: "white",
  cursor: "pointer",
  fontSize: 13,
};
const badge = {
  display: "inline-block",
  padding: "2px 10px",
  borderRadius: 999,
  color: "white",
  fontSize: 12,
  fontWeight: 700,
};
const table = { width: "100%", borderCollapse: "collapse", marginTop: 8 };
const th = {
  textAlign: "left",
  borderBottom: "2px solid #e5e7eb",
  padding: "8px 10px",
  fontSize: 13,
  color: "#6b7280",
};
const td = {
  borderBottom: "1px solid #f3f4f6",
  padding: "10px",
  fontSize: 14,
  verticalAlign: "top",
};
const errorBox = {
  background: "#fef2f2",
  border: "1px solid #fecaca",
  color: "#991b1b",
  padding: "8px 12px",
  borderRadius: 6,
  marginBottom: 12,
  fontSize: 14,
};
