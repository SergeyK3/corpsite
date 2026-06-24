"use client";

import * as React from "react";

import { taskActionLabel, taskSourceLabel, taskStatusLabel, uiFieldLabel } from "@/lib/i18n";
import { splitTaskDescription } from "@/lib/taskDescription";
import {
  isHttpUrl,
  reportLinkDisplayText,
  reportLinkHint,
  resolveTaskReportLink,
  shouldShowReportSection,
} from "@/lib/taskReportLink";

type AllowedAction = "report" | "approve" | "reject" | "archive";
type TaskAction = AllowedAction;

export type TaskDetailPanelProps = {
  drawerLoading: boolean;
  selectedItem: any | null;
  drawerError: string | null;
  uiNotice: string;
  showExecutorColumn: boolean;
  selectedEditable: boolean;
  showDeleteButtons: boolean;
  isSystemAdmin: boolean;
  saving: boolean;
  reportLink: string;
  reason: string;
  onReportLinkChange: (value: string) => void;
  onReasonChange: (value: string) => void;
  onEdit: () => void;
  onDelete: (permanent: boolean) => void;
  onRunAction: (action: TaskAction) => void;
};

function taskIdOf(t: any): number {
  return Number(t?.task_id ?? t?.id ?? 0);
}

function allowedActionsOf(t: any): AllowedAction[] {
  const raw = t?.allowed_actions;
  const all: AllowedAction[] = ["report", "approve", "reject", "archive"];

  if (Array.isArray(raw)) {
    return raw
      .map((x) => String(x ?? "").trim().toLowerCase())
      .filter((x): x is AllowedAction => all.includes(x as AllowedAction));
  }

  if (raw && typeof raw === "object") {
    return all.filter((key) => Boolean(raw[key]));
  }

  return [];
}

function statusTextOf(t: any): string {
  const sRu = String(t?.status_name_ru ?? "").trim();
  if (sRu) return sRu;

  const sCode = String(t?.status_code ?? "").trim();
  if (sCode) return taskStatusLabel(sCode);

  const sLegacy = String(t?.status ?? "").trim();
  if (sLegacy) return taskStatusLabel(sLegacy);

  const sid = t?.status_id;
  if (sid != null) return `Статус №${sid}`;

  return "—";
}

function formatDeadline(t: any): string {
  const raw =
    t?.due_at ??
    t?.due_date ??
    t?.deadline ??
    t?.deadline_at ??
    t?.deadline_date ??
    t?.due ??
    null;

  if (!raw) return "—";
  const s = String(raw).trim();
  if (!s) return "—";

  if (/^\d{2}\.\d{2}\.\d{4}/.test(s)) return s;

  const d = new Date(s);
  if (!Number.isFinite(d.getTime())) return s;

  try {
    return d.toLocaleDateString("ru-RU");
  } catch {
    return s;
  }
}

function normalizeTaskKind(value: any): string {
  const s = String(value ?? "").trim().toLowerCase();
  if (s === "adhoc" || s === "regular") return s;
  return s ? "other" : "";
}

function taskKindLabelOf(src: any): string {
  const v = normalizeTaskKind(src?.task_kind);
  if (v === "adhoc") return "Разовая";
  if (v === "regular") return "Регулярная";
  if (v === "other") return "Прочее";
  return "—";
}

function executorRoleLabelOf(src: any): string {
  const roleRu = String(
    src?.executor_role_name_ru ??
      src?.role_name_ru ??
      src?.target_role_name_ru ??
      src?.executor_role_ru ??
      "",
  ).trim();
  if (roleRu) return roleRu;

  const roleName = String(
    src?.executor_role_name ??
      src?.role_name ??
      src?.target_role_name ??
      src?.executor_role ??
      "",
  ).trim();
  if (roleName) return roleName;

  const roleCode = String(
    src?.executor_role_code ??
      src?.role_code ??
      src?.target_role_code ??
      "",
  ).trim();
  if (roleCode) return roleCode;

  const roleId = Number(src?.executor_role_id ?? src?.role_id ?? 0);
  if (Number.isFinite(roleId) && roleId > 0) return `Роль #${roleId}`;

  const person = String(src?.executor_name ?? "").trim();
  return person || "—";
}

function executorPersonLabelOf(src: any): string {
  return String(src?.executor_name ?? "").trim();
}

function fmtDtRu(raw: any): string {
  if (!raw) return "";
  const s = String(raw).trim();
  if (!s) return "";

  const d = new Date(s);
  if (!Number.isFinite(d.getTime())) return s;

  try {
    return d.toLocaleString("ru-RU");
  } catch {
    return s;
  }
}

