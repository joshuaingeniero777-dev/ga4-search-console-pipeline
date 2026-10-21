"use client";

import Link from "next/link";
import { type FormEvent, useEffect, useState } from "react";

import { ApiError, SERVER_DOWN, api, type Run } from "@/lib/api";
import { formatRange, yesterdayInNewYork } from "@/lib/format";

type Result = { ok: true; run: Run } | { ok: false; message: string };

export function RunNowForm() {
  const [mode, setMode] = useState<"usual" | "choose">("usual");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  // Worked out in the browser when the page opens, not when the site is built.
  const [latest, setLatest] = useState<string | undefined>(undefined);
  useEffect(() => {
    const timer = setTimeout(() => setLatest(yesterdayInNewYork()), 0);
    return () => clearTimeout(timer);
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setResult(null);
    if (mode === "choose") {
      if (!start || !end) return setProblem("Please choose both a start date and an end date.");
      if (start > end) return setProblem("The start date is after the end date.");
    }
    setProblem(null);

    setSending(true);
    try {
      const body = mode === "usual" ? {} : { start_date: start, end_date: end };
      const { run } = await api<{ run: Run }>("/runs", { method: "POST", body: JSON.stringify(body) });
      setResult({ ok: true, run });
    } catch (e) {
      setResult({ ok: false, message: e instanceof ApiError ? e.message : SERVER_DOWN });
    } finally {
      setSending(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      <fieldset>
        <legend>Which days?</legend>
        <label className="choice">
          <input type="radio" name="mode" checked={mode === "usual"} onChange={() => setMode("usual")} />
          The last 7 days (the same as the daily run)
        </label>
        <label className="choice">
          <input type="radio" name="mode" checked={mode === "choose"} onChange={() => setMode("choose")} />
          Choose the days, e.g. to fill in a gap or re-pull a past month
        </label>

        {mode === "choose" && (
          <>
            <div className="field">
              <label htmlFor="start" className="field-label">
                First day
              </label>
              <input id="start" type="date" max={latest} value={start} onChange={(e) => setStart(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="end" className="field-label">
                Last day
              </label>
              <input id="end" type="date" max={latest} value={end} onChange={(e) => setEnd(e.target.value)} />
            </div>
            <p className="muted small">
              Up to yesterday, as far back as 16 months, and no more than 366 days in one go.
            </p>
          </>
        )}
        {problem && (
          <p className="error-text" role="alert">
            {problem}
          </p>
        )}
      </fieldset>

      <button type="submit" className="primary" disabled={sending}>
        {sending ? "Starting…" : "Start the run"}
      </button>

      {result?.ok && (
        <div className="notice good" role="status" style={{ marginTop: "1rem" }}>
          Run started for {formatRange(result.run.start_date, result.run.end_date)}.{" "}
          <Link href="/">The Status page</Link> shows when it&apos;s finished and how it went.
        </div>
      )}
      {result && !result.ok && (
        <div className="notice bad" role="alert" style={{ marginTop: "1rem" }}>
          {result.message}
        </div>
      )}
    </form>
  );
}
