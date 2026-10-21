import { describe, expect, it } from "vitest";

import { fakeApi, json } from "@/test/fakes";

import { ApiError, NO_CONNECTION, SERVER_DOWN, api } from "./api";
import { formatDate, formatDateTime, formatRange, startedBy, yesterdayInNewYork } from "./format";

describe("api", () => {
  it("calls the panel's /backend forwarding and returns the JSON", async () => {
    const fetchMock = fakeApi(() => json(200, { runs: [] }));

    expect(await api("/runs")).toEqual({ runs: [] });
    expect(fetchMock.mock.calls[0][0]).toBe("/backend/runs");
  });

  it("passes on the API's plain-English explanation", async () => {
    fakeApi(() => json(409, { detail: "A run is already in progress." }));

    await expect(api("/runs", { method: "POST" })).rejects.toEqual(
      new ApiError(409, "A run is already in progress."),
    );
  });

  it("explains when the API doesn't answer properly", async () => {
    fakeApi(() => new Response("<html>Internal Server Error</html>", { status: 500 }));
    await expect(api("/status")).rejects.toThrow(SERVER_DOWN);
  });

  it("explains when there's no connection at all", async () => {
    fakeApi(() => {
      throw new TypeError("Failed to fetch");
    });
    await expect(api("/status")).rejects.toThrow(NO_CONNECTION);
  });
});

describe("format", () => {
  it("shows times in New York", () => {
    expect(formatDateTime("2026-10-21T10:00:00Z")).toBe("Wed, Oct 21, 6:00 AM");
  });

  it("shows calendar dates without shifting them a day", () => {
    expect(formatDate("2026-10-14")).toBe("Oct 14, 2026");
    expect(formatRange("2026-10-14", "2026-10-20")).toBe("Oct 14, 2026 – Oct 20, 2026");
    expect(formatRange("2026-10-14", "2026-10-14")).toBe("Oct 14, 2026");
  });

  it("works out yesterday in New York, not in UTC", () => {
    // 02:00 UTC on the 22nd is still the evening of the 21st in New York.
    expect(yesterdayInNewYork(new Date("2026-10-22T02:00:00Z"))).toBe("2026-10-20");
    expect(yesterdayInNewYork(new Date("2026-03-01T15:00:00Z"))).toBe("2026-02-28");
  });

  it("names the daily schedule instead of a robot account", () => {
    expect(startedBy("scheduled", "scheduler")).toBe("Daily schedule");
    expect(startedBy("manual", "owner@joinswc.org")).toBe("owner@joinswc.org");
  });
});