function roleLabelOfReport(src: any, kind: "submitted" | "approved"): string {
  const nameKey = kind === "submitted" ? "report_submitted_by_role_name" : "report_approved_by_role_name";
  const codeKey = kind === "submitted" ? "report_submitted_by_role_code" : "report_approved_by_role_code";
  const idKey = kind === "submitted" ? "report_submitted_by" : "report_approved_by";

  const name = String(src?.[nameKey] ?? "").trim();
  if (name) return name;

  const code = String(src?.[codeKey] ?? "").trim();
  if (code) return code;

  const id = src?.[idKey];
  if (id != null && String(id).trim()) return `ID ${String(id)}`;

  return "—";
}

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {}

  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

type ReportUiState = "none" | "draft" | "sent_waiting" | "approved" | "rejected_or_archived";

function computeReportUiState(src: any): ReportUiState {
  const statusCode = String(src?.status_code ?? "").trim().toUpperCase();
  const link = resolveTaskReportLink(src);
  const submittedAt = src?.report_submitted_at ?? null;
  const approvedAt = src?.report_approved_at ?? null;

  if (statusCode === "ARCHIVED") return "rejected_or_archived";
  if (statusCode === "REJECTED") return "rejected_or_archived";
  if (approvedAt) return "approved";

  const sent = Boolean(submittedAt) || Boolean(link);
  if (sent) return "sent_waiting";

  return "draft";
}

function reportStatusBadgeText(st: ReportUiState): string {
  if (st === "approved") return "Отчёт согласован";
  if (st === "sent_waiting") return "Отчёт отправлен на согласование";
  if (st === "draft") return "Отчёт не отправлен";
  if (st === "rejected_or_archived") return "Задача отклонена/в архиве";
  return "—";
}

function reportStatusBadgeClass(st: ReportUiState): string {
  if (st === "approved") return "border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200";
  if (st === "sent_waiting") return "border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200";
  if (st === "draft") return "border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-zinc-700 dark:text-zinc-300";
  if (st === "rejected_or_archived") return "border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-zinc-600 dark:text-zinc-400";
  return "border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-zinc-600 dark:text-zinc-400";
}

