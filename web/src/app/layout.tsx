import type { Metadata } from "next";

import { AuthGate } from "@/components/AuthGate";
import { Nav } from "@/components/Nav";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Pipeline control panel", template: "%s · Pipeline control panel" },
  description: "Status, history and settings for the Starr Wellness Collective data pipeline.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="inner">
            <span className="site-name">SWC data pipeline</span>
            <Nav />
          </div>
        </header>
        <main>
          <AuthGate>{children}</AuthGate>
        </main>
      </body>
    </html>
  );
}
