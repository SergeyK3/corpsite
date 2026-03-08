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
  isStub?: boolean;
};

const DICTIONARY_ITEMS: DictionaryNavItem[] = [
  { href: "/directory/roles", title: "Роли" },
  { href: "/directory/positions", title: "Должности", isStub: true },
  { href: "/directory/contacts", title: "Контакты", isStub: true },
  { href: "/directory/personnel", title: "Персонал", isStub: true },
  { href: "/directory/working-contacts", title: "Рабочие контакты", isStub: true },
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
  if (pathname.startsWith("/admin/regular-tasks")) return "";
  if (pathname.startsWith("/tasks")) return "Задачи";
  if (pathname.startsWith("/regular-tasks")) return "Шаблоны задач";
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
    <nav className="space-y-2">
      {items.map((it) => {
        const active = pathname === it.href || (it.href !== "/tasks" && pathname.startsWith(it.href));

        return (
          <Link
            key={it.href}
            href={it.href}
            className={[
              "block rounded-lg border px-3 py-2 text-sm transition",
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
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={[
          "flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-sm transition",
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
        <div className="ml-3 space-y-1 border-l border-zinc-800 pl-3">
          {DICTIONARY_ITEMS.map((item) => {
            const active = isPathActive(pathname, item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={[
                  "flex items-center justify-between rounded-lg px-3 py-2 text-sm transition",
                  active
                    ? "bg-zinc-800 text-zinc-100"
                    : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100",
                ].join(" ")}
              >
                <span>{item.title}</span>
                {item.isStub ? (
                  <span className="ml-3 rounded border border-zinc-700 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-zinc-500">
                    stub
                  </span>
                ) : null}
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

  const whoLine = "";

  const roleId = Number(me?.role_id ?? 0);
  const isTechAdmin = roleId === 2 || roleId === 58;

  const navTop = useMemo<NavItem[]>(() => {
    const items: NavItem[] = [{ href: "/tasks", title: "Задачи" }];

    if (isTechAdmin) {
      items.push({ href: "/admin/regular-tasks", title: "Регулярные задачи" });
    }

    return items;
  }, [isTechAdmin]);

  const orgTreeBasePath = pathname.startsWith("/directory/org") ? "/directory/org" : "/directory/employees";
  const secTitle = sectionTitle(pathname);

  if (isLogin) return <>{children}</>;

  return (
    <div className="min-h-[calc(100vh-52px)] bg-zinc-950 text-zinc-100">
      <div className="w-full px-4 py-6">
        <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-2xl font-semibold">{roleTitle}</div>
            {whoLine ? <div className="mt-1 text-sm text-zinc-400">{whoLine}</div> : null}
            {secTitle ? <div className="mt-2 text-sm text-zinc-300">{secTitle}</div> : null}
          </div>

          <button
            onClick={onLogoutClick}
            className="rounded-md border border-zinc-800 bg-zinc-950/40 px-3 py-2 text-sm text-zinc-200 hover:bg-zinc-900/60"
          >
            Выйти
          </button>
        </div>

        {loading ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-400">Загрузка…</div>
        ) : err ? (
          <div className="rounded-2xl border border-red-900/60 bg-red-950/40 p-4 text-sm text-red-200">{err}</div>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            <aside className="space-y-4 lg:col-span-3">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-3">
                <div className="space-y-3">
                  <SidebarNav pathname={pathname} items={navTop} />
                  <DictionariesSidebarGroup pathname={pathname} />
                </div>
              </div>

              <OrgUnitsSidebarPanel basePath={orgTreeBasePath} />
            </aside>

            <section className="min-w-0 lg:col-span-9">{children}</section>
          </div>
        )}
      </div>
    </div>
  );
}