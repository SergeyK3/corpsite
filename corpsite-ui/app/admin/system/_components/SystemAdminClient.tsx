// FILE: corpsite-ui/app/admin/system/_components/SystemAdminClient.tsx
"use client";

import Link from "next/link";
import { useState } from "react";

import AccessTab from "./tabs/AccessTab";
import AssignmentsTab from "./tabs/AssignmentsTab";
import AuditTab from "./tabs/AuditTab";
import EnrollmentTab from "./tabs/EnrollmentTab";
import UserLinkageReviewTab from "./tabs/UserLinkageReviewTab";
import UsersTab from "./tabs/UsersTab";
import VisibilityTab from "./tabs/VisibilityTab";
import TelegramStatusPanel from "./TelegramStatusPanel";

type MainTab =
  | "users"
  | "access"
  | "enrollment"
  | "assignments"
  | "audit"
  | "visibility"
  | "user-linkage-review";

const TABS: { id: MainTab; label: string }[] = [
  { id: "users", label: "Пользователи" },
  { id: "access", label: "Доступы" },
  { id: "visibility", label: "Видимость персонала" },
  { id: "enrollment", label: "Зачисление" },
  { id: "assignments", label: "Назначения" },
  { id: "user-linkage-review", label: "Проверка привязок пользователей" },
  { id: "audit", label: "Аудит безопасности" },
];

function tabButtonClass(active: boolean): string {
  return [
    "rounded-lg px-3 py-1.5 text-sm font-medium transition",
    active
      ? "bg-blue-600 text-white"
      : "bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  ].join(" ");
}

export default function SystemAdminClient() {
  const [activeTab, setActiveTab] = useState<MainTab>("users");

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Кабинет системного администратора</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Управление пользователями, доступами, зачислением и аудитом (ADR-042 Phase C1).
        </p>
        <p className="mt-2">
          <Link
            href="/admin/system/personnel-lifecycle"
            className="text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            Жизненный цикл персонала →
          </Link>
        </p>
      </header>

      <TelegramStatusPanel />

      <nav className="flex flex-wrap gap-2" aria-label="Разделы кабинета">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={tabButtonClass(activeTab === tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-700 dark:bg-zinc-950">
        {activeTab === "users" ? <UsersTab /> : null}
        {activeTab === "access" ? <AccessTab /> : null}
        {activeTab === "visibility" ? <VisibilityTab /> : null}
        {activeTab === "enrollment" ? <EnrollmentTab /> : null}
        {activeTab === "assignments" ? <AssignmentsTab /> : null}
        {activeTab === "user-linkage-review" ? <UserLinkageReviewTab /> : null}
        {activeTab === "audit" ? <AuditTab /> : null}
      </div>
    </div>
  );
}
