// FILE: corpsite-ui/app/directory/employees/_components/EmployeeCreateDrawer.tsx
"use client";

import * as React from "react";

import EmployeeCreateForm, {
  type EmployeeCreateFormValues,
  type OrgUnitOption,
  type PositionOption,
} from "./EmployeeCreateForm";

type EmployeeCreateDrawerProps = {
  open: boolean;
  initialValues: EmployeeCreateFormValues;
  orgUnitOptions: OrgUnitOption[];
  positionOptions: PositionOption[];
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (values: EmployeeCreateFormValues) => Promise<void> | void;
};

export default function EmployeeCreateDrawer({
  open,
  initialValues,
  orgUnitOptions,
  positionOptions,
  saving = false,
  error = null,
  onClose,
  onSubmit,
}: EmployeeCreateDrawerProps) {
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
      <div className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto h-full w-full max-w-[720px] border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl">
        <EmployeeCreateForm
          initialValues={initialValues}
          orgUnitOptions={orgUnitOptions}
          positionOptions={positionOptions}
          saving={saving}
          error={error}
          onCancel={onClose}
          onSubmit={onSubmit}
        />
      </div>
    </div>
  );
}
