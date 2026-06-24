"use client";

import * as React from "react";

import {
  TemplateField,
  TemplateReadOnlyValue,
  templateFieldInputClassName,
} from "./templateDetailShared";

export const ADVANCED_PLANNING_TITLE = "Дополнительные параметры планирования";

export const CREATE_OFFSET_DAYS_HINT =
  "Создать задачу заранее относительно начала периода.";

export const DUE_OFFSET_DAYS_HINT =
  "Сдвиг срока выполнения относительно стандартного срока.";

export function hasNonDefaultPlanningOffsets(
  createOffsetDays?: number | string | null,
  dueOffsetDays?: number | string | null,
): boolean {
  const create = Number(createOffsetDays ?? 0);
  const due = Number(dueOffsetDays ?? 0);
  return (Number.isFinite(create) && create !== 0) || (Number.isFinite(due) && due !== 0);
}

type TemplateAdvancedPlanningBlockEditProps = {
  mode: "edit";
  createOffsetDays: string;
  dueOffsetDays: string;
  onCreateOffsetDaysChange: (value: string) => void;
  onDueOffsetDaysChange: (value: string) => void;
};

type TemplateAdvancedPlanningBlockViewProps = {
  mode: "view";
  createOffsetDays?: number | null;
  dueOffsetDays?: number | null;
};

type TemplateAdvancedPlanningBlockProps =
  | TemplateAdvancedPlanningBlockEditProps
  | TemplateAdvancedPlanningBlockViewProps;

function FieldHint({ children }: { children: string }) {
  return <p className="text-xs text-zinc-600 dark:text-zinc-400">{children}</p>;
}

function BlockShell({
  open,
  onToggle,
  children,
  toggleType = "button",
}: {
  open: boolean;
  onToggle?: () => void;
  children: React.ReactNode;
  toggleType?: "button" | "static";
}) {
  const headerClassName =
    "flex w-full items-center justify-between gap-3 rounded-xl border border-dashed border-zinc-300 dark:border-zinc-700 bg-zinc-100/50 dark:bg-zinc-900/40 px-4 py-3 text-left text-sm font-medium text-zinc-700 dark:text-zinc-300";

  return (
    <div className="flex flex-col gap-3">
      {toggleType === "button" ? (
        <button type="button" onClick={onToggle} className={headerClassName}>
          <span>{ADVANCED_PLANNING_TITLE}</span>
          <span aria-hidden className="text-xs text-zinc-500 dark:text-zinc-400">
            {open ? "Свернуть" : "Развернуть"}
          </span>
        </button>
      ) : (
        <div className={headerClassName}>
          <span>{ADVANCED_PLANNING_TITLE}</span>
        </div>
      )}

      {open ? (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white/70 dark:bg-zinc-950/70 p-4">
          {children}
        </div>
      ) : null}
    </div>
  );
}

export default function TemplateAdvancedPlanningBlock(props: TemplateAdvancedPlanningBlockProps) {
  if (props.mode === "view") {
    if (!hasNonDefaultPlanningOffsets(props.createOffsetDays, props.dueOffsetDays)) {
      return null;
    }

    return (
      <BlockShell open toggleType="static">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <TemplateField label="Создать за N дней">
            <TemplateReadOnlyValue value={props.createOffsetDays ?? 0} />
            <FieldHint>{CREATE_OFFSET_DAYS_HINT}</FieldHint>
          </TemplateField>
          <TemplateField label="Срок +N дней">
            <TemplateReadOnlyValue value={props.dueOffsetDays ?? 0} />
            <FieldHint>{DUE_OFFSET_DAYS_HINT}</FieldHint>
          </TemplateField>
        </div>
      </BlockShell>
    );
  }

  const [open, setOpen] = React.useState(() =>
    hasNonDefaultPlanningOffsets(props.createOffsetDays, props.dueOffsetDays),
  );

  React.useEffect(() => {
    if (hasNonDefaultPlanningOffsets(props.createOffsetDays, props.dueOffsetDays)) {
      setOpen(true);
    }
  }, [props.createOffsetDays, props.dueOffsetDays]);

  return (
    <BlockShell open={open} onToggle={() => setOpen((value) => !value)}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <TemplateField label="Создать за N дней" htmlFor="template-create-offset">
          <input
            id="template-create-offset"
            value={props.createOffsetDays}
            onChange={(e) => props.onCreateOffsetDaysChange(e.target.value)}
            placeholder="0"
            inputMode="numeric"
            className={templateFieldInputClassName}
          />
          <FieldHint>{CREATE_OFFSET_DAYS_HINT}</FieldHint>
        </TemplateField>

        <TemplateField label="Срок +N дней" htmlFor="template-due-offset">
          <input
            id="template-due-offset"
            value={props.dueOffsetDays}
            onChange={(e) => props.onDueOffsetDaysChange(e.target.value)}
            placeholder="0"
            inputMode="numeric"
            className={templateFieldInputClassName}
          />
          <FieldHint>{DUE_OFFSET_DAYS_HINT}</FieldHint>
        </TemplateField>
      </div>
    </BlockShell>
  );
}
