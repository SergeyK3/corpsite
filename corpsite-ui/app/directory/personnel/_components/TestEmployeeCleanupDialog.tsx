"use client";

import * as React from "react";
import { groupedCleanupCounts, TestCleanupConfirmationCheckbox, useTestCleanupConfirmation } from "../../_components/TestCleanupConfirmation";
import {
  deleteTestEmployee,
  markTestEmployee,
  markTestPersonnelOrder,
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
  personnel_file_sets: "Наборы файлов личного дела",
  personnel_file_versions: "Версии файлов личного дела",
  personnel_file_events: "События файлов личного дела",
  security_audit_log: "События журнала безопасности",
  person_photos: "Фотографии",
  person_relatives: "Родственники",
  person_education: "Образование",
  person_training: "Квалификация",
  person_military_service: "Воинский учёт",
  person_contacts: "Контакты",
  person_telegram_bindings: "Telegram-привязки",
  notifications: "Уведомления",
  verification_tasks: "Индивидуальные задачи",
  person_card_change_requests: "Заявки на изменение личной карточки",
  person_card_change_documents: "Документы заявок на карточку",
  person_card_change_events: "История рассмотрения заявок на карточку",
  person_card_record_documents: "Связи документов с разделами карточки",
  person_relative_change_requests: "Заявки на изменение родственников",
  person_relative_change_events: "История рассмотрения заявок на родственников",
  ppr_stage0_cohort_participants: "Участники кадровой когорты",
  task_event_deliveries: "Журнал доставки событий задач",
  task_event_recipients: "Получатели событий задач",
  tasks: "Задачи",
  user_linkage_execute_items: "Журнал привязки учётных записей",
  electronic_hire_approval_tasks: "Задачи согласования приёма",
  employee_onboarding_notifications: "История уведомлений адаптации",
  ppr_migration_section_status_projection: "Исторические срезы кадровой миграции",
  employee_onboarding_notification_recipients: "Получатели уведомлений адаптации",
  employee_onboarding_notification_deliveries: "Доставка уведомлений адаптации",
};

const historyActionLabels: Record<string, string> = {
  CANCEL_PENDING_DELIVERIES: "Ожидающие доставки будут отменены с сохранением снимка",
  ARCHIVE_COMPLETED_DELIVERIES: "Выполненные доставки тестовой учётной записи останутся в архиве",
  KEEP_COMPLETED_DELIVERIES: "Выполненные доставки другим пользователям останутся в журнале",
  KEEP_APPROVAL_DECISIONS: "Результаты согласования останутся в истории",
  KEEP_PPR_COHORT: "Участники замороженных когорт PPR останутся в снимке",
  KEEP_USER_LINKAGE: "Операции привязки учётной записи останутся в истории",
  KEEP_TASK_ATTRIBUTION: "Исходное авторство общих задач останется в архиве",
};

function blockerLabel(detail: string): string {
  const match = detail.match(/^(?:Внешняя зависимость|Неописанная связь|Составная внешняя зависимость) ([a-z_]+)\.[a-z_]+: (\d+)$/);
  if (!match) return detail;
  return `${tableLabels[match[1]] ?? "Связанные данные"}: ${match[2]} — требуется отдельное решение`;
}

