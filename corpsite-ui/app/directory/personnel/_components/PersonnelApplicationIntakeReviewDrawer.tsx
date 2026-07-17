"use client";

import * as React from "react";

import { formatPersonnelApplicationDateTime } from "../_lib/personnelApplicationLabels";
import {
  acceptIntakeSection,
  getIntakeReviewState,
  mapPersonnelApplicationsApiError,
  reworkIntakeSection,
  skipIntakeSection,
  transferIntakeToPpr,
  type IntakeReviewSection,
  type IntakeReviewState,
} from "../_lib/personnelApplicationsApi.client";

type Props = {
  applicationId: number | null;
  open: boolean;
  onClose: () => void;
  onTransferred?: () => void;
};

function renderPayload(payload: Record<string, unknown> | unknown[]): React.ReactNode {
  if (Array.isArray(payload)) {
    if (payload.length === 0) return <span className="text-zinc-500">Нет записей</span>;
    return (
      <pre className="overflow-x-auto rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-900">
        {JSON.stringify(payload, null, 2)}
      </pre>
    );
  }
  return (
    <pre className="overflow-x-auto rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-900">
      {JSON.stringify(payload, null, 2)}
    </pre>
  );
}

function statusBadgeClass(status: string): string {
  switch (status) {
    case "accepted":
      return "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200";
    case "rework_requested":
      return "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200";
    case "skipped":
      return "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";
    default:
      return "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200";
  }
}

