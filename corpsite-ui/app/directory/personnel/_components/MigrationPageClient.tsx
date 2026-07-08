// PMF-4B — page guard wrapper for Migration Wizard routes.
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { canSeeHrProcessesNav } from "@/lib/personnelNav";
import type { MeInfo } from "@/lib/types";

import MigrationHomePageClient from "./MigrationHomePageClient";
import { MigrationForbiddenPanel, MigrationLoadingPanel } from "./MigrationWizardShell";

export default function MigrationPageClient() {
  const router = useRouter();
  const [me, setMe] = useState<MeInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const data = await apiAuthMe();
        setMe(data);
        if (!canSeeHrProcessesNav(data)) {
          router.replace("/tasks");
        }
      } catch {
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  if (loading) {
    return (
      <div className="px-4 py-3">
        <MigrationLoadingPanel />
      </div>
    );
  }

  if (!canSeeHrProcessesNav(me)) {
    return (
      <div className="px-4 py-3">
        <MigrationForbiddenPanel />
      </div>
    );
  }

  return <MigrationHomePageClient />;
}
