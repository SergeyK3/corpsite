// FILE: corpsite-ui/app/directory/employees/_components/EmployeeTransferDrawer.tsx
"use client";

import * as React from "react";

import type { EmployeeDetails } from "../_lib/types";
import EmployeeTransferForm, { type EmployeeTransferFormValues } from "./EmployeeTransferForm";

type EmployeeTransferDrawerProps = {
  open: boolean;
  details: EmployeeDetails | null;
  initialToOrgUnitId?: string;
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (values: EmployeeTransferFormValues) => Promise<void> | void;
};

export default function EmployeeTransferDrawer({
  open,
  details,
  initialToOrgUnitId,
  saving = false,
  error = null,
  onClose,
  onSubmit,
}: EmployeeTransferDrawerProps) {
  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open && !saving) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, saving]);

  if (!open || !details) return null;

  return (
    <div className="fixed inset-0 z-[60] flex">
      <div
        className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm"
        onClick={saving ? undefined : onClose}
      />
      <div className="relative ml-auto h-full w-full max-w-[720px] border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl">
        <EmployeeTransferForm
          details={details}
          initialToOrgUnitId={initialToOrgUnitId}
          saving={saving}
          error={error}
          onCancel={onClose}
          onSubmit={onSubmit}
        />
      </div>
    </div>
  );
}
