import type { Metadata } from "next";

import { SettingsForm } from "@/components/SettingsForm";

export const metadata: Metadata = { title: "Settings" };

export default function SettingsPage() {
  return (
    <>
      <h1>Settings</h1>
      <p>What the pipeline pulls each day, when it sends an alert, and who gets it.</p>
      <SettingsForm />
    </>
  );
}
