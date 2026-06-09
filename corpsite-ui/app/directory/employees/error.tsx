"use client";

import { formatThrownError } from "@/lib/i18n";

export default function Error({ error }: { error: Error }) {
  const message = formatThrownError(error, { fallback: "Не удалось загрузить список сотрудников." });

  return (
    <div className="p-6">
      <div className="border rounded p-4 bg-white dark:bg-zinc-950">
        <div className="font-semibold">Ошибка загрузки</div>
        <div className="text-sm text-gray-600 mt-2">{message}</div>
      </div>
    </div>
  );
}
