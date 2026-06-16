// FILE: corpsite-ui/app/directory/personnel/_components/EmployeeDocumentFormModal.tsx
"use client";

import * as React from "react";

import { loadOrgUnitSelectOptions } from "@/lib/orgUnitsSelect";
import { getEmployees } from "../../employees/_lib/api.client";
import type { EmployeeListItem } from "../../employees/_lib/types";
import type {
  DocumentKindRow,
  DocumentTypeRow,
  EmployeeDocumentRow,
  MedicalSpecialtyRow,
} from "../_lib/documentsApi.client";
import {
  archiveEmployeeDocument,
  createEmployeeDocument,
  mapDocumentsApiError,
  updateEmployeeDocument,
} from "../_lib/documentsApi.client";

type Props = {
  open: boolean;
  mode: "create" | "edit";
  document: EmployeeDocumentRow | null;
  documentTypes: DocumentTypeRow[];
  documentKinds: DocumentKindRow[];
  specialties: MedicalSpecialtyRow[];
  onClose: () => void;
  onSaved: () => void;
};

type FormState = {
  org_unit_id: string;
  employee_id: string;
  document_type_id: string;
  document_kind_id: string;
  medical_specialty_id: string;
  title: string;
  training_title: string;
  document_number: string;
  issued_by: string;
  issued_at: string;
  valid_until: string;
  file_url: string;
  comment: string;
};

const EMPTY_FORM: FormState = {
  org_unit_id: "",
  employee_id: "",
  document_type_id: "",
  document_kind_id: "",
  medical_specialty_id: "",
  title: "",
  training_title: "",
  document_number: "",
  issued_by: "",
  issued_at: "",
  valid_until: "",
  file_url: "",
  comment: "",
};

const selectClass =
  "w-full max-w-xs rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950";
const inputClass =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950";
const wideInputClass = `${inputClass} sm:col-span-2`;

const ALL_ORG_UNITS_VALUE = "__all__";
const EMPLOYEES_PAGE_LIMIT = 200;

function toDateInput(value: string | null | undefined): string {
  if (!value) return "";
  return value.slice(0, 10);
}

