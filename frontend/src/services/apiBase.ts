const DEFAULT_CLOUD_API_BASE_URL =
  "https://agentic-graphic-motion-designer-backend.onrender.com";

const configuredApiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD
    ? DEFAULT_CLOUD_API_BASE_URL
    : "http://127.0.0.1:8000");

let runtimeApiBaseUrl = configuredApiBaseUrl.replace(/\/+$/, "");

export function getApiBaseUrl(): string {
  return runtimeApiBaseUrl;
}

export function setApiBaseUrl(value: string): void {
  runtimeApiBaseUrl = value.replace(/\/+$/, "");
}