export default function TestEmployeeCleanupDialog({
  employeeId, fullName, mode, onClose, onMarked, onDeleted,
}: Props) {
  const [preview, setPreview] = React.useState<TestEmployeeCleanupPreview | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const { confirmed, setConfirmed } = useTestCleanupConfirmation(preview);
  const [evidence, setEvidence] = React.useState("");
  const [confirmedName, setConfirmedName] = React.useState("");
  const [stage, setStage] = React.useState<"mark" | "delete" | "blocked">(mode);
  const [selectedOrderId, setSelectedOrderId] = React.useState<number | null>(null);
  const [orderEvidence, setOrderEvidence] = React.useState("");
  const [confirmedOrderNumber, setConfirmedOrderNumber] = React.useState("");

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
    if (!preview || submitting || (stage === "delete" && (!confirmed || !preview.can_delete))) return;
    setSubmitting(true);
    setError(null);
    try {
      if (stage === "mark") {
        await markTestEmployee(employeeId, evidence, confirmedName);
        const refreshed = await previewTestEmployeeCleanup(employeeId);
        setPreview(refreshed);
        setStage(refreshed.can_delete ? "delete" : "blocked");
        onMarked();
      } else {
        const result = await deleteTestEmployee(employeeId, preview.snapshot_hash);
        onDeleted(result);
      }
    } catch (cause) {
      setError(mapPersonnelLkApiError(cause, "Операция не выполнена."));
      if (stage === "delete") {
        try { setPreview(await previewTestEmployeeCleanup(employeeId)); } catch { /* Keep the original error. */ }
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function confirmOrder(orderId: number) {
    if (submitting || orderEvidence.trim().length < 20) return;
    setSubmitting(true);
    setError(null);
    try {
      await markTestPersonnelOrder(employeeId, orderId, orderEvidence, confirmedOrderNumber);
      const refreshed = await previewTestEmployeeCleanup(employeeId);
      setPreview(refreshed);
      setStage(refreshed.can_delete ? "delete" : "blocked");
      setSelectedOrderId(null);
      setOrderEvidence("");
      setConfirmedOrderNumber("");
    } catch (cause) {
      setError(mapPersonnelLkApiError(cause, "Не удалось подтвердить происхождение приказа."));
    } finally {
      setSubmitting(false);
    }
  }

  const title = stage === "mark" ? "Подтверждение тестового сотрудника" : "Полное удаление тестового сотрудника";
  const rows = Object.entries(preview?.counts ?? {}).filter(([, count]) => count > 0);
  const retainedRows = Object.entries(preview?.retained_counts ?? {}).filter(([, count]) => count > 0);
  const groupedRows = groupedCleanupCounts(preview?.counts, tableLabels, "Другие персональные данные");
  const groupedRetainedRows = groupedCleanupCounts(preview?.retained_counts, tableLabels, "Исторические записи");
  const blockerGroups = preview?.blocker_groups ?? [];
  const groupedTables = new Set(blockerGroups.map((group) => group.table));
  const ungroupedBlockers = (preview?.blockers ?? []).filter((detail) => {
    const match = detail.match(/^(?:Внешняя зависимость|Составная внешняя зависимость) ([a-z_]+)\./);
    return !match || !groupedTables.has(match[1]);
  });
  const evidenceLength = evidence.trim().length;
  const nameMatches = confirmedName === preview?.full_name;
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
              <p className="mb-2 font-medium">Будут удалены</p>
              {groupedRows.length ? <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
                {groupedRows.map(([label, count]) => <React.Fragment key={label}>
                  <dt>{label}</dt><dd className="text-right font-medium">{count}</dd>
                </React.Fragment>)}
              </dl> : <p>Связанных записей нет.</p>}
              <p className="mt-2">Файловых объектов для очистки: {preview.file_count}</p>
              <details className="mt-2"><summary className="cursor-pointer">Подробности</summary>
                <ul className="mt-1 list-disc pl-5">{rows.map(([table, count]) => <li key={table}>{table}: {count}</li>)}</ul>
              </details>
            </div>
            <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700">
              <p className="mb-2 font-medium">Будут сохранены в истории</p>
              {groupedRetainedRows.length ? <dl className="grid grid-cols-[1fr_auto] gap-x-3 gap-y-1">
                {groupedRetainedRows.map(([label, count]) => <React.Fragment key={label}>
                  <dt>{label}</dt><dd className="text-right font-medium">{count}</dd>
                </React.Fragment>)}
              </dl> : <p>Связанных исторических записей нет.</p>}
              {retainedRows.length ? <p className="mt-2 text-zinc-600 dark:text-zinc-400">Исходная учётная запись будет указана в неизменяемой записи об удалении.</p> : null}
              {preview.history_actions?.length ? <ul className="mt-2 list-disc space-y-1 pl-5">
                {preview.history_actions.map((action) => <li key={action.code}>
                  {historyActionLabels[action.code] ?? action.code}: {action.count}
                </li>)}
              </ul> : null}
              {retainedRows.length ? <details className="mt-2"><summary className="cursor-pointer">Подробности</summary>
                <ul className="mt-1 list-disc pl-5">{retainedRows.map(([table, count]) => <li key={table}>{table}: {count}</li>)}</ul>
              </details> : null}
            </div>
            {preview.blockers.length ? <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
              <p className="font-medium">Препятствуют удалению</p>
              <ul className="mt-1 list-disc pl-5">
                {blockerGroups.map((group) => <li key={group.table}>
                  {tableLabels[group.table] ?? "Связанные данные нового типа"}: {group.count} — требуется отдельное решение
                </li>)}
                {ungroupedBlockers.map((blocker) => <li key={blocker}>{blockerLabel(blocker)}</li>)}
              </ul>
              <details className="mt-2"><summary className="cursor-pointer">Подробности</summary>
                <ul className="mt-1 list-disc pl-5">{preview.blockers.map((blocker) => <li key={blocker}>{blocker}</li>)}</ul>
              </details>
            </div> : null}
            {preview.personnel_orders?.length ? <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700">
              <p className="mb-2 font-medium">Кадровые приказы</p>
              <ul className="space-y-3">
                {preview.personnel_orders.map((order) => <li key={order.order_id} className="rounded border border-zinc-200 p-2 dark:border-zinc-700">
                  <p className="font-medium">№ {order.order_number ?? "без номера"} · ID {order.order_id}</p>
                  <p>Дата: {order.order_date ?? "—"} · Тип: {order.order_type_code} · Статус: {order.status} · Пунктов: {order.item_count}</p>
                  <p>Сотрудники: {order.employees.map((person) => `${person.full_name ?? "—"} (ID ${person.employee_id ?? "—"})`).join(", ")}</p>
                  <p>Подписанных копий: {order.signed_copy_count} · Вложений: {order.attachment_count} · Событий ознакомления: {order.acknowledgement_count}</p>
                  <p className="mt-1">{order.is_test_marked ? "Тестовое происхождение приказа подтверждено" : "Тестовое происхождение приказа не подтверждено"}</p>
                  {preview.is_test_marked && !order.is_test_marked ? <div className="mt-2 space-y-2">
                    {selectedOrderId === order.order_id ? <>
                      <label className="block">Документированное основание тестового происхождения приказа
                        <textarea value={orderEvidence} onChange={(event) => setOrderEvidence(event.target.value)} rows={3} maxLength={2000}
                          className="mt-1 w-full rounded border p-2 dark:bg-zinc-950" />
                      </label>
                      <p>Минимум 20 символов; одного номера или ФИО недостаточно.</p>
                      <label className="block">Введите точный номер приказа
                        <input value={confirmedOrderNumber} onChange={(event) => setConfirmedOrderNumber(event.target.value)}
                          className="mt-1 w-full rounded border p-2 dark:bg-zinc-950" />
                      </label>
                      <button type="button" disabled={submitting || orderEvidence.trim().length < 20 || confirmedOrderNumber !== (order.order_number ?? "")}
                        onClick={() => void confirmOrder(order.order_id)} className="rounded bg-amber-700 px-3 py-2 text-white disabled:opacity-50">
                        Подтвердить тестовый приказ
                      </button>
                    </> : <button type="button" onClick={() => { setSelectedOrderId(order.order_id); setOrderEvidence(""); setConfirmedOrderNumber(""); }}
                      className="rounded border px-3 py-2">Подтвердить тестовый приказ</button>}
                  </div> : null}
                </li>)}
              </ul>
            </div> : null}
          </div>
        ) : null}

        {stage === "mark" ? <div className="mt-4 space-y-3 text-sm">
          <p>Подтвердите происхождение тестовой записи по независимому основанию. Одного имени недостаточно.</p>
          <label className="block">Основание подтверждения
            <textarea value={evidence} onChange={(event) => setEvidence(event.target.value)} rows={3} maxLength={1000}
              className="mt-1 w-full rounded-md border border-zinc-300 p-2 dark:border-zinc-700 dark:bg-zinc-950" />
          </label>
          <p className={evidenceLength > 0 && evidenceLength < 12 ? "text-amber-700 dark:text-amber-300" : "text-zinc-600 dark:text-zinc-400"}>
            Основание: от 12 до 1000 символов после удаления пробелов по краям. Сейчас: {evidenceLength}.
          </p>
          <label className="block">Введите точное ФИО
            <input value={confirmedName} onChange={(event) => setConfirmedName(event.target.value)}
              className="mt-1 w-full rounded-md border border-zinc-300 p-2 dark:border-zinc-700 dark:bg-zinc-950" />
          </label>
          {confirmedName && !nameMatches ? <p className="text-amber-700 dark:text-amber-300">Введите ФИО точно как в карточке, включая пробелы.</p> : null}
        </div> : <div className="mt-4 space-y-3 text-sm">
          {stage === "blocked" ? <p role="status" className="text-amber-700 dark:text-amber-300">Тестовое происхождение подтверждено. Удаление пока заблокировано указанными зависимостями.</p> : null}
          <p className="font-medium text-red-700 dark:text-red-400">Сотрудник и связанные с ним тестовые данные будут удалены без возможности восстановления через интерфейс системы.</p>
          <TestCleanupConfirmationCheckbox checked={confirmed} onChange={setConfirmed} />
        </div>}
        {error ? <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-400">{error}</p> : null}
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} disabled={submitting} className="rounded-md border px-3 py-2 text-sm">Отмена</button>
          {stage !== "blocked" ? <button type="button" onClick={() => void submit()}
            disabled={submitting || !preview || (stage === "mark" ? evidenceLength < 12 || !nameMatches : !preview.can_delete || !confirmed)}
            className="rounded-md bg-red-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-50">
            {submitting ? "Выполнение…" : stage === "mark" ? "Подтвердить тестовую запись" : "Удалить окончательно"}
          </button> : null}
        </div>
      </section>
    </div>
  );
}
