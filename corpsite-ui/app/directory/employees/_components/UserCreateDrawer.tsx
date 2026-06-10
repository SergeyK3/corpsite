// FILE: corpsite-ui/app/directory/employees/_components/UserCreateDrawer.tsx
"use client";

import * as React from "react";

import UserCreateForm, {
  type RoleOption,
  type UserCreateFormValues,
} from "./UserCreateForm";

type UserCreateDrawerProps = {
  open: boolean;
  fullName: string;
  orgUnitLabel: string;
  initialValues: UserCreateFormValues;
  roleOptions: RoleOption[];
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (values: UserCreateFormValues) => Promise<void> | void;
};

export default function UserCreateDrawer({
  open,
  fullName,
  orgUnitLabel,
  initialValues,
  roleOptions,
  saving = false,
  error = null,
  onClose,
  onSubmit,
}: UserCreateDrawerProps) {
  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex">
      <div className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div className="relative ml-auto h-full w-full max-w-[720px] border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl">
        <UserCreateForm
          fullName={fullName}
          orgUnitLabel={orgUnitLabel}
          initialValues={initialValues}
          roleOptions={roleOptions}
          saving={saving}
          error={error}
          onCancel={onClose}
          onSubmit={onSubmit}
        />
      </div>
    </div>
  );
}
