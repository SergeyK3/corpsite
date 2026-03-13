// FILE: corpsite-ui/components/AppShell.tsx
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { isAuthed, logout as authLogout } from "@/lib/auth";

import OrgUnitsSidebarPanel from "./OrgUnitsSidebarPanel";

type MeInfo = {
  user_id?: number;
  role_id?: number;
  role_name_ru?: string;
  role_name?: string;
  full_name?: string;
  login?: string;
};

type NavItem = { href: string; title: string };

type DictionaryNavItem = {
  href: string;
  title: string;
};

const DICTIONARY_ITEMS: DictionaryNavItem[] = [
  { href: "/directory/roles", title: "Роли" },
  { href: "/directory/positions", title: "Должности" },
  { href: "/directory/contacts", title: "Контакты" },
  { href: "/directory/personnel", title: "Персонал" },
  { href: "/directory/working-contacts", title: "Рабочие контакты" },
  { href: "/directory/department-groups", title: "Группы отделений" },
  { href: "/directory/org-unit-types", title: "Отделения" },
];

function normalizeMsg(msg: string): string {
  const s = String(msg || "").trim();
  return s || "Ошибка";
}

function isUnauthorized(e: any): boolean {
  return Number(e?.status ?? 0) === 401;
}

function isPathActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function sectionTitle(pathname: string): string {
  if (pathname.startsWith("/admin/regular-tasks")) return "Шаблоны регулярных задач";
  if (pathname.startsWith("/tasks")) return "Задачи";
  if (pathname.startsWith("/regular-tasks")) return "Шаблоны регулярных задач";
  if (pathname.startsWith("/directory/org")) return "Отделения";
  if (pathname.startsWith("/directory/employees")) return "Сотрудники";
  if (
    pathname.startsWith("/directory/dictionaries") ||
    pathname.startsWith("/directory/roles") ||
    pathname.startsWith("/directory/positions") ||
    pathname.startsWith("/directory/contacts") ||
    pathname.startsWith("/directory/personnel") ||
    pathname.startsWith("/directory/working-contacts") ||
    pathname.startsWith("/directory/department-groups") ||
    pathname.startsWith("/directory/org-unit-types")
  ) {
    return "Справочники";
  }
  if (pathname.startsWith("/directory")) return "Справочники";
  return "";
}

function SidebarNav({ pathname, items }: { pathname: string; items: NavItem[] }) {
  return (
    <nav className="space-y-1">
      {items.map((it) => {
        const active = pathname === it.href || (it.href !== "/tasks" && pathname.startsWith(it.href));

        return (
          <Link
            key={it.href}
            href={it.href}
            className={[
              "block rounded-lg border px-2.5 py-1 text-sm transition",
              active
                ? "border-zinc-600 bg-zinc-900 text-zinc-100"
                : "border-zinc-800 bg-zinc-950/40 text-zinc-200 hover:bg-zinc-900/60",
            ].join(" ")}
          >
            {it.title}
          </Link>
        );
      })}
    </nav>
  );
}

