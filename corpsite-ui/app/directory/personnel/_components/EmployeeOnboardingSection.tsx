"use client";

import * as React from "react";

import {
  addCustomOnboardingChecklistItem,
  addOnboardingChecklistAttachment,
  cancelEmployeeOnboarding,
  completeEmployeeOnboarding,
  completeOnboardingChecklistItem,
  formatDueDate,
  getEmployeeOnboardingByEmployeeId,
  getOnboardingTaskAudit,
  mapEmployeeOnboardingApiError,
  onboardingAssigneeLabel,
  onboardingChecklistStatusLabel,
  onboardingPriorityLabel,
  onboardingStatusLabel,
  onboardingTaskAuditLabel,
  skipOnboardingChecklistItem,
  type EmployeeOnboardingDetail,
  type OnboardingTaskAuditEntry,
} from "../_lib/employeeOnboardingApi.client";

type Props = {
  employeeId: string;
};

export default function EmployeeOnboardingSection({ employeeId }: Props) {
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [detail, setDetail] = React.useState<EmployeeOnboardingDetail | null>(null);
  const [customTitle, setCustomTitle] = React.useState("");
  const [busyKey, setBusyKey] = React.useState<string | null>(null);
  const [expandedAuditItemId, setExpandedAuditItemId] = React.useState<number | null>(null);
  const [auditByItem, setAuditByItem] = React.useState<Record<number, OnboardingTaskAuditEntry[]>>({});
  const [attachmentUrl, setAttachmentUrl] = React.useState<Record<number, string>>({});

  const reload = React.useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getEmployeeOnboardingByEmployeeId(Number(employeeId));
      setDetail(data);
    } catch (e) {
      setDetail(null);
      setError(mapEmployeeOnboardingApiError(e, "Не удалось загрузить программу адаптации"));
    } finally {
      setLoading(false);
    }
  }, [employeeId]);

  React.useEffect(() => {
    void reload();
  }, [reload]);

  async function runAction(key: string, fn: () => Promise<EmployeeOnboardingDetail>) {
    setBusyKey(key);
    setError(null);
    try {
      const data = await fn();
      setDetail(data);
    } catch (e) {
      setError(mapEmployeeOnboardingApiError(e, "Не удалось выполнить действие"));
    } finally {
      setBusyKey(null);
    }
  }

  async function toggleAudit(itemId: number, onboardingId: number) {
    if (expandedAuditItemId === itemId) {
      setExpandedAuditItemId(null);
      return;
    }
    setExpandedAuditItemId(itemId);
    if (auditByItem[itemId]) return;
    try {
      const res = await getOnboardingTaskAudit(onboardingId, itemId);
      setAuditByItem((prev) => ({ ...prev, [itemId]: res.items }));
    } catch (e) {
      setError(mapEmployeeOnboardingApiError(e, "Не удалось загрузить историю задачи"));
    }
  }

  if (loading) {
    return (
      <div data-testid="employee-onboarding-loading" className="h-16 animate-pulse rounded-lg bg-zinc-100 dark:bg-zinc-900" />
    );
  }

  if (error && !detail) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
        {error}
      </div>
    );
  }

  if (!detail) {
    return <p className="text-sm text-zinc-500">Программа адаптации ещё не создана.</p>;
  }

  const readOnly = detail.is_read_only;
  const dueDates = detail.checklist_items
    .filter((item) => item.due_date)
    .map((item) => ({ item, date: new Date(item.due_date as string) }))
    .sort((a, b) => a.date.getTime() - b.date.getTime());

  return (
    <div className="space-y-4" data-testid="employee-onboarding-section">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Статус</div>
          <div className="text-sm font-medium">{onboardingStatusLabel(detail.status)}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Прогресс</div>
          <div className="text-sm font-medium" data-testid="employee-onboarding-progress">
            {detail.progress_percent}%
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Просрочки</div>
          <div
            className={`text-sm font-medium ${detail.overdue_count > 0 ? "text-red-700 dark:text-red-300" : ""}`}
            data-testid="employee-onboarding-overdue-count"
          >
            {detail.overdue_count}
          </div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-zinc-500">Плановое завершение</div>
          <div className="text-sm">
            {detail.planned_end_at ? new Date(detail.planned_end_at).toLocaleDateString("ru-RU") : "—"}
          </div>
        </div>
      </div>

      {dueDates.length > 0 ? (
        <section data-testid="employee-onboarding-due-calendar">
          <h3 className="mb-2 text-sm font-semibold">Календарь сроков</h3>
          <ul className="space-y-1 text-sm">
            {dueDates.map(({ item, date }) => (
              <li key={item.item_id} className={item.is_overdue ? "text-red-700 dark:text-red-300" : undefined}>
                {date.toLocaleDateString("ru-RU")} — {item.title}
                {item.is_overdue ? " (просрочено)" : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      ) : null}

      <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
          <thead className="bg-zinc-50 text-left text-xs uppercase tracking-wide text-zinc-500 dark:bg-zinc-900/60">
            <tr>
              <th className="px-3 py-2">Пункт</th>
              <th className="px-3 py-2">Срок</th>
              <th className="px-3 py-2">Ответственный</th>
              <th className="px-3 py-2">Приоритет</th>
              <th className="px-3 py-2">Статус</th>
              <th className="px-3 py-2">Комментарий</th>
              {!readOnly ? <th className="px-3 py-2" /> : null}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-900">
            {detail.checklist_items.map((item) => (
              <React.Fragment key={item.item_id}>
                <tr
                  key={item.item_id}
                  data-testid={`onboarding-checklist-item-${item.item_id}`}
                  className={item.is_overdue ? "bg-red-50/50 dark:bg-red-950/20" : undefined}
                >
                  <td className="px-3 py-2">{item.title}</td>
                  <td className="px-3 py-2">{formatDueDate(item.due_date)}</td>
                  <td className="px-3 py-2">{onboardingAssigneeLabel(item.assignee_kind)}</td>
                  <td className="px-3 py-2">{onboardingPriorityLabel(item.priority)}</td>
                  <td className="px-3 py-2">{onboardingChecklistStatusLabel(item.status)}</td>
                  <td className="px-3 py-2">{item.comment || "—"}</td>
                  {!readOnly ? (
                    <td className="px-3 py-2">
                      {item.status === "pending" ? (
                        <div className="flex flex-wrap gap-2">
                          <button
                            type="button"
                            disabled={busyKey != null}
                            className="text-sm text-emerald-700 hover:underline dark:text-emerald-300"
                            data-testid={`onboarding-complete-item-${item.item_id}`}
                            onClick={() =>
                              void runAction(`complete-${item.item_id}`, () =>
                                completeOnboardingChecklistItem(detail.onboarding_id, item.item_id),
                              )
                            }
                          >
                            Выполнено
                          </button>
                          <button
                            type="button"
                            disabled={busyKey != null}
                            className="text-sm text-zinc-600 hover:underline dark:text-zinc-400"
                            data-testid={`onboarding-skip-item-${item.item_id}`}
                            onClick={() =>
                              void runAction(`skip-${item.item_id}`, () =>
                                skipOnboardingChecklistItem(detail.onboarding_id, item.item_id),
                              )
                            }
                          >
                            Пропустить
                          </button>
                        </div>
                      ) : null}
                      <button
                        type="button"
                        className="mt-1 block text-xs text-blue-700 hover:underline dark:text-blue-300"
                        data-testid={`onboarding-audit-item-${item.item_id}`}
                        onClick={() => void toggleAudit(item.item_id, detail.onboarding_id)}
                      >
                        История
                      </button>
                      {!readOnly ? (
                        <div className="mt-2 flex gap-1">
                          <input
                            value={attachmentUrl[item.item_id] || ""}
                            onChange={(e) =>
                              setAttachmentUrl((prev) => ({ ...prev, [item.item_id]: e.target.value }))
                            }
                            placeholder="URL вложения"
                            className="w-full rounded border px-2 py-1 text-xs dark:border-zinc-700 dark:bg-zinc-900"
                            data-testid={`onboarding-attachment-url-${item.item_id}`}
                          />
                          <button
                            type="button"
                            disabled={busyKey != null || !(attachmentUrl[item.item_id] || "").trim()}
                            className="text-xs text-blue-700 hover:underline dark:text-blue-300"
                            onClick={() =>
                              void runAction(`attach-${item.item_id}`, () =>
                                addOnboardingChecklistAttachment(
                                  detail.onboarding_id,
                                  item.item_id,
                                  (attachmentUrl[item.item_id] || "").trim(),
                                ),
                              )
                            }
                          >
                            +
                          </button>
                        </div>
                      ) : null}
                      {(item.attachments?.length ?? 0) > 0 ? (
                        <ul className="mt-1 space-y-1 text-xs">
                          {(item.attachments ?? []).map((attachment) => (
                            <li key={attachment.attachment_id}>
                              <a href={attachment.file_url} target="_blank" rel="noreferrer" className="text-blue-700 dark:text-blue-300">
                                вложение
                              </a>
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </td>
                  ) : null}
                </tr>
                {expandedAuditItemId === item.item_id ? (
                  <tr>
                    <td colSpan={readOnly ? 6 : 7} className="bg-zinc-50 px-3 py-2 dark:bg-zinc-900/40">
                      <div data-testid={`onboarding-audit-panel-${item.item_id}`}>
                        {(auditByItem[item.item_id] || []).length === 0 ? (
                          <p className="text-xs text-zinc-500">История изменений пуста.</p>
                        ) : (
                          <ul className="space-y-1 text-xs">
                            {(auditByItem[item.item_id] || []).map((entry) => (
                              <li key={entry.audit_id}>
                                {new Date(entry.created_at).toLocaleString("ru-RU")} —{" "}
                                {onboardingTaskAuditLabel(entry.action)}
                                {entry.actor_name ? ` (${entry.actor_name})` : ""}
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    </td>
                  </tr>
                ) : null}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {!readOnly ? (
        <div className="flex flex-wrap items-end gap-2">
          <label className="block text-sm">
            <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Произвольная задача</span>
            <input
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              data-testid="onboarding-custom-title"
            />
          </label>
          <button
            type="button"
            disabled={busyKey != null || !customTitle.trim()}
            className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
            data-testid="onboarding-add-custom-item"
            onClick={() =>
              void runAction("add-custom", async () => {
                const data = await addCustomOnboardingChecklistItem(
                  detail.onboarding_id,
                  customTitle.trim(),
                );
                setCustomTitle("");
                return data;
              })
            }
          >
            Добавить задачу
          </button>
          <button
            type="button"
            disabled={busyKey != null}
            className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            data-testid="onboarding-complete-program"
            onClick={() =>
              void runAction("complete-program", () => completeEmployeeOnboarding(detail.onboarding_id))
            }
          >
            Завершить адаптацию
          </button>
          <button
            type="button"
            disabled={busyKey != null}
            className="rounded-lg border border-red-300 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:text-red-300"
            data-testid="onboarding-cancel-program"
            onClick={() =>
              void runAction("cancel-program", () =>
                cancelEmployeeOnboarding(detail.onboarding_id, "Отменено HR"),
              )
            }
          >
            Отменить
          </button>
        </div>
      ) : null}
    </div>
  );
}
