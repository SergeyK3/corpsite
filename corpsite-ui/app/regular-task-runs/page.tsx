// FILE: corpsite-ui/app/regular-task-runs/page.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { RegularTaskRunsJournalView } from "./_components/RegularTaskRunsJournalView";

import { apiAuthMe, apiGetRegularTaskRunItems, apiGetRegularTaskRuns } from "@/lib/api";
import { canSeeRegularTaskRunsJournal } from "@/lib/adminNav";
import { isAuthed, logout as authLogout } from "@/lib/auth";
import { formatThrownError } from "@/lib/i18n";
import type { RegularTaskRunItemRow, RegularTaskRunRow } from "@/lib/regularTaskRunJournal";
import type { MeInfo } from "@/lib/types";

type APIErrorLike = {
  status?: number;
  message?: string;
};

function isUnauthorized(e: unknown): boolean {
  return Number((e as APIErrorLike)?.status ?? 0) === 401;
}

export default function RegularTaskRunsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialRunId = useMemo(() => {
    const raw = String(searchParams.get("run_id") ?? "").trim();
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? Math.trunc(n) : null;
  }, [searchParams]);

  const [me, setMe] = useState<MeInfo | null>(null);
  const [meLoading, setMeLoading] = useState(true);
  const [meError, setMeError] = useState<string | null>(null);
  const canSeeRuns = useMemo(() => canSeeRegularTaskRunsJournal(me), [me]);

  const [runs, setRuns] = useState<RegularTaskRunRow[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [runsError, setRunsError] = useState<string | null>(null);

  const [selectedRunId, setSelectedRunId] = useState<number | null>(initialRunId);
  const [items, setItems] = useState<RegularTaskRunItemRow[]>([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [itemsError, setItemsError] = useState<string | null>(null);

  const [onlyIssues, setOnlyIssues] = useState(false);
  const [search, setSearch] = useState("");

  function redirectToLogin() {
    authLogout();
    router.replace("/login");
  }

  async function loadRuns(preferredRunId?: number | null) {
    setRunsLoading(true);
    setRunsError(null);
    try {
      const data = (await apiGetRegularTaskRuns()) as RegularTaskRunRow[];
      setRuns(data);
      const keepId = preferredRunId ?? selectedRunId;
      if (keepId && data.some((r) => r.run_id === keepId)) {
        if (selectedRunId !== keepId) setSelectedRunId(keepId);
      } else if (selectedRunId && !data.some((r) => r.run_id === selectedRunId)) {
        setSelectedRunId(null);
        setItems([]);
        setItemsError(null);
      }
    } catch (e: unknown) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      setRuns([]);
      setSelectedRunId(null);
      setItems([]);
      setItemsError(null);
      setRunsError(formatThrownError(e));
    } finally {
      setRunsLoading(false);
    }
  }

  async function openRun(runId: number) {
    setItems([]);
    setItemsLoading(true);
    setItemsError(null);
    try {
      const data = (await apiGetRegularTaskRunItems({ run_id: runId })) as RegularTaskRunItemRow[];
      setItems(data);
    } catch (e: unknown) {
      if (isUnauthorized(e)) {
        redirectToLogin();
        return;
      }
      setItems([]);
      setItemsError(formatThrownError(e));
    } finally {
      setItemsLoading(false);
    }
  }

  function handleSelectRun(runId: number) {
    setItems([]);
    setItemsError(null);
    setItemsLoading(true);
    setSelectedRunId(runId);
  }

  useEffect(() => {
    void (async () => {
      setMeLoading(true);
      setMeError(null);
      if (!isAuthed()) {
        router.replace("/login");
        return;
      }
      try {
        setMe(await apiAuthMe());
      } catch (e: unknown) {
        if (isUnauthorized(e)) {
          redirectToLogin();
          return;
        }
        setMeError(formatThrownError(e));
        setMe(null);
      } finally {
        setMeLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (meLoading || !me || !canSeeRuns) return;
    void loadRuns(initialRunId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meLoading, me, canSeeRuns]);

  useEffect(() => {
    if (meLoading || !me || !canSeeRuns || selectedRunId == null) return;
    void openRun(selectedRunId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRunId, meLoading, me, canSeeRuns]);

  if (meLoading) {
    return <div className="px-4 py-6 text-sm text-zinc-600 dark:text-zinc-400">Загрузка профиля…</div>;
  }

  if (meError) {
    return (
      <div className="px-4 py-6">
        <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-300">
          {meError}
        </div>
      </div>
    );
  }

  if (!me || !canSeeRuns) {
    return (
      <div className="px-4 py-6">
        <div className="rounded-2xl border border-zinc-200 bg-zinc-100 p-4 text-sm text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
          Доступ к разделу запусков ограничен. Этот раздел предназначен для службы поддержки/администраторов.
        </div>
      </div>
    );
  }

  return (
    <RegularTaskRunsJournalView
      runs={runs}
      runsLoading={runsLoading}
      runsError={runsError}
      selectedRunId={selectedRunId}
      onSelectRun={handleSelectRun}
      onRefreshRuns={() => void loadRuns()}
      items={items}
      itemsLoading={itemsLoading}
      itemsError={itemsError}
      onRefreshItems={() => (selectedRunId != null ? void openRun(selectedRunId) : undefined)}
      onlyIssues={onlyIssues}
      onOnlyIssuesChange={setOnlyIssues}
      search={search}
      onSearchChange={setSearch}
    />
  );
}
