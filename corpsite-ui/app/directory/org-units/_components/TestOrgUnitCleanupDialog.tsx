"use client";

import { useEffect, useState } from "react";
import { groupedCleanupCounts, TestCleanupConfirmationCheckbox, useTestCleanupConfirmation } from "../../_components/TestCleanupConfirmation";
import {
  deleteTestOrgUnit, markTestOrgUnit, previewTestOrgUnitCleanup,
  type TestOrgUnitCleanupPreview,
} from "../_lib/api.client";

const labels: Record<string, string> = {
  child_org_units: "Дочерние подразделения",
  employees: "Сотрудники",
  person_assignments: "Назначения",
  org_unique_position: "Штатные единицы",
  org_unit_allowed_positions: "Разрешённые должности",
  users: "Пользователи",
  regular_tasks: "Задачи",
  personnel_order_items: "Пункты кадровых приказов",
};

function errorMessage(error: unknown): string {
  const value = error as { details?: { detail?: unknown }; message?: string };
  return typeof value?.details?.detail === "string" ? value.details.detail
    : value?.message || "Операция не выполнена";
}

export default function TestOrgUnitCleanupDialog({ unitId, name, onClose, onDeleted }: {
  unitId: number; name: string; onClose: () => void; onDeleted: () => void;
}) {
  const [preview, setPreview] = useState<TestOrgUnitCleanupPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [evidence, setEvidence] = useState("");
  const [confirmedName, setConfirmedName] = useState("");
  const { confirmed, setConfirmed } = useTestCleanupConfirmation(preview);

  useEffect(() => {
    let live = true;
    void previewTestOrgUnitCleanup(unitId).then((data) => {
      if (live) setPreview(data);
    }).catch((cause) => { if (live) setError(errorMessage(cause)); })
      .finally(() => { if (live) setLoading(false); });
    return () => { live = false; };
  }, [unitId]);

  async function submit() {
    if (!preview || busy || (preview.is_test_marked && (!confirmed || !preview.can_delete))) return;
    setBusy(true);
    setError("");
    try {
      if (!preview.is_test_marked) {
        await markTestOrgUnit(unitId, confirmedName, evidence);
        setPreview(await previewTestOrgUnitCleanup(unitId));
      } else {
        await deleteTestOrgUnit(unitId, preview.snapshot_hash);
        onDeleted();
      }
    } catch (cause) {
      setError(errorMessage(cause));
      if (preview.is_test_marked) {
        try { setPreview(await previewTestOrgUnitCleanup(unitId)); } catch { /* Keep the original error. */ }
      }
    } finally {
      setBusy(false);
    }
  }

  const visibleCounts = Object.entries(preview?.counts ?? {}).filter(([, count]) => count > 0);
  const groupedCounts = groupedCleanupCounts(preview?.counts, labels, "Другие связанные данные");
  return <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4">
    <section role="dialog" aria-modal="true" aria-label="Удаление тестового подразделения"
      className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl dark:bg-zinc-900">
      <h2 className="text-lg font-semibold">Удаление тестового подразделения</h2>
      <p className="mt-2 font-medium">{preview?.name ?? name} · ID {unitId}</p>
      {loading ? <p className="mt-3">Загрузка зависимостей…</p> : null}
      {preview ? <div className="mt-4 rounded-lg border p-3 text-sm">
        <p className="font-medium">Связанные объекты по данным сервера</p>
        {groupedCounts.length ? <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
          {groupedCounts.map(([label, count]) => <div key={label} className="contents"><dt>{label}</dt><dd>{count}</dd></div>)}
        </dl> : <p className="mt-2">Зависимостей нет.</p>}
        {visibleCounts.length ? <details className="mt-2"><summary className="cursor-pointer">Подробности</summary>
          <ul className="mt-1 list-disc pl-5">{visibleCounts.map(([key, count]) => <li key={key}>{key}: {count}</li>)}</ul>
        </details> : null}
      </div> : null}
      {preview?.blockers.length ? <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
        <p className="font-medium">Удаление заблокировано</p>
        <ul className="mt-1 list-disc pl-5">{preview.blockers.map((item) => <li key={item}>{item}</li>)}</ul>
      </div> : null}
      {preview && !preview.is_test_marked ? <div className="mt-4 space-y-3 text-sm">
        <p>Подтвердите тестовое происхождение по независимому основанию. Одного названия недостаточно.</p>
        <label className="block">Основание подтверждения
          <textarea value={evidence} onChange={(e) => setEvidence(e.target.value)} rows={3}
            className="mt-1 w-full rounded-md border p-2 dark:bg-zinc-950" />
        </label>
        <label className="block">Введите точное название подразделения
          <input value={confirmedName} onChange={(e) => setConfirmedName(e.target.value)}
            className="mt-1 w-full rounded-md border p-2 dark:bg-zinc-950" />
        </label>
      </div> : null}
      {preview?.is_test_marked ? <div className="mt-4 space-y-3 text-sm">
        <p className="font-medium text-red-700">Подразделение будет физически удалено без восстановления через интерфейс. Связанные сотрудники, назначения и дочерние подразделения не удаляются.</p>
        <TestCleanupConfirmationCheckbox checked={confirmed} onChange={setConfirmed} />
      </div> : null}
      {error ? <p role="alert" className="mt-3 text-sm text-red-700">{error}</p> : null}
      <div className="mt-5 flex justify-end gap-2">
        <button type="button" disabled={busy} onClick={onClose} className="rounded-md border px-3 py-2 text-sm">Отмена</button>
        <button type="button" onClick={() => void submit()} className="rounded-md bg-red-700 px-3 py-2 text-sm text-white disabled:opacity-50"
          disabled={busy || !preview || (!preview.is_test_marked
            ? evidence.trim().length < 20 || confirmedName !== preview.name
            : !preview.can_delete || !confirmed)}>
          {preview?.is_test_marked ? "Удалить окончательно" : "Подтвердить тестовое происхождение"}
        </button>
      </div>
    </section>
  </div>;
}
