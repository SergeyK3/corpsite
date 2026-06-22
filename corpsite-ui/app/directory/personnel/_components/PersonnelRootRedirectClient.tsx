// FILE: corpsite-ui/app/directory/personnel/_components/PersonnelRootRedirectClient.tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { resolvePersonnelRootRedirect } from "@/lib/personnelNav";

export default function PersonnelRootRedirectClient() {
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const me = await apiAuthMe();
        if (cancelled) return;
        router.replace(resolvePersonnelRootRedirect(me));
      } catch {
        if (cancelled) return;
        router.replace("/login");
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div className="px-4 py-6 text-sm text-zinc-600 dark:text-zinc-400" aria-live="polite">
      Переход…
    </div>
  );
}