function DictionariesSidebarGroup({ pathname }: { pathname: string }) {
  const sectionActive =
    pathname.startsWith("/directory/dictionaries") ||
    pathname.startsWith("/directory/roles") ||
    pathname.startsWith("/directory/positions") ||
    pathname.startsWith("/directory/contacts") ||
    pathname.startsWith("/directory/personnel") ||
    pathname.startsWith("/directory/working-contacts") ||
    pathname.startsWith("/directory/department-groups") ||
    pathname.startsWith("/directory/org-unit-types");

  const [open, setOpen] = useState<boolean>(sectionActive);

  useEffect(() => {
    if (sectionActive) setOpen(true);
  }, [sectionActive]);

  return (
    <div className="space-y-1">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={[
          "flex w-full items-center justify-between rounded-lg border px-2.5 py-1 text-left text-sm transition",
          sectionActive
            ? "border-zinc-600 bg-zinc-900 text-zinc-100"
            : "border-zinc-800 bg-zinc-950/40 text-zinc-200 hover:bg-zinc-900/60",
        ].join(" ")}
      >
        <span>Справочники</span>
        <span className={["text-xs text-zinc-500 transition-transform", open ? "rotate-180" : ""].join(" ")}>
          ▾
        </span>
      </button>

      {open ? (
        <div className="ml-2 space-y-0.5 border-l border-zinc-800 pl-2">
          {DICTIONARY_ITEMS.map((item) => {
            const active = isPathActive(pathname, item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "flex items-center justify-between rounded-lg px-2.5 py-1 text-sm transition",
                  active
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100",
                ].join(" ")}
              >
                <span>{item.title}</span>
              </Link>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function RightSidebarPlaceholder() {
  return (
    <aside className="hidden xl:block">
      <div className="min-h-[640px] rounded-2xl border border-zinc-800 bg-zinc-900/40 p-2">
        <div className="h-full rounded-xl border border-dashed border-zinc-800 bg-zinc-950/30" />
      </div>
    </aside>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname() || "/tasks";

  const isLogin = pathname === "/login";

  const [me, setMe] = useState<MeInfo | null>(null);
  const [loading, setLoading] = useState<boolean>(!isLogin);
  const [err, setErr] = useState<string | null>(null);

  function redirectToLogin() {
    authLogout();
    router.replace("/login");
  }

  function onLogoutClick() {
    authLogout();
    router.push("/login");
  }

  useEffect(() => {
    if (isLogin) return;

    void (async () => {
      setLoading(true);
      setErr(null);

      if (!isAuthed()) {
        router.replace("/login");
        return;
      }

      try {
        const data = (await apiAuthMe()) as any;
        setMe(data as MeInfo);
      } catch (e: any) {
        if (isUnauthorized(e)) {
          redirectToLogin();
          return;
        }
        setErr(normalizeMsg(e?.message || "Не удалось загрузить профиль"));
        setMe(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [isLogin, router]);

  const roleTitle = useMemo(() => {
    const t = String(me?.role_name_ru ?? me?.role_name ?? "").trim();
    return t || "Сотрудник";
  }, [me]);

  const whoLine = "";

  const roleId = Number(me?.role_id ?? 0);
  const isAdmin = roleId === 2;

  const forbiddenNonAdminRoute =
    !loading &&
    !isAdmin &&
    (pathname.startsWith("/directory") ||
      pathname.startsWith("/regular-tasks") ||
      pathname.startsWith("/admin/regular-tasks"));

  useEffect(() => {
    if (isLogin || loading) return;
    if (!forbiddenNonAdminRoute) return;
    router.replace("/tasks");
  }, [isLogin, loading, forbiddenNonAdminRoute, router]);

  const navTop = useMemo<NavItem[]>(() => {
    if (!isAdmin) return [];

    return [
      { href: "/admin/regular-tasks", title: "Шаблоны регулярных задач" },
      { href: "/tasks", title: "Задачи" },
    ];
  }, [isAdmin]);

  const showOrgUnitsPanel = useMemo(() => {
    if (!isAdmin) return false;

    if (pathname.startsWith("/directory/department-groups")) return false;

    return (
      pathname.startsWith("/tasks") ||
      pathname.startsWith("/admin/regular-tasks") ||
      pathname.startsWith("/regular-tasks") ||
      pathname.startsWith("/directory")
    );
  }, [isAdmin, pathname]);

  const orgTreeBasePath = useMemo(() => {
    if (pathname.startsWith("/tasks")) return "/tasks";
    if (pathname.startsWith("/admin/regular-tasks")) return "/admin/regular-tasks";
    if (pathname.startsWith("/regular-tasks")) return "/regular-tasks";

    if (pathname.startsWith("/directory/roles")) return "/directory/roles";
    if (pathname.startsWith("/directory/positions")) return "/directory/positions";
    if (pathname.startsWith("/directory/contacts")) return "/directory/contacts";
    if (pathname.startsWith("/directory/personnel")) return "/directory/personnel";
    if (pathname.startsWith("/directory/working-contacts")) return "/directory/working-contacts";
    if (pathname.startsWith("/directory/org-unit-types")) return "/directory/org-unit-types";
    if (pathname.startsWith("/directory/org")) return "/directory/org";
    if (pathname.startsWith("/directory/employees")) return "/directory/employees";

    return pathname;
  }, [pathname]);

  const secTitle = useMemo(() => {
    if (forbiddenNonAdminRoute) return "Задачи";
    if (!isAdmin) return "Задачи";
    return sectionTitle(pathname);
  }, [forbiddenNonAdminRoute, isAdmin, pathname]);

  const showRightSidebar = !isAdmin && pathname.startsWith("/tasks");

  if (isLogin) return <>{children}</>;

  return (
    <div className="min-h-[calc(100vh-52px)] bg-zinc-950 text-zinc-100">
      <div className="w-full px-3 py-3 xl:px-4 xl:py-4">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-2xl font-semibold">{roleTitle}</div>
            {whoLine ? <div className="mt-1 text-sm text-zinc-400">{whoLine}</div> : null}
            {secTitle ? <div className="mt-1 text-sm text-zinc-300">{secTitle}</div> : null}
          </div>

          <button
            onClick={onLogoutClick}
            className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-1 text-sm text-zinc-200 hover:bg-zinc-900/60"
          >
            Выйти
          </button>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-3 text-sm text-zinc-400">Загрузка…</div>
        ) : err ? (
          <div className="rounded-2xl border border-red-900/60 bg-red-950/40 p-3 text-sm text-red-200">{err}</div>
        ) : isAdmin ? (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[165px_minmax(0,1fr)]">
            <aside className="space-y-3">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-1.5">
                <div className="space-y-1.5">
                  <SidebarNav pathname={pathname} items={navTop} />
                  <DictionariesSidebarGroup pathname={pathname} />
                </div>
              </div>

              {showOrgUnitsPanel ? <OrgUnitsSidebarPanel basePath={orgTreeBasePath} /> : null}
            </aside>

            <section className="min-w-0">{children}</section>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[180px_minmax(0,1fr)_320px]">
            <aside className="hidden xl:block" />

            <section className="min-w-0">
              {forbiddenNonAdminRoute ? (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-400">
                  Переход к задачам…
                </div>
              ) : (
                children
              )}
            </section>

            {showRightSidebar ? <RightSidebarPlaceholder /> : null}
          </div>
        )}
      </div>
    </div>
  );
}