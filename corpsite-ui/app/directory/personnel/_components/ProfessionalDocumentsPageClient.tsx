// FILE: corpsite-ui/app/directory/personnel/_components/ProfessionalDocumentsPageClient.tsx
"use client";

import * as React from "react";
import Link from "next/link";

import { buildEmployeeCardHref } from "@/lib/employeeCardNav";
import { OPEN_HR_DOSSIER_CTA } from "@/lib/personnelCardTerminology";
import {
  countDocumentsByExpiryStatus,
  DOCUMENT_QUICK_FILTERS,
  DOCUMENT_STATUS_SUMMARY_ORDER,
  documentExpiryStatus,
  expiryStatusMeta,
  fmtProfileDate,
  matchesDocumentQuickFilter,
  trainingHoursStatusMeta,
  type DocumentQuickFilter,
} from "../../employees/_lib/professionalProfile";
import EmployeeDocumentFormModal from "./EmployeeDocumentFormModal";
import EmployeeDocumentViewModal from "./EmployeeDocumentViewModal";
import {
  isHttpUrl,
  listDocumentKinds,
  listDocumentTypes,
  listEmployeeDocuments,
  getEmployeeTrainingHoursSummary,
  listMedicalSpecialties,
  listMedicalSpecialtyGroups,
  mapDocumentsApiError,
  type DocumentKindRow,
  type DocumentTypeRow,
  type EmployeeDocumentRow,
  type MedicalSpecialtyGroupRow,
  type MedicalSpecialtyRow,
  type TrainingHoursSummary,
} from "../_lib/documentsApi.client";

const EXPIRY_FILTER_OPTIONS = [
  { value: "", label: "Все статусы срока" },
  ...DOCUMENT_STATUS_SUMMARY_ORDER.map((status) => ({
    value: status,
    label: expiryStatusMeta(status).label,
  })),
];

const EMPLOYEE_ACTIVE_OPTIONS = [
  { value: "", label: "Все сотрудники" },
  { value: "true", label: "Только активные" },
  { value: "false", label: "Только неактивные" },
];

function FileUrlCell({ value }: { value: string | null | undefined }) {
  const url = String(value || "").trim();
  if (!url) return <span className="text-zinc-400">—</span>;
  if (isHttpUrl(url)) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 hover:underline dark:text-blue-400"
        onClick={(e) => e.stopPropagation()}
        title={url}
      >
        {url.length > 28 ? `${url.slice(0, 28)}…` : url}
      </a>
    );
  }
  return (
    <span className="font-mono text-xs text-zinc-700 dark:text-zinc-300" title={url}>
      {url.length > 28 ? `${url.slice(0, 28)}…` : url}
    </span>
  );
}

