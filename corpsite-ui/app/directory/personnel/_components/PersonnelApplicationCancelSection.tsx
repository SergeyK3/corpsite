"use client";

import * as React from "react";

import {
  cancelPersonnelApplication,
  mapPersonnelApplicationsApiError,
  type PersonnelApplicationDetail,
} from "../_lib/personnelApplicationsApi.client";

type Props = {
  detail: PersonnelApplicationDetail;
  onCancelled: () => void;
};

export default function PersonnelApplicationCancelSection({ detail, onCancelled }: Props) {
  const [open, setOpen] = React.useState(false);
  const [reason, setReason] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const canCancel =
    !detail.is_read_only && detail.employee_id == null && detail.status !== "cancelled";

  if (!canCancel) return null;

  async function submitCancel() {
    const cleaned = reason.trim();
    if (!cleaned) {
      setError("Укажите причину отмены.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await cancelPersonnelApplication(detail.application_id, cleaned);
      setOpen(false);
      setReason("");
      onCancelled();
    } catch (e) {
      setError(mapPersonnelApplicationsApiError(e, "Не удалось отменить обращение"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="space-y-3" data-testid="personnel-application-cancel-section">
      <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Отмена обращения</h3>
      <p className="text-sm text-zinc-600 dark:text-zinc-400">
        Доступно до создания сотрудника. Действие необратимо.
      </p>
      {!open ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="rounded-lg border border-red-300 px-3 py-2 text-sm text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950/30"
          data-testid="personnel-application-cancel-open"
        >
          Отменить обращение
        </button>
      ) : (
        <div className="space-y-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
          <label className="block text-sm">
            <span className="mb-1 block text-zinc-600 dark:text-zinc-400">Причина отмены *</span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              className="w-full rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              data-testid="personnel-application-cancel-reason"
            />
          </label>
          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
              {error}
            </div>
          ) : null}
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void submitCancel()}
              className="rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              data-testid="personnel-application-cancel-submit"
            >
              Подтвердить отмену
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setOpen(false);
                setReason("");
                setError(null);
              }}
              className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
            >
              Назад
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
