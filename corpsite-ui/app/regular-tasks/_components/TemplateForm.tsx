// FILE: corpsite-ui/app/regular-tasks/_components/TemplateForm.tsx
"use client";

import * as React from "react";

import { scheduleTypeLabel, uiFieldLabel } from "@/lib/i18n";

export const TEMPLATE_FORM_ID = "regular-task-template-form";

export const SCHEDULE_TYPE_FORM_OPTIONS = [
  { value: "weekly", label: "Еженедельно" },
  { value: "monthly", label: "Ежемесячно" },
  { value: "yearly", label: "Ежегодно" },
] as const;

export type TemplateFormValues = {
  title: string;
  description: string;
  executor_role_id: string;
  owner_unit_id: string;
  schedule_type: string;
  schedule_params: string;
  create_offset_days: string;
  due_offset_days: string;
};

export type TemplateFormOwnerUnitOption = {
  unit_id: number;
  name: string;
  code?: string | null;
};

type TemplateFormProps = {
  mode: "create" | "edit";
  initialValues: TemplateFormValues;
  saving?: boolean;
  error?: string | null;
  validate?: (values: TemplateFormValues) => string | null;
  onSubmit: (values: TemplateFormValues) => Promise<void> | void;
  onFormValidationChange?: (error: string | null) => void;
  ownerUnitOptions?: TemplateFormOwnerUnitOption[];
  ownerUnitLoading?: boolean;
};

