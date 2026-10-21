import type { RunStatus } from "@/lib/api";

const LOOK: Record<RunStatus, { label: string; tone: string }> = {
  success: { label: "Worked", tone: "good" },
  failed: { label: "Failed", tone: "bad" },
  running: { label: "Running", tone: "info" },
};

export function RunBadge({ status }: { status: RunStatus }) {
  const { label, tone } = LOOK[status];
  return <span className={`badge ${tone}`}>{label}</span>;
}