export default function ProfessionalDocumentsPageClient() {
  const [items, setItems] = React.useState<EmployeeDocumentRow[]>([]);
  const [chipItems, setChipItems] = React.useState<EmployeeDocumentRow[]>([]);
  const [total, setTotal] = React.useState(0);
  const [loading, setLoading] = React.useState(true);
  const [refsLoading, setRefsLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [forbidden, setForbidden] = React.useState(false);
  const [refsError, setRefsError] = React.useState<string | null>(null);

  const [documentTypes, setDocumentTypes] = React.useState<DocumentTypeRow[]>([]);
  const [documentKinds, setDocumentKinds] = React.useState<DocumentKindRow[]>([]);
  const [specialtyGroups, setSpecialtyGroups] = React.useState<MedicalSpecialtyGroupRow[]>([]);
  const [specialties, setSpecialties] = React.useState<MedicalSpecialtyRow[]>([]);


  const [formOpen, setFormOpen] = React.useState(false);
  const [formMode, setFormMode] = React.useState<"create" | "edit">("create");
  const [editingDocument, setEditingDocument] = React.useState<EmployeeDocumentRow | null>(null);
  const [viewOpen, setViewOpen] = React.useState(false);
  const [viewDocument, setViewDocument] = React.useState<EmployeeDocumentRow | null>(null);

  const [searchQ, setSearchQ] = React.useState("");
  const [debouncedQ, setDebouncedQ] = React.useState("");
  const [documentTypeFilter, setDocumentTypeFilter] = React.useState("");
  const [groupFilter, setGroupFilter] = React.useState("");
  const [specialtyFilter, setSpecialtyFilter] = React.useState("");
  const [expiryFilter, setExpiryFilter] = React.useState("");
  const [employeeActiveFilter, setEmployeeActiveFilter] = React.useState("");
  const [quickFilter, setQuickFilter] = React.useState<DocumentQuickFilter>("ALL");

  const [reloadToken, setReloadToken] = React.useState(0);
  const [trainingSummary, setTrainingSummary] = React.useState<TrainingHoursSummary | null>(null);
  const [trainingSummaryLoading, setTrainingSummaryLoading] = React.useState(false);

  React.useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedQ(searchQ.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [searchQ]);

  React.useEffect(() => {
    let cancelled = false;
    setRefsLoading(true);
    setRefsError(null);
    (async () => {
      try {
        const [typesBody, kindsBody, groupsBody, specialtiesBody] = await Promise.all([
          listDocumentTypes(true),
          listDocumentKinds(true),
          listMedicalSpecialtyGroups(),
          listMedicalSpecialties({ is_active: true }),
        ]);
        if (cancelled) return;
        setDocumentTypes(Array.isArray(typesBody.items) ? typesBody.items : []);
        setDocumentKinds(Array.isArray(kindsBody.items) ? kindsBody.items : []);
        setSpecialtyGroups(Array.isArray(groupsBody.items) ? groupsBody.items : []);
        setSpecialties(Array.isArray(specialtiesBody.items) ? specialtiesBody.items : []);
      } catch (e) {
        if (cancelled) return;
        setRefsError(mapDocumentsApiError(e, "Не удалось загрузить справочники."));
      } finally {
        if (!cancelled) setRefsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setForbidden(false);

    const employeeIsActive =
      employeeActiveFilter === "true"
        ? true
        : employeeActiveFilter === "false"
          ? false
          : undefined;

    (async () => {
      try {
        const commonArgs = {
          lifecycle_status: "ACTIVE" as const,
          q: debouncedQ || undefined,
          document_type_id: documentTypeFilter ? Number(documentTypeFilter) : undefined,
          group_id: groupFilter ? Number(groupFilter) : undefined,
          medical_specialty_id: specialtyFilter ? Number(specialtyFilter) : undefined,
          employee_is_active: employeeIsActive,
          limit: 500,
          offset: 0,
        };

        const [listBody, chipBody] = await Promise.all([
          listEmployeeDocuments({
            ...commonArgs,
            expiry_status: expiryFilter || undefined,
          }),
          listEmployeeDocuments(commonArgs),
        ]);

        if (cancelled) return;
        setItems(Array.isArray(listBody.items) ? listBody.items : []);
        setTotal(Number(listBody.total) || 0);
        setChipItems(Array.isArray(chipBody.items) ? chipBody.items : []);
      } catch (e) {
        if (cancelled) return;
        const message = mapDocumentsApiError(e, "Не удалось загрузить реестр документов.");
        if (message.includes("Недостаточно прав")) {
          setForbidden(true);
        }
        setItems([]);
        setChipItems([]);
        setTotal(0);
        setError(message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [
    debouncedQ,
    documentTypeFilter,
    groupFilter,
    specialtyFilter,
    expiryFilter,
    employeeActiveFilter,
    reloadToken,
  ]);

  const filteredSpecialties = React.useMemo(() => {
    if (!groupFilter) return specialties;
    return specialties.filter((s) => String(s.group_id) === groupFilter);
  }, [groupFilter, specialties]);

  const statusCounts = React.useMemo(() => countDocumentsByExpiryStatus(chipItems), [chipItems]);

  const visibleItems = React.useMemo(() => {
    if (!quickFilter || quickFilter === "ALL") return items;
    if (expiryFilter) return items;
    return items.filter((row) =>
      matchesDocumentQuickFilter(documentExpiryStatus(row), quickFilter)
    );
  }, [items, quickFilter, expiryFilter]);

  const summaryEmployeeId = React.useMemo(() => {
    if (visibleItems.length === 0) return null;
    const ids = new Set(visibleItems.map((row) => row.employee_id));
    if (ids.size !== 1) return null;
    return visibleItems[0].employee_id;
  }, [visibleItems]);

  React.useEffect(() => {
    if (!summaryEmployeeId) {
      setTrainingSummary(null);
      return;
    }
    let cancelled = false;
    setTrainingSummaryLoading(true);
    (async () => {
      try {
        const summary = await getEmployeeTrainingHoursSummary({
          employee_id: summaryEmployeeId,
        });
        if (!cancelled) setTrainingSummary(summary);
      } catch {
        if (!cancelled) setTrainingSummary(null);
      } finally {
        if (!cancelled) setTrainingSummaryLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [summaryEmployeeId, reloadToken]);

  function reloadDocuments() {
    setReloadToken((v) => v + 1);
  }

  function openCreateForm() {
    setFormMode("create");
    setEditingDocument(null);
    setFormOpen(true);
  }

  function openView(row: EmployeeDocumentRow) {
    setViewDocument(row);
    setViewOpen(true);
  }

  function openEditForm(row: EmployeeDocumentRow) {
    setViewOpen(false);
    setFormMode("edit");
    setEditingDocument(row);
    setFormOpen(true);
  }

  function handleQuickFilter(value: DocumentQuickFilter) {
    setQuickFilter(value);
    if (value === "ALL" || value === "PROBLEMATIC" || !value) {
      setExpiryFilter("");
      return;
    }
    setExpiryFilter(value);
  }

  function handleExpiryDropdown(value: string) {
    setExpiryFilter(value);
    if (!value) {
      setQuickFilter("ALL");
      return;
    }
    const chip = DOCUMENT_QUICK_FILTERS.find((c) => c.value === value);
    setQuickFilter(chip ? (chip.value as DocumentQuickFilter) : "ALL");
  }

  const tableColSpan = 12;
  const trainingMeta = trainingSummary
    ? trainingHoursStatusMeta(trainingSummary.training_hours_status)
    : null;
  const trainingProgressPct = trainingSummary
    ? Math.min(
        100,
        Math.round(
          (trainingSummary.training_hours_last_5y / trainingSummary.training_hours_required) * 100
        )
      )
    : 0;
  const summaryEmployeeName =
    summaryEmployeeId != null
      ? visibleItems.find((row) => row.employee_id === summaryEmployeeId)?.employee_name
      : null;

  return (
    <div className="space-y-4 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">
            Реестр профессиональных документов
          </h1>
          <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
            Production-реестр ADR-037. Контроль сроков и профессиональных документов сотрудников.
          </p>
        </div>
        <button
          type="button"
          onClick={openCreateForm}
          disabled={refsLoading || Boolean(refsError) || forbidden}
          className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
        >
          + Добавить документ
        </button>
      </div>

      {refsError ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/55 dark:bg-amber-950/35 dark:text-amber-200">
          {refsError}
        </div>
      ) : null}

      {forbidden ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
          Недостаточно прав для просмотра реестра документов. Требуется доступ к кадровым процессам (personnel admin).
        </div>
      ) : null}

      {error && !forbidden ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {!loading && !error ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
          {DOCUMENT_STATUS_SUMMARY_ORDER.map((statusKey) => {
            const meta = expiryStatusMeta(statusKey);
            const active = quickFilter === statusKey || expiryFilter === statusKey;
            return (
              <button
                key={statusKey}
                type="button"
                onClick={() => handleQuickFilter(statusKey as DocumentQuickFilter)}
                className={[
                  "rounded-xl border p-4 text-left transition",
                  active
                    ? "border-blue-400 ring-2 ring-blue-200 dark:border-blue-600 dark:ring-blue-900/40"
                    : "border-zinc-200 hover:border-zinc-300 dark:border-zinc-800 dark:hover:border-zinc-700",
                  "bg-white dark:bg-zinc-950",
                ].join(" ")}
              >
                <div className="text-xs text-zinc-600 dark:text-zinc-400">{meta.label}</div>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
                    {statusCounts[statusKey] ?? 0}
                  </span>
                  <span
                    className={`inline-flex rounded-md px-1.5 py-0.5 text-[10px] font-medium ${meta.className}`}
                  >
                    {meta.label}
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      ) : null}

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/40">
        <div className="min-w-[14rem] flex-1">
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Поиск
          </label>
          <input
            type="search"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            placeholder="ФИО, название, номер документа"
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Тип документа
          </label>
          <select
            value={documentTypeFilter}
            onChange={(e) => setDocumentTypeFilter(e.target.value)}
            className="min-w-[12rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            <option value="">Все типы</option>
            {documentTypes.map((type) => (
              <option key={type.document_type_id} value={String(type.document_type_id)}>
                {type.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Группа специальностей
          </label>
          <select
            value={groupFilter}
            onChange={(e) => {
              setGroupFilter(e.target.value);
              setSpecialtyFilter("");
            }}
            className="min-w-[10rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            <option value="">Все группы</option>
            {specialtyGroups.map((group) => (
              <option key={group.group_id} value={String(group.group_id)}>
                {group.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Специальность
          </label>
          <select
            value={specialtyFilter}
            onChange={(e) => setSpecialtyFilter(e.target.value)}
            className="min-w-[12rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            <option value="">Все специальности</option>
            {filteredSpecialties.map((spec) => (
              <option key={spec.medical_specialty_id} value={String(spec.medical_specialty_id)}>
                {spec.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Статус срока
          </label>
          <select
            value={expiryFilter}
            onChange={(e) => handleExpiryDropdown(e.target.value)}
            className="min-w-[10rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            {EXPIRY_FILTER_OPTIONS.map((opt) => (
              <option key={opt.value || "all"} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
            Сотрудник
          </label>
          <select
            value={employeeActiveFilter}
            onChange={(e) => setEmployeeActiveFilter(e.target.value)}
            className="min-w-[10rem] rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          >
            {EMPLOYEE_ACTIVE_OPTIONS.map((opt) => (
              <option key={opt.value || "all"} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        <div className="text-sm text-zinc-500 dark:text-zinc-400">
          {loading ? "Загрузка…" : `${visibleItems.length} из ${total}`}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {DOCUMENT_QUICK_FILTERS.map((chip) => {
          const active = quickFilter === chip.value;
          return (
            <button
              key={chip.value || "all"}
              type="button"
              onClick={() => handleQuickFilter(chip.value)}
              className={[
                "rounded-full border px-3 py-1.5 text-sm font-medium transition",
                active
                  ? "border-blue-600 bg-blue-600 text-white"
                  : "border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-900",
              ].join(" ")}
            >
              {chip.label}
            </button>
          );
        })}
      </div>

      {summaryEmployeeId && (trainingSummaryLoading || trainingSummary) ? (
        <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          {trainingSummaryLoading && !trainingSummary ? (
            <div className="text-sm text-zinc-500">Загрузка сводки по часам…</div>
          ) : trainingSummary ? (
            <>
              <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                    Часы обучения: {summaryEmployeeName || `#${summaryEmployeeId}`}
                  </div>
                  <div className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                    За 5 лет ({fmtProfileDate(trainingSummary.window_start)} —{" "}
                    {fmtProfileDate(trainingSummary.as_of)})
                  </div>
                </div>
                {trainingMeta ? (
                  <span
                    className={`inline-flex rounded-md px-2 py-0.5 text-xs font-semibold ${trainingMeta.className}`}
                  >
                    {trainingMeta.label}
                  </span>
                ) : null}
              </div>
              <div className="mb-2 text-sm text-zinc-700 dark:text-zinc-300">
                <span className="font-semibold text-zinc-900 dark:text-zinc-50">
                  {trainingSummary.training_hours_last_5y} / {trainingSummary.training_hours_required}{" "}
                  ч
                </span>
                {trainingSummary.training_hours_remaining > 0 ? (
                  <span className="ml-3 text-zinc-600 dark:text-zinc-400">
                    Осталось {trainingSummary.training_hours_remaining} ч
                  </span>
                ) : null}
                {trainingSummary.incomplete_documents_count > 0 ? (
                  <span className="ml-3 text-amber-700 dark:text-amber-300">
                    Неполных: {trainingSummary.incomplete_documents_count}
                  </span>
                ) : null}
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
                <div
                  className={[
                    "h-full rounded-full",
                    trainingSummary.training_hours_status === "MET"
                      ? "bg-emerald-500"
                      : trainingSummary.training_hours_status === "INCOMPLETE"
                        ? "bg-amber-500"
                        : "bg-orange-500",
                  ].join(" ")}
                  style={{ width: `${trainingProgressPct}%` }}
                />
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-zinc-200 dark:border-zinc-800">
        <div className="overflow-x-auto">
          <table className="min-w-full border-collapse text-sm">
            <thead>
              <tr className="bg-zinc-100 text-left dark:bg-zinc-900">
                {[
                  "Сотрудник",
                  "Тип документа",
                  "Вид",
                  "Специальность",
                  "Обучение / программа",
                  "№ документа",
                  "Выдан",
                  "Часы",
                  "Действует до",
                  "Статус срока",
                  "Файл",
                  "",
                ].map((label) => (
                  <th
                    key={label || "actions"}
                    className="px-3 py-2 text-[11px] font-medium uppercase tracking-wide text-zinc-600 dark:text-zinc-400"
                  >
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={tableColSpan} className="px-3 py-8 text-center text-zinc-500">
                    Загрузка…
                  </td>
                </tr>
              ) : null}
              {!loading && !error && visibleItems.length === 0 ? (
                <tr>
                  <td colSpan={tableColSpan} className="px-3 py-8 text-center text-zinc-500">
                    {total === 0
                      ? "Документы не зарегистрированы. Нажмите «+ Добавить документ»."
                      : "Записи не найдены по выбранным фильтрам"}
                  </td>
                </tr>
              ) : null}
              {!loading
                ? visibleItems.map((row) => {
                    const meta = expiryStatusMeta(documentExpiryStatus(row));
                    return (
                      <tr
                        key={row.document_id}
                        onClick={() => openView(row)}
                        className="cursor-pointer border-t border-zinc-200 hover:bg-blue-50/60 dark:border-zinc-800 dark:hover:bg-blue-950/20"
                      >
                        <td className="px-3 py-2 font-medium text-zinc-900 dark:text-zinc-50">
                          <div>{row.employee_name || `#${row.employee_id}`}</div>
                          {row.employee_is_active === false ? (
                            <div className="text-[11px] text-zinc-500">неактивен</div>
                          ) : null}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {row.document_type_name}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {row.document_kind_name || "—"}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {row.medical_specialty_name || "—"}
                        </td>
                        <td className="max-w-[12rem] truncate px-3 py-2 text-zinc-700 dark:text-zinc-300" title={row.training_title || undefined}>
                          {row.training_title || "—"}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {row.document_number || "—"}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {fmtProfileDate(row.issued_at)}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {row.hours != null ? row.hours : "—"}
                        </td>
                        <td className="px-3 py-2 text-zinc-700 dark:text-zinc-300">
                          {fmtProfileDate(row.valid_until)}
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`inline-flex rounded-md px-2 py-0.5 text-xs font-medium ${meta.className}`}
                          >
                            {meta.label}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <FileUrlCell value={row.file_url} />
                        </td>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              openEditForm(row);
                            }}
                            className="rounded-md border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
                          >
                            Изменить
                          </button>
                          <Link
                            href={buildEmployeeCardHref(row.employee_id)}
                            onClick={(e) => e.stopPropagation()}
                            className="ml-1 inline-block rounded-md border border-zinc-300 px-2 py-1 text-xs hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-900"
                            title={OPEN_HR_DOSSIER_CTA}
                          >
                            Сотрудник
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                : null}
            </tbody>
          </table>
        </div>
      </div>


      <EmployeeDocumentViewModal
        open={viewOpen}
        document={viewDocument}
        onClose={() => setViewOpen(false)}
        onEdit={openEditForm}
        onArchived={reloadDocuments}
      />

      <EmployeeDocumentFormModal
        open={formOpen}
        mode={formMode}
        document={editingDocument}
        documentTypes={documentTypes}
        documentKinds={documentKinds}
        specialties={specialties}
        onClose={() => setFormOpen(false)}
        onSaved={reloadDocuments}
      />
    </div>
  );
}
