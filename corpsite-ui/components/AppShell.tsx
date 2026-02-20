// FILE: corpsite-ui/components/AppShell.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { apiAuthMe } from "@/lib/api";
import { isAuthed, logout as authLogout } from "@/lib/auth";

type MeInfo = {
  user_id?: number;
  role_id?: number;
  role_name_ru?: string;
  role_name?: string;
  full_name?: string;
  login?: string;
};

function normalizeMsg(msg: string): string {
  const s = String(msg || "").trim();
  return s || "Ошибка";
}

function isUnauthorized(e: any): boolean {
  return Number(e?.status ?? 0) === 401;
}

function sectionTitle(pathname: string): string {
  if (pathname.startsWith("/tasks")) return "Задачи";
  if (pathname.startsWith("/regular-tasks")) return "Шаблоны задач";
  if (pathname.startsWith("/directory/org")) return "Оргструктура";
  if (pathname.startsWith("/directory/employees")) return "Сотрудники";
  if (pathname.startsWith("/directory")) return "Справочники";
  return "";
}

type NavItem = { href: string; title: string };

function SidebarNav({ pathname, items }: { pathname: string; items: NavItem[] }) {
  return (
    <nav className="space-y-1">
      {items.map((it) => {
        const active = pathname === it.href || (it.href !== "/tasks" && pathname.startsWith(it.href));

        return (
          <a
            key={it.href}
            href={it.href}
            className={[
              "block rounded-lg border px-3 py-2 text-sm",
              active
                ? "border-zinc-600 bg-zinc-900 text-zinc-100"
                : "border-zinc-800 bg-zinc-950/40 text-zinc-200 hover:bg-zinc-900/60",
            ].join(" ")}
          >
            {it.title}
          </a>
        );
      })}
    </nav>
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

  // IMPORTANT: do not show any identity line under role title (no login, no ID)
  const whoLine = "";

  const isSupport = Number(me?.role_id ?? 0) === 1;

  const navItems = useMemo(() => {
    const base: NavItem[] = [
      { href: "/tasks", title: "Задачи" },
      { href: "/directory/org", title: "Оргструктура" },
      { href: "/directory/employees", title: "Сотрудники" },
    ];

    if (isSupport) {
      base.push({ href: "/regular-tasks", title: "Шаблоны задач" });
      base.push({ href: "/directory", title: "Справочники" });
    }

    return base;
  }, [isSupport]);

  const secTitle = sectionTitle(pathname);

  if (isLogin) return <>{children}</>;

  return (
    <div className="min-h-[calc(100vh-52px)] bg-zinc-950 text-zinc-100">
      <div className="mx-auto max-w-6xl px-4 py-6">
        {/* Верхняя строка */}
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
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4 text-sm text-zinc-400">
            Загрузка…
          </div>
        ) : err ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {err}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
            {/* Sidebar */}
            <aside className="lg:col-span-3">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-3">
                <SidebarNav pathname={pathname} items={navItems} />
              </div>
            </aside>

            {/* Контент */}
            <section className="lg:col-span-9">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-4">{children}</div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
