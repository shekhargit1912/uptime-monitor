// Thin wrapper around the backend API. All paths are relative to /api so the
// same code works behind the nginx reverse proxy and the Vite dev proxy.
const BASE = "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // response had no JSON body; keep statusText
    }
    throw new Error(detail);
  }
  // 204 No Content has no body to parse.
  return res.status === 204 ? null : res.json();
}

export const listMonitors = () => request("/monitors");

export const addMonitor = (url, name) =>
  request("/monitors", {
    method: "POST",
    body: JSON.stringify({ url, name: name || null }),
  });

export const deleteMonitor = (id) =>
  request(`/monitors/${id}`, { method: "DELETE" });
