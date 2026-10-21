import type { Metadata } from "next";

import { RunHistory } from "@/components/RunHistory";

export const metadata: Metadata = { title: "Run history" };

export default function RunsPage() {
  return (
    <>
      <h1>Run history</h1>
      <RunHistory />
    </>
  );
}
