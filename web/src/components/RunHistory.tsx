"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, SERVER_DOWN, api, type Run } from "@/lib/api";
import { formatDateTime, formatRange, startedBy } from "@/lib/format";

import { RunBadge } from "./RunBadge";

export const HISTORY_LIMIT = 50;

export function RunHistory() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRuns((await api<{ runs: Run[] }>(`/runs?limit=${HISTORY_LIMIT}`)).runs);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : SERVER_DOWN);
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(load, 0);
    return () => clearTimeout(first);
  }, [load]);

  return (
    <>
      {error && (
        <div className="notice bad" role="alert">
          {error}
        </div>
      )}
      {!runs && !error && <p className="muted">Loading…</p>}
      {runs && runs.length === 0 && <p>No runs yet. The first one happens at the next scheduled time.</p>}
      {runs && runs.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Started</th>
                <th scope="col">Result</th>
                <th scope="col">Days covered</th>
                <th scope="col">Rows updated</th>
                <th scope="col">Started by</th>
                <th scope="col">Details</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td className="nowrap">{formatDateTime(run.started_at)}</td>
                  <td>
                    <RunBadge status={run.status} />
                  </td>
                  <td className="nowrap">{formatRange(run.start_date, run.end_date)}</td>
                  <td>{run.rows_written ?? "—"}</td>
                  <td>{startedBy(run.trigger, run.triggered_by)}</td>
                  <td>{run.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="actions">
        <button type="button" onClick={load}>
          Refresh
        </button>
        <span className="muted small">Showing the latest {HISTORY_LIMIT} runs, newest first. Times are New York time.</span>
      </p>
    </>
  );
}
