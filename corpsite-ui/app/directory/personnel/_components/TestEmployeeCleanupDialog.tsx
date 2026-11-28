"use client";

import * as React from "react";
import {
  deleteTestEmployee,
  markTestEmployee,
  mapPersonnelLkApiError,
  previewTestEmployeeCleanup,
  type TestEmployeeCleanupPreview,
  type TestEmployeeCleanupResult,
} from "../_lib/personnelLkApi.client";

type Props = {
  employeeId: number;
  fullName: string;
  mode: "mark" | "delete";
  onClose: () => void;
  onMarked: () => void;
  onDeleted: (result: TestEmployeeCleanupResult) => void;
};

const tableLabels: Record<string, string> = {
  persons: "Физическое лицо",
  employees: "Сотрудник",
  users: "Учётная запись",
  person_assignments: "Назначения",
  employee_assignment_links: "Связи назначений",
  personnel_orders: "Кадровые приказы",
  personnel_order_items: "Пункты приказов",
  personnel_applications: "Заявления",
  employee_documents: "Документы",
  person_photos: "Фотографии",
  person_relatives: "Родственники",
  person_education: "Образование",
  person_training: "Квалификация",
  person_military_service: "Воинский учёт",
  person_contacts: "Контакты",
  person_telegram_bindings: "Telegram-привязки",
  notifications: "Уведомления",
  verification_tasks: "Индивидуальные задачи",
};

export default function TestEmployeeCleanupDialog({
  employeeId, fullName, mode, onClose, onMarked, onDeleted,
}: Props) {
  const [preview, setPreview] = React.useState<TestEmployeeCleanupPreview | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [confirmation, setConfirmation] = React.useState("");
  const [evidence, setEvidence] = React.useState("");
  const [confirmedName, setConfirmedName] = React.useState("");

  React.useEffect(() => {
    let alive = true;
    void previewTestEmployeeCleanup(employeeId)
      .then((result) => { if (alive) setPreview(result); })
      .catch((cause) => { if (alive) setError(mapPersonnelLkApiError(cause, "Не удалось загрузить состав удаления.")); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [employeeId]);

  React.useEffect(() => {
    function onKey(event: KeyboardEvent) { if (event.key === "Escape" && !submitting) onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, submitting]);

  async function submit() {
    if (!preview || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      if (mode === "mark") {
        await markTestEmployee(employeeId, evidence, confirmedName);
        onMarked();
      } else {
        const result = await deleteTestEmployee(employeeId, preview.snapshot_hash);
        onDeleted(result);
      }
    } catch (cause) {
      setError(mapPersonnelLkApiError(cause, "Операция не выполнена."));
    } finally {
      setSubmitting(false);
    }
  }

  const title = mode === "mark" ? "Подтверждение тестового сотрудника" : "Полное удаление тестового сотрудника";
  const rows = Object.entries(preview?.counts ?? {}).filter(([, count]) => count > 0);
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4" data-testid="test-employee-dialog-backdrop">
      <section role="dialog" aria-modal="true" aria-label={title} className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl dark:bg-zinc-900">
        <h2 className="text-lg font-semibold">{title}</h2>
        <p className="mt-2 font-medium">{preview?.full_name ?? fullName}</p>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Сотрудник ID {employeeId} · логин: {preview?.login || "—"}</p>

        {loading ? <p className="mt-4 text-sm">Загрузка зависимостей…</p> : null}
        {preview ? (
          <div className="mt-4 space-y-3">
            <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700">
              <p className="mb-2 font-medium">Связанные записи по данным сервера</p>
              {rows.length ? <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
                {rows.map(([table, count]) => <React.Fragment key={table}>
                  <dt>{tableLabels[table] ?? table}</dt><dd className="text-right font-medium">{count}</dd>
                </React.Fragment>)}
              </dl> : <p>Связанных записей нет.</p>}
              <p className="mt-2">Файлов для очистки: {preview.file_count}</p>
            </div>
            {preview.blockers.length ? <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
              <p className="font-medium">Зависимости, препятствующие удалению</p>
              <ul className="mt-1 list-disc pl-5">{preview.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul>
            </div> : null}
          </div>
        ) : null}

        {mode === "mark" ? <div className="mt-4 space-y-3 text-sm">
          <p>Подтвердите происхождение тестовой записи по независимому основанию. Одного имени недостаточно.</p>
          <label className="block">Основание подтверждения
            <textarea value={evidence} onChange={(event) => setEvidence(event.target.value)} rows={3} maxLength={1000}
              className="mt-1 w-full rounded-md border border-zinc-300 p-2 dark:border-zinc-700 dark:bg-zinc-950" />
          </label>
          <label className="block">Введите точное ФИО
            <input value={confirmedName} onChange={(event) => setConfirmedName(event.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 p-2 dark:border-zinc-700 dark:bg-zinc-950" />
          </label>
        </div> : <div className="mt-4 space-y-3 text-sm">
          <p className="font-medium text-red-700 dark:text-red-400">Сотрудник и связанные с ним тестовые данные будут удалены без возможности восстановления через интерфейс системы.</p>
          <label className="block">Для подтверждения введите слово «УДАЛИТЬ»
            <input value={confirmation} onChange={(event) => setConfirmation(event.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 p-2 dark:border-zinc-700 dark:bg-zinc-950" />
          </label>
        </div>}
        {error ? <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-400">{error}</p> : null}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={submitting} className="rounded-md border px-3 py-2 text-sm">Отмена</button>
          <button type="button" onClick={() => void submit()}
            disabled={submitting || !preview || (mode === "mark" ? evidence.trim().length < 20 || confirmedName !== preview.full_name : !preview.can_delete || confirmation !== "УДАЛИТЬ")}
            className="rounded-md bg-red-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
            {submitting ? "Выполнение…" : mode === "mark" ? "Подтвердить тестовую запись" : "Удалить окончательно"}
          </button>
        </div>
      </section>
    </div>
  );
}
