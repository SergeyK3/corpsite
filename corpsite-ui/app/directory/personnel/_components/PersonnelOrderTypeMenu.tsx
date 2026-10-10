"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { personnelOrderTypeLabel } from "../_lib/personnelOrderLabels";
import {
  PERSONNEL_ORDER_GROUPS, PERSONNEL_ORDER_TYPE_GROUP,
  personnelOrderGroupLabel, personnelOrderGroupTypes, searchPersonnelOrderTypes,
  type PersonnelOrderCreateType, type PersonnelOrderGroupId,
} from "../_lib/personnelOrderTypeGroups";
import type { PersonnelSectionLanguage } from "../_lib/personnelSectionLanguage";
import type { PersonnelPublishedTemplateVariant } from "../_lib/personnelOrdersApi.client";

type Props = {
  value: string;
  language: PersonnelSectionLanguage;
  onChange: (type: PersonnelOrderCreateType, versionId?: number) => void;
  variants?: Record<string, PersonnelPublishedTemplateVariant[]>;
  selectedVersion?: number;
  disabled?: boolean;
};

type Position = { left: number; top: number; groupWidth: number; itemWidth: number; maxHeight: number; side: "right" | "left" | "below" };
type Point = { x: number; y: number };

export function pointerHeadsToSubmenu(origin: Point, point: Point, bounds: Pick<DOMRect, "left" | "right" | "top" | "bottom">, side: Position["side"]): boolean {
  if (side === "below") return false;
  const edge = side === "right" ? bounds.left : bounds.right;
  if (Math.abs(edge - origin.x) < 1) return false;
  const progress = (point.x - origin.x) / (edge - origin.x);
  if (progress < 0 || progress > 1) return false;
  const top = origin.y + (bounds.top - 8 - origin.y) * progress;
  const bottom = origin.y + (bounds.bottom + 8 - origin.y) * progress;
  return point.y >= top && point.y <= bottom;
}

export function orderTypeMenuHorizontalPosition(anchorLeft: number, viewportWidth: number): Pick<Position, "left" | "groupWidth" | "itemWidth" | "side"> {
  const padding = 8;
  const groupWidth = Math.min(280, viewportWidth - padding * 2);
  const groupLeft = Math.max(padding, Math.min(anchorLeft, viewportWidth - padding - groupWidth));
  const right = viewportWidth - padding - groupLeft - groupWidth;
  const left = groupLeft - padding;
  if (right >= 240) return { left: groupLeft, groupWidth, itemWidth: Math.min(360, right), side: "right" };
  if (left >= 240) {
    const itemWidth = Math.min(360, left);
    return { left: groupLeft - itemWidth, groupWidth, itemWidth, side: "left" };
  }
  return { left: groupLeft, groupWidth, itemWidth: groupWidth, side: "below" };
}

const itemClass = "block w-full rounded px-3 py-2.5 text-left text-sm leading-5 hover:bg-blue-50 focus:bg-blue-50 focus:outline-none dark:hover:bg-zinc-800 dark:focus:bg-zinc-800";

