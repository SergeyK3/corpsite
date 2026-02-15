// FILE: corpsite-ui/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";

import TenantTitle from "../components/TenantTitle";
import AppShell from "../components/AppShell";

export const metadata: Metadata = {
  title: "Система личных кабинетов",
  description: "Личный кабинет",
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
            borderBottom: "1px solid rgba(255,255,255,0.10)",
            background: "rgb(9 9 11)",
            color: "rgb(244 244 245)",
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
            <a
              href="/"
              style={{
                fontWeight: 700,
                textDecoration: "none",
                color: "inherit",
                letterSpacing: 0.2,
              }}
            >
              <TenantTitle />
            </a>

            {/* Reserved: right side (DEV badge / user menu) */}
            <div style={{ display: "flex", alignItems: "center", gap: 10 }} />
          </div>
        </header>

        <main>
          <AppShell>{children}</AppShell>
        </main>
      </body>
    </html>
  );
}
