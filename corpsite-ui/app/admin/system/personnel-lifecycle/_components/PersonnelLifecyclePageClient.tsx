// FILE: corpsite-ui/app/admin/system/personnel-lifecycle/_components/PersonnelLifecyclePageClient.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { canSeePersonnelLifecycleNav } from "@/lib/adminNav";
import type { MeInfo } from "@/lib/types";

import PersonnelLifecycleClient from "../../_components/personnel-lifecycle/PersonnelLifecycleClient";

export default function PersonnelLifecyclePageClient() {
  const router = useRouter();
  const [me, setMe] = useState<MeInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      try {
        const data = await apiAuthMe();
        setMe(data);
        if (!canSeePersonnelLifecycleNav(data)) {
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

  if (!canSeePersonnelLifecycleNav(me)) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-zinc-100 p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">
        Переход…
      </div>
    );
  }

  return <PersonnelLifecycleClient me={me} />;
}