export default function TaskDetailPanel({
  drawerLoading,
  selectedItem,
  drawerError,
  uiNotice,
  showExecutorColumn,
  selectedEditable,
  showDeleteButtons,
  isSystemAdmin,
  saving,
  reportLink,
  reason,
  onReportLinkChange,
  onReasonChange,
  onEdit,
  onDelete,
  onRunAction,
}: TaskDetailPanelProps) {
  const [copyHint, setCopyHint] = React.useState("");

  const selectedAllowed = React.useMemo(() => allowedActionsOf(selectedItem), [selectedItem]);
  const selectedStatus = React.useMemo(() => statusTextOf(selectedItem), [selectedItem]);
  const selectedReportUiState = React.useMemo(() => computeReportUiState(selectedItem), [selectedItem]);
  const selectedExecutorRole = React.useMemo(() => executorRoleLabelOf(selectedItem), [selectedItem]);
  const selectedExecutorPerson = React.useMemo(() => executorPersonLabelOf(selectedItem), [selectedItem]);
  const resolvedReportLink = React.useMemo(
    () => resolveTaskReportLink(selectedItem),
    [selectedItem],
  );
  const reportHint = React.useMemo(() => reportLinkHint(resolvedReportLink), [resolvedReportLink]);
  const descriptionParts = React.useMemo(
    () => splitTaskDescription(selectedItem?.description),
    [selectedItem?.description],
  );
  const visibleDescription = descriptionParts.humanText;
  const showDescriptionBlock = Boolean(visibleDescription.trim());
  const showOriginMetadata = isSystemAdmin && descriptionParts.hasOriginMetadata;

  return (
    <div className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {drawerLoading && !selectedItem ? (
          <div className="text-sm text-zinc-600 dark:text-zinc-400">Загрузка...</div>
        ) : !selectedItem ? (
          <div className="text-sm text-zinc-600 dark:text-zinc-400">Задача не выбрана.</div>
        ) : (
          <div className="space-y-5">
            {!!drawerError && (
              <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
                {drawerError}
              </div>
            )}

            {!!uiNotice && (
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-800 dark:text-zinc-200">
                {uiNotice}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-2">
              <div className="rounded-md border border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 px-2 py-1 text-xs text-zinc-800 dark:text-zinc-200">
                {selectedStatus}
              </div>

              <div
                className={[
                  "rounded-md border px-2 py-1 text-xs",
                  reportStatusBadgeClass(selectedReportUiState),
                ].join(" ")}
              >
                {reportStatusBadgeText(selectedReportUiState)}
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <div className="text-xs text-zinc-600 dark:text-zinc-400">ID</div>
                <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{taskIdOf(selectedItem)}</div>
              </div>

              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <div className="text-xs text-zinc-600 dark:text-zinc-400">Дедлайн</div>
                <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{formatDeadline(selectedItem)}</div>
              </div>

              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <div className="text-xs text-zinc-600 dark:text-zinc-400">Тип задачи</div>
                <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{taskKindLabelOf(selectedItem)}</div>
              </div>

              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <div className="text-xs text-zinc-600 dark:text-zinc-400">Источник</div>
                <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">
                  {taskSourceLabel(selectedItem?.source_kind)}
                </div>
              </div>

              {showExecutorColumn ? (
                <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4 sm:col-span-2">
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">Роль</div>
                  <div className="mt-1 text-sm text-zinc-900 dark:text-zinc-50">{selectedExecutorRole}</div>
                  {selectedExecutorPerson && selectedExecutorPerson !== selectedExecutorRole ? (
                    <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">{selectedExecutorPerson}</div>
                  ) : null}
                </div>
              ) : null}
            </div>

            {showDescriptionBlock ? (
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <div className="text-xs text-zinc-600 dark:text-zinc-400">Описание</div>
                <div className="mt-2 whitespace-pre-wrap text-sm text-zinc-900 dark:text-zinc-50">
                  {visibleDescription}
                </div>
              </div>
            ) : null}

            {showOriginMetadata ? (
              <details className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <summary className="cursor-pointer text-xs font-medium text-zinc-600 dark:text-zinc-400">
                  Служебная информация
                </summary>
                <div className="mt-3 space-y-1 text-sm text-zinc-900 dark:text-zinc-50">
                  {descriptionParts.originMetadata.source ? (
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">Источник:</span>{" "}
                      {descriptionParts.originMetadata.source}
                    </div>
                  ) : null}
                  {descriptionParts.originMetadata.run_id ? (
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">{uiFieldLabel("run_id")}:</span>{" "}
                      {descriptionParts.originMetadata.run_id}
                    </div>
                  ) : null}
                  {descriptionParts.originMetadata.occurrence_date ? (
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">
                        {uiFieldLabel("occurrence_date")}:
                      </span>{" "}
                      {descriptionParts.originMetadata.occurrence_date}
                    </div>
                  ) : null}
                  {descriptionParts.originMetadata.run_kind ? (
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">{uiFieldLabel("run_kind")}:</span>{" "}
                      {descriptionParts.originMetadata.run_kind}
                    </div>
                  ) : null}
                  {descriptionParts.originMetadata.period ? (
                    <div>
                      <span className="text-zinc-600 dark:text-zinc-400">{uiFieldLabel("period")}:</span>{" "}
                      {descriptionParts.originMetadata.period}
                    </div>
                  ) : null}
                  {descriptionParts.originMetadata.run_id ? (
                    <div className="pt-2">
                      <a
                        href={`/regular-task-runs?run_id=${encodeURIComponent(descriptionParts.originMetadata.run_id)}`}
                        className="text-sm text-blue-600 dark:text-blue-400 underline"
                      >
                        Журнал запусков
                      </a>
                    </div>
                  ) : null}
                </div>
              </details>
            ) : null}

            {String(selectedItem?.source_note ?? "").trim() ? (
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <div className="text-xs text-zinc-600 dark:text-zinc-400">Примечание</div>
                <div className="mt-2 whitespace-pre-wrap text-sm text-zinc-900 dark:text-zinc-50">
                  {String(selectedItem?.source_note ?? "").trim()}
                </div>
              </div>
            ) : null}

            {shouldShowReportSection(selectedItem) ? (
              <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
                <div className="mb-2 text-xs text-zinc-600 dark:text-zinc-400">Отчёт</div>

                {resolvedReportLink && isHttpUrl(resolvedReportLink) ? (
                  <div className="space-y-2">
                    <a
                      href={resolvedReportLink}
                      target="_blank"
                      rel="noreferrer"
                      className="break-all text-sm text-blue-600 dark:text-blue-400 underline"
                    >
                      {resolvedReportLink}
                    </a>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={async () => {
                          const ok = await copyToClipboard(resolvedReportLink);
                          setCopyHint(ok ? "Ссылка скопирована" : "Не удалось скопировать");
                          window.setTimeout(() => setCopyHint(""), 1500);
                        }}
                        className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-xs text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                      >
                        Скопировать путь
                      </button>

                      {copyHint ? <div className="text-xs text-zinc-600 dark:text-zinc-400">• {copyHint}</div> : null}
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <div className="break-all text-sm text-zinc-800 dark:text-zinc-200">
                      {reportLinkDisplayText(resolvedReportLink)}
                    </div>

                    {resolvedReportLink ? (
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={async () => {
                            const ok = await copyToClipboard(resolvedReportLink);
                            setCopyHint(ok ? "Путь скопирован" : "Не удалось скопировать");
                            window.setTimeout(() => setCopyHint(""), 1500);
                          }}
                          className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-xs text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700"
                        >
                          Скопировать путь
                        </button>

                        {reportHint ? (
                          <div className="text-xs text-zinc-600 dark:text-zinc-400">{reportHint}</div>
                        ) : null}

                        {copyHint ? <div className="text-xs text-zinc-600 dark:text-zinc-400">• {copyHint}</div> : null}
                      </div>
                    ) : null}
                  </div>
                )}

                {selectedItem?.report_submitted_at ? (
                  <div className="mt-3 text-xs text-zinc-600 dark:text-zinc-400">
                    Отчёт отправлен:{" "}
                    <span className="text-zinc-800 dark:text-zinc-200">{fmtDtRu(selectedItem?.report_submitted_at)}</span>
                  </div>
                ) : null}

                {selectedItem?.report_submitted_by ? (
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">
                    Отправил:{" "}
                    <span className="text-zinc-800 dark:text-zinc-200">
                      {roleLabelOfReport(selectedItem, "submitted")}
                    </span>
                  </div>
                ) : null}

                {selectedItem?.report_approved_at ? (
                  <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                    Решение принято:{" "}
                    <span className="text-zinc-800 dark:text-zinc-200">{fmtDtRu(selectedItem?.report_approved_at)}</span>
                  </div>
                ) : null}

                {selectedItem?.report_approved_by ? (
                  <div className="text-xs text-zinc-600 dark:text-zinc-400">
                    Принял решение:{" "}
                    <span className="text-zinc-800 dark:text-zinc-200">
                      {roleLabelOfReport(selectedItem, "approved")}
                    </span>
                  </div>
                ) : null}

                {String(selectedItem?.report_current_comment ?? "").trim() ? (
                  <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
                    Комментарий:{" "}
                    <span className="text-zinc-800 dark:text-zinc-200">
                      {String(selectedItem?.report_current_comment ?? "").trim()}
                    </span>
                  </div>
                ) : null}
              </div>
            ) : null}

            {selectedAllowed.includes("report") ? (
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Ссылка или путь на отчёт</label>
                <input
                  value={reportLink}
                  onChange={(e) => onReportLinkChange(e.target.value)}
                  placeholder="https://... или \\server\share\... или d:\..."
                  className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                />
              </div>
            ) : null}

            {selectedAllowed.length > 0 ? (
              <div className="flex flex-col gap-2">
                <label className="text-sm font-medium text-zinc-800 dark:text-zinc-200">Причина / комментарий</label>
                <textarea
                  value={reason}
                  onChange={(e) => onReasonChange(e.target.value)}
                  rows={4}
                  placeholder="Комментарий для действия"
                  className="min-h-[96px] resize-y rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                />
              </div>
            ) : null}
          </div>
        )}
      </div>

      {selectedItem ? (
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
            {selectedEditable ? (
              <button
                type="button"
                onClick={onEdit}
                disabled={saving || drawerLoading}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
              >
                Изменить
              </button>
            ) : null}

            {showDeleteButtons ? (
              <button
                type="button"
                onClick={() => onDelete(false)}
                disabled={saving || drawerLoading}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
              >
                Удалить
              </button>
            ) : null}

            {isSystemAdmin ? (
              <button
                type="button"
                onClick={() => onDelete(true)}
                disabled={saving || drawerLoading}
                className="rounded-lg border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-2 text-sm text-red-800 dark:text-red-200 transition hover:bg-red-50 dark:bg-red-950/35 disabled:opacity-60"
              >
                Удалить навсегда
              </button>
            ) : null}

            {selectedAllowed.includes("report") ? (
              <button
                type="button"
                onClick={() => onRunAction("report")}
                disabled={saving || drawerLoading}
                className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:opacity-60"
              >
                {taskActionLabel("report")}
              </button>
            ) : null}

            {selectedAllowed.includes("approve") ? (
              <button
                type="button"
                onClick={() => onRunAction("approve")}
                disabled={saving || drawerLoading}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
              >
                {taskActionLabel("approve")}
              </button>
            ) : null}

            {selectedAllowed.includes("reject") ? (
              <button
                type="button"
                onClick={() => onRunAction("reject")}
                disabled={saving || drawerLoading}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
              >
                {taskActionLabel("reject")}
              </button>
            ) : null}

            {selectedAllowed.includes("archive") ? (
              <button
                type="button"
                onClick={() => {
                  const ok = window.confirm("Переместить задачу в архив?");
                  if (ok) onRunAction("archive");
                }}
                disabled={saving || drawerLoading}
                className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
              >
                {taskActionLabel("archive")}
              </button>
            ) : null}
        </div>
      ) : null}
    </div>
  );
}
