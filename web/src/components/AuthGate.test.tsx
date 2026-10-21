import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { SIGNED_OUT_EVENT, api } from "@/lib/api";
import { fakeApi, json } from "@/test/fakes";

import { AuthGate, SIGN_IN_OUTCOMES } from "./AuthGate";

const PAGE = <p>Secret page content</p>;

afterEach(() => window.history.replaceState(null, "", "/"));

describe("Sign-in gate", () => {
  it("shows the page to someone signed in", async () => {
    fakeApi(() => json(200, { email: "owner@joinswc.org", name: "Owner" }));
    render(<AuthGate>{PAGE}</AuthGate>);

    expect(await screen.findByText("Secret page content")).toBeTruthy();
    expect(screen.getByText(/Signed in as owner@joinswc.org/)).toBeTruthy();
  });

  it("hides the page and offers Google sign-in to everyone else", async () => {
    window.history.replaceState(null, "", "/settings");
    fakeApi(() => json(401, { detail: "Please sign in." }));
    render(<AuthGate>{PAGE}</AuthGate>);

    const link = await screen.findByRole("link", { name: "Sign in with Google" });
    expect(link.getAttribute("href")).toBe("/backend/auth/login?next=%2Fsettings");
    expect(screen.queryByText("Secret page content")).toBeNull();
  });

  it.each(Object.entries(SIGN_IN_OUTCOMES))("explains a sign-in that didn't work (%s)", async (outcome, text) => {
    window.history.replaceState(null, "", `/?signin=${outcome}`);
    fakeApi(() => json(401, { detail: "Please sign in." }));
    render(<AuthGate>{PAGE}</AuthGate>);

    expect((await screen.findByRole("status")).textContent).toBe(text);
    expect(window.location.search).toBe(""); // tidied away so a reload doesn't repeat it
  });

  it("stays locked and says why when sign-in isn't set up", async () => {
    fakeApi(() => json(503, { detail: "Sign-in isn't set up yet, so the control panel is locked." }));
    render(<AuthGate>{PAGE}</AuthGate>);

    expect((await screen.findByRole("alert")).textContent).toContain("Sign-in isn't set up yet");
    expect(screen.queryByText("Secret page content")).toBeNull();
  });

  it("goes back to sign-in when a session runs out mid-visit", async () => {
    fakeApi(() => json(200, { email: "owner@joinswc.org", name: "Owner" }));
    render(<AuthGate>{PAGE}</AuthGate>);
    await screen.findByText("Secret page content");

    act(() => {
      window.dispatchEvent(new Event(SIGNED_OUT_EVENT));
    });

    expect(screen.getByRole("link", { name: "Sign in with Google" })).toBeTruthy();
    expect(screen.queryByText("Secret page content")).toBeNull();
  });

  it("signs out", async () => {
    const fetchMock = fakeApi((url, init) =>
      init?.method === "POST" ? json(200, { signed_out: true }) : json(200, { email: "owner@joinswc.org", name: "" }),
    );
    render(<AuthGate>{PAGE}</AuthGate>);
    await screen.findByText("Secret page content");

    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));

    expect(await screen.findByText("You're signed out.")).toBeTruthy();
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe("/backend/auth/logout");
  });
});

it("any API call that comes back 'not signed in' tells the gate", async () => {
  fakeApi(() => json(401, { detail: "Please sign in." }));
  let told = false;
  window.addEventListener(SIGNED_OUT_EVENT, () => (told = true), { once: true });

  await expect(api("/status")).rejects.toThrow("Please sign in.");
  expect(told).toBe(true);
});
