import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SERVER_DOWN } from "@/lib/api";
import { aRun, aStatus, bodyOf, fakeApi, json } from "@/test/fakes";

import { Nav } from "./Nav";
import { RunHistory } from "./RunHistory";
import { RunNowForm } from "./RunNowForm";
import { POLL_MS, StatusView } from "./StatusView";

vi.mock("next/navigation", () => ({ usePathname: () => "/runs" }));

describe("Status page", () => {
  it("shows how things stand, in words", async () => {
    fakeApi(() => json(200, aStatus({ warnings: ["Alert recipients still use the placeholder defaults."] })));
    render(<StatusView />);

    expect(await screen.findByText("Working")).toBeTruthy();
    expect(screen.getByText(/worked\. Pulled 14 rows\./)).toBeTruthy();
    expect(screen.getByText("Alert recipients still use the placeholder defaults.")).toBeTruthy();
    expect(screen.getByText("Thu, Oct 22, 6:00 AM (New York time)")).toBeTruthy();
    expect(screen.getByText(/started by Daily schedule/)).toBeTruthy();
  });

  it("points to Settings when the settings are broken", async () => {
    fakeApi(() => json(200, aStatus({ state: "settings_invalid", message: "The settings have a problem." })));
    render(<StatusView />);

    expect(await screen.findByText("Settings need fixing")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go to Settings to fix it" }).getAttribute("href")).toBe("/settings");
  });

  it("explains when the server can't be reached", async () => {
    fakeApi(() => new Response("", { status: 502 }));
    render(<StatusView />);

    expect((await screen.findByRole("alert")).textContent).toBe(SERVER_DOWN);
  });

  it("checks again on its own, no faster than every 15 seconds", async () => {
    vi.useFakeTimers();
    const fetchMock = fakeApi(() => json(200, aStatus()));
    render(<StatusView />);

    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(POLL_MS - 1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(POLL_MS).toBeGreaterThanOrEqual(15_000);
  });
});

describe("Run history page", () => {
  it("lists runs with their outcome", async () => {
    fakeApi(() =>
      json(200, {
        runs: [
          aRun({ id: "b", status: "failed", trigger: "manual", triggered_by: "owner@joinswc.org",
                 rows_written: null, message: "Google said no (403)." }),
          aRun({ id: "a" }),
        ],
      }),
    );
    render(<RunHistory />);

    const rows = await screen.findAllByRole("row");
    expect(rows).toHaveLength(3); // header + 2 runs
    expect(rows[1].textContent).toContain("Failed");
    expect(rows[1].textContent).toContain("owner@joinswc.org");
    expect(rows[1].textContent).toContain("—");
    expect(rows[2].textContent).toContain("Worked");
    expect(rows[2].textContent).toContain("Daily schedule");
  });

  it("says so when there are no runs yet", async () => {
    fakeApi(() => json(200, { runs: [] }));
    render(<RunHistory />);
    expect(await screen.findByText(/No runs yet/)).toBeTruthy();
  });
});

describe("Run now page", () => {
  it("runs the usual last 7 days by default", async () => {
    const fetchMock = fakeApi(() => json(202, { run: aRun({ status: "running" }) }));
    render(<RunNowForm />);

    await userEvent.click(screen.getByRole("button", { name: "Start the run" }));

    expect(await screen.findByRole("status")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("Run started for Oct 14, 2026 – Oct 20, 2026");
    expect(fetchMock.mock.calls[0][0]).toBe("/backend/runs");
    expect(bodyOf(fetchMock)).toEqual({});
  });

  it("sends the chosen days", async () => {
    const fetchMock = fakeApi(() => json(202, { run: aRun({ start_date: "2026-09-01", end_date: "2026-09-30" }) }));
    render(<RunNowForm />);

    await userEvent.click(screen.getByLabelText(/Choose the days/));
    await userEvent.type(screen.getByLabelText("First day"), "2026-09-01");
    await userEvent.type(screen.getByLabelText("Last day"), "2026-09-30");
    await userEvent.click(screen.getByRole("button", { name: "Start the run" }));

    await screen.findByRole("status");
    expect(bodyOf(fetchMock)).toEqual({ start_date: "2026-09-01", end_date: "2026-09-30" });
  });

  it("catches dates the wrong way round before sending", async () => {
    const fetchMock = fakeApi(() => json(202, {}));
    render(<RunNowForm />);

    await userEvent.click(screen.getByLabelText(/Choose the days/));
    await userEvent.type(screen.getByLabelText("First day"), "2026-09-30");
    await userEvent.type(screen.getByLabelText("Last day"), "2026-09-01");
    await userEvent.click(screen.getByRole("button", { name: "Start the run" }));

    expect(screen.getByRole("alert").textContent).toBe("The start date is after the end date.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the API's reason when a run can't start", async () => {
    fakeApi(() => json(409, { detail: "A run is already in progress. Wait for it to finish, then try again." }));
    render(<RunNowForm />);

    await userEvent.click(screen.getByRole("button", { name: "Start the run" }));

    expect((await screen.findByRole("alert")).textContent).toContain("A run is already in progress.");
  });
});

describe("Navigation", () => {
  it("marks the page you're on", () => {
    render(<Nav />);
    expect(screen.getByRole("link", { name: "Run history" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Status" }).getAttribute("aria-current")).toBeNull();
  });
});

it("never calls anything but the panel's own /backend paths", async () => {
  const fetchMock = fakeApi(() => json(200, aStatus()));
  render(<StatusView />);
  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  for (const [url] of fetchMock.mock.calls) expect(String(url).startsWith("/backend/")).toBe(true);
});
