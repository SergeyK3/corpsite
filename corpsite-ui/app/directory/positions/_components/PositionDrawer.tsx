// FILE: corpsite-ui/app/directory/positions/_components/PositionDrawer.tsx
"use client";

import * as React from "react";
import PositionForm, { type PositionFormValues, type PositionCategory } from "./PositionForm";

type PositionRecord = {
  position_id?: number;
  id?: number;
  name: string;
  category?: string | null;
};

type PositionDrawerProps = {
  open: boolean;
  mode: "create" | "edit";
  position: PositionRecord | null;
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (values: PositionFormValues) => Promise<void> | void;
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

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto h-full w-full max-w-[720px] border-l border-zinc-800 bg-[#050816] shadow-2xl">
        <PositionForm
          mode={mode}
          initialValues={{
            name: position?.name ?? "",
            category: normalizeCategory(position?.category),
          }}
          saving={saving}
          error={error}
          onCancel={onClose}
          onSubmit={onSubmit}
        />
      </div>
    </div>
  );
}