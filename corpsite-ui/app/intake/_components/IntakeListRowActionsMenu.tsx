"use client";

import * as React from "react";

type Props = {
  index: number;
  readOnly?: boolean;
  testIdPrefix: string;
  onEdit: () => void;
  onDelete: () => void;
};

export default function IntakeListRowActionsMenu({
  index,
  readOnly,
  testIdPrefix,
  onEdit,
  onDelete,
}: Props) {
  const [open, setOpen] = React.useState(false);
  const menuRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    function onDocumentClick(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocumentClick);
    return () => document.removeEventListener("mousedown", onDocumentClick);
  }, [open]);

  if (readOnly) return null;

  return (
    <div className="relative inline-flex" ref={menuRef}>
      <button
        type="button"
        aria-label="Действия"
        aria-haspopup="menu"
        aria-expanded={open}
        data-testid={`${testIdPrefix}-actions-${index}`}
        className="rounded-lg border border-zinc-300 px-2 py-1 text-sm text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        onClick={() => setOpen((value) => !value)}
      >
        ⋮
      </button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 min-w-36 rounded-lg border border-zinc-200 bg-white py-1 shadow-sm dark:border-zinc-800 dark:bg-zinc-950"
          data-testid={`${testIdPrefix}-actions-menu-${index}`}
        >
          <button
            type="button"
            role="menuitem"
            className="block w-full px-3 py-1.5 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-900"
            data-testid={`${testIdPrefix}-row-edit-${index}`}
            onClick={() => {
              setOpen(false);
              onEdit();
            }}
          >
            Редактировать
          </button>
          <button
            type="button"
            role="menuitem"
            className="block w-full px-3 py-1.5 text-left text-sm text-red-700 hover:bg-red-50 dark:text-red-300 dark:hover:bg-red-950/40"
            data-testid={`${testIdPrefix}-row-delete-${index}`}
            onClick={() => {
              setOpen(false);
              onDelete();
            }}
          >
            Удалить
          </button>
        </div>
      ) : null}
    </div>
  );
}
