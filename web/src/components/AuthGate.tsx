"use client";

import { type ReactNode, useCallback, useEffect, useState } from "react";

import { ApiError, SERVER_DOWN, SIGNED_OUT_EVENT, api } from "@/lib/api";

// Why the last sign-in didn't work, as the API reports it in ?signin=... (api/auth.py).
export const SIGN_IN_OUTCOMES: Record<string, string> = {
  not_allowed:
    "That Google account can't use the control panel. Please sign in with your Starr Wellness Collective work account.",
  cancelled: "Sign-in was cancelled.",
  failed: "Sign-in didn't work. Please try again.",
};

type State =
  | { kind: "checking" }
  | { kind: "signed-in"; email: string; name: string }
  | { kind: "signed-out"; note: string | null }
  | { kind: "problem"; message: string };

/** Shows the page only to someone signed in (CLAUDE.md rule 7); otherwise, a way to sign in. */
export function AuthGate({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ kind: "checking" });

  const check = useCallback(async (note: string | null = null) => {
    try {
      const me = await api<{ email: string; name: string }>("/auth/me");
      setState({ kind: "signed-in", email: me.email, name: me.name });
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setState({ kind: "signed-out", note });
      else setState({ kind: "problem", message: e instanceof ApiError ? e.message : SERVER_DOWN });
    }
  }, []);

  useEffect(() => {
    // Coming back from Google with a reason it didn't work? Show it once, then tidy the address bar.
    const params = new URLSearchParams(window.location.search);
    const outcome = params.get("signin");
    if (outcome) {
      params.delete("signin");
      const query = params.toString();
      window.history.replaceState(null, "", window.location.pathname + (query ? `?${query}` : ""));
    }
    const first = setTimeout(() => check(outcome ? (SIGN_IN_OUTCOMES[outcome] ?? null) : null), 0);

    const signedOut = () => setState({ kind: "signed-out", note: "You've been signed out. Please sign in again." });
    window.addEventListener(SIGNED_OUT_EVENT, signedOut);
    return () => {
      clearTimeout(first);
      window.removeEventListener(SIGNED_OUT_EVENT, signedOut);
    };
  }, [check]);

  async function signOut() {
    try {
      await api("/auth/logout", { method: "POST" });
      setState({ kind: "signed-out", note: "You're signed out." });
    } catch (e) {
      setState({ kind: "problem", message: e instanceof ApiError ? e.message : SERVER_DOWN });
    }
  }

  if (state.kind === "checking") return <p className="muted">Checking you&apos;re signed in…</p>;

  if (state.kind === "problem")
    return (
      <div className="notice bad" role="alert">
        {state.message}{" "}
        <button type="button" className="link" onClick={() => check()}>
          Try again
        </button>
      </div>
    );

  if (state.kind === "signed-out") {
    const next = encodeURIComponent(window.location.pathname);
    return (
      <section className="card">
        <h1>Sign in</h1>
        {state.note && (
          <p className="notice warn" role="status">
            {state.note}
          </p>
        )}
        <p>The control panel is only for Starr Wellness Collective staff. Sign in with your work Google account.</p>
        {/* A normal link, not fetch: sign-in is a trip to Google's page and back. */}
        <a className="button primary" href={`/backend/auth/login?next=${next}`}>
          Sign in with Google
        </a>
      </section>
    );
  }

  return (
    <>
      <p className="account small muted">
        Signed in as {state.email}{" "}
        <button type="button" className="link" onClick={signOut}>
          Sign out
        </button>
      </p>
      {children}
    </>
  );
}
