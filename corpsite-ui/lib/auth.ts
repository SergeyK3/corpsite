// FILE: corpsite-ui/lib/auth.ts
"use client";

export const AUTH_SESSION_ACCESS_TOKEN_KEY = "access_token";
export const AUTH_SESSION_LOGIN_KEY = "login";

// Оставляем как справочник-подсказку логинов для UI (например, /login).
// НЕ используется для авторизации и НЕ должен управлять доступом.
export const LOGIN_TO_USER_ID: Record<string, number> = {
  "director@corp.local": 263,
  "dep_med@corp.local": 264,
  "dep_outpatient_audit@corp.local": 265,
  "dep_admin@corp.local": 266,
  "dep_strategy@corp.local": 267,

  "stat_head@corp.local": 0,
  "stat_head_deputy@corp.local": 0,
  "stat_erob_input@corp.local": 270,
  "stat_erob_output@corp.local": 0,
  "stat_erob_analytics@corp.local": 0,

  "qm_head@corp.local": 0,
  "qm_hosp@corp.local": 0,
  "qm_amb@corp.local": 262,

  "qm_complaint_reg@corp.local": 0,
  "qm_complaint_pat@corp.local": 0,

  "hr_head@corp.local": 0,
  "acc_head@corp.local": 279,

  "econ_head@corp.local": 0,
  "econ_1@corp.local": 281,
  "econ_2@corp.local": 282,
  "econ_3@corp.local": 283,
};

function normalizeLogin(v: string): string {
  return (v ?? "").toString().trim().toLowerCase();
}

// -------------------- session storage helpers --------------------

export function getSessionAccessToken(): string {
  if (typeof window === "undefined") return "";
  try {
    return (window.sessionStorage.getItem(AUTH_SESSION_ACCESS_TOKEN_KEY) ?? "").toString().trim();
  } catch {
    return "";
  }
}

export function setSessionAccessToken(token: string): void {
  if (typeof window === "undefined") return;
  const t = (token ?? "").toString().trim();
  if (!t) return;
  try {
    window.sessionStorage.setItem(AUTH_SESSION_ACCESS_TOKEN_KEY, t);
  } catch {
    // ignore
  }
}

export function clearSessionAccessToken(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(AUTH_SESSION_ACCESS_TOKEN_KEY);
  } catch {
    // ignore
  }
}

export function setSessionLogin(login: string): void {
  if (typeof window === "undefined") return;
  const l = normalizeLogin(login);
  if (!l) return;
  try {
    window.sessionStorage.setItem(AUTH_SESSION_LOGIN_KEY, l);
  } catch {
    // ignore
  }
}

export function getSessionLogin(): string {
  if (typeof window === "undefined") return "";
  try {
    return normalizeLogin(window.sessionStorage.getItem(AUTH_SESSION_LOGIN_KEY) ?? "");
  } catch {
    return "";
  }
}

export function clearSessionLogin(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(AUTH_SESSION_LOGIN_KEY);
  } catch {
    // ignore
  }
}

export function logout(): void {
  clearSessionAccessToken();
  clearSessionLogin();
}

export function isAuthed(): boolean {
  return !!getSessionAccessToken();
}
