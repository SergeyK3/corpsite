// FILE: corpsite-ui/app/directory/personnel/layout.tsx
import type { ReactNode } from "react";

import PersonnelLayoutShell from "./_components/PersonnelLayoutShell";

export default function PersonnelLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
      <PersonnelLayoutShell>{children}</PersonnelLayoutShell>
    </div>
  );
}
