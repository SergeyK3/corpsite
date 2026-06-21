// FILE: corpsite-ui/app/admin/system/personnel-identity/operations/_components/PersonnelIdentityOperationsPageClient.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { canSeePersonnelIdentityOperationsNav } from "@/lib/adminNav";

import UserLinkageOperationsClient from "../../../_components/user-linkage-operations/UserLinkageOperationsClient";

export default function PersonnelIdentityOperationsPageClient() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    void (async () => {
      try {
        const data = await apiAuthMe();
        if (!canSeePersonnelIdentityOperationsNav(data)) {
          router.replace("/tasks");
          return;
        }
        setAllowed(true);
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

  if (!allowed) {
    return (
      <div className="rounded-2xl border border-zinc-200 bg-zinc-100 p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">
        Переход…
      </div>
    );
  }

  return <UserLinkageOperationsClient />;
}
