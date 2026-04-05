"use client";

type WorkingContactItem = {
  id?: number;
  user_id?: number | null;
  full_name?: string | null;
  login?: string | null;
  phone?: string | null;
  telegram_username?: string | null;
  role_name?: string | null;
  role_name_ru?: string | null;
  unit_name?: string | null;
  unit_name_ru?: string | null;
  is_active?: boolean | null;
};

type WorkingContactsTableProps = {
  items?: WorkingContactItem[] | null;
  total?: number;
  limit?: number;
  offset?: number;
  loading?: boolean;
  onOpen: (item: WorkingContactItem) => void;
  onChangePage: (nextOffset: number) => void;
};

function itemIdOf(item: WorkingContactItem): number {
  return Number(item.id ?? item.user_id ?? 0);
}

function textOrDash(value?: string | null): string {
  return String(value ?? "").trim() || "—";
}

function displayRole(item: WorkingContactItem): string {
  return textOrDash(item.role_name_ru ?? item.role_name);
}

function displayUnit(item: WorkingContactItem): string {
  return textOrDash(item.unit_name_ru ?? item.unit_name);
}

function displayTelegram(item: WorkingContactItem): string {
  const raw = String(item.telegram_username ?? "").trim();
  if (!raw) return "—";
  return raw.startsWith("@") ? raw : `@${raw}`;
}

export default function WorkingContactsTable({
  items,
  total,
  limit,
  offset,
  loading,
  onOpen,
  onChangePage,
}: WorkingContactsTableProps) {
  const safeItems = Array.isArray(items) ? items : [];
  const safeTotal =
    typeof total === "number" && Number.isFinite(total) && total >= 0 ? total : safeItems.length;
  const safeLimit =
    typeof limit === "number" && Number.isFinite(limit) && limit > 0 ? limit : 100;
  const safeOffset =
    typeof offset === "number" && Number.isFinite(offset) && offset >= 0 ? offset : 0;
  const safeLoading = Boolean(loading);

  const page = Math.floor(safeOffset / safeLimit) + 1;
  const pages = Math.max(1, Math.ceil(Math.max(safeTotal, 1) / safeLimit));

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead>
            <tr className="bg-zinc-100 dark:bg-zinc-900 text-left">
              <th className="w-[72px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                ID
              </th>
              <th className="min-w-[250px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                ФИО
              </th>
              <th className="min-w-[180px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Логин
              </th>
              <th className="min-w-[170px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Телефон
              </th>
              <th className="min-w-[170px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Telegram
              </th>
              <th className="min-w-[240px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Роль
              </th>
              <th className="min-w-[220px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Отделение
              </th>
              <th className="w-[120px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Статус
              </th>
              <th className="w-[130px] px-3 py-2 text-[11px] font-medium uppercase tracking-[0.08em] text-zinc-600 dark:text-zinc-400">
                Действие
              </th>
            </tr>
          </thead>

          <tbody>
            {safeItems.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-3 py-3 text-[13px] text-zinc-600 dark:text-zinc-400">
                  {safeLoading ? "Загрузка..." : "Записи не найдены."}
                </td>
              </tr>
            ) : (
              safeItems.map((item) => (
                <tr
                  key={itemIdOf(item)}
                  className="cursor-pointer border-t border-zinc-200 dark:border-zinc-800 align-middle transition hover:bg-zinc-100 dark:hover:bg-zinc-800"
                  onClick={() => onOpen(item)}
                >
                  <td className="px-3 py-2 text-[13px] leading-5 text-zinc-900 dark:text-zinc-50">{itemIdOf(item)}</td>

                  <td className="px-3 py-2 text-[13px] leading-5 text-zinc-900 dark:text-zinc-50">
                    {textOrDash(item.full_name)}
                  </td>

                  <td className="px-3 py-2 text-[13px] leading-5 text-zinc-700 dark:text-zinc-300">
                    {textOrDash(item.login)}
                  </td>

                  <td className="px-3 py-2 text-[13px] leading-5 text-zinc-700 dark:text-zinc-300">
                    {textOrDash(item.phone)}
                  </td>

                  <td className="px-3 py-2 text-[13px] leading-5 text-zinc-700 dark:text-zinc-300">
                    {displayTelegram(item)}
                  </td>

                  <td className="px-3 py-2 text-[13px] leading-5 text-zinc-700 dark:text-zinc-300">
                    {displayRole(item)}
                  </td>

                  <td className="px-3 py-2 text-[13px] leading-5 text-zinc-700 dark:text-zinc-300">
                    {displayUnit(item)}
                  </td>

                  <td className="px-3 py-2">
                    {item.is_active ? (
                      <span className="inline-flex rounded-md border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 px-2 py-0.5 text-[12px] text-emerald-800 dark:text-emerald-200">
                        Да
                      </span>
                    ) : (
                      <span className="inline-flex rounded-md border border-zinc-300 dark:border-zinc-700 bg-zinc-100 dark:bg-zinc-900 px-2 py-0.5 text-[12px] text-zinc-600 dark:text-zinc-400">
                        Нет
                      </span>
                    )}
                  </td>

                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpen(item);
                      }}
                      className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-2.5 py-1 text-[12px] leading-4 text-zinc-900 dark:text-zinc-50 transition hover:bg-zinc-200 dark:hover:bg-zinc-700"
                    >
                      Открыть
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t border-zinc-200 dark:border-zinc-800 px-3 py-2 text-sm">
        <div className="text-zinc-600 dark:text-zinc-400">
          Страница {page} из {pages}
          {safeLoading ? " (обновление...)" : ""}
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            className="rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-50"
            disabled={safeOffset <= 0 || safeLoading}
            onClick={() => onChangePage(Math.max(0, safeOffset - safeLimit))}
          >
            Назад
          </button>

          <button
            type="button"
            className="rounded border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-zinc-800 dark:text-zinc-200 transition hover:bg-zinc-200 dark:hover:bg-zinc-700 disabled:opacity-50"
            disabled={safeOffset + safeLimit >= safeTotal || safeLoading}
            onClick={() => onChangePage(safeOffset + safeLimit)}
          >
            Вперёд
          </button>
        </div>
      </div>
    </div>
  );
}