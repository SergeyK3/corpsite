"use client";

import {useEffect, useId, useRef, useState} from "react";

export function parsePersonnelFilterDate(raw: string): string | null {
  const match = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(raw) || /^(\d{2})(\d{2})(\d{4})$/.exec(raw);
  if (!match) return null;
  const [, day, month, year] = match;
  const date = new Date(0);
  date.setUTCFullYear(Number(year), Number(month) - 1, Number(day));
  return Number(year) > 0 && date.getUTCFullYear() === Number(year) && date.getUTCMonth() === Number(month) - 1 && date.getUTCDate() === Number(day)
    ? `${year}-${month}-${day}` : null;
}

function displayDate(value?: string): string {
  return value && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split("-").reverse().join(".") : "";
}

const fieldClass = "rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950";
const months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];

export default function PersonnelOrderDateFilter({label, value, onCommit, resetKey = 0}: {
  label: string; value?: string; onCommit: (value: string | undefined) => void; resetKey?: number;
}) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const pending = useRef(new Set<string>());
  const latest = useRef(value || "");
  const previousReset = useRef(resetKey);
  const [draft, setDraft] = useState(() => displayDate(value));
  const [invalid, setInvalid] = useState(false);
  const [open, setOpen] = useState(false);
  const [year, setYear] = useState(String(new Date().getFullYear()));
  const [month, setMonth] = useState(new Date().getMonth() + 1);

  useEffect(() => {
    if (previousReset.current !== resetKey) {
      previousReset.current = resetKey;
      pending.current.clear(); setDraft(displayDate(value)); setInvalid(false); setOpen(false);
      return;
    }
    const next = value || "";
    if (pending.current.delete(next)) {
      if (latest.current === next) pending.current.clear();
      return;
    }
    pending.current.clear(); setDraft(displayDate(value)); setInvalid(false);
  }, [value, resetKey]);

  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {if (!root.current?.contains(event.target as Node)) setOpen(false);};
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  function commit(next?: string) {
    latest.current = next || "";
    if (next !== value) {pending.current.add(next || ""); onCommit(next);}
  }

  function change(raw: string) {
    setDraft(raw); setInvalid(false);
    if (!raw) {commit(undefined); return;}
    const iso = parsePersonnelFilterDate(raw);
    if (iso) {
      if (/^\d{8}$/.test(raw)) setDraft(displayDate(iso));
      commit(iso);
    }
  }

  function toggleCalendar() {
    if (!open) {
      const iso = parsePersonnelFilterDate(draft) || value;
      setYear(iso ? iso.slice(0, 4) : String(new Date().getFullYear()));
      setMonth(iso ? Number(iso.slice(5, 7)) : new Date().getMonth() + 1);
    }
    setOpen(current => !current);
  }

  const numericYear = /^\d{1,4}$/.test(year) ? Number(year) : 0;
  const first = new Date(0); first.setUTCFullYear(numericYear, month - 1, 1);
  const last = new Date(0); last.setUTCFullYear(numericYear, month, 0);
  const offset = (first.getUTCDay() + 6) % 7;

  return <div ref={root} className="relative" onKeyDown={event => {
    if (event.key === "Escape" && open) {event.stopPropagation(); setOpen(false); input.current?.focus();}
  }}>
    <label htmlFor={id} className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">{label}</label>
    <div className="flex gap-1">
      <input ref={input} id={id} type="text" placeholder="дд.мм.гггг" autoComplete="off" maxLength={10}
        value={draft} onChange={event => change(event.target.value)}
        onBlur={() => setInvalid(Boolean(draft && !parsePersonnelFilterDate(draft)))}
        aria-invalid={invalid || undefined} aria-describedby={invalid ? `${id}-error` : undefined}
        className={`${fieldClass} w-36`} />
      <button type="button" aria-label={`Открыть календарь: ${label}`} aria-expanded={open} aria-controls={`${id}-calendar`}
        onClick={toggleCalendar} className={fieldClass}>📅</button>
      {draft ? <button type="button" aria-label={`Очистить: ${label}`} className={fieldClass}
        onClick={() => {setDraft(""); setInvalid(false); setOpen(false); commit(undefined); input.current?.focus();}}>×</button> : null}
    </div>
    {invalid ? <p id={`${id}-error`} role="alert" className="mt-1 text-xs text-red-700">Введите корректную дату: дд.мм.гггг</p> : null}
    {open ? <div id={`${id}-calendar`} role="dialog" aria-label={`Календарь: ${label}`}
      className="absolute left-0 top-full z-40 mt-1 w-72 rounded-lg border border-zinc-300 bg-white p-3 shadow-lg dark:border-zinc-700 dark:bg-zinc-950">
      <div className="flex gap-2">
        <label className="text-xs">Год<input aria-label={`Год: ${label}`} inputMode="numeric" maxLength={4} value={year}
          onChange={event => setYear(event.target.value)} className={`${fieldClass} mt-1 w-24`} /></label>
        <label className="text-xs">Месяц<select aria-label={`Месяц: ${label}`} value={month}
          onChange={event => setMonth(Number(event.target.value))} className={`${fieldClass} mt-1 w-full`}>
          {months.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}
        </select></label>
      </div>
      {numericYear > 0 ? <div className="mt-3 grid grid-cols-7 gap-1 text-center text-sm">
        {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map(day => <span key={day} className="text-xs text-zinc-500">{day}</span>)}
        {Array.from({length: offset}, (_, index) => <span key={`empty-${index}`} />)}
        {Array.from({length: last.getUTCDate()}, (_, index) => {
          const iso = `${String(numericYear).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(index + 1).padStart(2, "0")}`;
          return <button key={iso} type="button" aria-label={displayDate(iso)} aria-pressed={parsePersonnelFilterDate(draft) === iso}
            className="rounded p-1 hover:bg-blue-100 aria-pressed:bg-blue-200 dark:hover:bg-blue-900 dark:aria-pressed:bg-blue-900"
            onClick={() => {setDraft(displayDate(iso)); setInvalid(false); commit(iso); setOpen(false); input.current?.focus();}}>{index + 1}</button>;
        })}
      </div> : <p className="mt-2 text-sm">Введите год от 1 до 9999</p>}
    </div> : null}
  </div>;
}
