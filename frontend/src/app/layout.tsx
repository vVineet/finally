import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinAlly — AI Trading Workstation",
  description: "A terminal-style simulated trading workstation with a live market feed and an AI copilot.",
};

// Deliberately no next/font/google here: system font stacks only (see
// globals.css), so the build has zero network dependency for fonts --
// consistent with the project's offline-first ethos (simulator by
// default, SQLite, single container).
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full h-full flex flex-col">{children}</body>
    </html>
  );
}
