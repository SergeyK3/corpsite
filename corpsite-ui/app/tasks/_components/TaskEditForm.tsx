// FILE: corpsite-ui/app/tasks/_components/TaskEditForm.tsx
"use client";

import * as React from "react";

export type TaskEditValues = {
  title: string;
  description: string;
  source_note: string;
  due_date: string;
};

type TaskEditFormProps = {
  mode: "edit";
  initialValues: TaskEditValues;
  saving?: boolean;
  error?: string | null;
  onSubmit: (values: TaskEditValues) => Promise<void> | void;
  onCancel: () => void;
};

export default function TaskEditForm({
  initialValues,
  saving = false,
  error = null,
  onSubmit,
  onCancel,
}: TaskEditFormProps) {
  const [values, setValues] = React.useState<TaskEditValues>(initialValues);

  React.useEffect(() => {
    setValues(initialValues);
  }, [initialValues]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await onSubmit({
      title: values.title.trim(),
      description: values.description,
      source_note: values.source_note,
      due_date: values.due_date,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex h-full flex-col bg-[#050816] text-zinc-100">
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-5">
          {!!error && (
            <div className="rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <div className="flex flex-col gap-2">
            <label htmlFor="title" className="text-sm font-medium text-zinc-200">
              Название задачи <span className="text-red-400">*</span>
            </label>
            <input
              id="title"
              name="title"
              type="text"
              value={values.title}
              onChange={(e) => setValues((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="Например: Подготовить отчет"
              autoComplete="off"
              spellCheck={false}
              className="h-11 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
              required
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="description" className="text-sm font-medium text-zinc-200">
              Описание
            </label>
            <textarea
              id="description"
              name="description"
              value={values.description}
              onChange={(e) => setValues((prev) => ({ ...prev, description: e.target.value }))}
              placeholder="Описание задачи"
              rows={5}
              className="min-h-[120px] resize-y rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-3 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="source_note" className="text-sm font-medium text-zinc-200">
              Примечание
            </label>
            <textarea
              id="source_note"
              name="source_note"
              value={values.source_note}
              onChange={(e) => setValues((prev) => ({ ...prev, source_note: e.target.value }))}
              placeholder="Служебное примечание"
              rows={4}
              className="min-h-[96px] resize-y rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-3 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor="due_date" className="text-sm font-medium text-zinc-200">
              Дедлайн
            </label>
            <input
              id="due_date"
              name="due_date"
              type="date"
              value={values.due_date}
              onChange={(e) => setValues((prev) => ({ ...prev, due_date: e.target.value }))}
              className="h-11 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-100 outline-none transition focus:border-zinc-600"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 border-t border-zinc-800 px-6 py-4">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-2 text-sm text-zinc-200 transition hover:bg-zinc-900/60"
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