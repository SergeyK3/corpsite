// FILE: corpsite-ui/app/admin/system/org-units/_components/OrgUnitsAdminPageClient.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { canSeeSysadminCabinetNav } from "@/lib/adminNav";
import type { MeInfo } from "@/lib/types";

import OrgUnitsAdminClient from "./OrgUnitsAdminClient";

export default function OrgUnitsAdminPageClient() {
  const router = useRouter();
  const [me, setMe] = useState<MeInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const data = await apiAuthMe();
        setMe(data);
        if (!canSeeSysadminCabinetNav(data)) {
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
      <div className="rounded-2xl border border-zinc-200 bg-zinc-100 p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">
        Загрузка…
      </div>
    );
  }

  if (!canSeeSysadminCabinetNav(me)) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-zinc-100 p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">
        Переход…
      </div>
    );
  }

  return <OrgUnitsAdminClient />;
}
