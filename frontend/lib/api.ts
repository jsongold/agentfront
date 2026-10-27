export const API = "/backend-api/api";

export function authHeaders(): Record<string, string> {
  const token = process.env.NEXT_PUBLIC_ADMIN_TOKEN;
  return token ? { "X-Admin-Token": token } : {};
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }
  for (const [key, value] of Object.entries(authHeaders())) {
    headers.set(key, value);
  }
  const response = await fetch(`${API}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}