export default function PersonnelOrderTypeMenu({ value, language, onChange, disabled = false, variants = {}, selectedVersion }: Props) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const popup = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const submenu = useRef<HTMLDivElement>(null);
  const variantMenu = useRef<HTMLDivElement>(null);
  const [variantType, setVariantType] = useState<PersonnelOrderCreateType | null>(null);
  const variantOrigin = useRef<Point | null>(null);
  const variantTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingVariant = useRef<{ type: PersonnelOrderCreateType | null } | null>(null);
  const groups = useRef(new Map<PersonnelOrderGroupId, HTMLButtonElement>());
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingGroup = useRef<PersonnelOrderGroupId | null>(null);
  const pointerOrigin = useRef<Point | null>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState<PersonnelOrderGroupId | null>(null);
  const [position, setPosition] = useState<Position>({ left: 8, top: 8, groupWidth: 280, itemWidth: 360, maxHeight: 460, side: "right" });
  const kk = language === "kk";
  const searching = query.trim().length > 0;
  const results = searching ? [...new Set([...searchPersonnelOrderTypes(query), ...Object.entries(variants).filter(([,rows]) => rows.some(row => `${row.name_ru} ${row.name_kk}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))).map(([code]) => code as PersonnelOrderCreateType)])] : [];
  const types = active ? personnelOrderGroupTypes(active) : [];

  function cancelHover() {
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    hoverTimer.current = null;
    pendingGroup.current = null;
  }

  function cancelVariantHover() {
    if (variantTimer.current) clearTimeout(variantTimer.current);
    variantTimer.current = null; pendingVariant.current = null;
  }
  function headsToVariant(point: Point) {
    return Boolean(variantOrigin.current && variantMenu.current && pointerHeadsToSubmenu(variantOrigin.current, point, variantMenu.current.getBoundingClientRect(), position.side));
  }
  function scheduleVariantIntent() {
    if (variantTimer.current) clearTimeout(variantTimer.current);
    variantTimer.current = setTimeout(() => {
      if (pendingVariant.current) setVariantType(pendingVariant.current.type);
      pendingVariant.current = null; variantOrigin.current = null;
    }, 350);
  }
  function hoverType(type: PersonnelOrderCreateType, point: Point) {
    const next = (variants[type]?.length || 0) > 1 ? type : null;
    cancelVariantHover();
    if (variantType && next !== variantType && headsToVariant(point)) {
      pendingVariant.current = { type: next }; scheduleVariantIntent();
    } else { variantOrigin.current = point; setVariantType(next); }
  }

  function close(restoreFocus = true) {
    cancelHover();
    cancelVariantHover();
    setOpen(false);
    if (restoreFocus) trigger.current?.focus();
  }

  function scheduleIntent() {
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    // A deliberate pause over another group still opens it. Continuous travel
    // inside the triangle to the submenu keeps the current group instead.
    hoverTimer.current = setTimeout(() => {
      if (pendingGroup.current) { setActive(pendingGroup.current); setVariantType(null); cancelVariantHover(); }
      pendingGroup.current = null;
      pointerOrigin.current = null;
    }, 350);
  }

  function headsToSubmenu(point: Point) {
    return Boolean(pointerOrigin.current && submenu.current && pointerHeadsToSubmenu(pointerOrigin.current, point, submenu.current.getBoundingClientRect(), position.side));
  }

  function activate(group: PersonnelOrderGroupId, hover = false, point?: Point) {
    cancelHover();
    if (hover && active && group !== active && point && headsToSubmenu(point)) {
      pendingGroup.current = group;
      scheduleIntent();
    } else {
      cancelVariantHover();
      pointerOrigin.current = point || null;
      setActive(group);
      setVariantType(null);
    }
  }

  function choose(type: PersonnelOrderCreateType, versionId?: number) {
    const choices = variants[type] || [];
    if (versionId == null && choices.length > 1) { setVariantType(type); return; }
    if (versionId == null && choices.length === 1) onChange(type, choices[0].template_version_id);
    else if (versionId != null) onChange(type, versionId);
    else onChange(type);
    close();
  }

  useEffect(() => {
    if (!open) return;
    search.current?.focus();
    const outside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!popup.current?.contains(target) && !trigger.current?.contains(target)) close(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => { document.removeEventListener("pointerdown", outside); cancelHover(); cancelVariantHover(); };
  }, [open]);

  useLayoutEffect(() => {
    if (!open || !trigger.current) return;
    const place = () => {
      const rect = trigger.current!.getBoundingClientRect();
      const viewport = window.visualViewport;
      const viewportLeft = viewport?.offsetLeft || 0;
      const viewportTop = viewport?.offsetTop || 0;
      const horizontal = orderTypeMenuHorizontalPosition(rect.left - viewportLeft, viewport?.width || window.innerWidth);
      if (variantType) {
        const width = viewport?.width || window.innerWidth;
        const anchor = rect.left - viewportLeft;
        const panels = searching ? 1 : 2;
        const minimum = horizontal.groupWidth + 240 * panels;
        if (width - anchor - 8 >= minimum) {
          horizontal.side = "right"; horizontal.left = anchor;
          horizontal.itemWidth = Math.min(360, (width - anchor - 8 - horizontal.groupWidth) / panels);
        } else if (anchor + horizontal.groupWidth - 8 >= minimum) {
          horizontal.side = "left";
          horizontal.itemWidth = Math.min(360, (anchor - 8) / panels);
          horizontal.left = anchor - horizontal.itemWidth * panels;
        } else {
          horizontal.side = "below"; horizontal.left = Math.max(8, Math.min(anchor, width - horizontal.groupWidth - 8));
          horizontal.itemWidth = horizontal.groupWidth;
        }
      }
      horizontal.left += viewportLeft;
      const groupLeft = horizontal.side === "left" ? horizontal.left + horizontal.itemWidth * (variantType && !searching ? 2 : 1) : horizontal.left;
      const below = viewportTop + (viewport?.height || window.innerHeight) - rect.bottom - 12;
      const above = rect.top - viewportTop - 12;
      const height = Math.min(popup.current?.scrollHeight || 460, 460);
      const down = below >= 460 || below >= above;
      const maxHeight = Math.max(80, Math.min(460, down ? below : above));
      const top = down ? rect.bottom + 4 : Math.max(viewportTop + 8, rect.top - 4 - Math.min(height, maxHeight));
      setPosition({ ...horizontal, left: (active && !searching) || variantType ? horizontal.left : groupLeft, top, maxHeight });
    };
    place();
    const scroll = (event: Event) => {
      // Scrolling the menu must not move its fixed frame under a fingertip.
      if (!popup.current?.contains(event.target as Node)) place();
    };
    window.addEventListener("resize", place);
    window.addEventListener("scroll", scroll, true);
    window.visualViewport?.addEventListener("resize", place);
    window.visualViewport?.addEventListener("scroll", place);
    return () => {
      window.removeEventListener("resize", place); window.removeEventListener("scroll", scroll, true);
      window.visualViewport?.removeEventListener("resize", place); window.visualViewport?.removeEventListener("scroll", place);
    };
  }, [open, active, query, language, variantType]);

  useEffect(() => {
    if (open && active && !searching && position.side === "below" && popup.current && submenu.current) {
      popup.current.scrollTop = variantType && variantMenu.current ? variantMenu.current.offsetTop : submenu.current.offsetTop;
    }
  }, [open, active, searching, position.side, position.maxHeight, variantType]);

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" || event.key === "Tab") {
      event.preventDefault(); event.stopPropagation(); close(); return;
    }
    const target = event.target as HTMLElement;
    if (target === search.current) {
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        event.preventDefault();
        const buttons = popup.current?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]');
        if (buttons?.length) buttons[event.key === "ArrowDown" ? 0 : buttons.length - 1].focus();
      } else if (event.key === "Enter") {
        event.preventDefault(); event.stopPropagation();
        if (searching && results[0]) choose(results[0]);
      }
      return;
    }
    if (event.key === "ArrowRight" && target.dataset.group) {
      event.preventDefault();
      activate(target.dataset.group as PersonnelOrderGroupId);
      requestAnimationFrame(() => submenu.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus());
    } else if (event.key === "ArrowRight" && target.dataset.typeCode && (variants[target.dataset.typeCode]?.length || 0) > 1) {
      event.preventDefault(); setVariantType(target.dataset.typeCode as PersonnelOrderCreateType);
      requestAnimationFrame(() => variantMenu.current?.querySelector<HTMLButtonElement>('[role="menuitem"]')?.focus());
    } else if (event.key === "ArrowLeft" && variantMenu.current?.contains(target) && variantType) {
      event.preventDefault(); submenu.current?.querySelector<HTMLButtonElement>(`[data-type-code="${variantType}"]`)?.focus(); setVariantType(null);
    } else if (event.key === "ArrowLeft" && submenu.current?.contains(target) && active) {
      event.preventDefault(); groups.current.get(active)?.focus();
    } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const buttons = Array.from(target.closest('[role="menu"]')?.querySelectorAll<HTMLButtonElement>('[role="menuitem"]') || []);
      const index = buttons.indexOf(target as HTMLButtonElement);
      const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
      buttons[next]?.focus();
    }
  }

  const variantName = (type: string, variant: PersonnelPublishedTemplateVariant) => {
    const name = (kk ? variant.name_kk || variant.name_ru : variant.name_ru || variant.name_kk).trim();
    const duplicates = (variants[type] || []).filter(v => (kk ? v.name_kk || v.name_ru : v.name_ru || v.name_kk).trim() === name);
    return duplicates.length > 1 ? `${name} · #${variant.template_id}, ${kk ? "нұсқа" : "версия"} ${variant.version_number}` : name;
  };
  const selectedVariant = variants[value]?.find(v => v.template_version_id === selectedVersion);
  const selectedName = selectedVariant ? variantName(value, selectedVariant) : "";
  const typeLabel = value ? personnelOrderTypeLabel(value, language) : kk ? "Бұйрық түрін таңдаңыз" : "Выберите тип кадрового приказа";
  const selectionLabel = selectedName || typeLabel;

  const menuItems = (codes: readonly PersonnelOrderCreateType[]) => codes.map(type => (
    <button key={type} type="button" role="menuitem" data-type-code={type} className={itemClass} onClick={() => choose(type)}
      aria-haspopup={(variants[type]?.length || 0) > 1 ? "menu" : undefined}
      aria-expanded={(variants[type]?.length || 0) > 1 ? variantType === type : undefined}
      onPointerEnter={event => { if (event.pointerType !== "touch") hoverType(type, { x: event.clientX, y: event.clientY }); }}
      onPointerMove={event => { if (variantType === type) variantOrigin.current = { x: event.clientX, y: event.clientY }; }}>
      {(variants[type]?.length || 0) === 1 ? variantName(type, variants[type][0]) : personnelOrderTypeLabel(type, language)}
      {(variants[type]?.length || 0) > 1 ? <span aria-hidden="true"> ›</span> : null}
    </button>
  ));

  return (
    <div className="space-y-1 text-sm font-medium leading-5 text-zinc-800 dark:text-zinc-100">
      <label htmlFor={`${id}-trigger`}>Тип кадрового приказа</label>
      <button ref={trigger} id={`${id}-trigger`} type="button" value={value} aria-label="Тип кадрового приказа" aria-haspopup="menu" aria-expanded={open} aria-controls={open ? `${id}-popup` : undefined} disabled={disabled} className="flex w-full items-center justify-between gap-3 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-left text-sm font-normal text-zinc-950 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50" onClick={() => {
        if (open) close();
        else { setQuery(""); setVariantType(null); setActive(value ? PERSONNEL_ORDER_TYPE_GROUP[value as PersonnelOrderCreateType] || null : null); setOpen(true); }
      }}>
        <span>{selectionLabel}</span>
        <span aria-hidden="true">▾</span>
      </button>
      {open && createPortal(
        <div ref={popup} id={`${id}-popup`} data-testid="personnel-order-type-menu" onKeyDown={onKeyDown} onPointerLeave={() => { cancelHover(); cancelVariantHover(); }} onPointerMove={event => {
          if (pendingVariant.current) {
            const point = { x: event.clientX, y: event.clientY };
            if (headsToVariant(point)) scheduleVariantIntent();
            else { const next = pendingVariant.current.type; cancelVariantHover(); variantOrigin.current = point; setVariantType(next); }
          }
          if (!pendingGroup.current) return;
          const point = { x: event.clientX, y: event.clientY };
          if (headsToSubmenu(point)) scheduleIntent();
          else { const group = pendingGroup.current; cancelHover(); cancelVariantHover(); pointerOrigin.current = point; setActive(group); setVariantType(null); }
        }} className="fixed z-[80] flex overflow-y-auto overscroll-contain rounded-xl border border-zinc-200 bg-white text-zinc-950 shadow-xl dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50" style={{ left: position.left, top: position.top, maxHeight: position.maxHeight, maxWidth: "calc(100vw - 16px)", flexDirection: position.side === "below" ? "column" : position.side === "left" ? "row-reverse" : "row" }} data-side={position.side}>
          <div style={{ width: position.groupWidth }} className="shrink-0 p-2">
            <input ref={search} type="search" aria-label={kk ? "Бұйрық түрін іздеу" : "Поиск вида приказа"} placeholder={kk ? "RU / KZ атауы бойынша іздеу" : "Поиск по названию RU / KZ"} value={query} onChange={event => { cancelHover(); setQuery(event.target.value); }} className="mb-2 w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 dark:border-zinc-600" />
            {searching ? (
              <div role="menu" aria-label={kk ? "Іздеу нәтижелері" : "Результаты поиска"}>
                {results.length ? menuItems(results) : <p role="status" className="px-3 py-2 text-sm text-zinc-500">{kk ? "Ештеңе табылмады" : "Ничего не найдено"}</p>}
              </div>
            ) : (
              <div role="menu" aria-label={kk ? "Бұйрық топтары" : "Группы приказов"}>
                {PERSONNEL_ORDER_GROUPS.map(group => (
                  <button ref={node => { if (node) groups.current.set(group.id, node); else groups.current.delete(group.id); }} key={group.id} type="button" role="menuitem" data-group={group.id} aria-haspopup="menu" aria-expanded={active === group.id} aria-controls={active === group.id ? `${id}-types` : undefined} onPointerEnter={event => { if (event.pointerType !== "touch") activate(group.id, true, { x: event.clientX, y: event.clientY }); }} onPointerMove={event => { if (active === group.id) pointerOrigin.current = { x: event.clientX, y: event.clientY }; }} onFocus={() => activate(group.id)} onClick={() => activate(group.id)} className={`${itemClass} flex items-center justify-between gap-3 ${active === group.id ? "bg-blue-50 dark:bg-zinc-800" : ""}`}>
                    <span>{group[language]}</span><span aria-hidden="true">{position.side === "left" ? "‹" : "›"}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {!searching && active ? (
            <div ref={submenu} id={`${id}-types`} role="menu" aria-label={personnelOrderGroupLabel(active, language)} onPointerEnter={cancelHover} className="shrink-0 border-l border-zinc-200 p-2 dark:border-zinc-700" style={{ width: position.itemWidth }}>
              <p className="px-3 py-2 text-xs font-semibold text-zinc-500">{personnelOrderGroupLabel(active, language)}</p>
              {types.length ? menuItems(types) : <p role="status" className="px-3 py-2 text-sm text-zinc-500">{kk ? "Қолжетімді түрлер әзірге жоқ" : "Пока нет доступных видов"}</p>}
            </div>
          ) : null}
          {variantType && (variants[variantType]?.length || 0) > 1 ? <div ref={variantMenu} role="menu" aria-label={kk ? "Үлгі нұсқалары" : "Варианты шаблона"} onPointerEnter={cancelVariantHover}
            className="shrink-0 border-l border-zinc-200 p-2 dark:border-zinc-700" style={{ width: position.itemWidth }}>
            <p className="px-3 py-2 text-xs font-semibold text-zinc-500">{kk ? "Үлгі нұсқалары" : "Варианты шаблона"}</p>
            {variants[variantType].map(v => <button key={v.template_version_id} type="button" role="menuitem" data-template-version={v.template_version_id}
              onClick={() => choose(variantType, v.template_version_id)} className={itemClass}>{variantName(variantType, v)}</button>)}
          </div> : null}
        </div>, document.body,
      )}
    </div>
  );
}
