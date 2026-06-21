// FILE: corpsite-ui/app/admin/system/_components/user-linkage-operations/RepairPreviewPanel.tsx
"use client";

import { useState } from "react";

import {
  mapUserLinkageOperationsApiError,
  postRepairPreview,
  type UserLinkageRepairPreviewResponse,
} from "../../_lib/userLinkageOperationsApi.client";
import {
  diagnosisClass,
  diagnosisLabel,
  diagnosisTone,
  itemActionLabel,
  recommendedActionLabel,
  yesNoLabel,
} from "../../_lib/userLinkageOperationsLabels";
import ErrorBanner from "../shared/ErrorBanner";
import JsonViewer from "../shared/JsonViewer";

type SearchMode = "user" | "employee";

export default function RepairPreviewPanel() {
  const [mode, setMode] = useState<SearchMode>("user");
  const [targetId, setTargetId] = useState("");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<UserLinkageRepairPreviewResponse | null>(null);

  async function onSubmit(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    const id = Number(targetId);
    if (!targetId || Number.isNaN(id) || id < 1) {
      setError("Укажите корректный ID");
      setLoading(false);
      return;
    }
    if (reason.trim().length < 10) {
      setError("Причина должна содержать минимум 10 символов");
      setLoading(false);
      return;
    }

    try {
      const body =
        mode === "user"
          ? { user_id: id, reason: reason.trim() }
          : { employee_id: id, reason: reason.trim() };
      const res = await postRepairPreview(body);
      setResult(res);
    } catch (err) {
      setError(mapUserLinkageOperationsApiError(err, "Не удалось выполнить диагностику привязки"));
    } finally {
      setLoading(false);
    }
  }

  const tone = result ? diagnosisTone(result.diagnosis_code) : null;

  return (
    <section className="space-y-4" data-testid="repair-preview-panel">
      <div>
        <h2 className="text-lg font-semibold">Диагностика привязки</h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Только чтение. Не изменяет привязку пользователя к сотруднику.
        </p>
      </div>

      <form className="space-y-4" onSubmit={(e) => void onSubmit(e)}>
        <div className="flex flex-wrap gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="search-mode"
              checked={mode === "user"}
              onChange={() => setMode("user")}
              data-testid="repair-preview-mode-user"
            />
            Поиск по ID пользователя
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="radio"
              name="search-mode"
              checked={mode === "employee"}
              onChange={() => setMode("employee")}
              data-testid="repair-preview-mode-employee"
            />
            Поиск по ID сотрудника
          </label>
        </div>

        <label className="flex max-w-xs flex-col gap-1 text-sm">
          <span>{mode === "user" ? "ID пользователя" : "ID сотрудника"}</span>
          <input
            type="number"
            min={1}
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            className="rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="repair-preview-target-id"
          />
        </label>

        <label className="flex max-w-lg flex-col gap-1 text-sm">
          <span>Причина (мин. 10 символов)</span>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={3}
            className="rounded border px-2 py-1 dark:border-zinc-600 dark:bg-zinc-900"
            data-testid="repair-preview-reason"
          />
        </label>

        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          data-testid="repair-preview-submit"
        >
          {loading ? "Выполняется…" : "Запустить диагностику"}
        </button>
      </form>

      <ErrorBanner message={error} />

      {loading ? (
        <p className="text-sm text-zinc-500" data-testid="repair-preview-loading">
          Загрузка…
        </p>
      ) : null}

      {result && tone ? (
        <div className="space-y-4" data-testid="repair-preview-result">
          <div className={diagnosisClass(tone)} data-testid="repair-preview-diagnosis">
            <div className="text-xs text-zinc-600 dark:text-zinc-400">Диагноз</div>
            <div className="mt-1 text-lg font-semibold">{diagnosisLabel(result.diagnosis_code)}</div>
            <div className="mt-0.5 text-xs text-zinc-500">{result.diagnosis_code}</div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <Metric label="Готово к выполнению" value={yesNoLabel(result.execute_ready)} />
            <Metric label="Рекомендуемое действие" value={recommendedActionLabel(result.recommended_action)} />
            <Metric label="Действие выполнения" value={itemActionLabel(result.execute_action)} />
            <Metric label="ID запуска" value={`#${result.run_id}`} />
            <Metric label="ID элемента" value={`#${result.item_id}`} />
          </div>

          <JsonViewer title="Текущая привязка" value={result.current_linkage} testId="repair-current-linkage" />
          <JsonViewer title="Кандидат привязки" value={result.candidate_linkage} testId="repair-candidate-linkage" />
          <JsonViewer title="Текущий пользователь" value={result.current_user} />
          <JsonViewer title="Состояние проверки" value={result.review} />
        </div>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 text-sm font-medium">{value}</div>
    </div>
  );
}
