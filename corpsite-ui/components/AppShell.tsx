// FILE: corpsite-ui/components/AppShell.tsx
"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import {
  canSeeAdminShell,
  canSeePersonnelIdentityOperationsNav,
  canSeePersonnelLifecycleNav,
  canSeeSysadminCabinetNav,
  isForbiddenAdminRoute,
  isPersonnelIdentityOperationsRoute,
  isPersonnelLifecycleRoute,
} from "@/lib/adminNav";
import {
  canAccessDirectoryRoute,
  canViewPersonnelTasksReadOnly,
  hasPersonnelVisibility,
  shouldShowOrgUnitsPanel,
} from "@/lib/visibilityNav";
import {
  buildPersonnelSidebarNavItems,
  buildVisibilityDirectoryNavItems,
  HR_PROCESSES_NAV_ITEM,
  isHrProcessesRoute,
  isPersonnelDirectoryRoute,
  PERSONNEL_DIRECTORY_NAV_ITEM,
  resolveDirectoryOrgTreeBasePath,
  shouldShowPrimaryAdminNavItem,
} from "@/lib/personnelNav";
import { isAuthed, logout as authLogout } from "@/lib/auth";
import type { MeInfo } from "@/lib/types";
import { shouldShowPositionCabinetNav } from "@/lib/positionCabinetNav";
import { resolveCabinetTitle } from "@/lib/userCabinetTitle";

import OrgUnitsSidebarPanel from "./OrgUnitsSidebarPanel";
import PositionCabinetLibraryLinks from "./PositionCabinetLibraryLinks";
import PositionCabinetNav from "./PositionCabinetNav";

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
    href: "/admin/regular-tasks/catch-up",
    title: "Догоняющий запуск",
    matchPrefixes: ["/admin/regular-tasks/catch-up"],
  },
  {
    href: "/admin/system",
    title: "Кабинет системного администратора",
    matchPrefixes: ["/admin/system"],
  },
  {
    href: "/admin/system/personnel-lifecycle",
    title: "Жизненный цикл персонала",
    matchPrefixes: ["/admin/system/personnel-lifecycle"],
  },
  {
    href: "/admin/system/personnel-identity/operations",
    title: "Операции привязки пользователей",
    matchPrefixes: ["/admin/system/personnel-identity"],
  },
  {
    href: "/admin/sync",
    title: "Синхронизация данных",
    matchPrefixes: ["/admin/sync"],
  },
  {
    href: "/tasks",
    title: "Задачи",
    matchPrefixes: ["/tasks"],
  },
  {
    href: "/directory/roles",
    title: "Роли доступа",
    matchPrefixes: ["/directory/roles"],
  },
  {
    href: "/directory/contacts",
    title: "Контакты",
    matchPrefixes: ["/directory/contacts"],
  },
  PERSONNEL_DIRECTORY_NAV_ITEM,
  HR_PROCESSES_NAV_ITEM,
];

