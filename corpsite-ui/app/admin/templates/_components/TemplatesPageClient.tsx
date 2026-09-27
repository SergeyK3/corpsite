"use client";

import { useRouter, useSearchParams } from "next/navigation";

import RegularTasksAdminClient from "@/app/regular-tasks/_components/RegularTasksAdminClient";

import {
  buildTemplateSectionHref,
  resolveTemplateSection,
  TEMPLATE_SECTIONS,
  type TemplateSection,
} from "../_lib/templateSections";

const TAB_CLASS = "rounded-xl border px-4 py-2 text-sm font-medium transition";

export default function TemplatesPageClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const activeSection = resolveTemplateSection(searchParams.get("section"));

  function selectSection(section: TemplateSection) {
    if (section === activeSection) return;
    router.push(buildTemplateSectionHref(section, searchParams));
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
        <section
          className="rounded-2xl border border-zinc-200 bg-zinc-100 p-5 dark:border-zinc-800 dark:bg-zinc-900"
          aria-labelledby="personnel-order-templates-heading"
          data-testid="personnel-order-templates-empty-state"
        >
          <h2 id="personnel-order-templates-heading" className="text-xl font-semibold">Шаблоны кадровых приказов</h2>
          <p className="mt-2 text-sm text-zinc-600 dark:text-zinc-400">
            Здесь будет каталог версионируемых RU/KK-шаблонов кадровых приказов.
          </p>
        </section>
      )}
    </div>
  );
}
