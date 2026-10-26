// FILE: corpsite-ui/app/directory/positions/_components/PositionForm.tsx
"use client";

import * as React from "react";
import {positionSignature,type PositionSaveResult} from "./positionSaveState";
import PositionDetailsFields, {type PositionDetails} from "./PositionDetailsFields";

export type PositionCategory = "leaders" | "medical" | "admin" | "technical" | "other";

export type PositionFormValues = PositionDetails & {
  name: string;
  category: PositionCategory;
};

type PositionFormProps = {
  mode: "create" | "edit";
  initialValues: PositionFormValues;
  orgUnitLabel?: string | null;
  saving?: boolean;
  error?: string | null;
  onSubmit: (values: PositionFormValues) => Promise<PositionSaveResult | void> | PositionSaveResult | void;
  onCancel: () => void;
};

const CATEGORY_OPTIONS: Array<{ value: PositionCategory; label: string }> = [
  { value: "leaders", label: "Руководители" },
  { value: "medical", label: "Медицинские" },
  { value: "admin", label: "Административные" },
  { value: "technical", label: "Технические" },
  { value: "other", label: "Прочие" },
];

export default function PositionForm({
  mode,
  initialValues,
  orgUnitLabel = null,
  saving = false,
  error = null,
  onSubmit,
  onCancel,
}: PositionFormProps) {
  const [values, setValues] = React.useState<PositionFormValues>(initialValues);

  const [savedSignature,setSavedSignature]=React.useState<string|null>(null);
  const [submitError,setSubmitError]=React.useState<string|null>(null);
  // Apply a re-read revision before the form becomes interactive again.
  // A passive effect can otherwise overwrite the first edit after saving.
  React.useLayoutEffect(() => {
    setValues(initialValues);
    setSavedSignature(previous=>previous===positionSignature(initialValues)?previous:null);
  }, [initialValues]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if(saving)return;
    setSubmitError(null);setSavedSignature(null);
    try {
      const result=await onSubmit({...values,name:values.name.trim(),category:values.category});
      if(result){setValues(result.savedValues);setSavedSignature(positionSignature(result.savedValues));}
      else setSubmitError("Сохранение не подтверждено. Проверьте сообщение сервера и повторите попытку.");
    }catch(caught){setSubmitError(caught instanceof Error?caught.message:"Не удалось сохранить должность.");}

  }

  return (
    <form data-testid="position-form" aria-busy={saving} onSubmit={handleSubmit} className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="flex items-start justify-between border-b border-zinc-200 dark:border-zinc-800 px-6 py-5">
        <div>
          <h2 className="text-2xl font-semibold leading-tight text-zinc-900 dark:text-zinc-50">
            {mode === "create" ? "Создание записи" : "Редактирование записи"}
          </h2>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">Должности</p>
        </div>

        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
        >
          Закрыть
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <fieldset disabled={saving} className="mx-auto flex w-full max-w-3xl flex-col gap-5">
          {orgUnitLabel ? (
            <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 px-4 py-3 text-sm text-zinc-700 dark:text-zinc-300">
              <div className="text-xs uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Фильтр отделения
              </div>
              <div className="mt-1 text-zinc-900 dark:text-zinc-50">{orgUnitLabel}</div>
            </div>
          ) : null}

          <div className="flex flex-col gap-2">
            <label htmlFor="name" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Название должности <span className="text-red-400">*</span>
            </label>
            <input
              id="name"
              name="name"
              type="text"
              value={values.name}
              onChange={(e) => setValues((prev) => ({ ...prev, name: e.target.value }))}
              placeholder="Например: Врач"
              autoComplete="off"
              spellCheck={false}
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="category" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Категория <span className="text-red-400">*</span>
            </label>
            <select
              id="category"
              name="category"
              value={values.category}
              onChange={(e) =>
                setValues((prev) => ({
                  ...prev,
                  category: e.target.value as PositionCategory,
                }))
              }
              className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
              required
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value} className="bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <PositionDetailsFields value={values} onChange={details=>setValues(v=>({...v,...details}))} />
        </fieldset>
      </div>

      <div data-testid="position-save-footer" className="shrink-0 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
        {!saving && !!(error||submitError) && (
          <div role="alert" className="mb-3 max-h-32 overflow-y-auto rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
            {error||submitError}
          </div>
        )}
        <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
          disabled={saving}
        >
          Закрыть
        </button>

        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Сохранение..." : savedSignature===positionSignature(values) ? "Сохранено" : "Сохранить"}
        </button>
        </div>
      </div>
    </form>
  );
}
