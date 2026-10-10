"use client";

import { useState } from "react";
import { usePersonnelSectionLanguage, type PersonnelSectionLanguage } from "../_lib/personnelSectionLanguage";

export default function PersonnelLanguageSetting() {
  const { language, canEdit, ready, error: loadError, reload, save } = usePersonnelSectionLanguage();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const kk = language === "kk";
  const label = kk ? "Кадр бөлімінің тілі" : "Язык кадрового раздела";
  const loadMessage = loadError === "schema"
    ? (kk ? "Тіл баптауы әзірге қолжетімсіз. Әкімшіге хабарласыңыз." : "Настройка языка пока недоступна. Обратитесь к администратору.")
    : (kk ? "Кадр бөлімінің тілін жүктеу мүмкін болмады." : "Не удалось загрузить язык кадрового раздела.");
  return <details className="mt-2 text-sm">
    <summary className="cursor-pointer">{kk ? "Баптаулар" : "Настройки"}</summary>
    <label className="mt-2 flex items-center gap-2">{label}
      <select aria-label={label} value={language} disabled={!ready || !canEdit || busy} className="rounded border bg-transparent px-2 py-1" onChange={async event => {
        const next = event.target.value as PersonnelSectionLanguage;
        setBusy(true); setError("");
        try { await save(next); } catch { setError(kk ? "Тілді сақтау мүмкін болмады." : "Не удалось сохранить язык."); } finally { setBusy(false); }
      }}><option value="kk">Қазақша</option><option value="ru">Русский</option></select>
    </label>
    {error || loadError ? <p role="alert" className="text-red-600">{error || loadMessage}</p> : null}
    {loadError ? <button type="button" onClick={reload} className="mt-1 rounded border px-2 py-1">{kk ? "Қайталау" : "Повторить"}</button> : null}
  </details>;
}
