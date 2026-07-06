// FILE: corpsite-ui/components/PositionCabinetSectionShell.tsx

type Props = {
  title: string;
  children: React.ReactNode;
};

/** Shared card layout for Position Cabinet sections (stub pages and future content). */
export default function PositionCabinetSectionShell({ title, children }: Props) {
  return (
    <div className="bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="w-full px-0 py-0">
        <div className="overflow-hidden rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
          <div className="border-b border-zinc-200 dark:border-zinc-800 px-4 py-3">
            <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">{title}</h1>
          </div>
          <div className="px-4 py-6">{children}</div>
        </div>
      </div>
    </div>
  );
}
