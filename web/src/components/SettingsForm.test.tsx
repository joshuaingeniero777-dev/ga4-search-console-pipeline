import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { OPTIONS, bodyOf, fakeApi, json, someSettings } from "@/test/fakes";

import { SettingsForm, check, toForm, toSettings } from "./SettingsForm";

function checkbox(name: string) {
  return screen.getByRole("checkbox", { name }) as HTMLInputElement;
}

describe("Settings page", () => {
  it("shows the saved settings", async () => {
    fakeApi(() => json(200, someSettings()));
    render(<SettingsForm />);

    expect((await screen.findByRole("checkbox", { name: "Sessions" }) as HTMLInputElement).checked).toBe(true);
    expect(checkbox("Total users").checked).toBe(false);
    expect(checkbox("Clicks").checked).toBe(true);
    expect((screen.getByLabelText("Sessions alert threshold (%)") as HTMLInputElement).value).toBe("30");
    expect(screen.getByText(/Last changed by owner@joinswc.org on/)).toBeTruthy();
    expect(screen.getByText(/Alerts are posted to the pipeline's Slack channel/)).toBeTruthy();
    expect(screen.queryByLabelText(/Email address/)).toBeNull();
  });

  it("saves changes with the version it loaded", async () => {
    const fetchMock = fakeApi((url, init) =>
      init?.method === "PUT" ? json(200, someSettings({ version: "v2" })) : json(200, someSettings()),
    );
    render(<SettingsForm />);
    await screen.findByRole("checkbox", { name: "Sessions" });

    await userEvent.click(checkbox("Impressions"));
    await userEvent.type(screen.getByLabelText("Impressions alert threshold (%)"), "40");
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));

    expect((await screen.findByRole("status")).textContent).toContain("Saved.");
    expect(bodyOf(fetchMock, 1)).toEqual({
      version: "2026-10-21T07:27:59.647692+00:00",
      settings: {
        metrics: { ga4: ["sessions"], search_console: ["clicks", "impressions"] },
        alert_thresholds: { sessions: { drop_pct: 30 }, impressions: { drop_pct: 40 } },
        alert_recipients: [], // alerts go to Slack; saving clears any old email list
      },
    });
  });

  it("catches mistakes before saving and says what's wrong next to each", async () => {
    const fetchMock = fakeApi(() => json(200, someSettings()));
    render(<SettingsForm />);
    await screen.findByRole("checkbox", { name: "Sessions" });

    await userEvent.click(checkbox("Clicks")); // nothing left from Search Console
    await userEvent.clear(screen.getByLabelText("Sessions alert threshold (%)"));
    await userEvent.type(screen.getByLabelText("Sessions alert threshold (%)"), "150");
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));

    expect(screen.getByText("Choose at least one.")).toBeTruthy();
    expect(screen.getByText(/Enter a whole number from 1 to 100/)).toBeTruthy();
    expect(screen.getByLabelText("Sessions alert threshold (%)").getAttribute("aria-invalid")).toBe("true");
    expect(fetchMock).toHaveBeenCalledTimes(1); // only the initial load
  });

  it("offers a reload when someone else saved first", async () => {
    fakeApi((url, init) =>
      init?.method === "PUT"
        ? json(409, { detail: "Someone else changed the settings. Reload and try again." })
        : json(200, someSettings()),
    );
    render(<SettingsForm />);
    await screen.findByRole("checkbox", { name: "Sessions" });

    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));

    expect((await screen.findByRole("alert")).textContent).toContain("Someone else changed the settings.");
    expect(screen.getByRole("button", { name: /Reload the settings/ })).toBeTruthy();
  });

  it("explains broken saved settings and still lets them be fixed", async () => {
    fakeApi(() => json(200, someSettings({ settings: null, problem: "Alert thresholds > sessions > drop %: Input should be less than or equal to 100" })));
    render(<SettingsForm />);

    expect((await screen.findByRole("alert")).textContent).toContain("Input should be less than or equal to 100");
    expect(checkbox("Sessions").checked).toBe(false);
    expect(screen.getByRole("button", { name: "Save settings" })).toBeTruthy();
  });

  it("shows the placeholder warnings", async () => {
    fakeApi(() => json(200, someSettings({ warnings: ["Metrics still use the placeholder defaults and need to be set."] })));
    render(<SettingsForm />);

    expect(await screen.findByText("Metrics still use the placeholder defaults and need to be set.")).toBeTruthy();
    expect(screen.getByText(/Alerts stay switched off/)).toBeTruthy();
  });
});

describe("settings rules", () => {
  const form = toForm(someSettings().settings);

  it("drops thresholds for metrics that are no longer pulled", () => {
    const settings = toSettings({ ...form, ga4: ["totalUsers"] }, OPTIONS);
    expect(settings.alert_thresholds).toEqual({});
  });

  it("allows an empty threshold box (no alert) but not a fraction", () => {
    expect(check({ ...form, thresholds: { sessions: "" } }, OPTIONS).thresholds).toEqual({});
    expect(check({ ...form, thresholds: { sessions: "2.5" } }, OPTIONS).thresholds.sessions).toBeTruthy();
  });

  it("saving clears any email list left from the old placeholders", () => {
    expect(toSettings(form, OPTIONS).alert_recipients).toEqual([]);
  });
});

it("says when an alert level won't be used (rates aren't checked yet)", async () => {
  fakeApi(() =>
    json(200, someSettings({
      settings: {
        metrics: { ga4: ["sessions"], search_console: ["clicks", "ctr"] },
        alert_thresholds: { ctr: { drop_pct: 10 } },
        alert_recipients: ["owner@joinswc.org"],
      },
    })),
  );
  render(<SettingsForm />);

  const rate = await screen.findByLabelText("Click-through rate alert threshold (%)");
  expect(document.getElementById(rate.getAttribute("aria-describedby") ?? "")?.textContent).toContain("Not used yet");
  const count = screen.getByLabelText("Clicks alert threshold (%)");
  expect(count.getAttribute("aria-describedby")).toBeNull();
});
