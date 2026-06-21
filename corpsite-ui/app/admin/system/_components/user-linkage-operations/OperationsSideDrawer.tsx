// FILE: corpsite-ui/app/admin/system/_components/user-linkage-operations/OperationsSideDrawer.tsx
"use client";

type OperationsSideDrawerProps = {
  open: boolean;
  title: string;
  onClose: () => void;
  loading?: boolean;
  testId?: string;
  children: React.ReactNode;
};

export default function OperationsSideDrawer({
  open,
  title,
  onClose,
  loading = false,
  testId,
  children,
}: OperationsSideDrawerProps) {
  if (!open && !loading) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/30"
      role="dialog"
      aria-modal="true"
      data-testid={testId}
    >
      <div className="h-full w-full max-w-xl overflow-y-auto border-l border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="rounded border px-2 py-1 text-sm dark:border-zinc-600"
            data-testid={testId ? `${testId}-close` : undefined}
          >
            Закрыть
          </button>
        </div>
        {loading ? (
          <p className="text-sm text-zinc-500" data-testid={testId ? `${testId}-loading` : undefined}>
            Загрузка…
          </p>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
