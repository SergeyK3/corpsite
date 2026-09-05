// FILE: corpsite-ui/app/admin/system/_components/SystemAdminClient.tsx
"use client";

import Link from "next/link";
import { useState } from "react";

import { useCurrentUser } from "@/lib/currentUser";
import {
  canSeeTestPersonnelAdmin,
  TEST_PERSONNEL_ADMIN_HREF,
} from "@/lib/testPersonnelDeletionNav";

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
    "whitespace-nowrap rounded-lg border px-3 py-1.5 text-sm font-medium transition xl:px-2 xl:text-xs 2xl:px-3 2xl:text-sm",
    active
      ? "border-blue-900 bg-blue-600 font-semibold text-white shadow-sm ring-2 ring-blue-300 dark:border-blue-200 dark:ring-blue-700"
      : "border-zinc-300 bg-zinc-100 text-zinc-800 hover:bg-zinc-200 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700",
  ].join(" ");
}

export default function SystemAdminClient() {
  const me = useCurrentUser();
  const [activeTab, setActiveTab] = useState<MainTab>("users");

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-semibold">Кабинет системного администратора</h1>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Управление пользователями, доступами, зачислением и аудитом (ADR-042 Phase C1).
        </p>
      </header>

      <TelegramStatusPanel />

      <nav className="flex flex-wrap gap-2 xl:flex-nowrap xl:gap-1 2xl:gap-2" aria-label="Разделы кабинета">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={tabButtonClass(activeTab === tab.id)}
            aria-current={activeTab === tab.id ? "page" : undefined}
          >
            {tab.label}
          </button>
        ))}
        <Link href="/admin/system/personnel-lifecycle" className={tabButtonClass(false)}>
          Жизненный цикл
        </Link>
        {canSeeTestPersonnelAdmin(me) ? (
          <Link href={TEST_PERSONNEL_ADMIN_HREF} className={tabButtonClass(false)}>
            Тестовые данные
          </Link>
        ) : null}
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
