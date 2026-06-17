// FILE: corpsite-ui/lib/auth.ts
"use client";

import { sanitizeBearerToken } from "./bearerToken";

export const AUTH_SESSION_ACCESS_TOKEN_KEY = "access_token";
export const AUTH_SESSION_LOGIN_KEY = "login";

// Оставляем как справочник-подсказку логинов для UI (например, /login).
// НЕ используется для авторизации и НЕ должен управлять доступом.
export const LOGIN_TO_USER_ID: Record<string, number> = {
  "acc_head@corp.local": 9,
  "admin": 25,
  "admin_legacy_1@corp.local": 1,
  "admission_head_7": 7,
  "dep_admin@corp.local": 10,
  "dep_med@corp.local": 11,
  "dep_outpatient_audit@corp.local": 12,
  "dep_strategy@corp.local": 13,
  "director@corp.local": 14,
  "director_test": 26,
  "econ_1@corp.local": 15,
  "econ_2@corp.local": 16,
  "econ_3@corp.local": 17,
  "econ_head@corp.local": 18,
  "hr_head@corp.local": 8,
  "proc_head@corp.local": 24,
  "qm_amb@corp.local": 5,
  "qm_complaint_pat@corp.local": 3,
  "qm_complaint_reg@corp.local": 2,
  "qm_head@corp.local": 6,
  "qm_hosp@corp.local": 4,
  "stat_erob_analytics@corp.local": 19,
  "stat_erob_input@corp.local": 20,
  "stat_erob_output@corp.local": 21,
  "stat_head@corp.local": 22,
  "stat_head_deputy@corp.local": 23,
};

function normalizeLogin(v: string): string {
  return (v ?? "").toString().trim().toLowerCase();
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payloadB64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = payloadB64 + "=".repeat((4 - (payloadB64.length % 4)) % 4);
    const json = atob(padded);
    const payload = JSON.parse(json);
    return payload && typeof payload === "object" ? payload : null;
  } catch {
    return null;
  }
}

function isAccessTokenExpired(token: string): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload) return false;
  const exp = Number(payload.exp ?? 0);
  if (!exp) return false;
  return Date.now() / 1000 >= exp;
}

function readAuthStorage(key: string): string {
  if (typeof window === "undefined") return "";
  try {
    const fromLocal = (window.localStorage.getItem(key) ?? "").toString().trim();
    if (fromLocal) return fromLocal;

    const fromSession = (window.sessionStorage.getItem(key) ?? "").toString().trim();
    if (!fromSession) return "";

    window.localStorage.setItem(key, fromSession);
    window.sessionStorage.removeItem(key);
    return fromSession;
  } catch {
    return "";
  }
}

function writeAuthStorage(key: string, value: string): void {
  if (typeof window === "undefined") return;
  const next = (value ?? "").toString().trim();
  if (!next) return;
  try {
    window.localStorage.setItem(key, next);
    window.sessionStorage.removeItem(key);
  } catch {
    // ignore
  }
}

function clearAuthStorage(key: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
    window.sessionStorage.removeItem(key);
  } catch {
    // ignore
  }
}

// -------------------- auth storage helpers --------------------

export function getSessionAccessToken(): string {
  const token = sanitizeBearerToken(readAuthStorage(AUTH_SESSION_ACCESS_TOKEN_KEY));
  if (!token) return "";
  if (isAccessTokenExpired(token)) {
    clearSessionAccessToken();
    return "";
  }
  return token;
}

export function setSessionAccessToken(token: string): void {
  writeAuthStorage(AUTH_SESSION_ACCESS_TOKEN_KEY, sanitizeBearerToken(token));
}

export function clearSessionAccessToken(): void {
  clearAuthStorage(AUTH_SESSION_ACCESS_TOKEN_KEY);
}

export function setSessionLogin(login: string): void {
  writeAuthStorage(AUTH_SESSION_LOGIN_KEY, normalizeLogin(login));
}

export function getSessionLogin(): string {
  return normalizeLogin(readAuthStorage(AUTH_SESSION_LOGIN_KEY));
}

export function clearSessionLogin(): void {
  clearAuthStorage(AUTH_SESSION_LOGIN_KEY);
}

export function logout(): void {
  clearSessionAccessToken();
  clearSessionLogin();
}

export function isAuthed(): boolean {
  const token = getSessionAccessToken();
  if (!token) return false;
  return !isAccessTokenExpired(token);
}