export default function PersonnelApplicationIntakeReviewDrawer({
  applicationId,
  open,
  onClose,
  onTransferred,
}: Props) {
  const [loading, setLoading] = React.useState(false);
  const [busySection, setBusySection] = React.useState<string | null>(null);
  const [transferring, setTransferring] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [state, setState] = React.useState<IntakeReviewState | null>(null);
  const [reworkSection, setReworkSection] = React.useState<string | null>(null);
  const [reworkComment, setReworkComment] = React.useState("");

  const reload = React.useCallback(async () => {
    if (applicationId == null) return;
    setLoading(true);
    setError(null);
    try {
      const data = await getIntakeReviewState(applicationId);
      setState(data);
    } catch (e) {
      setState(null);
      setError(mapPersonnelApplicationsApiError(e, "Не удалось загрузить review"));
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  React.useEffect(() => {
    if (!open || applicationId == null) {
      setState(null);
      setError(null);
      setReworkSection(null);
      setReworkComment("");
      return;
    }
    void reload();
  }, [open, applicationId, reload]);

  async function runSectionAction(
    section: IntakeReviewSection,
    action: "accept" | "skip" | "rework",
  ) {
    if (applicationId == null) return;
    setBusySection(section.section_code);
    setError(null);
    try {
      let next: IntakeReviewState;
      if (action === "accept") {
        next = await acceptIntakeSection(applicationId, section.section_code);
      } else if (action === "skip") {
        next = await skipIntakeSection(applicationId, section.section_code);
      } else {
        if (!reworkComment.trim()) {
          setError("Укажите комментарий для доработки.");
          return;
        }
        next = await reworkIntakeSection(applicationId, section.section_code, reworkComment.trim());
        setReworkSection(null);
        setReworkComment("");
      }
      setState(next);
    } catch (e) {
      setError(mapPersonnelApplicationsApiError(e, "Не удалось выполнить действие"));
    } finally {
      setBusySection(null);
    }
  }

  async function handleTransfer() {
    if (applicationId == null) return;
    setTransferring(true);
    setError(null);
    try {
      await transferIntakeToPpr(applicationId);
      await reload();
      onTransferred?.();
    } catch (e) {
      setError(mapPersonnelApplicationsApiError(e, "Не удалось перенести данные в PPR"));
    } finally {
      setTransferring(false);
    }
  }

  if (!open) return null;

  const transferDone = state?.transfer?.status === "completed";

  return (
    <div className="fixed inset-0 z-[70] flex justify-end" data-testid="intake-review-drawer">
      <button type="button" aria-label="Закрыть" className="absolute inset-0 bg-black/30" onClick={onClose} />
      <aside className="relative flex h-full w-full max-w-4xl flex-col border-l border-zinc-200 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-start justify-between gap-3 border-b border-zinc-200 px-4 py-4 dark:border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold">Проверка анкеты #{applicationId ?? "—"}</h2>
            {state?.transfer?.transferred_at ? (
              <p className="mt-1 text-sm text-zinc-500">
                Перенос выполнен {formatPersonnelApplicationDateTime(state.transfer.transferred_at)}
                {state.transfer.transferred_by_user_id
                  ? ` · user #${state.transfer.transferred_by_user_id}`
                  : ""}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
          >
            Закрыть
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          {loading ? <p className="text-sm text-zinc-500">Загрузка…</p> : null}
          {error ? <p className="mb-3 text-sm text-red-600">{error}</p> : null}

          {state ? (
            <div className="space-y-4">
              {state.sections.map((section) => (
                <section
                  key={section.section_code}
                  className="rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
                  data-testid={`intake-review-section-${section.section_code}`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h3 className="font-medium text-zinc-900 dark:text-zinc-50">{section.section_label}</h3>
                      <span
                        className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${statusBadgeClass(section.status)}`}
                      >
                        {section.status}
                      </span>
                      {section.rework_comment ? (
                        <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">
                          Комментарий: {section.rework_comment}
                        </p>
                      ) : null}
                    </div>
                    {!transferDone ? (
                      <div className="flex flex-wrap gap-2">
                        {!section.is_empty ? (
                          <button
                            type="button"
                            disabled={busySection != null}
                            onClick={() => void runSectionAction(section, "accept")}
                            className="rounded-lg bg-emerald-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                          >
                            Принять
                          </button>
                        ) : null}
                        {section.is_empty ? (
                          <button
                            type="button"
                            disabled={busySection != null}
                            onClick={() => void runSectionAction(section, "skip")}
                            className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
                          >
                            Пропустить
                          </button>
                        ) : null}
                        <button
                          type="button"
                          disabled={busySection != null}
                          onClick={() => {
                            setReworkSection(section.section_code);
                            setReworkComment(section.rework_comment || "");
                          }}
                          className="rounded-lg border border-amber-300 px-3 py-1.5 text-sm text-amber-800 dark:border-amber-900 dark:text-amber-300"
                        >
                          Вернуть на доработку
                        </button>
                      </div>
                    ) : null}
                  </div>
                  <div className="mt-3">{renderPayload(section.payload as Record<string, unknown> | unknown[])}</div>
                  {reworkSection === section.section_code ? (
                    <div className="mt-3 space-y-2">
                      <textarea
                        value={reworkComment}
                        onChange={(e) => setReworkComment(e.target.value)}
                        className="w-full rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                        rows={3}
                        placeholder="Комментарий для претендента / HR"
                      />
                      <button
                        type="button"
                        disabled={busySection != null}
                        onClick={() => void runSectionAction(section, "rework")}
                        className="rounded-lg bg-amber-600 px-3 py-1.5 text-sm text-white disabled:opacity-50"
                      >
                        Отправить на доработку
                      </button>
                    </div>
                  ) : null}
                </section>
              ))}

              {state.transfer_blocked_reason && !state.can_transfer ? (
                <p className="text-sm text-zinc-500">{state.transfer_blocked_reason}</p>
              ) : null}

              {state.can_transfer && !transferDone ? (
                <button
                  type="button"
                  disabled={transferring}
                  onClick={() => void handleTransfer()}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                  data-testid="intake-transfer-button"
                >
                  {transferring ? "Перенос…" : "Перенести в PPR"}
                </button>
              ) : null}

              {state.transfer ? (
                <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900">
                  <div className="font-medium">Журнал переноса</div>
                  <div className="mt-1">Статус: {state.transfer.status}</div>
                  <div>Результат: {state.transfer.result || "—"}</div>
                  <div>Разделы: {state.transfer.sections_transferred.join(", ") || "—"}</div>
                  {state.transfer.error_message ? (
                    <div className="mt-1 text-red-600">{state.transfer.error_message}</div>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </aside>
    </div>
  );
}
