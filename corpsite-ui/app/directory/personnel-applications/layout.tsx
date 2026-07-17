import type { ReactNode } from "react";

import PersonnelLayoutShell from "../personnel/_components/PersonnelLayoutShell";

export default function PersonnelApplicationsLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
      <PersonnelLayoutShell>{children}</PersonnelLayoutShell>
    </div>
  );
}
