const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export async function apiPost(path, body, token) {
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Something went wrong");
  return data;
}
export async function apiGet(path, token) {
  const res = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed");
  return data;
}
