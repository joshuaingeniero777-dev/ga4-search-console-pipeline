"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { ApiError, SERVER_DOWN, api, type Settings, type SettingsOptions, type SettingsResponse } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

// The same email check the pipeline uses (src/pipeline/settings.py).
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

type Source = "ga4" | "search_console";

interface Form {
  ga4: string[];
  search_console: string[];
  thresholds: Record<string, string>; // metric -> text typed in the box ("" = no alert)
  recipients: string[];
}

interface Problems {
  ga4?: string;
  search_console?: string;
  thresholds: Record<string, string>;
  recipients: Record<number, string>;
  recipientsOverall?: string;
}

type Message = { tone: "good" | "bad"; text: string; conflict?: boolean };

export function toForm(settings: Settings | null): Form {
  return {
    ga4: settings?.metrics.ga4 ?? [],
    search_console: settings?.metrics.search_console ?? [],
    thresholds: Object.fromEntries(
      Object.entries(settings?.alert_thresholds ?? {}).map(([metric, t]) => [metric, String(t.drop_pct)]),
    ),
    recipients: settings?.alert_recipients.length ? [...settings.alert_recipients] : [""],
  };
}

export function check(form: Form, options: SettingsOptions): Problems {
  const problems: Problems = { thresholds: {}, recipients: {} };
  if (form.ga4.length === 0) problems.ga4 = "Choose at least one.";
  if (form.search_console.length === 0) problems.search_console = "Choose at least one.";

  for (const metric of [...form.ga4, ...form.search_console]) {
    const text = (form.thresholds[metric] ?? "").trim();
    if (!text) continue;
    const value = Number(text);
    if (!Number.isInteger(value) || value < options.min_drop_pct || value > options.max_drop_pct) {
      problems.thresholds[metric] =
        `Enter a whole number from ${options.min_drop_pct} to ${options.max_drop_pct}, or leave it empty for no alert.`;
    }
  }

  const seen = new Set<string>();
  form.recipients.forEach((raw, index) => {
    const address = raw.trim().toLowerCase();
    if (!address) return;
    if (!EMAIL.test(address)) problems.recipients[index] = "This isn't a valid email address.";
    else if (seen.has(address)) problems.recipients[index] = "This address is listed twice.";
    seen.add(address);
  });
  const filled = form.recipients.filter((r) => r.trim()).length;
  if (filled === 0) problems.recipientsOverall = "Add at least one person to receive alerts.";
  if (filled > options.max_recipients) problems.recipientsOverall = `Up to ${options.max_recipients} people.`;
  return problems;
}

function hasProblems(problems: Problems): boolean {
  return Boolean(
    problems.ga4 ||
      problems.search_console ||
      problems.recipientsOverall ||
      Object.keys(problems.thresholds).length ||
      Object.keys(problems.recipients).length,
  );
}

export function toSettings(form: Form, options: SettingsOptions): Settings {
  // Keep metrics in the same order as the options, so saving doesn't reshuffle them.
  const ordered = (source: Source) => options[source].map((m) => m.name).filter((n) => form[source].includes(n));
  const metrics = { ga4: ordered("ga4"), search_console: ordered("search_console") };
  const alert_thresholds = Object.fromEntries(
    [...metrics.ga4, ...metrics.search_console]
      .filter((metric) => (form.thresholds[metric] ?? "").trim())
      .map((metric) => [metric, { drop_pct: Number(form.thresholds[metric]) }]),
  );
  const alert_recipients = form.recipients.map((r) => r.trim()).filter(Boolean);
  return { metrics, alert_thresholds, alert_recipients };
}

// The version marks the last save. Today it's that save's time, but the API doesn't
// promise that, so only show it as a date when it is one.
function savedAt(version: string | null): string | null {
  return version && !Number.isNaN(Date.parse(version)) ? formatDateTime(version) : null;
}

