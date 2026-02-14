// FILE: corpsite-ui/lib/dev_user.ts

export const DEV_USER_STORAGE_KEY = "corpsite.dev_user_id";

/**
 * sessionStorage — пер-окно/пер-вкладка.
 * Это то, что нужно для моделирования "разных рабочих мест".
 */
export function getDevUserId(fallback = 1): number {
  if (typeof window === "undefined") return fallback;

  // 1) sessionStorage (главный источник)
  try {
    const raw = window.sessionStorage.getItem(DEV_USER_STORAGE_KEY);
    if (raw) {
      const n = Number(raw);
      if (Number.isFinite(n) && n > 0) return Math.floor(n);
    }
  } catch {
    // ignore
  }

  // 2) query string (удобно делиться ссылками / быстро менять)
  try {
    const qs = new URLSearchParams(window.location.search);
    const q = qs.get("asUser") || qs.get("devUserId") || qs.get("userId");
    if (q) {
      const n = Number(q);
      if (Number.isFinite(n) && n > 0) return Math.floor(n);
    }
  } catch {
    // ignore
  }

  return fallback;
}

export function setDevUserId(userId: number): void {
  if (typeof window === "undefined") return;
  const n = Number(userId);
  if (!Number.isFinite(n) || n <= 0) return;

  try {
    window.sessionStorage.setItem(DEV_USER_STORAGE_KEY, String(Math.floor(n)));
  } catch {
    // ignore
  }
}

export function clearDevUserId(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(DEV_USER_STORAGE_KEY);
  } catch {
    // ignore
  }
}
