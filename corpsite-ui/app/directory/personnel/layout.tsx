// FILE: corpsite-ui/app/directory/personnel/layout.tsx
import type { ReactNode } from "react";

import PersonnelLayoutShell from "./_components/PersonnelLayoutShell";

export default function PersonnelLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
      <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
        <div className="rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
          <PersonnelLayoutShell>{children}</PersonnelLayoutShell>
        </div>
      </div>
    </div>
  );
}
