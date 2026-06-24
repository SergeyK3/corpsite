"use client";

import * as React from "react";

import { uiFieldLabel } from "@/lib/i18n";
import {
  TemplateField,
  TemplateReadOnlyValue,
  TemplateSection,
  scheduleTypeFormLabel,
  templateTextareaClassName,
} from "./templateDetailShared";
import TemplateAdvancedPlanningBlock from "./TemplateAdvancedPlanningBlock";

export type TemplateViewItem = {
  regular_task_id: number;
  title: string;
  description?: string | null;
  is_active: boolean;
  schedule_type?: string | null;
  schedule_params?: Record<string, unknown> | null;
  create_offset_days?: number | null;
  due_offset_days?: number | null;
  executor_role_id?: number | null;
  executor_role_name?: string | null;
  executor_role_code?: string | null;
  owner_unit_id?: number | null;
  owner_unit_name?: string | null;
  created_at?: string | null;
  archived_at?: string | null;
  updated_at?: string | null;
};

type TemplateViewPanelProps = {
  template: TemplateViewItem;
  error?: string | null;
  hasOwnerDefect?: boolean;
  roleLabel: string;
  formatDateTime: (value?: string | null) => string;
  footer?: React.ReactNode;
};

function ownerUnitDisplay(template: TemplateViewItem): string {
  const name = String(template.owner_unit_name ?? "").trim();
  const id = template.owner_unit_id;
  if (name && id != null) return `${name} (#${id})`;
  if (name) return name;
  if (id != null) return `#${id}`;
  return "—";
}

export default function TemplateViewPanel({
  template,
  error = null,
  hasOwnerDefect = false,
  roleLabel,
  formatDateTime,
  footer,
}: TemplateViewPanelProps) {
  return (
    <div className="flex h-full flex-col bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-5">
          {!!error && (
            <div className="rounded-xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 px-4 py-3 text-sm text-red-800 dark:text-red-200">
              {error}
            </div>
          )}

          {hasOwnerDefect ? (
            <div className="rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/30 px-4 py-3 text-sm text-amber-900 dark:text-amber-200">
              Диагностика: у шаблона не заполнено отделение.
            </div>
          ) : null}

          <TemplateSection
            title="Основные данные"
            description="Название и описание шаблона регулярной задачи."
          >
            <div className="flex flex-col gap-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <TemplateField label="Ид">
                  <TemplateReadOnlyValue value={template.regular_task_id} />
                </TemplateField>
                <TemplateField label="Статус">
                  <TemplateReadOnlyValue value={template.is_active ? "Активен" : "Архивный"} />
                </TemplateField>
                <TemplateField label="Создан">
                  <TemplateReadOnlyValue value={formatDateTime(template.created_at)} />
                </TemplateField>
                <TemplateField label="Архивирован">
                  <TemplateReadOnlyValue value={formatDateTime(template.archived_at)} />
                </TemplateField>
              </div>

              <TemplateField label="Отчёт">
                <TemplateReadOnlyValue value={template.title} />
              </TemplateField>

              <TemplateField label="Описание">
                <div
                  className={`${templateTextareaClassName} min-h-[144px] whitespace-pre-wrap bg-zinc-100/70 dark:bg-zinc-900/70`}
                >
                  {template.description?.trim() ? template.description : "—"}
                </div>
              </TemplateField>
            </div>
          </TemplateSection>

          <TemplateSection title="Расписание" description="Периодичность генерации задач.">
            <div className="flex flex-col gap-4">
              <TemplateField label="Периодичность">
                <TemplateReadOnlyValue value={scheduleTypeFormLabel(template.schedule_type)} />
              </TemplateField>

              <TemplateAdvancedPlanningBlock
                mode="view"
                createOffsetDays={template.create_offset_days}
                dueOffsetDays={template.due_offset_days}
              />
            </div>
          </TemplateSection>

          <TemplateSection title="Параметры расписания" description="JSON-параметры генерации.">
            <TemplateField label={`${uiFieldLabel("schedule_params")} (JSON)`}>
              <pre
                className={`${templateTextareaClassName} min-h-[240px] overflow-auto font-mono bg-zinc-100/70 dark:bg-zinc-900/70`}
              >
                {JSON.stringify(template.schedule_params ?? {}, null, 2)}
              </pre>
            </TemplateField>
          </TemplateSection>

          <TemplateSection title="Исполнитель" description="Роль, для которой создаётся задача.">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <TemplateField label="ID роли исполнителя">
                <TemplateReadOnlyValue value={template.executor_role_id ?? "—"} />
              </TemplateField>
              <TemplateField label="Исполнитель">
                <TemplateReadOnlyValue value={roleLabel} />
              </TemplateField>
            </div>
          </TemplateSection>

          <TemplateSection
            title="Подразделение-владелец"
            description="Выберите подразделение-владелец шаблона."
          >
            <TemplateField label="Подразделение">
              <TemplateReadOnlyValue value={ownerUnitDisplay(template)} />
            </TemplateField>
          </TemplateSection>
        </div>
      </div>

      {footer ? (
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-zinc-200 dark:border-zinc-800 px-6 py-4">
          {footer}
        </div>
      ) : null}
    </div>
  );
}
