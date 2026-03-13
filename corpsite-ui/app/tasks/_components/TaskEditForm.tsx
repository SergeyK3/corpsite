// FILE: corpsite-ui/app/regular-tasks/_components/TemplateForm.tsx
"use client";

import * as React from "react";

export type TemplateFormValues = {
  title: string;
  description: string;
  executor_role_id: string;
  schedule_type: string;
  schedule_params: string;
  create_offset_days: string;
  due_offset_days: string;
};

type TemplateFormProps = {
  mode: "create" | "edit";
  initialValues: TemplateFormValues;
  saving?: boolean;
  error?: string | null;
  validate?: (values: TemplateFormValues) => string | null;
  onSubmit: (values: TemplateFormValues) => Promise<void> | void;
  onCancel: () => void;
};

export default function TemplateForm({
  mode,
  initialValues,
  saving = false,
  error = null,
  validate,
  onSubmit,
  onCancel,
}: TemplateFormProps) {
  const [values, setValues] = React.useState<TemplateFormValues>(initialValues);

  React.useEffect(() => {
    setValues(initialValues);
  }, [
    mode,
    initialValues.title,
    initialValues.description,
    initialValues.executor_role_id,
    initialValues.schedule_type,
    initialValues.schedule_params,
    initialValues.create_offset_days,
    initialValues.due_offset_days,
  ]);

  const formError = React.useMemo(() => {
    return validate ? validate(values) : null;
  }, [validate, values]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await onSubmit({
      title: values.title.trim(),
      description: values.description,
      executor_role_id: values.executor_role_id,
      schedule_type: values.schedule_type,
      schedule_params: values.schedule_params,
      create_offset_days: values.create_offset_days,
      due_offset_days: values.due_offset_days,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex h-full flex-col bg-[#050816] text-zinc-100">
      <div className="flex-1 overflow-y-auto px-5 py-4">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
          {!!error && (
            <div className="rounded-xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
            <div className="flex flex-col gap-4">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-950/30 p-4">
                <div className="mb-3">
                  <h3 className="text-base font-semibold text-zinc-100">Основные данные</h3>
                </div>

                <div className="flex flex-col gap-3">
                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-title" className="text-sm font-medium text-zinc-200">
                      Отчёт <span className="text-red-400">*</span>
                    </label>
                    <input
                      id="template-title"
                      value={values.title}
                      onChange={(e) => setValues((prev) => ({ ...prev, title: e.target.value }))}
                      placeholder="Например: Отчёт по приёмному отделению — месячный"
                      className="h-10 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                    />
                  </div>

                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-description" className="text-sm font-medium text-zinc-200">
                      Описание
                    </label>
                    <textarea
                      id="template-description"
                      value={values.description}
                      onChange={(e) => setValues((prev) => ({ ...prev, description: e.target.value }))}
                      placeholder="Краткое описание назначения шаблона"
                      rows={4}
                      className="min-h-[110px] resize-y rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2.5 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                    />
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-zinc-800 bg-zinc-950/30 p-4">
                <div className="mb-3">
                  <h3 className="text-base font-semibold text-zinc-100">Расписание</h3>
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-schedule-type" className="text-sm font-medium text-zinc-200">
                      Тип расписания
                    </label>
                    <input
                      id="template-schedule-type"
                      list="schedule-type-options"
                      value={values.schedule_type}
                      onChange={(e) => setValues((prev) => ({ ...prev, schedule_type: e.target.value }))}
                      placeholder="weekly / monthly / yearly"
                      className="h-10 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                    />
                    <datalist id="schedule-type-options">
                      <option value="daily" />
                      <option value="weekly" />
                      <option value="monthly" />
                      <option value="yearly" />
                    </datalist>
                  </div>

                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-create-offset" className="text-sm font-medium text-zinc-200">
                      Создать за N дней
                    </label>
                    <input
                      id="template-create-offset"
                      value={values.create_offset_days}
                      onChange={(e) => setValues((prev) => ({ ...prev, create_offset_days: e.target.value }))}
                      placeholder="0"
                      inputMode="numeric"
                      className="h-10 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                    />
                  </div>

                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-due-offset" className="text-sm font-medium text-zinc-200">
                      Срок +N дней
                    </label>
                    <input
                      id="template-due-offset"
                      value={values.due_offset_days}
                      onChange={(e) => setValues((prev) => ({ ...prev, due_offset_days: e.target.value }))}
                      placeholder="0"
                      inputMode="numeric"
                      className="h-10 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                    />
                  </div>
                </div>

                <div className="mt-3 flex flex-col gap-2">
                  <label htmlFor="template-schedule-params" className="text-sm font-medium text-zinc-200">
                    schedule_params (JSON)
                  </label>
                  <textarea
                    id="template-schedule-params"
                    value={values.schedule_params}
                    onChange={(e) => setValues((prev) => ({ ...prev, schedule_params: e.target.value }))}
                    placeholder='Например: {"byweekday":["TH"],"time":"10:00"}'
                    rows={10}
                    className="min-h-[200px] resize-y rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2.5 font-mono text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                  />
                  <div className={`text-sm ${formError ? "text-red-300" : "text-zinc-500"}`}>
                    {formError ?? "JSON корректен. Форму можно сохранять."}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-4">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-950/30 p-4">
                <div className="mb-3">
                  <h3 className="text-base font-semibold text-zinc-100">Исполнитель</h3>
                </div>

                <div className="flex flex-col gap-2">
                  <label htmlFor="template-executor-role" className="text-sm font-medium text-zinc-200">
                    ID роли исполнителя
                  </label>
                  <input
                    id="template-executor-role"
                    value={values.executor_role_id}
                    onChange={(e) => setValues((prev) => ({ ...prev, executor_role_id: e.target.value }))}
                    placeholder="Например: 60"
                    inputMode="numeric"
                    className="h-10 rounded-lg border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-500 focus:border-zinc-600"
                  />
                </div>
              </div>

              <div className="rounded-2xl border border-zinc-800 bg-zinc-950/30 p-4">
                <h3 className="text-base font-semibold text-zinc-100">Подсказка</h3>
                <div className="mt-2 space-y-1.5 text-sm text-zinc-400">
                  <p>
                    Для еженедельных шаблонов обычно используют <span className="text-zinc-200">weekly</span>.
                  </p>
                  <p>
                    Для ежемесячных — <span className="text-zinc-200">monthly</span>.
                  </p>
                  <p>JSON должен быть именно объектом, а не массивом.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-zinc-800 px-5 py-3">
        <button
          type="button"
          onClick={onCancel}
          disabled={saving}
          className="rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-1.5 text-sm text-zinc-200 transition hover:bg-zinc-900/60 disabled:opacity-60"
        >
          Закрыть
        </button>

        <button
          type="submit"
          disabled={saving || !!formError}
          className="rounded-lg bg-blue-600 px-5 py-1.5 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {saving ? "Сохранение..." : mode === "create" ? "Создать" : "Сохранить"}
        </button>
      </div>
    </form>
  );
}