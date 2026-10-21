import type { Metadata } from "next";

import { RunNowForm } from "@/components/RunNowForm";

export const metadata: Metadata = { title: "Run now" };

export default function RunNowPage() {
  return (
    <>
      <h1>Run now</h1>
      <p>
        The pipeline already runs by itself every morning. Use this to run it straight away, for example after
        fixing a problem, or to re-pull past days.
      </p>
      <RunNowForm />
    </>
  );
}
