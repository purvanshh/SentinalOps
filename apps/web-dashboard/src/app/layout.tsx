import "./globals.css";

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "SentinelOps AI Dashboard",
  description: "Incident command center for SentinelOps AI"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="hero">
            <div className="eyebrow">SentinelOps AI</div>
            <h1>Autonomous incident response with inspectable agent orchestration.</h1>
            <p>
              Monitor active incidents, review agent traces, approve remediations, and watch evaluation health from one
              operations command surface.
            </p>
            <nav className="nav">
              <Link href="/">Overview</Link>
              <Link href="/incidents">Incidents</Link>
              <Link href="/approvals">Approvals</Link>
              <Link href="/evaluations">Evaluations</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
