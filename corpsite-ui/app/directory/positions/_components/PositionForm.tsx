// FILE: corpsite-ui/app/directory/positions/_components/PositionForm.tsx
"use client";

import * as React from "react";

export type PositionCategory = "leaders" | "medical" | "admin" | "technical" | "other";

export type PositionFormValues = {
  name: string;
  category: PositionCategory;
};

type PositionFormProps = {
  mode: "create" | "edit";
  initialValues: PositionFormValues;
  saving?: boolean;
  error?: string | null;
  onSubmit: (values: PositionFormValues) => Promise<void> | void;
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
  saving = false,
  error = null,
  onSubmit,
  onCancel,
}: PositionFormProps) {
  const [values, setValues] = React.useState<PositionFormValues>(initialValues);

  React.useEffect(() => {
    setValues(initialValues);
  }, [initialValues]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await onSubmit({
      name: values.name.trim(),
      category: values.category,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
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
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
        >
          Закрыть
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
          {!!error && (
            <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              {error}
            </div>
          )}

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
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
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
          {saving ? "Сохранение..." : "Сохранить"}
        </button>
      </div>
    </form>
  );
}