export default function TemplateForm({
  mode,
  initialValues,
  saving = false,
  error = null,
  validate,
  onSubmit,
  onFormValidationChange,
  ownerUnitOptions = [],
  ownerUnitLoading = false,
}: TemplateFormProps) {
  const [values, setValues] = React.useState<TemplateFormValues>(initialValues);

  React.useEffect(() => {
    setValues(initialValues);
  }, [
    mode,
    initialValues.title,
    initialValues.description,
    initialValues.executor_role_id,
    initialValues.owner_unit_id,
    initialValues.schedule_type,
    initialValues.schedule_params,
    initialValues.create_offset_days,
    initialValues.due_offset_days,
  ]);

  const formError = React.useMemo(() => {
    return validate ? validate(values) : null;
  }, [validate, values]);

  React.useEffect(() => {
    onFormValidationChange?.(formError);
  }, [formError, onFormValidationChange]);

  const hasOwnerUnitOptions = ownerUnitOptions.length > 0;
  const scheduleTypeValues = React.useMemo(
    () => new Set<string>(SCHEDULE_TYPE_FORM_OPTIONS.map((option) => option.value)),
    [],
  );
  const scheduleTypeTrimmed = String(values.schedule_type ?? "").trim();
  const legacyScheduleType =
    scheduleTypeTrimmed && !scheduleTypeValues.has(scheduleTypeTrimmed) ? scheduleTypeTrimmed : null;

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    await onSubmit({
      title: values.title.trim(),
      description: values.description,
      executor_role_id: values.executor_role_id,
      owner_unit_id: values.owner_unit_id,
      schedule_type: values.schedule_type,
      schedule_params: values.schedule_params,
      create_offset_days: values.create_offset_days,
      due_offset_days: values.due_offset_days,
    });
  }

  return (
    <form
      id={TEMPLATE_FORM_ID}
      onSubmit={handleSubmit}
      className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50"
    >
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-5">
          {!!error && (
            <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              {error}
            </div>
          )}

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div className="flex flex-col gap-5">
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-5">
                <div className="mb-4">
                  <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Основные данные</h3>
                  <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                    Название и описание шаблона регулярной задачи.
                  </p>
                </div>

                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-title" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                      Отчёт <span className="text-red-400">*</span>
                    </label>
                    <input
                      id="template-title"
                      value={values.title}
                      onChange={(e) => setValues((prev) => ({ ...prev, title: e.target.value }))}
                      placeholder="Например: Отчёт по приёмному отделению — месячный"
                      className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                    />
                  </div>

                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-description" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                      Описание
                    </label>
                    <textarea
                      id="template-description"
                      value={values.description}
                      onChange={(e) => setValues((prev) => ({ ...prev, description: e.target.value }))}
                      placeholder="Краткое описание назначения шаблона"
                      rows={6}
                      className="min-h-[144px] resize-y rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-3 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                    />
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-5">
                <div className="mb-4">
                  <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Расписание</h3>
                  <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                    Тип расписания и JSON-параметры генерации.
                  </p>
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-schedule-type" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                      Тип расписания
                    </label>
                    <select
                      id="template-schedule-type"
                      value={values.schedule_type}
                      onChange={(e) => setValues((prev) => ({ ...prev, schedule_type: e.target.value }))}
                      className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400"
                    >
                      <option value="">Выберите тип расписания</option>
                      {SCHEDULE_TYPE_FORM_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                      {legacyScheduleType ? (
                        <option value={legacyScheduleType}>
                          {scheduleTypeLabel(legacyScheduleType) || legacyScheduleType}
                        </option>
                      ) : null}
                    </select>
                  </div>

                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-create-offset" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                      Создать за N дней
                    </label>
                    <input
                      id="template-create-offset"
                      value={values.create_offset_days}
                      onChange={(e) => setValues((prev) => ({ ...prev, create_offset_days: e.target.value }))}
                      placeholder="0"
                      inputMode="numeric"
                      className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                    />
                  </div>

                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-due-offset" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                      Срок +N дней
                    </label>
                    <input
                      id="template-due-offset"
                      value={values.due_offset_days}
                      onChange={(e) => setValues((prev) => ({ ...prev, due_offset_days: e.target.value }))}
                      placeholder="0"
                      inputMode="numeric"
                      className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                    />
                  </div>
                </div>

                <div className="mt-4 flex flex-col gap-2">
                  <label htmlFor="template-schedule-params" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                    {uiFieldLabel("schedule_params")} (JSON)
                  </label>
                  <textarea
                    id="template-schedule-params"
                    value={values.schedule_params}
                    onChange={(e) => setValues((prev) => ({ ...prev, schedule_params: e.target.value }))}
                    placeholder='Например: {"byweekday":["TH"],"time":"10:00"}'
                    rows={12}
                    className="min-h-[240px] resize-y rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-3 font-mono text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  />
                  <div className={`text-sm ${formError ? "text-red-700 dark:text-red-300" : "text-zinc-600 dark:text-zinc-400"}`}>
                    {formError ?? "JSON корректен. Форму можно сохранять."}
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-5">
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-5">
                <div className="mb-4">
                  <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Исполнитель</h3>
                  <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                    Укажи ID роли, для которой создаётся задача.
                  </p>
                </div>

                <div className="flex flex-col gap-2">
                  <label htmlFor="template-executor-role" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                    ID роли исполнителя
                  </label>
                  <input
                    id="template-executor-role"
                    value={values.executor_role_id}
                    onChange={(e) => setValues((prev) => ({ ...prev, executor_role_id: e.target.value }))}
                    placeholder="Например: 60"
                    inputMode="numeric"
                    className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                  />
                </div>
              </div>

              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-5">
                <div className="mb-4">
                  <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Подразделение-владелец</h3>
                  <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
                    Выберите подразделение-владелец шаблона.
                  </p>
                </div>

                <div className="flex flex-col gap-3">
                  {hasOwnerUnitOptions ? (
                    <div className="flex flex-col gap-2">
                      <label htmlFor="template-owner-unit-select" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                        Подразделение <span className="text-red-400">*</span>
                      </label>
                      <select
                        id="template-owner-unit-select"
                        value={values.owner_unit_id}
                        onChange={(e) => setValues((prev) => ({ ...prev, owner_unit_id: e.target.value }))}
                        disabled={ownerUnitLoading}
                        className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition focus:border-zinc-400 disabled:opacity-60"
                      >
                        <option value="">Выберите подразделение</option>
                        {ownerUnitOptions.map((opt) => (
                          <option key={opt.unit_id} value={String(opt.unit_id)}>
                            {opt.name} (#{opt.unit_id})
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : null}

                  <div className="flex flex-col gap-2">
                    <label htmlFor="template-owner-unit" className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
                      {uiFieldLabel("owner_unit_id")} <span className="text-red-400">*</span>
                    </label>
                    <input
                      id="template-owner-unit"
                      value={values.owner_unit_id}
                      onChange={(e) => setValues((prev) => ({ ...prev, owner_unit_id: e.target.value }))}
                      placeholder="Например: 54"
                      inputMode="numeric"
                      className="h-11 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-4 py-2 text-sm text-zinc-900 dark:text-zinc-50 outline-none transition placeholder:text-zinc-600 focus:border-zinc-400"
                    />
                  </div>

                  <div className="text-xs text-zinc-600 dark:text-zinc-400">
                    {ownerUnitLoading
                      ? "Загрузка списка подразделений..."
                      : hasOwnerUnitOptions
                        ? "Можно выбрать из списка или ввести ID вручную."
                        : "Список подразделений недоступен, используй ручной ввод ID."}
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 p-5">
                <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">Подсказка</h3>
                <div className="mt-3 space-y-2 text-sm text-zinc-600 dark:text-zinc-400">
                  <p>
                    Для еженедельных шаблонов обычно используют{" "}
                    <span className="text-zinc-800 dark:text-zinc-200">{scheduleTypeLabel("weekly")}</span> (
                    <span className="font-mono text-zinc-600 dark:text-zinc-400">weekly</span>).
                  </p>
                  <p>
                    Для ежемесячных —{" "}
                    <span className="text-zinc-800 dark:text-zinc-200">{scheduleTypeLabel("monthly")}</span> (
                    <span className="font-mono text-zinc-600 dark:text-zinc-400">monthly</span>).
                  </p>
                  <p>
                    Для ежегодных —{" "}
                    <span className="text-zinc-800 dark:text-zinc-200">{scheduleTypeLabel("yearly")}</span> (
                    <span className="font-mono text-zinc-600 dark:text-zinc-400">yearly</span>).
                  </p>
                  <p>JSON должен быть именно объектом, а не массивом.</p>
                  <p>{uiFieldLabel("owner_unit_id")} лучше не оставлять пустым, чтобы не создавать новые дефекты.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </form>
  );
}