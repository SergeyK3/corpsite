// FILE: corpsite-ui/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";
import DevUserBadge from "../components/DevUserBadge";

export const metadata: Metadata = {
  title: "corpsite-ui",
  description: "Corpsite UI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <header
          style={{
            position: "sticky",
            top: 0,
            zIndex: 10,
            borderBottom: "1px solid rgba(0,0,0,0.12)",
            background: "white",
          }}
        >
          <div
            style={{
              maxWidth: 1200,
              margin: "0 auto",
              padding: "10px 16px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
              <a href="/" style={{ fontWeight: 700, textDecoration: "none", color: "inherit" }}>
                corpsite
              </a>

              <nav style={{ display: "flex", gap: 12, fontSize: 14, opacity: 0.9 }}>
                <a href="/tasks">Tasks</a>
                <a href="/regular-tasks">Regular Tasks</a>
                <a href="/directory">Directory</a>
              </nav>
            </div>

            <DevUserBadge />
          </div>
        </header>

        <main style={{ maxWidth: 1200, margin: "0 auto", padding: "16px" }}>{children}</main>
      </body>
    </html>
  );
}
