// Pretend API responses for the panel's tests. No test talks to a real server.

import { vi } from "vitest";

import type { Run, SettingsOptions, SettingsResponse, Status } from "@/lib/api";

export function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

type Handler = (url: string, init: RequestInit | undefined) => Response | Promise<Response>;

/** Replace fetch for this test. Returns the mock so calls can be checked. */
export function fakeApi(handler: Handler) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => handler(String(input), init));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export function bodyOf(fetchMock: ReturnType<typeof fakeApi>, call = 0): unknown {
  return JSON.parse(String(fetchMock.mock.calls[call][1]?.body));
}

export function aRun(overrides: Partial<Run> = {}): Run {
  return {
    id: "abc123",
    started_at: "2026-10-21T10:00:00Z", // 6:00 AM New York
    finished_at: "2026-10-21T10:02:00Z",
    status: "success",
    trigger: "scheduled",
    start_date: "2026-10-14",
    end_date: "2026-10-20",
    rows_written: 14,
    message: "Pulled 14 rows.",
    triggered_by: "scheduler",
    ...overrides,
  };
}

export function aStatus(overrides: Partial<Status> = {}): Status {
  return {
    state: "ok",
    message: "The last run (Wed 21 Oct, 6:00 AM) worked. Pulled 14 rows.",
    warnings: [],
    last_run: aRun(),
    next_run_at: "2026-10-22T10:00:00Z",
    ...overrides,
  };
}

export const OPTIONS: SettingsOptions = {
  ga4: [
    { name: "sessions", label: "Sessions" },
    { name: "totalUsers", label: "Total users" },
  ],
  search_console: [
    { name: "clicks", label: "Clicks" },
    { name: "impressions", label: "Impressions" },
    { name: "ctr", label: "Click-through rate" },
  ],
  alertable: ["sessions", "totalUsers", "clicks", "impressions"],
  max_recipients: 3,
  min_drop_pct: 1,
  max_drop_pct: 100,
};

export function someSettings(overrides: Partial<SettingsResponse> = {}): SettingsResponse {
  return {
    settings: {
      metrics: { ga4: ["sessions"], search_console: ["clicks"] },
      alert_thresholds: { sessions: { drop_pct: 30 } },
      alert_recipients: ["owner@joinswc.org"],
    },
    problem: null,
    version: "2026-10-21T07:27:59.647692+00:00",
    updated_by: "owner@joinswc.org",
    warnings: [],
    options: OPTIONS,
    ...overrides,
  };
}
