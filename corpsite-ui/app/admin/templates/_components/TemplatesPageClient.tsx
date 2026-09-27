"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import RegularTasksAdminClient from "@/app/regular-tasks/_components/RegularTasksAdminClient";

import {
  buildTemplateSectionHref,
  resolveTemplateSection,
  TEMPLATE_SECTIONS,
  type TemplateSection,
} from "../_lib/templateSections";
import { listPersonnelOrderTemplateCatalog, type PersonnelOrderTemplateCatalogItem } from "../_lib/personnelOrderTemplatesApi.client";

const TAB_CLASS = "rounded-xl border px-4 py-2 text-sm font-medium transition";

export default function TemplatesPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeSection = resolveTemplateSection(searchParams.get("section"));
  const [items, setItems] = useState<PersonnelOrderTemplateCatalogItem[]>([]);
  const [query, setQuery] = useState("");
  const [level, setLevel] = useState("ALL");
  const selectedType = searchParams.get("type") || "";

  useEffect(() => {
    if (activeSection !== TEMPLATE_SECTIONS.personnelOrders) return;
    void listPersonnelOrderTemplateCatalog().then((data) => setItems(data.items)).catch(() => setItems([]));
  }, [activeSection]);
  const visibleItems = useMemo(() => items.filter((item) => {
    const haystack = `${item.type_code} ${item.title_ru} ${item.title_kk}`.toLowerCase();
    return (level === "ALL" || item.support_level === level) && haystack.includes(query.toLowerCase());
  }), [items, level, query]);

  function selectSection(section: TemplateSection) {
    if (section === activeSection) return;
    router.push(buildTemplateSectionHref(section, searchParams));
  }
  function selectType(type: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("section", TEMPLATE_SECTIONS.personnelOrders);
    params.set("type", type);
    router.push(`/admin/templates?${params.toString()}`);
  }

  return (
    <div className="notranslate flex flex-col gap-3 text-zinc-900 dark:text-zinc-50" lang="ru" translate="no" data-testid="templates-page">
      <header>
        <h1 className="text-3xl font-semibold tracking-tight">Шаблоны</h1>
      </header>

      <nav className="flex flex-wrap gap-2" aria-label="Разделы шаблонов">
        <button
          type="button"
          onClick={() => selectSection(TEMPLATE_SECTIONS.tasks)}
          className={`${TAB_CLASS} ${activeSection === TEMPLATE_SECTIONS.tasks ? "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50" : "border-zinc-200 bg-zinc-100/30 text-zinc-600 hover:bg-zinc-200 dark:border-zinc-800 dark:bg-zinc-900/30 dark:text-zinc-400 dark:hover:bg-zinc-800"}`}
          aria-current={activeSection === TEMPLATE_SECTIONS.tasks ? "page" : undefined}
        >
          Шаблоны задач
        </button>
        <button
          type="button"
          onClick={() => selectSection(TEMPLATE_SECTIONS.personnelOrders)}
          className={`${TAB_CLASS} ${activeSection === TEMPLATE_SECTIONS.personnelOrders ? "border-zinc-300 bg-white text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-50" : "border-zinc-200 bg-zinc-100/30 text-zinc-600 hover:bg-zinc-200 dark:border-zinc-800 dark:bg-zinc-900/30 dark:text-zinc-400 dark:hover:bg-zinc-800"}`}
          aria-current={activeSection === TEMPLATE_SECTIONS.personnelOrders ? "page" : undefined}
        >
          Шаблоны кадровых приказов
        </button>
      </nav>

      {activeSection === TEMPLATE_SECTIONS.tasks ? (
        <section aria-labelledby="task-templates-heading" data-testid="task-templates-section">
          <h2 id="task-templates-heading" className="sr-only">Шаблоны задач</h2>
          <RegularTasksAdminClient embedded />
        </section>
      ) : (
        <section className="space-y-3" aria-labelledby="personnel-order-templates-heading" data-testid="personnel-order-templates-catalog">
          <h2 id="personnel-order-templates-heading" className="text-xl font-semibold">Шаблоны кадровых приказов</h2>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Встроенные read-only шаблоны, построенные по действующим генераторам. Редактирование и версионирование будут добавлены на следующем этапе.
          </p>
          <div className="flex gap-2"><input aria-label="Поиск шаблонов кадровых приказов" value={query} onChange={(e) => setQuery(e.target.value)} className="rounded border px-2 py-1" /><select aria-label="Уровень поддержки" value={level} onChange={(e) => setLevel(e.target.value)} className="rounded border px-2 py-1"><option value="ALL">Все уровни</option><option value="SUPPORTED">SUPPORTED</option><option value="PARTIAL">PARTIAL</option><option value="NOT_IMPLEMENTED">NOT_IMPLEMENTED</option></select></div>
          <div className="grid gap-2 md:grid-cols-2" data-testid="personnel-order-template-list">{visibleItems.map((item) => <button type="button" key={item.type_code} onClick={() => selectType(item.type_code)} className="rounded border p-3 text-left" data-testid={`personnel-order-template-${item.type_code}`}><div className="font-medium">{item.title_ru}</div><div>{item.title_kk}</div><div className="font-mono text-xs">{item.type_code}</div><div>{item.support_level} · {item.supported_locales.join(", ")} · Встроенный шаблон {item.is_pilot ? "· Пилот" : ""}</div></button>)}</div>
          {selectedType && items.find((item) => item.type_code === selectedType) ? (() => { const item = items.find((row) => row.type_code === selectedType)!; return <aside data-testid="personnel-order-template-detail" className="rounded border p-3"><h3>{item.title_ru}</h3><p>{item.title_kk}</p><p>{item.type_code} · {item.support_level}</p><p>{item.uses_specialized_generator ? "Специализированный генератор" : "Общий fallback"}</p><p>Обязательные поля: {item.required_fields.join(", ") || "не формализованы"}</p><p>{item.notes}</p></aside>; })() : null}
        </section>
      )}
    </div>
  );
}