export default function EmployeeDocumentFormModal({
  open,
  mode,
  document: documentRow,
  documentTypes,
  documentKinds,
  specialties,
  onClose,
  onSaved,
}: Props) {
  const [form, setForm] = React.useState<FormState>(EMPTY_FORM);
  const [initialForm, setInitialForm] = React.useState<FormState>(EMPTY_FORM);
  const [orgUnitOptions, setOrgUnitOptions] = React.useState<Array<{ unit_id: number; name: string }>>([]);
  const [employees, setEmployees] = React.useState<EmployeeListItem[]>([]);
  const [loadingOrgUnits, setLoadingOrgUnits] = React.useState(false);
  const [loadingEmployees, setLoadingEmployees] = React.useState(false);
  const [employeesFetchError, setEmployeesFetchError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [archiving, setArchiving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const selectedType = React.useMemo(
    () => documentTypes.find((t) => String(t.document_type_id) === form.document_type_id) ?? null,
    [documentTypes, form.document_type_id]
  );

  const selectedKind = React.useMemo(
    () => documentKinds.find((k) => String(k.document_kind_id) === form.document_kind_id) ?? null,
    [documentKinds, form.document_kind_id]
  );

  const specialtyRequired = Boolean(selectedType?.requires_medical_specialty);

  React.useEffect(() => {
    if (!open) return;
    setError(null);

    if (mode === "edit" && documentRow) {
      const next: FormState = {
        org_unit_id: "",
        employee_id: String(documentRow.employee_id),
        document_type_id: String(documentRow.document_type_id),
        document_kind_id: documentRow.document_kind_id ? String(documentRow.document_kind_id) : "",
        medical_specialty_id: documentRow.medical_specialty_id
          ? String(documentRow.medical_specialty_id)
          : "",
        title: documentRow.title || "",
        training_title: documentRow.training_title || "",
        document_number: documentRow.document_number || "",
        issued_by: documentRow.issued_by || "",
        issued_at: toDateInput(documentRow.issued_at),
        valid_until: toDateInput(documentRow.valid_until),
        file_url: documentRow.file_url || "",
        comment: documentRow.comment || "",
      };
      setForm(next);
      setInitialForm(next);
      return;
    }

    setForm(EMPTY_FORM);
    setInitialForm(EMPTY_FORM);
  }, [open, mode, documentRow]);

  React.useEffect(() => {
    if (!open || mode !== "create") return;
    let cancelled = false;
    setLoadingOrgUnits(true);
    (async () => {
      try {
        const options = await loadOrgUnitSelectOptions();
        if (cancelled) return;
        setOrgUnitOptions(
          options.map((opt) => ({ unit_id: opt.unit_id, name: opt.name })).sort((a, b) => a.name.localeCompare(b.name, "ru"))
        );
      } catch {
        if (!cancelled) setOrgUnitOptions([]);
      } finally {
        if (!cancelled) setLoadingOrgUnits(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, mode]);

  React.useEffect(() => {
    if (!open || mode !== "create") return;
    const unitId = form.org_unit_id.trim();
    if (!unitId) {
      setEmployees([]);
      setEmployeesFetchError(null);
      return;
    }

    let cancelled = false;
    setLoadingEmployees(true);
    setEmployeesFetchError(null);
    (async () => {
      try {
        const body = await getEmployees(
          unitId === ALL_ORG_UNITS_VALUE
            ? {
                status: "all",
                limit: EMPLOYEES_PAGE_LIMIT,
                offset: 0,
              }
            : {
                status: "all",
                org_unit_id: unitId,
                include_children: true,
                limit: EMPLOYEES_PAGE_LIMIT,
                offset: 0,
              }
        );
        if (cancelled) return;
        setEmployees(Array.isArray(body.items) ? body.items : []);
      } catch (err) {
        if (!cancelled) {
          setEmployees([]);
          setEmployeesFetchError(
            mapDocumentsApiError(err, "Не удалось загрузить список сотрудников.")
          );
        }
      } finally {
        if (!cancelled) setLoadingEmployees(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, mode, form.org_unit_id]);

  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      if (key === "org_unit_id") {
        next.employee_id = "";
      }
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const typeId = Number(form.document_type_id);
      if (!Number.isFinite(typeId) || typeId <= 0) {
        setError("Выберите тип документа.");
        return;
      }

      const kindId = Number(form.document_kind_id);
      if (!Number.isFinite(kindId) || kindId <= 0) {
        setError("Выберите вид документа.");
        return;
      }

      if (specialtyRequired) {
        const specId = Number(form.medical_specialty_id);
        if (!Number.isFinite(specId) || specId <= 0) {
          setError("Выберите специальность для данного типа документа.");
          return;
        }
      }

      const kindCode = selectedKind?.code;
      const titleValue =
        kindCode === "OTHER" ? form.title.trim() || null : form.title.trim() || null;

      if (mode === "create") {
        const employeeId = Number(form.employee_id);
        if (!Number.isFinite(employeeId) || employeeId <= 0) {
          setError("Выберите сотрудника.");
          return;
        }

        await createEmployeeDocument({
          employee_id: employeeId,
          document_type_id: typeId,
          document_kind_id: kindId,
          medical_specialty_id: form.medical_specialty_id
            ? Number(form.medical_specialty_id)
            : null,
          title: titleValue,
          training_title: form.training_title.trim() || null,
          document_number: form.document_number.trim() || null,
          issued_by: form.issued_by.trim() || null,
          issued_at: form.issued_at || null,
          valid_until: selectedType?.has_valid_until ? form.valid_until || null : null,
          file_url: form.file_url.trim() || null,
          comment: form.comment.trim() || null,
        });
      } else if (documentRow) {
        const payload: Record<string, unknown> = {};

        if (form.document_type_id !== initialForm.document_type_id) {
          payload.document_type_id = typeId;
        }
        if (form.document_kind_id !== initialForm.document_kind_id) {
          payload.document_kind_id = kindId;
        }
        if (form.training_title !== initialForm.training_title) {
          payload.training_title = form.training_title.trim() || null;
        }
        if (form.title !== initialForm.title) payload.title = titleValue;
        if (form.document_number !== initialForm.document_number) {
          payload.document_number = form.document_number.trim() || null;
        }
        if (form.issued_by !== initialForm.issued_by) {
          payload.issued_by = form.issued_by.trim() || null;
        }
        if (form.issued_at !== initialForm.issued_at) {
          payload.issued_at = form.issued_at || null;
        }
        if (form.comment !== initialForm.comment) payload.comment = form.comment.trim() || null;

        if (form.medical_specialty_id !== initialForm.medical_specialty_id) {
          if (!form.medical_specialty_id && initialForm.medical_specialty_id) {
            payload.clear_medical_specialty = true;
          } else if (form.medical_specialty_id) {
            payload.medical_specialty_id = Number(form.medical_specialty_id);
          }
        }

        const typeForUpdate =
          documentTypes.find((t) => String(t.document_type_id) === form.document_type_id) ??
          selectedType;
        if (form.valid_until !== initialForm.valid_until) {
          if (!form.valid_until && initialForm.valid_until) {
            payload.clear_valid_until = true;
          } else {
            payload.valid_until = typeForUpdate?.has_valid_until ? form.valid_until || null : null;
          }
        }

        if (form.file_url !== initialForm.file_url) {
          if (!form.file_url.trim() && initialForm.file_url) {
            payload.clear_file_url = true;
          } else {
            payload.file_url = form.file_url.trim() || null;
          }
        }

        if (Object.keys(payload).length === 0) {
          setError("Измените хотя бы одно поле.");
          return;
        }

        await updateEmployeeDocument(documentRow.document_id, payload);
      }

      onSaved();
      onClose();
    } catch (err) {
      setError(mapDocumentsApiError(err, "Не удалось сохранить документ."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleArchive() {
    if (!documentRow) return;
    if (!window.confirm("Снять документ с действия (архивировать)?")) return;
    setError(null);
    setArchiving(true);
    try {
      await archiveEmployeeDocument(documentRow.document_id);
      onSaved();
      onClose();
    } catch (err) {
      setError(mapDocumentsApiError(err, "Не удалось архивировать документ."));
    } finally {
      setArchiving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-zinc-200 bg-white p-5 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
              {mode === "create" ? "Добавить документ" : "Редактировать документ"}
            </h2>
            {mode === "edit" && documentRow ? (
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
                {documentRow.employee_name}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-2 py-1 text-zinc-500 hover:bg-zinc-100 dark:hover:bg-zinc-900"
          >
            ✕
          </button>
        </div>

        {error ? (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
            {error}
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode === "create" ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                  Отделение *
                </label>
                <select
                  required
                  value={form.org_unit_id}
                  onChange={(e) => setField("org_unit_id", e.target.value)}
                  className={selectClass}
                >
                  <option value="">
                    {loadingOrgUnits ? "Загрузка…" : "Выберите отделение"}
                  </option>
                  <option value={ALL_ORG_UNITS_VALUE}>Все отделения</option>
                  {orgUnitOptions.map((unit) => (
                    <option key={unit.unit_id} value={String(unit.unit_id)}>
                      {unit.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                  Сотрудник *
                </label>
                <select
                  required
                  value={form.employee_id}
                  onChange={(e) => setField("employee_id", e.target.value)}
                  disabled={!form.org_unit_id || loadingEmployees}
                  className={selectClass}
                >
                  <option value="">
                    {!form.org_unit_id
                      ? "Сначала выберите отделение"
                      : loadingEmployees
                        ? "Загрузка…"
                        : employeesFetchError
                          ? "Ошибка загрузки"
                          : employees.length === 0
                            ? "Сотрудники не найдены"
                            : "Выберите сотрудника"}
                  </option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={String(emp.id)}>
                      {emp.fio || `#${emp.id}`}
                      {emp.status !== "active" ? " (неактивен)" : ""}
                    </option>
                  ))}
                </select>
                {employeesFetchError ? (
                  <p className="mt-1 text-xs text-red-600 dark:text-red-400">{employeesFetchError}</p>
                ) : null}
                {!employeesFetchError &&
                form.org_unit_id &&
                !loadingEmployees &&
                employees.length === 0 ? (
                  <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                    {form.org_unit_id === ALL_ORG_UNITS_VALUE
                      ? "Сотрудники не найдены в справочнике."
                      : "В выбранном отделении сотрудники не найдены. Попробуйте «Все отделения» или другое отделение."}
                  </p>
                ) : null}
              </div>
            </div>
          ) : null}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                Тип документа *
              </label>
              <select
                required
                value={form.document_type_id}
                onChange={(e) => setField("document_type_id", e.target.value)}
                className={selectClass}
              >
                <option value="">Выберите тип</option>
                {documentTypes.map((type) => (
                  <option key={type.document_type_id} value={String(type.document_type_id)}>
                    {type.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                Вид документа *
              </label>
              <select
                required
                value={form.document_kind_id}
                onChange={(e) => setField("document_kind_id", e.target.value)}
                className={selectClass}
              >
                <option value="">Выберите вид</option>
                {documentKinds.map((kind) => (
                  <option key={kind.document_kind_id} value={String(kind.document_kind_id)}>
                    {kind.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Специальность{specialtyRequired ? " *" : ""}
            </label>
            <select
              required={specialtyRequired}
              value={form.medical_specialty_id}
              onChange={(e) => setField("medical_specialty_id", e.target.value)}
              className={selectClass}
            >
              <option value="">
                {specialtyRequired ? "Выберите специальность" : "Не указана"}
              </option>
              {specialties.map((spec) => (
                <option key={spec.medical_specialty_id} value={String(spec.medical_specialty_id)}>
                  {spec.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Название обучения / программы
            </label>
            <input
              value={form.training_title}
              onChange={(e) => setField("training_title", e.target.value)}
              placeholder="Например: «Современные подходы в онкологии»"
              className={wideInputClass}
            />
          </div>

          {selectedKind?.code === "OTHER" ? (
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                Уточнение вида документа
              </label>
              <input
                value={form.title}
                onChange={(e) => setField("title", e.target.value)}
                className={wideInputClass}
              />
            </div>
          ) : null}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                Номер документа
              </label>
              <input
                value={form.document_number}
                onChange={(e) => setField("document_number", e.target.value)}
                className={selectClass}
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Кем выдан
            </label>
            <input
              value={form.issued_by}
              onChange={(e) => setField("issued_by", e.target.value)}
              className={wideInputClass}
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                Дата выдачи
              </label>
              <input
                type="date"
                value={form.issued_at}
                onChange={(e) => setField("issued_at", e.target.value)}
                className={selectClass}
              />
            </div>
            {selectedType?.has_valid_until ? (
              <div>
                <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                  Действует до *
                </label>
                <input
                  type="date"
                  required
                  value={form.valid_until}
                  onChange={(e) => setField("valid_until", e.target.value)}
                  className={selectClass}
                />
              </div>
            ) : null}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Ссылка на файл (URL или UNC)
            </label>
            <input
              value={form.file_url}
              onChange={(e) => setField("file_url", e.target.value)}
              placeholder="https://… или \\\\server\\share\\file.pdf"
              className={wideInputClass}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Комментарий
            </label>
            <textarea
              value={form.comment}
              onChange={(e) => setField("comment", e.target.value)}
              rows={3}
              className={wideInputClass}
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
            {mode === "edit" ? (
              <button
                type="button"
                onClick={handleArchive}
                disabled={archiving || submitting}
                className="rounded-lg border border-red-300 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:text-red-300 dark:hover:bg-red-950/30"
              >
                {archiving ? "Архивирование…" : "Снять с действия"}
              </button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={submitting || archiving}
                className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
              >
                {submitting ? "Сохранение…" : "Сохранить"}
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
