export interface AuthUser {
  id: string;
  email: string;
  display_name: string;
  status: string;
  roles: string[];
  must_change_password: boolean;
  created_at: string;
  last_login_at: string | null;
}

interface AuthTokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

import { getApiBaseUrl } from "./apiBase";

const ACCESS_TOKEN_KEY = "agentic.auth.access_token";
const REFRESH_TOKEN_KEY = "agentic.auth.refresh_token";
const USER_KEY = "agentic.auth.user";

let accessToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);
let refreshToken = sessionStorage.getItem(REFRESH_TOKEN_KEY);
let refreshInFlight: Promise<boolean> | null = null;

export function getAuthHeaders(): HeadersInit {
  return accessToken
    ? { Authorization: `Bearer ${accessToken}` }
    : {};
}

export async function login(
  email: string,
  password: string,
): Promise<AuthUser> {
  const response = await fetch(`${getApiBaseUrl()}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password, device_label: "desktop-web" }),
  });
  const payload = await readJson(response);
  if (!response.ok) {
    throw new Error(String(payload.detail || "Login failed."));
  }
  const tokens = payload as unknown as AuthTokenResponse;
  storeSession(tokens);
  return tokens.user;
}

export async function restoreSession(): Promise<AuthUser | null> {
  if (!accessToken && !refreshToken) {
    return null;
  }

  try {
    const response = await authorizedFetch(`${getApiBaseUrl()}/api/auth/me`);
    if (!response.ok) {
      clearSession();
      return null;
    }
    const user = (await response.json()) as AuthUser;
    sessionStorage.setItem(USER_KEY, JSON.stringify(user));
    return user;
  } catch {
    clearSession();
    return null;
  }
}

export async function logout(): Promise<void> {
  if (refreshToken) {
    await fetch(`${getApiBaseUrl()}/api/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => undefined);
  }
  clearSession();
}

export async function authorizedFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
  retry = true,
): Promise<Response> {
  const response = await fetchWithCurrentToken(input, init);

  if (response.status === 401 && retry && refreshToken) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      // Retry the original request explicitly with the newly issued token.
      // Do not recurse here: a Request body may only be consumed once, and
      // recursion also made refresh/retry failures look like network errors.
      return fetchWithCurrentToken(input, init);
    }
  }

  return response;
}

async function fetchWithCurrentToken(
  input: RequestInfo | URL,
  init: RequestInit,
): Promise<Response> {
  const headers = new Headers(init.headers);
  const authHeaders = getAuthHeaders();
  Object.entries(authHeaders).forEach(([name, value]) => {
    if (value) headers.set(name, String(value));
  });

  return fetch(input, {
    ...init,
    headers,
    credentials: "include",
  });
}

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshToken) return false;
  if (refreshInFlight) return refreshInFlight;

  const tokenBeingRefreshed = refreshToken;
  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${getApiBaseUrl()}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          refresh_token: tokenBeingRefreshed,
          device_label: "desktop-web",
        }),
      });
      const payload = await readJson(response);
      if (!response.ok || !isAuthTokenResponse(payload)) {
        clearSession();
        return false;
      }
      storeSession(payload as unknown as AuthTokenResponse);
      return true;
    } catch (error) {
      console.error("[FRONTEND AUTH] Token refresh failed:", error);
      clearSession();
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

function isAuthTokenResponse(
  payload: Record<string, unknown>,
): boolean {
  return (
    typeof payload.access_token === "string" &&
    payload.access_token.length > 0 &&
    typeof payload.refresh_token === "string" &&
    payload.refresh_token.length > 0 &&
    typeof payload.user === "object" &&
    payload.user !== null
  );
}

function storeSession(payload: AuthTokenResponse): void {
  accessToken = payload.access_token;
  refreshToken = payload.refresh_token;
  sessionStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  sessionStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(payload.user));
}

function clearSession(): void {
  accessToken = null;
  refreshToken = null;
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

async function readJson(response: Response): Promise<Record<string, unknown>> {
  try {
    return (await response.json()) as Record<string, unknown>;
  } catch {
    return {};
  }
}
