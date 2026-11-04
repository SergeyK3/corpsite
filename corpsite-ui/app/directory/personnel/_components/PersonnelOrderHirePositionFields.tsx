"use client";
import * as React from "react";
import {createPortal} from "react-dom";
import type {DocumentPosition} from "../_lib/personnelOrderPositions";


type Locale = "ru" | "kk";
const normalize = (text: string) => text.normalize("NFKC").toLocaleLowerCase().replace(/ё/g, "е").replace(/[^\p{L}\p{N}]+/gu, " ").trim();

export default function PersonnelOrderHirePositionFields({value, positions: options, onSelect, onTextChange, disabled = false, loading = false, error = false}: {
  value: {id: number | null; ru: string; kk: string}; positions: DocumentPosition[];
  onSelect: (value: DocumentPosition) => void; onTextChange: (locale: Locale, text: string) => void;
  disabled?: boolean; loading?: boolean; error?: boolean;
}) {
  const fields = {name_ru: value.ru, name_kk: value.kk};
  const [open, setOpen] = React.useState<Locale | null>(null);
  const [browseAll, setBrowseAll] = React.useState(false);
  const [active, setActive] = React.useState(0);
  const controls = React.useRef<Record<Locale, HTMLDivElement | null>>({ru: null, kk: null});
  const inputs = React.useRef<Record<Locale, HTMLInputElement | null>>({ru: null, kk: null});
  const popup = React.useRef<HTMLDivElement>(null);
  const [placement, setPlacement] = React.useState({left: 0, top: 0, width: 0, maxHeight: 192});
  const id = React.useId();
  const words = normalize(open ? fields[open === "ru" ? "name_ru" : "name_kk"] : "").split(/\s+/).filter(Boolean);
  const found = options.filter(row => browseAll || words.every(word => normalize(`${row.name} ${row.name_kk || ""}`).includes(word)));
  React.useEffect(() => {
    const close = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!Object.values(controls.current).some(control => control?.contains(target)) && !popup.current?.contains(target)) setOpen(null);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  React.useLayoutEffect(() => {
    if (!open || disabled) return;
    const update = () => {
      const rect = controls.current[open]?.getBoundingClientRect();
      if (!rect) return;
      const desired = found.length ? Math.min(192, found.length * 44 + 2) : 64;
      const above = Math.max(0, rect.top - 12), below = Math.max(0, window.innerHeight - rect.bottom - 12);
      const upwards = below < desired && above > below;
      const height = Math.max(32, Math.min(desired, upwards ? above : below));
      const width = Math.min(rect.width, Math.max(0, window.innerWidth - 16));
      setPlacement({left: Math.max(8, Math.min(rect.left, window.innerWidth - width - 8)),
        top: upwards ? Math.max(8, rect.top - height - 4) : rect.bottom + 4, width, maxHeight: height});
    };
    update(); window.addEventListener("resize", update); window.addEventListener("scroll", update, true);
    return () => {window.removeEventListener("resize", update); window.removeEventListener("scroll", update, true);};
  }, [open, disabled, found.length]);
  React.useEffect(() => {
    popup.current?.querySelector<HTMLElement>(`[data-option-index="${active}"]`)?.scrollIntoView?.({block: "nearest"});
  }, [open, active]);
  const select = (position: DocumentPosition) => {onSelect(position); setOpen(null);};
  return <fieldset disabled={disabled} className="space-y-3 rounded border border-zinc-200 p-3 sm:col-span-2 dark:border-zinc-700" data-testid="hire-position-fields">
    <div className="grid gap-3 sm:grid-cols-2">{(["ru", "kk"] as const).map(locale => {
      const key = locale === "ru" ? "name_ru" : "name_kk";
      const visible = open === locale && !disabled;
      const index = Math.min(active, Math.max(0, found.length - 1));
      const listId = `${id}-${locale}-options`;
      return <div key={locale} className="space-y-1">
        <label htmlFor={`${id}-${locale}`}>Должность ({locale.toUpperCase()})</label>
        <div ref={element => {controls.current[locale] = element;}} className="flex gap-1">
          <input ref={element => {inputs.current[locale] = element;}} id={`${id}-${locale}`} role="combobox" aria-autocomplete="list"
            aria-expanded={visible} aria-controls={visible ? listId : undefined}
            aria-activedescendant={visible && !loading && !error && found.length ? `${listId}-${index}` : undefined}
            value={fields[key]} maxLength={300} disabled={disabled} autoComplete="off" className="min-w-0 flex-1 rounded border bg-transparent p-2"
            onFocus={() => {setOpen(locale); setBrowseAll(false); setActive(0);}}
            onClick={() => {setOpen(locale); setBrowseAll(false); setActive(0);}} onBlur={() => setOpen(null)}
            onChange={event => {onTextChange(locale, event.target.value); setOpen(locale); setBrowseAll(false); setActive(0);}}
            onKeyDown={event => {
              if (event.key === "Escape") {event.preventDefault(); event.stopPropagation(); setOpen(null);}
              if (event.key === "ArrowDown" || event.key === "ArrowUp") {
                event.preventDefault(); setOpen(locale);
                setActive(visible ? Math.max(0, Math.min(found.length - 1, index + (event.key === "ArrowDown" ? 1 : -1))) : 0);
              }
              if (event.key === "Enter" && visible) {event.preventDefault(); if (!loading && !error && found[index]) select(found[index]);}
            }}/>
          <button type="button" aria-label={`Открыть список должностей (${locale.toUpperCase()})`} aria-haspopup="listbox"
            aria-expanded={visible} aria-controls={visible ? listId : undefined} disabled={disabled}
            className="shrink-0 rounded border px-3" onMouseDown={event => event.preventDefault()}
            onClick={() => {
              if (open === locale && browseAll) {setOpen(null); return;}
              inputs.current[locale]?.focus({preventScroll: true}); setOpen(locale); setBrowseAll(true); setActive(0);
            }}>▾</button>
        </div>
        {visible && createPortal(<div ref={popup} id={listId} role="listbox" aria-label={`Должности (${locale.toUpperCase()})`}
          style={placement} className="fixed z-[90] overflow-y-auto rounded border bg-white shadow-xl dark:bg-zinc-900">
          {loading && <p role="status" className="p-2">Загружаются должности…</p>}
          {error && <p className="p-2">Справочник недоступен. Сохранённый текст можно редактировать.</p>}
          {!loading && !error && found.map((unit, rowIndex) => <button key={unit.id} id={`${listId}-${rowIndex}`} type="button" role="option" data-option-index={rowIndex}
            aria-selected={unit.id === value.id} tabIndex={-1} onMouseDown={event => event.preventDefault()} onClick={() => select(unit)}
            className={`block w-full px-3 py-2 text-left hover:bg-zinc-100 dark:hover:bg-zinc-800 ${rowIndex === index ? 'bg-zinc-100 dark:bg-zinc-800' : ''}`}>
            {locale === "ru" ? unit.name : unit.name_kk || "Нет названия KK"}
          </button>)}
          {!loading && !error && !found.length && <p className="p-2">Совпадений нет. Можно сохранить введённое название</p>}
        </div>, document.body)}
      </div>;
    })}</div>
    {loading && !open ? <p role="status">Загружаются должности…</p> : null}
    {error ? <p role="alert">Не удалось загрузить справочник должностей. Сохранённый текст оставлен без изменений.</p> : null}
  </fieldset>;
}
