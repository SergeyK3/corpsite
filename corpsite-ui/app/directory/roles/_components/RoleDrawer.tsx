// FILE: corpsite-ui/app/directory/roles/_components/RoleDrawer.tsx
"use client";

import * as React from "react";
import RoleForm, { type RoleFormValues } from "./RoleForm";

type RoleRecord = {
  role_id?: number | null;
  id?: number | null;
  role_code: string;
  role_name: string;
  description?: string | null;
  is_active?: boolean | null;
};

type RoleDrawerProps = {
  open: boolean;
  mode: "create" | "edit";
  role: RoleRecord | null;
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (values: RoleFormValues) => Promise<void> | void;
};

function getInitialValues(role: RoleRecord | null): RoleFormValues {
  return {
    role_code: role?.role_code ?? "",
    role_name: role?.role_name ?? "",
    description: role?.description ?? "",
    is_active: role?.is_active ?? true,
  };
}

export default function RoleDrawer({
  open,
  mode,
  role,
  saving = false,
  error = null,
  onClose,
  onSubmit,
}: RoleDrawerProps) {
  React.useEffect(() => {
    if (!open) return;

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-zinc-600/35 backdrop-blur-sm" onClick={onClose} />

      <div className="relative ml-auto h-full w-full max-w-[760px] border-l border-white/10 bg-white shadow-2xl">
        <RoleForm
          mode={mode}
          initialValues={getInitialValues(role)}
          saving={saving}
          error={error}
          onCancel={onClose}
          onSubmit={onSubmit}
        />
      </div>
    </div>
  );
}