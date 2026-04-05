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

type NavItem = {
  href: string;
  title: string;
  matchPrefixes?: string[];
};

const PRIMARY_ADMIN_NAV: NavItem[] = [
  {
    href: "/admin/regular-tasks",
    title: "Шаблоны регулярных задач",
    matchPrefixes: ["/admin/regular-tasks", "/regular-tasks"],
  },
  {
    href: "/tasks",
    title: "Задачи",
    matchPrefixes: ["/tasks"],
  },
  {
    href: "/directory/roles",
    title: "Роли",
    matchPrefixes: ["/directory/roles"],
  },
  {
    href: "/directory/contacts",
    title: "Контакты",
    matchPrefixes: ["/directory/contacts"],
  },
  {
    href: "/directory/personnel",
    title: "Персонал",
    matchPrefixes: ["/directory/personnel", "/directory/employees"],
  },
];

const SECONDARY_DIRECTORY_NAV: NavItem[] = [
  {
    href: "/directory/positions",
    title: "Должности",
    matchPrefixes: ["/directory/positions"],
  },
  {
    href: "/directory/working-contacts",
    title: "Рабочие контакты",
    matchPrefixes: ["/directory/working-contacts"],
  },
  {
    href: "/directory/department-groups",
    title: "Группы отделений",
    matchPrefixes: ["/directory/department-groups"],
  },
  {
    href: "/directory/org-unit-types",
    title: "Отделения",
    matchPrefixes: ["/directory/org-unit-types"],
  },
];

function normalizeMsg(msg: string): string {
  const s = String(msg || "").trim();
  return s || "Ошибка";
}

function isUnauthorized(e: any): boolean {
  return Number(e?.status ?? 0) === 401;
}

function isNavItemActive(pathname: string, item: NavItem): boolean {
  const prefixes = item.matchPrefixes?.length ? item.matchPrefixes : [item.href];
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

function SidebarNav({ pathname, items }: { pathname: string; items: NavItem[] }) {
  return (
    <nav className="space-y-1">
      {items.map((it) => {
        const active = isNavItemActive(pathname, it);

        return (
          <Link
            key={it.href}
            href={it.href}
            className={[
              "block rounded-lg border px-2.5 py-1 text-sm leading-tight transition",
              active
                ? "border-zinc-400 dark:border-zinc-600 bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50"
                : "border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700",
            ].join(" ")}
          >
            {it.title}
          </Link>
        );
      })}
    </nav>
  );
}

function RareSidebarGroup({ pathname }: { pathname: string }) {
  const sectionActive = SECONDARY_DIRECTORY_NAV.some((item) => isNavItemActive(pathname, item));
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
          "flex w-full items-center justify-between rounded-lg border px-2.5 py-1 text-left text-sm leading-tight transition",
          sectionActive
            ? "border-zinc-400 dark:border-zinc-600 bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50"
            : "border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700",
        ].join(" ")}
        aria-expanded={open}
        aria-label="Показать дополнительные справочники"
      >
        <span className="text-base font-semibold leading-none">…</span>
        <span className={["text-xs text-zinc-600 dark:text-zinc-400 transition-transform", open ? "rotate-180" : ""].join(" ")}>
          ▾
        </span>
      </button>

      {open ? (
        <div className="ml-2 space-y-0.5 border-l border-zinc-200 dark:border-zinc-800 pl-2">
          {SECONDARY_DIRECTORY_NAV.map((item) => {
            const active = isNavItemActive(pathname, item);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "block rounded-lg px-2.5 py-1 text-sm leading-tight transition",
                  active
                    ? "bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50"
                    : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700 hover:text-zinc-900",
                ].join(" ")}
              >
                {item.title}
              </Link>
            );
          })}
        </div>
      ) : null}
    </div>
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

  if (isLogin) return <>{children}</>;

  return (
    <div className="min-h-[calc(100vh-52px)] bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="w-full px-3 py-2 xl:px-4 xl:py-3">
        <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-2xl font-semibold">{roleTitle}</div>
          </div>

          <button
            onClick={onLogoutClick}
            className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-sm text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700"
          >
            Выйти
          </button>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-3 text-sm text-zinc-600 dark:text-zinc-400">
            Загрузка…
          </div>
        ) : err ? (
          <div className="rounded-2xl border border-red-200 dark:border-red-900/55 bg-red-50 dark:bg-red-950/35 p-3 text-sm text-red-800 dark:text-red-200">
            {err}
          </div>
        ) : isAdmin ? (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[220px_minmax(0,1fr)]">
            <aside className="space-y-2.5">
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-1">
                <div className="space-y-1">
                  <SidebarNav pathname={pathname} items={PRIMARY_ADMIN_NAV} />
                  <RareSidebarGroup pathname={pathname} />
                </div>
              </div>

              {showOrgUnitsPanel ? <OrgUnitsSidebarPanel basePath={orgTreeBasePath} /> : null}
            </aside>

            <section className="min-w-0">{children}</section>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            <section className="min-w-0">
              {forbiddenNonAdminRoute ? (
                <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-4 text-sm text-zinc-600 dark:text-zinc-400">
                  Переход к задачам…
                </div>
              ) : (
                children
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}