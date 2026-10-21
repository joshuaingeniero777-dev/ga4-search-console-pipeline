// Everything the panel knows about the API: the shapes it returns and one way to call it.
// Shapes mirror api/schemas.py.

export type RunStatus = "running" | "success" | "failed";

export interface Run {
  id: string;
  started_at: string;
  finished_at: string | null;
  status: RunStatus;
  trigger: "scheduled" | "manual";
  start_date: string;
  end_date: string;
  rows_written: number | null;
  message: string;
  triggered_by: string;
}

export type StatusState = "ok" | "failed" | "running" | "never_run" | "settings_invalid";

export interface Status {
  state: StatusState;
  message: string;
  warnings: string[];
  last_run: Run | null;
  next_run_at: string;
}

export interface Settings {
  metrics: { ga4: string[]; search_console: string[] };
  alert_thresholds: Record<string, { drop_pct: number }>;
  alert_recipients: string[];
}

export interface MetricOption {
  name: string;
  label: string;
}

export interface SettingsOptions {
  ga4: MetricOption[];
  search_console: MetricOption[];
  max_recipients: number;
  min_drop_pct: number;
  max_drop_pct: number;
}

export interface SettingsResponse {
  settings: Settings | null;
  problem: string | null;
  version: string | null;
  updated_by: string | null;
  warnings: string[];
  options: SettingsOptions;
}

export const SERVER_DOWN =
  "The pipeline server isn't responding right now. Please try again in a minute.";
export const NO_CONNECTION =
  "Can't reach the control panel's server. Check your internet connection and try again.";

/** A failed call. `message` is always plain English, ready to show. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

/** Call the API (through the panel's /backend forwarding) and return its JSON. Throws ApiError. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/backend${path}`, {
      ...init,
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  } catch {
    throw new ApiError(0, NO_CONNECTION);
  }

  if (!response.ok) {
    // The API explains every error in {"detail": "..."}. Anything else means it didn't answer.
    let detail: unknown;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail = undefined;
    }
    throw new ApiError(response.status, typeof detail === "string" && detail ? detail : SERVER_DOWN);
  }
  return response.json() as Promise<T>;
}
