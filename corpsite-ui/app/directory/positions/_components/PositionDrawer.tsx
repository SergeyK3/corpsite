// FILE: corpsite-ui/app/directory/positions/_components/PositionDrawer.tsx
"use client";

import * as React from "react";
import type {PositionSaveResult} from "./positionSaveState";
import PositionForm, { type PositionFormValues, type PositionCategory } from "./PositionForm";

type PositionRecord = { [K in Exclude<keyof PositionFormValues,'name'|'category'>]?: PositionFormValues[K]|null } & {
  position_id?: number;
  id?: number;
  name: string;
  category?: string | null;
  revision?: number;
};

type PositionDrawerProps = {
  open: boolean;
  mode: "create" | "edit";
  position: PositionRecord | null;
  orgUnitLabel?: string | null;
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (values: PositionFormValues) => Promise<PositionSaveResult | void> | PositionSaveResult | void;
};

function normalizeCategory(value: string | null | undefined): PositionCategory {
  const s = String(value || "").trim().toLowerCase();
  if (
    s === "leaders" ||
    s === "medical" ||
    s === "admin" ||
    s === "technical" ||
    s === "other"
  ) {
    return s;
  }
  return "other";
}

export default function PositionDrawer({
  open,
  mode,
  position,
  orgUnitLabel = null,
  saving = false,
  error = null,
  onClose,
  onSubmit,
}: PositionDrawerProps) {
  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const initialValues=React.useMemo<PositionFormValues>(()=>({
    expected_revision:position?.revision,
    name:position?.name??'',category:normalizeCategory(position?.category),
    name_kk:position?.name_kk??'',
    document_nominative_ru:position?.document_nominative_ru??position?.name??'',
    document_possessive_kk:position?.document_possessive_kk??'',
    translation_status:position?.translation_status??'needs_review',
    document_form_status:position?.document_form_status??'needs_review',
    record_kind:position?.record_kind??'standalone',job_code:position?.job_code??'',
    aliases:position?.aliases??[],
  }),[position]);
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto h-full w-full max-w-[720px] border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl">
        <PositionForm
          mode={mode}
          orgUnitLabel={orgUnitLabel}
          initialValues={initialValues}
          saving={saving}
          error={error}
          onCancel={onClose}
          onSubmit={onSubmit}
        />
      </div>
    </div>
  );
}