const SECONDARY_DIRECTORY_NAV: NavItem[] = [
  {
    href: "/directory/positions",
    title: "Должности",
    matchPrefixes: ["/directory/positions"],
  },
  {
    href: "/directory/department-groups",
    title: "Типы деятельности",
    matchPrefixes: ["/directory/department-groups"],
  },
  {
    href: "/directory/org-units",
    title: "Отделения",
    matchPrefixes: ["/directory/org-units"],
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
  return prefixes.some((prefix) => {
    if (pathname === prefix) return true;
    if (!pathname.startsWith(`${prefix}/`)) return false;
    if (prefix === "/admin/regular-tasks" && pathname.startsWith("/admin/regular-tasks/catch-up")) {
      return false;
    }
    if (prefix === "/admin/system" && pathname.startsWith("/admin/system/personnel-lifecycle")) {
      return false;
    }
    if (prefix === "/admin/system" && pathname.startsWith("/admin/system/personnel-identity")) {
      return false;
    }
    if (prefix === "/directory/personnel" && pathname.startsWith("/directory/staff")) {
      return false;
    }
    if (prefix === "/directory/staff" && pathname.startsWith("/directory/personnel")) {
      return false;
    }
    return true;
  });
}

function SidebarNav({ pathname, items }: { pathname: string; items: NavItem[] }) {
  return (
    <nav className="space-y-1">
      {items.map((it) => {
        const active = isNavItemActive(pathname, it);

        return (
          <Link
            key={`${it.href}::${it.title}`}
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
        const data = await apiAuthMe();
        setMe(data);
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

  const cabinetTitle = useMemo(() => resolveCabinetTitle(me), [me]);

  const isAdmin = canSeeAdminShell(me);
  const showPersonnelVisibility = hasPersonnelVisibility(me) && !isAdmin;
  const showSysadminNav = canSeeSysadminCabinetNav(me);
  const showPersonnelLifecycleNav = canSeePersonnelLifecycleNav(me);
  const showPersonnelIdentityOperationsNav = canSeePersonnelIdentityOperationsNav(me);

  const sidebarNavItems = useMemo(() => {
    return PRIMARY_ADMIN_NAV.filter((item) =>
      shouldShowPrimaryAdminNavItem(item, me, {
        isAdmin,
        showSysadminNav,
        showPersonnelLifecycleNav,
        showPersonnelIdentityOperationsNav,
      }),
    );
  }, [isAdmin, me, showPersonnelIdentityOperationsNav, showPersonnelLifecycleNav, showSysadminNav]);

  const visibilityNavItems = useMemo(() => {
    return buildVisibilityDirectoryNavItems(me, {
      includeTasksReadOnly: canViewPersonnelTasksReadOnly(me),
    });
  }, [me]);

  const hrDirectoryNavItems = useMemo(() => buildPersonnelSidebarNavItems(me), [me]);

  const forbiddenNonAdminRoute =
    !loading && !!me && !canAccessDirectoryRoute(pathname, me) && isForbiddenAdminRoute(pathname, me);

  const privilegedSysadminOnly =
    !isAdmin &&
    showSysadminNav &&
    pathname.startsWith("/admin/system") &&
    !isPersonnelLifecycleRoute(pathname) &&
    !isPersonnelIdentityOperationsRoute(pathname);

  const personnelAdminStandaloneRoute =
    !isAdmin &&
    !showSysadminNav &&
    showPersonnelLifecycleNav &&
    (isPersonnelLifecycleRoute(pathname) || isPersonnelIdentityOperationsRoute(pathname));

  const showHrDirectoryOnly =
    !isAdmin &&
    !showPersonnelVisibility &&
    hrDirectoryNavItems.length > 0 &&
    (isHrProcessesRoute(pathname) || isPersonnelDirectoryRoute(pathname));

  useEffect(() => {
    if (isLogin || loading) return;
    if (!forbiddenNonAdminRoute) return;
    router.replace("/tasks");
  }, [isLogin, loading, forbiddenNonAdminRoute, router]);

  const showOrgUnitsPanel = useMemo(() => shouldShowOrgUnitsPanel(pathname, me), [me, pathname]);

  const orgTreeBasePath = useMemo(() => resolveDirectoryOrgTreeBasePath(pathname), [pathname]);

  const showPositionCabinetNav = shouldShowPositionCabinetNav(pathname, { showPersonnelVisibility });

  function renderMainSection(content: React.ReactNode) {
    return <section className="min-w-0">{content}</section>;
  }

  if (isLogin) return <>{children}</>;

  return (
    <div className="min-h-[calc(100vh-52px)] bg-white dark:bg-zinc-950 text-zinc-900 dark:text-zinc-50">
      <div className="w-full px-3 py-2 xl:px-4 xl:py-3">
        <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-2xl font-semibold">{cabinetTitle}</div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Link
              href="/profile"
              className={[
                "rounded-md border px-3 py-1 text-sm transition",
                pathname === "/profile"
                  ? "border-zinc-400 dark:border-zinc-600 bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50"
                  : "border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700",
              ].join(" ")}
            >
              Профиль
              {!loading && me && me.telegram_bound !== true ? (
                <span className="ml-1.5 inline-block h-2 w-2 rounded-full bg-amber-500 align-middle" aria-hidden="true" />
              ) : null}
            </Link>
            <button
              onClick={onLogoutClick}
              className="rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 px-3 py-1 text-sm text-zinc-800 dark:text-zinc-200 hover:bg-zinc-200 dark:hover:bg-zinc-700"
            >
              Выйти
            </button>
          </div>
        </div>

        {!loading && !err && showPositionCabinetNav ? (
          <div className="mb-4 mt-2 space-y-3">
            <PositionCabinetLibraryLinks me={me} />
            <PositionCabinetNav />
          </div>
        ) : null}

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
                  <SidebarNav pathname={pathname} items={sidebarNavItems} />
                  <RareSidebarGroup pathname={pathname} />
                </div>
              </div>

              {showOrgUnitsPanel ? <OrgUnitsSidebarPanel basePath={orgTreeBasePath} /> : null}
            </aside>

            {renderMainSection(children)}
          </div>
        ) : showPersonnelVisibility ? (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[220px_minmax(0,1fr)]">
            <aside className="space-y-2.5">
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-1">
                <div className="space-y-1">
                  <SidebarNav pathname={pathname} items={visibilityNavItems} />
                </div>
              </div>

              {showOrgUnitsPanel ? <OrgUnitsSidebarPanel basePath={orgTreeBasePath} /> : null}
            </aside>

            {renderMainSection(
              forbiddenNonAdminRoute ? (
                <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-4 text-sm text-zinc-600 dark:text-zinc-400">
                  Нет доступа к этому разделу.
                </div>
              ) : (
                children
              ),
            )}
          </div>
        ) : showHrDirectoryOnly ? (
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-[220px_minmax(0,1fr)]">
            <aside className="space-y-2.5">
              <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-1">
                <div className="space-y-1">
                  <SidebarNav pathname={pathname} items={hrDirectoryNavItems} />
                </div>
              </div>
            </aside>

            {renderMainSection(children)}
          </div>
        ) : privilegedSysadminOnly || personnelAdminStandaloneRoute ? (
          renderMainSection(children)
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {renderMainSection(
              forbiddenNonAdminRoute ? (
                <div className="rounded-2xl border border-zinc-200 dark:border-zinc-800 bg-zinc-100 dark:bg-zinc-900 p-4 text-sm text-zinc-600 dark:text-zinc-400">
                  Переход к задачам…
                </div>
              ) : (
                children
              ),
            )}
          </div>
        )}
      </div>
    </div>
  );
}