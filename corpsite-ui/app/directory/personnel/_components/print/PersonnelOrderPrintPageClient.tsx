"use client";

import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { getPositions } from "@/app/directory/employees/_lib/api.client";
import { getOrgUnitsTree, type TreeNode } from "@/app/directory/org-units/_lib/api.client";

import {
  PERSONNEL_ORDERS_BASE_PATH,
  getPersonnelOrder,
  getPersonnelOrderEditorial,
  mapPersonnelOrdersApiError,
} from "../../_lib/personnelOrdersApi.client";
import {
  PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT,
  buildPersonnelOrderPrintHref,
  parsePersonnelOrderPrintLanguage,
  type PersonnelOrderPrintLanguage,
} from "../../_lib/personnelOrderPrintLanguage";
import { openPersonnelOrderPdf } from "../../_lib/personnelOrderPdfOpen.client";
import {
  buildPersonnelOrderPrintViewModel,
  collectPersonnelOrderPrintLookupIds,
  type PersonnelOrderPrintViewModel,
} from "../../_lib/personnelOrderPrintViewModel";
import PersonnelOrderPrintDocument from "./PersonnelOrderPrintDocument";
import PersonnelOrderPrintToolbar from "./PersonnelOrderPrintToolbar";

type Props = {
  orderId: number;
};

function flattenOrgUnitNames(nodes: TreeNode[], out: Record<number, string>) {
  for (const node of nodes) {
    const unitId = Number(node.unit_id ?? node.id);
    if (Number.isFinite(unitId) && unitId > 0) {
      const name = String(node.name ?? node.name_ru ?? "").trim();
      if (name) out[unitId] = name;
    }
    if (Array.isArray(node.children) && node.children.length > 0) {
      flattenOrgUnitNames(node.children, out);
    }
  }
}

async function loadOrganizationName(): Promise<string | null> {
  try {
    const res = await fetch("/tenant.json", { cache: "no-store" });
    if (!res.ok) return null;
    const json = (await res.json()) as { orgName?: string };
    const name = String(json?.orgName ?? "").trim();
    return name || null;
  } catch {
    return null;
  }
}

export default function PersonnelOrderPrintPageClient({ orderId }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const languageParam = searchParams.get("language");
  const parsedLanguage = parsePersonnelOrderPrintLanguage(languageParam, {
    fallbackToDefault: false,
  });
  const languageInvalid = Boolean(languageParam && parsedLanguage == null);
  const language: PersonnelOrderPrintLanguage =
    parsedLanguage ?? PERSONNEL_ORDER_PRINT_LANGUAGE_DEFAULT;

  const [model, setModel] = React.useState<PersonnelOrderPrintViewModel | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [pdfBusy, setPdfBusy] = React.useState(false);
  const [pdfError, setPdfError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const detail = await getPersonnelOrder(orderId);
        const ids = collectPersonnelOrderPrintLookupIds(detail);
        const [organizationName, tree, positionsRaw, editorial] = await Promise.all([
          loadOrganizationName(),
          getOrgUnitsTree({ include_inactive: false }).catch(() => null),
          getPositions({ limit: 1000, offset: 0 }).catch(() => null),
          getPersonnelOrderEditorial(orderId).catch(() => null),
        ]);

        const orgUnitNames: Record<number, string> = {};
        if (tree?.items) flattenOrgUnitNames(tree.items, orgUnitNames);

        const positionNames: Record<number, string> = {};
        const list = Array.isArray(positionsRaw)
          ? positionsRaw
          : Array.isArray((positionsRaw as { items?: unknown[] } | null)?.items)
            ? ((positionsRaw as { items: unknown[] }).items)
            : [];
        for (const row of list) {
          const id = Number(
            (row as { position_id?: number; id?: number }).position_id ??
              (row as { id?: number }).id,
          );
          if (!Number.isFinite(id) || id <= 0) continue;
          if (ids.positionIds.length > 0 && !ids.positionIds.includes(id)) continue;
          const name = String((row as { name?: string }).name ?? "").trim();
          if (name) positionNames[id] = name;
        }

        if (cancelled) return;
        setModel(
          buildPersonnelOrderPrintViewModel(detail, {
            organizationName,
            orgUnitNames,
            positionNames,
            editorial,
          }),
        );
      } catch (e) {
        if (cancelled) return;
        setModel(null);
        setError(mapPersonnelOrdersApiError(e, "Не удалось загрузить приказ для печати."));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [orderId]);

  function handleLanguageChange(next: PersonnelOrderPrintLanguage) {
    router.replace(buildPersonnelOrderPrintHref(orderId, next));
  }

  async function handleOpenPdf() {
    setPdfBusy(true);
    setPdfError(null);
    const result = await openPersonnelOrderPdf(orderId, language);
    setPdfBusy(false);
    if (!result.ok) setPdfError(result.error);
  }

  return (
    <div className="personnel-order-print-page min-h-screen bg-zinc-100 px-3 py-4 text-zinc-900 dark:bg-zinc-900 dark:text-zinc-50">
      <div className="mx-auto max-w-[210mm]">
        <PersonnelOrderPrintToolbar
          backHref={`${PERSONNEL_ORDERS_BASE_PATH}?order_id=${orderId}`}
          language={language}
          onLanguageChange={handleLanguageChange}
          onOpenPdf={handleOpenPdf}
          pdfBusy={pdfBusy}
        />

        {languageInvalid ? (
          <div
            className="print:hidden mb-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
            data-testid="personnel-order-print-language-fallback"
          >
            Неизвестный язык «{languageParam}». Показан русский вариант.
          </div>
        ) : null}

        {loading ? (
          <div className="rounded-xl border border-zinc-200 bg-white px-4 py-8 text-sm text-zinc-500">
            Загрузка печатной формы…
          </div>
        ) : null}

        {error ? (
          <div
            className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            data-testid="personnel-order-print-error"
          >
            {error}
          </div>
        ) : null}

        {pdfError ? (
          <div
            className="print:hidden mb-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800"
            data-testid="personnel-order-pdf-error"
          >
            {pdfError}
          </div>
        ) : null}

        {model ? (
          <div className="personnel-order-print-sheet rounded-sm border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-700 sm:p-10">
            <PersonnelOrderPrintDocument model={model} language={language} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
