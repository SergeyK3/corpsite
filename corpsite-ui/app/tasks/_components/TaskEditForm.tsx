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
  initialValues: TaskEditValues;
  /** Описание и примечание — только для системного администратора (экономия места у обычного пользователя). */
  isSystemAdmin?: boolean;
  saving?: boolean;
  error?: string | null;
  onCancel: () => void;
  onSubmit: (values: TaskEditValues) => Promise<void> | void;
  /** Поле и отправка отчёта (как в карточке просмотра), если действие report разрешено. */
  reportSection?: {
    link: string;
    onLinkChange: (v: string) => void;
    comment: string;
    onCommentChange: (v: string) => void;
    onSend: () => void | Promise<void>;
    disabled?: boolean;
  };
};

export default function TaskEditForm({
  initialValues,
  isSystemAdmin = false,
  saving = false,
  error = null,
  onCancel,
  onSubmit,
  reportSection,
}: TaskEditFormProps) {
  const [values, setValues] = React.useState<TaskEditValues>(initialValues);

  React.useEffect(() => {
    setValues(initialValues);
  }, [
    initialValues.title,
    initialValues.description,
    initialValues.source_note,
    initialValues.due_date,
  ]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await onSubmit({
      title: values.title.trim(),
      description: isSystemAdmin ? values.description : initialValues.description,
      source_note: isSystemAdmin ? values.source_note : initialValues.source_note,
      due_date: values.due_date.trim(),
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
          {!!error && (
            <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              {error}
            </div>
          )}

          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
            <h3 className="mb-3 text-base font-semibold text-zinc-900 dark:text-zinc-50">Данные задачи</h3>

            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-2">
                <label htmlFor="task-edit-title" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                  Название <span className="text-red-400">*</span>
                </label>
                <input
                  id="task-edit-title"
                  value={values.title}
                  onChange={(e) => setValues((prev) => ({ ...prev, title: e.target.value }))}
                  className="h-10 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  placeholder="Название задачи"
                />
              </div>

              {isSystemAdmin ? (
                <>
                  <div className="flex flex-col gap-2">
                    <label htmlFor="task-edit-description" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                      Описание
                    </label>
                    <textarea
                      id="task-edit-description"
                      value={values.description}
                      onChange={(e) => setValues((prev) => ({ ...prev, description: e.target.value }))}
                      rows={5}
                      className="min-h-[120px] resize-y rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2.5 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                      placeholder="Описание"
                    />
                  </div>

                  <div className="flex flex-col gap-2">
                    <label htmlFor="task-edit-source-note" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                      Примечание / источник
                    </label>
                    <textarea
                      id="task-edit-source-note"
                      value={values.source_note}
                      onChange={(e) => setValues((prev) => ({ ...prev, source_note: e.target.value }))}
                      rows={3}
                      className="min-h-[80px] resize-y rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2.5 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                      placeholder="Внутреннее примечание"
                    />
                  </div>
                </>
              ) : null}

              <div className="flex flex-col gap-2">
                <label htmlFor="task-edit-due" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                  Срок (дата)
                </label>
                <input
                  id="task-edit-due"
                  type="date"
                  value={values.due_date}
                  onChange={(e) => setValues((prev) => ({ ...prev, due_date: e.target.value }))}
                  className="h-10 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
                />
              </div>
            </div>
          </div>

          {reportSection ? (
            <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-4">
              <h3 className="mb-3 text-base font-semibold text-zinc-900 dark:text-zinc-50">Отчёт</h3>
              <div className="flex flex-col gap-3">
                <div className="flex flex-col gap-2">
                  <label htmlFor="task-edit-report-link" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                    Ссылка или путь на отчёт
                  </label>
                  <input
                    id="task-edit-report-link"
                    value={reportSection.link}
                    onChange={(e) => reportSection.onLinkChange(e.target.value)}
                    disabled={reportSection.disabled}
                    placeholder="https://... или \\server\share\... или d:\..."
                    className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400 disabled:opacity-60"
                  />
                </div>
                <div className="flex flex-col gap-2">
                  <label htmlFor="task-edit-report-comment" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                    Комментарий к отчёту (при необходимости)
                  </label>
                  <textarea
                    id="task-edit-report-comment"
                    value={reportSection.comment}
                    onChange={(e) => reportSection.onCommentChange(e.target.value)}
                    disabled={reportSection.disabled}
                    rows={3}
                    placeholder="Комментарий"
                    className="min-h-[80px] resize-y rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-2.5 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400 disabled:opacity-60"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => void reportSection.onSend()}
                  disabled={reportSection.disabled}
                  className="self-start rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Отправить отчёт
                </button>
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-60"
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
