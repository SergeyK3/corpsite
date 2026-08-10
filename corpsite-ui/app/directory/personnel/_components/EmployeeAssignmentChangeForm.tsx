"use client";

import * as React from "react";

import { useCurrentUser } from "@/lib/currentUser";
import type { APIError } from "@/lib/types";
import { getPositions } from "../../employees/_lib/api.client";
import type { EmployeeDetails } from "../../employees/_lib/types";
import { changeEmployeeAssignment } from "../_lib/manualAssignmentChangeApi.client";

type Props = {
  employeeId: string;
  details: EmployeeDetails | null;
  onChanged: () => void | Promise<void>;
};

type PositionOption = {
  id: number;
  name: string;
  is_active?: boolean | null;
};

function newCommandKey(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `assignment-change-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function assignmentErrorMessage(error: unknown): string {
  const apiError = error as APIError | undefined;
  const details = apiError?.details as
    | { detail?: { code?: string; message?: string } | string; message?: string }
    | undefined;
  const nestedDetail = details?.detail;
  const code =
    apiError?.code ??
    (typeof nestedDetail === "object" && nestedDetail !== null ? nestedDetail.code : undefined);

  if (apiError?.status === 403) {
    return "Недостаточно прав для изменения назначения.";
  }
  if (code === "ACTIVE_ASSIGNMENT_CARDINALITY_INVALID") {
    return "У сотрудника обнаружено несколько активных назначений. Операция остановлена.";
  }
  if (code === "ACTIVE_ASSIGNMENT_STALE") {
    return "Текущее назначение уже изменилось. Обновите карточку и повторите операцию.";
  }
  if (typeof nestedDetail === "object" && nestedDetail?.message) {
    return nestedDetail.message;
  }
  if (apiError?.message) return apiError.message;
  if (error instanceof Error && error.message) return error.message;
  return "Не удалось изменить назначение. Данные не были сохранены.";
}

export default function EmployeeAssignmentChangeForm({
  employeeId,
  details,
  onChanged,
}: Props) {
  const me = useCurrentUser();
  const allowed = me?.has_hr_enrollment_manager === true;
  const [open, setOpen] = React.useState(false);
  const [positions, setPositions] = React.useState<PositionOption[]>([]);
  const [positionsLoading, setPositionsLoading] = React.useState(false);
  const [positionId, setPositionId] = React.useState("");
  const [startDate, setStartDate] = React.useState("");
  const [comment, setComment] = React.useState("");
  const [idempotencyKey, setIdempotencyKey] = React.useState("");
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const submittingRef = React.useRef(false);

  if (!allowed) return null;

  const activeAssignmentId = Number(details?.active_assignment_id ?? 0);
  const orgUnitId = Number(details?.org_unit?.unit_id ?? 0);
  const currentOrgName = details?.org_unit?.name?.trim() || "—";
  const currentPositionName = details?.position?.name?.trim() || "—";
  const selectedPosition = positions.find((item) => String(item.id) === positionId);
  const canSubmit =
    activeAssignmentId > 0 &&
    orgUnitId > 0 &&
    Number(positionId) > 0 &&
    Boolean(startDate) &&
    Boolean(idempotencyKey) &&
    !saving;

  async function openForm() {
    setOpen(true);
    setPositionId("");
    setStartDate("");
    setComment("");
    setError(null);
    setIdempotencyKey(newCommandKey());
    setPositionsLoading(true);
    try {
      const response = await getPositions({
        limit: 1000,
        offset: 0,
        org_unit_id: orgUnitId > 0 ? orgUnitId : undefined,
        scope: orgUnitId > 0 ? "allowed" : undefined,
      });
      const items = (Array.isArray(response?.items) ? response.items : [])
        .map((item: Record<string, unknown>) => ({
          id: Number(item.position_id ?? item.id),
          name: String(item.name ?? "").trim(),
          is_active: item.is_active as boolean | null | undefined,
        }))
        .filter(
          (item: PositionOption) =>
            Number.isFinite(item.id) && item.id > 0 && Boolean(item.name) && item.is_active !== false,
        )
        .sort(
          (left: PositionOption, right: PositionOption) =>
            left.name.localeCompare(right.name, "ru") || left.id - right.id,
        );
      setPositions(items);
    } catch (loadError) {
      setPositions([]);
      setError(assignmentErrorMessage(loadError));
    } finally {
      setPositionsLoading(false);
    }
  }

  function closeForm() {
    if (submittingRef.current) return;
    setOpen(false);
    setError(null);
  }

  function changeCommandInput(setter: (value: string) => void, value: string) {
    setter(value);
    setError(null);
    setIdempotencyKey(newCommandKey());
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit || submittingRef.current || !selectedPosition) return;

    submittingRef.current = true;
    const confirmed = window.confirm(
      `Оформить новое назначение?\nПрежняя должность: ${currentPositionName}\nНовая должность: ${selectedPosition.name}\nДата начала: ${startDate}`,
    );
    if (!confirmed) {
      submittingRef.current = false;
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await changeEmployeeAssignment(employeeId, {
        expected_assignment_id: activeAssignmentId,
        org_unit_id: orgUnitId,
        position_id: selectedPosition.id,
        start_date: startDate,
        idempotency_key: idempotencyKey,
        ...(comment.trim() ? { comment: comment.trim() } : {}),
      });
      setOpen(false);
      await onChanged();
    } catch (submitError) {
      setError(assignmentErrorMessage(submitError));
    } finally {
      submittingRef.current = false;
      setSaving(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => void openForm()}
        data-testid="assignment-change-open"
        className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
      >
        Оформить новое назначение
      </button>

      {open ? (
        <div className="fixed inset-0 z-[70] flex items-center justify-center p-4" data-testid="assignment-change-form">
          <button
            type="button"
            aria-label="Закрыть"
            className="absolute inset-0 bg-black/40"
            onClick={closeForm}
          />
          <form
            className="relative w-full max-w-lg rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
            onSubmit={(event) => void submit(event)}
          >
            <h2 className="text-lg font-semibold">Оформить новое назначение</h2>
            <p className="mt-1 text-sm text-zinc-500">
              Закроет текущее назначение и создаст новое с указанной даты. Кадровая история сохранится.
            </p>
            <dl className="mt-4 grid gap-3 rounded-lg bg-zinc-50 p-3 text-sm dark:bg-zinc-900">
              <div>
                <dt className="text-xs text-zinc-500">Текущее подразделение</dt>
                <dd data-testid="assignment-change-current-org">{currentOrgName}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Текущая должность</dt>
                <dd>{currentPositionName}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">Текущее назначение</dt>
                <dd data-testid="assignment-change-current-assignment">
                  {activeAssignmentId > 0 ? `#${activeAssignmentId}` : "не найдено"}
                </dd>
              </div>
            </dl>

            <label className="mt-4 block text-sm">
              <span className="text-zinc-600 dark:text-zinc-300">Новая должность</span>
              <select
                value={positionId}
                onChange={(event) => changeCommandInput(setPositionId, event.target.value)}
                disabled={positionsLoading || saving}
                data-testid="assignment-change-position"
                className="mt-1 w-full rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              >
                <option value="">{positionsLoading ? "Загрузка…" : "Выберите должность"}</option>
                {positions.map((position) => (
                  <option key={position.id} value={position.id}>
                    {position.name}
                  </option>
                ))}
              </select>
              {!positionsLoading && positions.length === 0 && !error ? (
                <p className="mt-2 text-sm text-amber-700" role="status">
                  Для текущего подразделения нет доступных действующих должностей.
                </p>
              ) : null}
            </label>

            <label className="mt-3 block text-sm">
              <span className="text-zinc-600 dark:text-zinc-300">Дата начала</span>
              <input
                type="date"
                value={startDate}
                onChange={(event) => changeCommandInput(setStartDate, event.target.value)}
                disabled={saving}
                data-testid="assignment-change-start-date"
                className="mt-1 w-full rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              />
            </label>

            <label className="mt-3 block text-sm">
              <span className="text-zinc-600 dark:text-zinc-300">Комментарий (необязательно)</span>
              <textarea
                value={comment}
                onChange={(event) => changeCommandInput(setComment, event.target.value)}
                disabled={saving}
                data-testid="assignment-change-comment"
                className="mt-1 min-h-20 w-full rounded border border-zinc-300 bg-white px-3 py-2 dark:border-zinc-700 dark:bg-zinc-900"
              />
            </label>

            {activeAssignmentId <= 0 ? (
              <p className="mt-3 text-sm text-amber-700">Активное назначение не найдено. Сохранение недоступно.</p>
            ) : null}
            {error ? (
              <p className="mt-3 text-sm text-red-600 dark:text-red-400" role="alert">
                {error}
              </p>
            ) : null}

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={closeForm}
                disabled={saving}
                className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={!canSubmit}
                data-testid="assignment-change-submit"
                className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </>
  );
}
