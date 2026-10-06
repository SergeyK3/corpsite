"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { apiFetchJson } from "@/lib/api";

export type PersonnelSectionLanguage = "kk" | "ru";
type Settings = { language: PersonnelSectionLanguage; can_edit: boolean };
type SettingsLoadError = "" | "load" | "schema";
const Context = createContext({ language: "kk" as PersonnelSectionLanguage, canEdit: false, ready: false, error: "" as SettingsLoadError, reload: () => {}, save: async (_language: PersonnelSectionLanguage) => {} });

export function localizedPersonnelTitle(titles: { title_ru?: string | null; title_kk?: string | null }, language: PersonnelSectionLanguage): string {
  return (language === "kk" ? titles.title_kk?.trim() || titles.title_ru : titles.title_ru?.trim() || titles.title_kk) || "";
}

export function PersonnelSectionLanguageProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [settings, setSettings] = useState<Settings>({ language: "kk", can_edit: false });
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<SettingsLoadError>("");
  const [reloadKey, setReloadKey] = useState(0);
  useEffect(() => {
    let active = true;
    setReady(false); setError("");
    apiFetchJson<Settings>("/personnel/settings").then(value => {
      if (active) { setSettings(value); setReady(true); }
    }).catch(cause => {
      if (active) setError(cause?.details?.detail?.code === "PERSONNEL_SETTINGS_SCHEMA_REQUIRED" ? "schema" : "load");
    });
    return () => { active = false; };
  }, [pathname, reloadKey]);
  async function save(language: PersonnelSectionLanguage) {
    const value = await apiFetchJson<Settings>("/personnel/settings", { method: "PUT", body: { language } });
    setSettings(value);
  }
  return <Context.Provider value={{ language: settings.language, canEdit: settings.can_edit, ready, error, reload: () => setReloadKey(key => key + 1), save }}>{children}</Context.Provider>;
}

export function usePersonnelSectionLanguage() { return useContext(Context); }
