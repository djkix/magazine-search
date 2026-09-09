const API_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore body parse errors
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

export function fileUrl(path: string): string {
  return `${API_URL}${path}`;
}

// The middleware only checks that the session cookie is present, not that
// it's still valid (expired, or signed with a rotated JWT_SECRET_KEY) -
// redirecting to /login on a 401 without clearing that cookie leaves it in
// place for the next request, which the middleware waves through straight
// into another 401: an infinite login-page bounce. /logout doesn't require
// a valid session itself, just clears the cookie server-side.
export function redirectToLogin(): void {
  api
    .post("/logout")
    .catch(() => {})
    .finally(() => {
      window.location.href = "/login";
    });
}

export { API_URL };
