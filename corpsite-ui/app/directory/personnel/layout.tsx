// FILE: corpsite-ui/app/directory/personnel/layout.tsx
import type { ReactNode } from "react";

import PersonnelLayoutShell from "./_components/PersonnelLayoutShell";
import { PersonnelSectionLanguageProvider } from "./_lib/personnelSectionLanguage";

export default function PersonnelLayout({ children }: { children: ReactNode }) {
  return (
    <div className="bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-50">
      <PersonnelSectionLanguageProvider><PersonnelLayoutShell>{children}</PersonnelLayoutShell></PersonnelSectionLanguageProvider>
    </div>
  );
}
