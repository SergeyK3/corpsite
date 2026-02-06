// FILE: corpsite-ui/app/page.tsx
import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-3xl px-4 py-10">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6">
          <div className="text-xl font-semibold">Corpsite UI</div>
          <div className="mt-1 text-sm text-zinc-400">Быстрый доступ к разделам (dev).</div>

          <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Link
              href="/tasks"
              className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-4 hover:bg-zinc-900/60"
            >
              <div className="text-sm uppercase tracking-wide text-zinc-300">Задачи</div>
              <div className="mt-1 text-base font-semibold">/tasks</div>
              <div className="mt-1 text-xs text-zinc-500">
                Список задач + карточка + report/approve/reject/archive.
              </div>
            </Link>

            <Link
              href="/regular-tasks"
              className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-4 hover:bg-zinc-900/60"
            >
              <div className="text-sm uppercase tracking-wide text-zinc-300">Regular tasks</div>
              <div className="mt-1 text-base font-semibold">/regular-tasks</div>
              <div className="mt-1 text-xs text-zinc-500">
                Шаблоны: list/create/patch + activate/deactivate.
              </div>
            </Link>
          </div>

          <div className="mt-6 text-xs text-zinc-500">
            Примечание: DEV User ID задаётся на страницах через localStorage (corpsite.devUserId).
          </div>
        </div>
      </div>
    </div>
  );
}
