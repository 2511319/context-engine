const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8900";

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `Request failed (${resp.status})`);
  }
  return await resp.json();
}

export { API_BASE };