export function SettingsForm() {
  const [data, setData] = useState<SettingsResponse | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [problems, setProblems] = useState<Problems | null>(null);
  const [message, setMessage] = useState<Message | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await api<SettingsResponse>("/settings");
      setData(response);
      setForm(toForm(response.settings));
      setProblems(null);
      setMessage(null);
      setLoadError(null);
    } catch (e) {
      setLoadError(e instanceof ApiError ? e.message : SERVER_DOWN);
    }
  }, []);

  useEffect(() => {
    const first = setTimeout(load, 0);
    return () => clearTimeout(first);
  }, [load]);

  if (loadError)
    return (
      <div className="notice bad" role="alert">
        {loadError}{" "}
        <button type="button" className="link" onClick={load}>
          Try again
        </button>
      </div>
    );
  if (!data || !form) return <p className="muted">Loading…</p>;

  const { options } = data;
  const update = (change: Partial<Form>) => setForm({ ...form, ...change });
  const toggle = (source: Source, metric: string) =>
    update({
      [source]: form[source].includes(metric) ? form[source].filter((m) => m !== metric) : [...form[source], metric],
    });
  const selected = [...options.ga4, ...options.search_console].filter(
    (m) => form.ga4.includes(m.name) || form.search_console.includes(m.name),
  );

  async function save(event: FormEvent) {
    event.preventDefault();
    if (!form || !data) return;
    const found = check(form, data.options);
    setProblems(found);
    if (hasProblems(found)) {
      setMessage({ tone: "bad", text: "Some settings need fixing. See the notes below each one." });
      return;
    }
    setSaving(true);
    try {
      const saved = await api<SettingsResponse>("/settings", {
        method: "PUT",
        body: JSON.stringify({ settings: toSettings(form, data.options), version: data.version }),
      });
      setData(saved);
      setForm(toForm(saved.settings));
      setMessage({ tone: "good", text: "Saved. The next run will use these settings." });
    } catch (e) {
      const text = e instanceof ApiError ? e.message : SERVER_DOWN;
      setMessage({ tone: "bad", text, conflict: e instanceof ApiError && e.status === 409 });
    } finally {
      setSaving(false);
    }
  }

  const metricBoxes = (source: Source, legend: string) => (
    <fieldset aria-describedby={problems?.[source] ? `${source}-problem` : undefined}>
      <legend>{legend}</legend>
      <div className="options">
        {options[source].map((metric) => (
          <label key={metric.name} className="choice">
            <input
              type="checkbox"
              checked={form[source].includes(metric.name)}
              onChange={() => toggle(source, metric.name)}
            />
            {metric.label}
          </label>
        ))}
      </div>
      {problems?.[source] && (
        <p id={`${source}-problem`} className="error-text">
          {problems[source]}
        </p>
      )}
    </fieldset>
  );

  return (
    <form onSubmit={save} noValidate>
      {data.problem && (
        <div className="notice bad" role="alert">
          <strong>The saved settings have a problem.</strong> {data.problem} Choose the settings again below and
          save to fix it.
        </div>
      )}
      {data.warnings.length > 0 && (
        <div className="notice warn">
          <ul>
            {data.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
          <p className="small" style={{ marginBottom: 0 }}>
            Alerts stay switched off until all of these are set.
          </p>
        </div>
      )}

      {metricBoxes("ga4", "What to pull from Google Analytics")}
      {metricBoxes("search_console", "What to pull from Search Console")}

      <fieldset>
        <legend>When to send an alert</legend>
        <p className="muted small" style={{ marginTop: 0 }}>
          An alert goes out when a number drops by at least this percentage. Leave a box empty for no alert on
          that number.
        </p>
        {selected.length === 0 && <p className="muted">Choose some numbers to pull first.</p>}
        {selected.map((metric) => {
          const problem = problems?.thresholds[metric.name];
          const id = `threshold-${metric.name}`;
          return (
            <div key={metric.name} className="field">
              <label htmlFor={id} className="field-label">
                {metric.label}
              </label>
              <input
                id={id}
                type="number"
                inputMode="numeric"
                aria-label={`${metric.label} alert threshold (%)`}
                min={options.min_drop_pct}
                max={options.max_drop_pct}
                value={form.thresholds[metric.name] ?? ""}
                aria-invalid={problem ? true : undefined}
                aria-describedby={problem ? `${id}-problem` : undefined}
                onChange={(e) => update({ thresholds: { ...form.thresholds, [metric.name]: e.target.value } })}
              />
              <span>% drop</span>
              {problem && (
                <p id={`${id}-problem`} className="error-text">
                  {problem}
                </p>
              )}
            </div>
          );
        })}
      </fieldset>

      <fieldset>
        <legend>Who gets alerts</legend>
        {form.recipients.map((recipient, index) => {
          const problem = problems?.recipients[index];
          const id = `recipient-${index}`;
          return (
            <div key={index} className="field">
              <label htmlFor={id} className="field-label">
                Email address {form.recipients.length > 1 ? index + 1 : ""}
              </label>
              <input
                id={id}
                type="email"
                autoComplete="off"
                value={recipient}
                aria-invalid={problem ? true : undefined}
                aria-describedby={problem ? `${id}-problem` : undefined}
                onChange={(e) =>
                  update({ recipients: form.recipients.map((r, i) => (i === index ? e.target.value : r)) })
                }
              />
              {form.recipients.length > 1 && (
                <button
                  type="button"
                  className="link"
                  onClick={() => update({ recipients: form.recipients.filter((_, i) => i !== index) })}
                >
                  Remove
                </button>
              )}
              {problem && (
                <p id={`${id}-problem`} className="error-text">
                  {problem}
                </p>
              )}
            </div>
          );
        })}
        {form.recipients.length < options.max_recipients && (
          <button type="button" onClick={() => update({ recipients: [...form.recipients, ""] })}>
            Add another person
          </button>
        )}
        {problems?.recipientsOverall && <p className="error-text">{problems.recipientsOverall}</p>}
      </fieldset>

      {message && (
        <div className={`notice ${message.tone}`} role={message.tone === "bad" ? "alert" : "status"}>
          {message.text}{" "}
          {message.conflict && (
            <button type="button" className="link" onClick={load}>
              Reload the settings (your unsaved changes will be lost)
            </button>
          )}
        </div>
      )}

      <p className="actions">
        <button type="submit" className="primary" disabled={saving}>
          {saving ? "Saving…" : "Save settings"}
        </button>
        {data.updated_by && (
          <span className="muted small">
            Last changed by {data.updated_by}
            {savedAt(data.version) && <> on {savedAt(data.version)}</>}.
          </span>
        )}
      </p>
    </form>
  );
}
