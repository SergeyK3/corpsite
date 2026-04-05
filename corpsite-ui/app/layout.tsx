// FILE: corpsite-ui/app/layout.tsx
import type { Metadata } from "next";
import "./globals.css";

import TenantTitle from "../components/TenantTitle";
import AppShell from "../components/AppShell";
import ThemeControl from "../components/ThemeControl";

const themeBootScript = `(function(){try{var k="corpsite_ui_theme";var m=localStorage.getItem(k);if(m==="document"){document.documentElement.classList.remove("dark");}else{document.documentElement.classList.add("dark");}}catch(e){document.documentElement.classList.add("dark");}})();`;

export const metadata: Metadata = {
  title: "Система личных кабинетов",
  description: "Личный кабинет",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body>
        <header className="sticky top-0 z-10 border-b border-zinc-200 bg-white text-zinc-900 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100">
          <div className="mx-auto flex max-w-[1200px] items-center justify-between gap-3 px-4 py-2.5">
            <a
              href="/"
              className="font-bold tracking-wide text-inherit no-underline"
            >
              <TenantTitle />
            </a>

            <div className="flex items-center gap-2">
              <ThemeControl />
            </div>
          </div>
        </header>

        <main>
          <AppShell>{children}</AppShell>
        </main>
      </body>
    </html>
  );
}
