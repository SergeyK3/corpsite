"use client";

import * as React from "react";

import { apiAuthMe } from "@/lib/api";
import type { MeInfo } from "@/lib/types";

import { canSeeOperationalOrdersNav } from "../_lib/permissions";
import AccessDeniedPanel from "./AccessDeniedPanel";
import OperationalOrdersSectionHeader from "./OperationalOrdersSectionHeader";

export default function OperationalOrdersLayoutShell({ children }: { children: React.ReactNode }) {
  const [me, setMe] = React.useState<MeInfo | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    apiAuthMe()
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setLoading(false));
  }, []);

  const denied = !loading && (me == null || !canSeeOperationalOrdersNav(me));

  return (
    <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
      <div className="rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        <div className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <OperationalOrdersSectionHeader />
        </div>
        <div className="min-w-0 p-4">
          {loading ? (
            <p className="text-sm text-zinc-500">Загрузка…</p>
          ) : denied ? (
            <AccessDeniedPanel me={me} />
          ) : (
            children
          )}
        </div>
      </div>
    </div>
  );
}
