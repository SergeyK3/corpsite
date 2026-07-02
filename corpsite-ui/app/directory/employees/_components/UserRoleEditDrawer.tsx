"use client";

import * as React from "react";

import UserRoleEditForm from "./UserRoleEditForm";

type UserRoleEditDrawerProps = {
  open: boolean;
  login: string;
  currentRoleId: number | null | undefined;
  currentRoleLabel: string;
  saving?: boolean;
  error?: string | null;
  onClose: () => void;
  onSubmit: (roleId: number) => Promise<void> | void;
};

export default function UserRoleEditDrawer({
  open,
  login,
  currentRoleId,
  currentRoleLabel,
  saving = false,
  error = null,
  onClose,
  onSubmit,
}: UserRoleEditDrawerProps) {
  React.useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && open && !saving) onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, saving]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex">
      <div className="absolute inset-0 bg-zinc-600/35 dark:bg-black/50 backdrop-blur-sm" onClick={saving ? undefined : onClose} />
      <div className="relative ml-auto h-full w-full max-w-[720px] border-l border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shadow-2xl">
        <UserRoleEditForm
          login={login}
          currentRoleId={currentRoleId}
          currentRoleLabel={currentRoleLabel}
          saving={saving}
          error={error}
          onCancel={onClose}
          onSubmit={onSubmit}
        />
      </div>
    </div>
  );
}
