"use client";

import { useState } from "react";

import TestPersonnelDataAdminClient from "../../test-personnel-data/_components/TestPersonnelDataAdminClient";
import TechnicalPersonnelOrdersPanel from "./TechnicalPersonnelOrdersPanel";

type CleanupCategory = "test" | "orders";

const CATEGORIES: { id: CleanupCategory; label: string }[] = [
  { id: "test", label: "Тестовые сотрудники и пользователи" },
  { id: "orders", label: "Технические кадровые приказы" },
];

function categoryTabClass(active: boolean): string {
  return [
    "whitespace-nowrap rounded-lg border px-3 py-1.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-zinc-950",
    active
      ? "border-blue-900 bg-blue-600 font-semibold text-white shadow-sm ring-2 ring-blue-300 hover:bg-blue-700 dark:border-blue-200 dark:ring-blue-700"
      : "border-zinc-300 bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  ].join(" ");
}

export default function DataCleanupCenter() {
  const [category, setCategory] = useState<CleanupCategory>("test");

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Очистка данных</h1>
        <p className="text-sm text-zinc-600 dark:text-zinc-400">
          Единый центр с изолированными правилами удаления для каждой категории.
        </p>
      </header>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Категории очистки данных">
        {CATEGORIES.map((item) => {
          const active = category === item.id;
          return (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setCategory(item.id)}
              className={categoryTabClass(active)}
            >
              {item.label}
            </button>
          );
        })}
      </div>
      {category === "test" ? <TestPersonnelDataAdminClient /> : <TechnicalPersonnelOrdersPanel />}
    </div>
  );
}
