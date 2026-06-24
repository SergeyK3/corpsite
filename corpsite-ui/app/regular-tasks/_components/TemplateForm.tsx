// FILE: corpsite-ui/app/regular-tasks/_components/TemplateForm.tsx
"use client";

import * as React from "react";

import { uiFieldLabel } from "@/lib/i18n";
import { resolveScheduleParamsOnTypeChange } from "@/lib/regularTaskScheduleParams";
import {
  SCHEDULE_TYPE_FORM_OPTIONS,
  TEMPLATE_FORM_ID,
  TemplateField,
  TemplateSection,
  scheduleTypeFormLabel,
  templateFieldInputClassName,
  templateTextareaClassName,
} from "./templateDetailShared";
import TemplateAdvancedPlanningBlock from "./TemplateAdvancedPlanningBlock";

export { TEMPLATE_FORM_ID, SCHEDULE_TYPE_FORM_OPTIONS } from "./templateDetailShared";

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
  initialValues,
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

  const ownerUnitIds = React.useMemo(
    () => new Set(ownerUnitOptions.map((option) => String(option.unit_id))),
    [ownerUnitOptions],
  );
  const legacyOwnerUnitId =
    values.owner_unit_id && !ownerUnitIds.has(values.owner_unit_id) ? values.owner_unit_id : null;

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

          <TemplateSection
            title="Основные данные"
            description="Название и описание шаблона регулярной задачи."
          >
            <div className="flex flex-col gap-4">
              <TemplateField label="Отчёт" htmlFor="template-title" required>
                <input
                  id="template-title"
                  value={values.title}
                  onChange={(e) => setValues((prev) => ({ ...prev, title: e.target.value }))}
                  placeholder="Например: Отчёт по приёмному отделению — месячный"
                  className={templateFieldInputClassName}
                />
              </TemplateField>

              <TemplateField label="Описание" htmlFor="template-description">
                <textarea
                  id="template-description"
                  value={values.description}
                  onChange={(e) => setValues((prev) => ({ ...prev, description: e.target.value }))}
                  placeholder="Краткое описание назначения шаблона"
                  rows={6}
                  className={`${templateTextareaClassName} min-h-[144px]`}
                />
              </TemplateField>
            </div>
          </TemplateSection>

          <TemplateSection title="Расписание" description="Периодичность генерации задач.">
            <div className="flex flex-col gap-4">
              <TemplateField label="Периодичность" htmlFor="template-schedule-type">
                <select
                  id="template-schedule-type"
                  value={values.schedule_type}
                  onChange={(e) => {
                    const nextType = e.target.value;
                    setValues((prev) => ({
                      ...prev,
                      schedule_type: nextType,
                      schedule_params: resolveScheduleParamsOnTypeChange(
                        prev.schedule_type,
                        nextType,
                        prev.schedule_params,
                      ),
                    }));
                  }}
                  className={templateFieldInputClassName}
                >
                  <option value="">Выберите периодичность</option>
                  {SCHEDULE_TYPE_FORM_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                  {legacyScheduleType ? (
                    <option value={legacyScheduleType}>
                      {scheduleTypeFormLabel(legacyScheduleType)}
                    </option>
                  ) : null}
                </select>
              </TemplateField>

              <TemplateAdvancedPlanningBlock
                mode="edit"
                createOffsetDays={values.create_offset_days}
                dueOffsetDays={values.due_offset_days}
                onCreateOffsetDaysChange={(value) =>
                  setValues((prev) => ({ ...prev, create_offset_days: value }))
                }
                onDueOffsetDaysChange={(value) =>
                  setValues((prev) => ({ ...prev, due_offset_days: value }))
                }
              />
            </div>
          </TemplateSection>

          <TemplateSection title="Параметры расписания" description="JSON-параметры генерации.">
            <TemplateField label={`${uiFieldLabel("schedule_params")} (JSON)`} htmlFor="template-schedule-params">
              <textarea
                id="template-schedule-params"
                value={values.schedule_params}
                onChange={(e) => setValues((prev) => ({ ...prev, schedule_params: e.target.value }))}
                placeholder='Например: {"byweekday":["TH"],"time":"10:00"}'
                rows={12}
                className={`${templateTextareaClassName} min-h-[240px] font-mono`}
              />
              <div className={`text-sm ${formError ? "text-red-700 dark:text-red-300" : "text-zinc-600 dark:text-zinc-400"}`}>
                {formError ?? "JSON корректен. Форму можно сохранять."}
              </div>
            </TemplateField>
          </TemplateSection>

          <TemplateSection title="Исполнитель" description="Роль, для которой создаётся задача.">
            <TemplateField label="ID роли исполнителя" htmlFor="template-executor-role">
              <input
                id="template-executor-role"
                value={values.executor_role_id}
                onChange={(e) => setValues((prev) => ({ ...prev, executor_role_id: e.target.value }))}
                placeholder="Например: 60"
                inputMode="numeric"
                className={templateFieldInputClassName}
              />
            </TemplateField>
          </TemplateSection>

          <TemplateSection
            title="Подразделение-владелец"
            description="Выберите подразделение-владелец шаблона."
          >
            <TemplateField label="Подразделение" htmlFor="template-owner-unit-select" required>
              <select
                id="template-owner-unit-select"
                value={values.owner_unit_id}
                onChange={(e) => setValues((prev) => ({ ...prev, owner_unit_id: e.target.value }))}
                disabled={ownerUnitLoading}
                className={`${templateFieldInputClassName} disabled:opacity-60`}
              >
                <option value="">
                  {ownerUnitLoading ? "Загрузка подразделений..." : "Выберите подразделение"}
                </option>
                {ownerUnitOptions.map((opt) => (
                  <option key={opt.unit_id} value={String(opt.unit_id)}>
                    {opt.name} (#{opt.unit_id})
                  </option>
                ))}
                {legacyOwnerUnitId ? (
                  <option value={legacyOwnerUnitId}>#{legacyOwnerUnitId} (текущее)</option>
                ) : null}
              </select>
            </TemplateField>
          </TemplateSection>
        </div>
      </div>
    </form>
  );
}
