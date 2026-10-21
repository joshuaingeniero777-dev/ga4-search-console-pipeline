"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ApiError, SERVER_DOWN, api, type Status, type StatusState } from "@/lib/api";
import { formatDateTime, formatRange, startedBy } from "@/lib/format";

import { RunBadge } from "./RunBadge";

// Not faster: Google limits how often the sheet can be read (see api/routes.py).
export const POLL_MS = 15_000;

const STATE: Record<StatusState, { label: string; tone: string }> = {
  ok: { label: "Working", tone: "good" },
  running: { label: "Running now", tone: "info" },
  failed: { label: "Last run failed", tone: "bad" },
  settings_invalid: { label: "Settings need fixing", tone: "bad" },
  never_run: { label: "Not run yet", tone: "neutral" },
};

export function StatusView() {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setStatus(await api<Status>("/status"));
      setError(null);
      setCheckedAt(formatDateTime(new Date().toISOString()));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : SERVER_DOWN);
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(load, 0);
    const timer = setInterval(load, POLL_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [load]);

  if (!status && !error) return <p className="muted">Checking…</p>;

  const look = status ? STATE[status.state] : null;
  return (
    <>
      {error && (
        <div className="notice bad" role="alert">
          {error}
        </div>
      )}

      {status && look && (
        <>
          <section className="card" aria-live="polite">
            <span className={`badge ${look.tone}`}>{look.label}</span>
            <p className="lead">{status.message}</p>
            {status.state === "settings_invalid" && (
              <p>
                <Link href="/settings">Go to Settings to fix it</Link>
              </p>
            )}
          </section>

          {status.warnings.length > 0 && (
            <section className="notice warn">
              <h2>Needs attention</h2>
              <ul>
                {status.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            </section>
          )}

          <section className="card">
            <dl className="facts">
              <dt>Next scheduled run</dt>
              <dd>{formatDateTime(status.next_run_at)} (New York time)</dd>
              {status.last_run && (
                <>
                  <dt>Most recent run</dt>
                  <dd>
                    <RunBadge status={status.last_run.status} /> {formatDateTime(status.last_run.started_at)}
                    <br />
                    <span className="muted small">
                      Covered {formatRange(status.last_run.start_date, status.last_run.end_date)} · started by{" "}
                      {startedBy(status.last_run.trigger, status.last_run.triggered_by)}
                    </span>
                  </dd>
                </>
              )}
            </dl>
          </section>
        </>
      )}

      <p className="actions">
        <button type="button" onClick={load}>
          Check again
        </button>
        <Link href="/run-now">Run now</Link>
        <Link href="/runs">See all runs</Link>
      </p>
      {checkedAt && (
        <p className="muted small">Updates on its own every 15 seconds. Last checked {checkedAt}.</p>
      )}
    </>
  );
}
