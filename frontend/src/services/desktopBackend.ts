import { join, localDataDir } from "@tauri-apps/api/path";
import { getCurrentWindow } from "@tauri-apps/api/window";
import {
  Command,
  type Child,
} from "@tauri-apps/plugin-shell";

import { getApiBaseUrl, setApiBaseUrl } from "./apiBase";

const CONFIGURED_BACKEND_URL = getApiBaseUrl();
const DEFAULT_BACKEND_HOST = "127.0.0.1";
const BACKEND_PORT_CANDIDATES = [8000, 18080, 18081, 18082, 18083];
const BACKEND_SERVICE_NAME = "agentic-graphic-motion-designer";

const BACKEND_MODE = (
  import.meta.env.VITE_BACKEND_MODE ||
  (import.meta.env.PROD ? "cloud" : "local")
).trim().toLowerCase();

let backendChild: Child | null = null;
let startPromise: Promise<void> | null = null;
let lifecycleRegistered = false;
let closeInProgress = false;

function isTauriRuntime(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

function usesLocalBackend(): boolean {
  return BACKEND_MODE !== "cloud";
}

function backendUrl(port: number): string {
  return `http://${DEFAULT_BACKEND_HOST}:${port}`;
}

async function probeBackend(url: string): Promise<boolean> {
  try {
    const response = await fetch(`${url}/health`);
    if (!response.ok) return false;

    const payload = await response.json() as {
      service?: string;
      storage_backend?: string;
    };

    return (
      payload.service === BACKEND_SERVICE_NAME &&
      payload.storage_backend === "sqlite"
    );
  } catch {
    return false;
  }
}

async function waitForBackend(
  url: string,
  attempts = 20,
  delayMs = 500,
): Promise<void> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (await probeBackend(url)) return;

    await new Promise((resolve) =>
      window.setTimeout(resolve, delayMs),
    );
  }

  throw new Error(
    `FastAPI sidecar did not become healthy at ${url}.`,
  );
}

async function stopChildQuietly(child: Child | null): Promise<void> {
  if (!child) return;
  try {
    await child.kill();
  } catch {
    // The sidecar may already have exited because its port was unavailable.
  }
}

export async function startDesktopBackend(): Promise<void> {
  if (!isTauriRuntime() || !usesLocalBackend()) {
    if (isTauriRuntime() && !usesLocalBackend()) {
      console.info(
        "[DESKTOP] Cloud backend mode selected; local sidecar disabled.",
      );
    }
    return;
  }

  if (backendChild || startPromise) {
    return startPromise ?? Promise.resolve();
  }

  startPromise = (async () => {
    const configuredDirectory =
      import.meta.env.VITE_BACKEND_CONFIG_DIR?.trim();
    const configDirectory =
      configuredDirectory ||
      await join(await localDataDir(), "AgenticGraphicMotionDesigner");

    let lastError: unknown = null;

    for (const port of BACKEND_PORT_CANDIDATES) {
      const url = backendUrl(port);

      // Reuse a healthy local sidecar if a previous app instance survived a
      // UI crash. This also avoids treating a stale process as a failure.
      if (await probeBackend(url)) {
        setApiBaseUrl(url);
        console.info(`[DESKTOP] Reusing healthy backend at ${url}.`);
        return;
      }

      const command = Command.sidecar(
        "binaries/agentic-backend-v2",
        [],
        {
          env: {
            AGENTIC_CONFIG_DIR: configDirectory,
            AGENTIC_BACKEND_HOST: DEFAULT_BACKEND_HOST,
            AGENTIC_BACKEND_PORT: String(port),
            STORAGE_BACKEND: "sqlite",
            AGENTIC_DESKTOP_MODE: "1",
          },
        },
      );

      command.stdout.on("data", (line) => {
        console.info("[BACKEND]", line);
      });

      command.stderr.on("data", (line) => {
        console.error("[BACKEND]", line);
      });

      let child: Child | null = null;
      try {
        child = await command.spawn();
        backendChild = child;
        await waitForBackend(url);
        setApiBaseUrl(url);
        console.info(`[DESKTOP] Backend sidecar is healthy at ${url}.`);
        return;
      } catch (error) {
        lastError = error;
        await stopChildQuietly(child);
        backendChild = null;
        console.warn(`[DESKTOP] Backend attempt on port ${port} failed.`, error);
      }
    }

    throw new Error(
      "The local backend could not start. " +
      "Close another Agentic Graphic Motion Designer window and retry. " +
      "See %LOCALAPPDATA%\\AgenticGraphicMotionDesigner\\logs\\backend.log. " +
      (lastError instanceof Error ? lastError.message : "Unknown sidecar error."),
    );
  })().catch((error) => {
    backendChild = null;
    startPromise = null;
    throw error;
  });

  return startPromise;
}

export async function stopDesktopBackend(): Promise<void> {
  const child = backendChild;

  backendChild = null;
  startPromise = null;

  await stopChildQuietly(child);

  if (child) {
    console.info("[DESKTOP] Backend sidecar stopped.");
  }
}

export async function registerDesktopLifecycle(): Promise<void> {
  if (
    !isTauriRuntime() ||
    !usesLocalBackend() ||
    lifecycleRegistered
  ) {
    return;
  }

  lifecycleRegistered = true;

  const currentWindow = getCurrentWindow();

  await currentWindow.onCloseRequested(
    async (event) => {
      if (closeInProgress) return;

      event.preventDefault();
      closeInProgress = true;

      await stopDesktopBackend();

      // The second close request is allowed to pass through.
      await currentWindow.close();
    },
  );
}

export function getConfiguredBackendUrl(): string {
  return CONFIGURED_BACKEND_URL;
}
