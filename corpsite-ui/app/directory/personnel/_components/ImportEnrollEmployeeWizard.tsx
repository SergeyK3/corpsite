"use client";

import * as React from "react";
import Link from "next/link";

import { getPositions } from "@/app/directory/employees/_lib/api.client";
import { getOrgUnitsTree, type TreeNode } from "@/app/directory/org-units/_lib/api.client";
import {
  EnrollEmployeeConflictError,
  enrollEmployeeFromNormalizedRecord,
  getNormalizedRecord,
  mapImportApiError,
  NORMALIZED_RECORD_KIND_LABELS,
  patchNormalizedRecordEmployeeBinding,
  type EnrollEmployeeResponse,
  type NormalizedRecord,
} from "../_lib/importApi.client";
import { displayNormalizedRecordIin } from "../_lib/normalizedRecordIin";

type Props = {
  record: NormalizedRecord;
  batchFileName?: string;
  canEnroll?: boolean;
  onReviewed: (record: NormalizedRecord) => void;
  onToast: (message: string, kind?: "success" | "error") => void;
};

type Step = 1 | 2 | 3;

type PositionOptionSource = {
  id?: number | string | null;
  position_id?: number | string | null;
  name?: string | null;
};

type PositionOption = {
  id: number;
  label: string;
};

function normalizePositionOptions(raw: unknown): PositionOption[] {
  const items = Array.isArray(raw)
    ? raw
    : raw && typeof raw === "object" && Array.isArray((raw as { items?: unknown[] }).items)
      ? (raw as { items: unknown[] }).items
      : [];

  return items
    .map((p: PositionOptionSource) => {
      const id = Number(p?.position_id ?? p?.id ?? 0);
      const label = String(p?.name ?? `#${id}`).trim();
      return { id, label } as PositionOption;
    })
    .filter((p) => Number.isFinite(p.id) && p.id > 0)
    .sort((a, b) => a.label.localeCompare(b.label, "ru"));
}

function flattenOrgUnits(nodes: TreeNode[], depth = 0): Array<{ id: number; label: string }> {
  const out: Array<{ id: number; label: string }> = [];
  for (const node of nodes) {
    const id = Number(node.unit_id ?? node.id);
    if (Number.isFinite(id) && id > 0) {
      const prefix = depth > 0 ? `${"—".repeat(depth)} ` : "";
      out.push({ id, label: `${prefix}${node.name}` });
    }
    if (node.children?.length) {
      out.push(...flattenOrgUnits(node.children, depth + 1));
    }
  }
  return out;
}

type PositionListSource = "none" | "unit" | "catalog";

const CATALOG_FALLBACK_NOTICE =
  "Для выбранного отделения пока нет используемых должностей. Показан общий справочник должностей.";

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

function ProvenanceChain({
  record,
  batchFileName,
  employeeId,
  linkedRecordIds,
}: {
  record: NormalizedRecord;
  batchFileName?: string;
  employeeId?: number | null;
  linkedRecordIds?: number[];
}) {
  const batchLabel = batchFileName
    ? `${batchFileName} (#${record.batch_id})`
    : `Batch #${record.batch_id}`;
  return (
    <div className="space-y-1 text-xs text-zinc-600 dark:text-zinc-400 font-mono">
      <div>{batchLabel}</div>
      <div className="pl-3">└─ Row #{record.row_id}</div>
      <div className="pl-6">└─ Normalized #{record.record_id} ← текущая</div>
      {(linkedRecordIds ?? [])
        .filter((id) => id !== record.record_id)
        .map((id) => (
          <div key={id} className="pl-6">
            └─ Normalized #{id} (тот же ИИН)
          </div>
        ))}
      {employeeId ? (
        <div className="pl-9 text-green-700 dark:text-green-300">
          └─ Employee #{employeeId} ✓
        </div>
      ) : null}
    </div>
  );
}

export default function ImportEnrollEmployeeWizard({
  record,
  batchFileName,
  canEnroll = true,
  onReviewed,
  onToast,
}: Props) {
  const [step, setStep] = React.useState<Step>(1);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [dryRunResult, setDryRunResult] = React.useState<EnrollEmployeeResponse | null>(null);
  const [conflictResult, setConflictResult] = React.useState<EnrollEmployeeResponse | null>(null);
  const [successEmployeeId, setSuccessEmployeeId] = React.useState<number | null>(null);
  const [fullName, setFullName] = React.useState(record.full_name || "");
  const [orgUnitId, setOrgUnitId] = React.useState("");
  const [positionId, setPositionId] = React.useState("");
  const [dateFrom, setDateFrom] = React.useState(todayIsoDate());
  const [employmentRate, setEmploymentRate] = React.useState("1");
  const [confirmChecked, setConfirmChecked] = React.useState(false);
  const [orgUnitOptions, setOrgUnitOptions] = React.useState<Array<{ id: number; label: string }>>([]);
  const [positionOptions, setPositionOptions] = React.useState<PositionOption[]>([]);
  const [positionListSource, setPositionListSource] = React.useState<PositionListSource>("none");
  const [unitPositionsLoading, setUnitPositionsLoading] = React.useState(false);
  const [positionValidationMessage, setPositionValidationMessage] = React.useState<string | null>(null);

  React.useEffect(() => {
    setStep(1);
    setError(null);
    setDryRunResult(null);
    setConflictResult(null);
    setSuccessEmployeeId(null);
    setFullName(record.full_name || "");
    setOrgUnitId("");
    setPositionId("");
    setPositionOptions([]);
    setPositionListSource("none");
    setPositionValidationMessage(null);
    setDateFrom(todayIsoDate());
    setEmploymentRate("1");
    setConfirmChecked(false);
  }, [record.record_id]);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const tree = await getOrgUnitsTree({ include_inactive: false });
        if (cancelled) return;
        setOrgUnitOptions(flattenOrgUnits(tree.items ?? []));
      } catch {
        if (!cancelled) setOrgUnitOptions([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    const unitId = orgUnitId.trim();
    if (!unitId) {
      setPositionOptions([]);
      setPositionListSource("none");
      setUnitPositionsLoading(false);
      return;
    }

    let cancelled = false;
    setUnitPositionsLoading(true);

    void (async () => {
      try {
        const scopedRaw = await getPositions({ org_unit_id: Number(unitId), limit: 500 });
        if (cancelled) return;

        const scopedOptions = normalizePositionOptions(scopedRaw);
        if (scopedOptions.length > 0) {
          setPositionOptions(scopedOptions);
          setPositionListSource("unit");
          return;
        }

        const catalogRaw = await getPositions({ limit: 500 });
        if (cancelled) return;
        setPositionOptions(normalizePositionOptions(catalogRaw));
        setPositionListSource("catalog");
      } catch {
        if (!cancelled) {
          setPositionOptions([]);
          setPositionListSource("none");
        }
      } finally {
        if (!cancelled) setUnitPositionsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [orgUnitId]);

  function handleOrgUnitChange(nextOrgUnitId: string) {
    if (positionId) {
      setPositionValidationMessage("Выбранная должность сброшена — выберите должность для нового отделения");
    } else {
      setPositionValidationMessage(null);
    }
    setPositionId("");
    setOrgUnitId(nextOrgUnitId);
  }

  function positionSelectPlaceholder(): string {
    if (!orgUnitId.trim()) return "Сначала выберите отделение";
    if (unitPositionsLoading) return "Загрузка должностей…";
    if (positionOptions.length === 0) return "Нет доступных должностей";
    return "Выберите должность";
  }

  const positionSelectDisabled =
    !orgUnitId.trim() || unitPositionsLoading || positionOptions.length === 0;

  React.useEffect(() => {
    const hint = dryRunResult?.preview?.org_unit_hint;
    if (hint?.org_unit_id && !orgUnitId) {
      setOrgUnitId(String(hint.org_unit_id));
    }
  }, [dryRunResult, orgUnitId]);

  async function runDryRun() {
    setLoading(true);
    setError(null);
    setConflictResult(null);
    try {
      const result = await enrollEmployeeFromNormalizedRecord(record.record_id, {
        dry_run: true,
        full_name: fullName.trim() || undefined,
      });
      setDryRunResult(result);
    } catch (e) {
      if (e instanceof EnrollEmployeeConflictError) {
        setConflictResult(e.payload);
        setDryRunResult(null);
      } else {
        setError(mapImportApiError(e));
      }
    } finally {
      setLoading(false);
    }
  }

  React.useEffect(() => {
    if (!canEnroll) return;
    void runDryRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record.record_id, canEnroll]);

  async function handleExecute() {
    if (!confirmChecked) {
      setError("Подтвердите создание сотрудника в операционном контуре");
      return;
    }
    const orgId = Number(orgUnitId);
    const posId = Number(positionId);
    if (!Number.isInteger(orgId) || orgId < 1) {
      setError("Выберите отделение");
      return;
    }
    if (!Number.isInteger(posId) || posId < 1) {
      setError("Выберите должность");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await enrollEmployeeFromNormalizedRecord(record.record_id, {
        dry_run: false,
        full_name: fullName.trim(),
        org_unit_id: orgId,
        position_id: posId,
        date_from: dateFrom || undefined,
        employment_rate: employmentRate ? Number(employmentRate) : 1,
        link_same_iin_in_batch: true,
      });
      setSuccessEmployeeId(result.employee_id ?? null);
      const updated = await getNormalizedRecord(record.record_id);
      onReviewed(updated);
      onToast("Сотрудник создан и записи привязаны", "success");
    } catch (e) {
      if (e instanceof EnrollEmployeeConflictError) {
        setConflictResult(e.payload);
        setStep(1);
      } else {
        setError(mapImportApiError(e));
      }
    } finally {
      setLoading(false);
    }
  }

  async function linkExistingEmployee(employeeId: number) {
    setLoading(true);
    setError(null);
    try {
      const updated = await patchNormalizedRecordEmployeeBinding(record.record_id, employeeId);
      onReviewed(updated);
      onToast(`Запись привязана к сотруднику #${employeeId}`, "success");
      setConflictResult(null);
    } catch (e) {
      setError(mapImportApiError(e));
    } finally {
      setLoading(false);
    }
  }

  if (!canEnroll) return null;

  const iin = displayNormalizedRecordIin(record);
  const bindingReason = record.employee_binding?.reason ?? "";
  const showWizard =
    !record.employee_id &&
    record.review_status !== "promoted" &&
    record.review_status !== "superseded" &&
    iin.length === 12 &&
    (record.employee_binding?.status === "unbound" ||
      bindingReason.includes("не найден"));

  if (!showWizard && !successEmployeeId) return null;

  if (successEmployeeId) {
    return (
      <section className="space-y-3 rounded-lg border border-green-200 bg-green-50/60 p-4 dark:border-green-900 dark:bg-green-950/30">
        <h3 className="text-sm font-semibold text-green-900 dark:text-green-100">
          Сотрудник создан · Employee ID {successEmployeeId}
        </h3>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/directory/staff?employeeId=${successEmployeeId}`}
            className="rounded-lg bg-green-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-800"
          >
            Открыть в «Персонал»
          </Link>
        </div>
        <ProvenanceChain
          record={record}
          batchFileName={batchFileName}
          employeeId={successEmployeeId}
          linkedRecordIds={dryRunResult?.linked_record_ids}
        />
      </section>
    );
  }

  if (conflictResult?.conflict) {
    const conflict = conflictResult.conflict;
    const primary =
      conflict.candidates?.[0] ??
      (conflict.existing_employee_id
        ? {
            employee_id: conflict.existing_employee_id,
            full_name: conflict.existing_employee_name,
            org_unit_name: conflict.existing_org_unit_name,
            position_name: conflict.existing_position_name,
          }
        : null);

    return (
      <section className="space-y-3 rounded-lg border border-orange-200 bg-orange-50/70 p-4 dark:border-orange-900 dark:bg-orange-950/30">
        <h3 className="text-sm font-semibold text-orange-900 dark:text-orange-100">
          ИИН уже в справочнике
        </h3>
        <p className="text-sm text-orange-800 dark:text-orange-200">{conflict.message}</p>
        {primary ? (
          <div className="rounded-lg border border-orange-200 bg-white/80 px-3 py-2 text-sm dark:border-orange-800 dark:bg-zinc-950">
            <div className="font-medium">{primary.full_name || "—"}</div>
            <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              Employee #{primary.employee_id}
              {primary.org_unit_name ? ` · ${primary.org_unit_name}` : ""}
              {primary.position_name ? ` · ${primary.position_name}` : ""}
            </div>
          </div>
        ) : null}
        {conflict.code === "IIN_ALREADY_EXISTS" && primary?.employee_id ? (
          <div className="flex flex-wrap gap-2">
            <Link
              href={`/directory/staff?employeeId=${primary.employee_id}`}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            >
              Открыть сотрудника
            </Link>
            <button
              type="button"
              disabled={loading}
              onClick={() => linkExistingEmployee(primary.employee_id!)}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Привязать запись
            </button>
          </div>
        ) : (
          <p className="text-xs text-zinc-600 dark:text-zinc-400">
            Используйте ручную привязку по ID или обратитесь к администратору.
          </p>
        )}
      </section>
    );
  }

  return (
    <section className="space-y-4 rounded-lg border border-blue-200 bg-blue-50/40 p-4 dark:border-blue-900 dark:bg-blue-950/20">
      <div>
        <h3 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">Добавить в персонал</h3>
        <p className="mt-1 text-xs text-zinc-500">
          Создание операционного Employee из записи импорта (не mass promotion).
        </p>
      </div>

      <div className="flex items-center gap-2 text-xs text-zinc-500">
        <span className={step === 1 ? "font-semibold text-blue-700 dark:text-blue-300" : ""}>1. Источник</span>
        <span>→</span>
        <span className={step === 2 ? "font-semibold text-blue-700 dark:text-blue-300" : ""}>2. Данные</span>
        <span>→</span>
        <span className={step === 3 ? "font-semibold text-blue-700 dark:text-blue-300" : ""}>3. Подтверждение</span>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>
      ) : null}

      {step === 1 ? (
        <div className="space-y-3 text-sm">
          <div className="rounded-lg border border-zinc-200 bg-white/80 p-3 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Происхождение</div>
            <ProvenanceChain record={record} batchFileName={batchFileName} />
            <div className="mt-2 text-xs text-zinc-600 dark:text-zinc-400">
              Тип: {NORMALIZED_RECORD_KIND_LABELS[record.record_kind] || record.record_kind}
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <span className="text-xs text-zinc-500">ФИО</span>
              <div>{fullName || "—"}</div>
            </div>
            <div>
              <span className="text-xs text-zinc-500">ИИН</span>
              <div className="font-mono">{iin}</div>
            </div>
          </div>
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100">
            Создаётся операционный Employee в справочнике «Персонал», а не HR raw row.
          </div>
          {dryRunResult ? (
            <div className="rounded-lg border border-zinc-200 bg-white/80 px-3 py-2 text-xs dark:border-zinc-800 dark:bg-zinc-950">
              <div>✓ ИИН валиден</div>
              <div>✓ Сотрудник с таким ИИН не найден</div>
              {dryRunResult.linked_records_count > 1 ? (
                <div>
                  ℹ В batch #{record.batch_id} будет привязано записей: {dryRunResult.linked_records_count}
                </div>
              ) : null}
              {dryRunResult.warnings.map((w) => (
                <div key={w} className="text-amber-700 dark:text-amber-300">
                  ⚠ {w}
                </div>
              ))}
            </div>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={loading}
              onClick={runDryRun}
              className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700"
            >
              Проверить
            </button>
            <button
              type="button"
              disabled={loading || !dryRunResult}
              onClick={() => setStep(2)}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              Далее
            </button>
          </div>
        </div>
      ) : null}

      {step === 2 ? (
        <div className="space-y-3 text-sm">
          <label className="grid gap-1">
            <span className="text-xs font-medium text-zinc-500">ФИО *</span>
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
            />
          </label>
          <label className="grid gap-1">
            <span className="text-xs font-medium text-zinc-500">ИИН</span>
            <input value={iin} readOnly className="rounded-lg border border-zinc-200 bg-zinc-100 px-3 py-2 font-mono dark:border-zinc-800 dark:bg-zinc-900" />
          </label>
          <label className="grid gap-1">
            <span className="text-xs font-medium text-zinc-500">Отделение *</span>
            <select
              value={orgUnitId}
              onChange={(e) => handleOrgUnitChange(e.target.value)}
              className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
            >
              <option value="">Выберите отделение</option>
              {orgUnitOptions.map((o) => (
                <option key={o.id} value={String(o.id)}>
                  {o.label}
                </option>
              ))}
            </select>
            {dryRunResult?.preview?.org_unit_hint?.value ? (
              <span className="text-xs text-blue-600 dark:text-blue-400">
                Из импорта: {dryRunResult.preview.org_unit_hint.value}
              </span>
            ) : null}
          </label>
          <label className="grid gap-1">
            <span className="text-xs font-medium text-zinc-500">Должность *</span>
            <select
              value={positionId}
              onChange={(e) => {
                setPositionId(e.target.value);
                setPositionValidationMessage(null);
              }}
              disabled={positionSelectDisabled}
              className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950 disabled:cursor-not-allowed disabled:opacity-70"
            >
              <option value="">{positionSelectPlaceholder()}</option>
              {positionOptions.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.label}
                </option>
              ))}
            </select>
            {positionListSource === "catalog" ? (
              <span className="text-xs text-amber-700 dark:text-amber-300">{CATALOG_FALLBACK_NOTICE}</span>
            ) : null}
            {positionValidationMessage ? (
              <span className="text-xs text-amber-700 dark:text-amber-300">{positionValidationMessage}</span>
            ) : null}
            {orgUnitId.trim() ? (
              <Link
                href="/directory/positions"
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-600 hover:text-blue-500 dark:text-blue-400 dark:hover:text-blue-300"
              >
                Справочник должностей
              </Link>
            ) : null}
            {dryRunResult?.preview?.position_hint?.value ? (
              <span className="text-xs text-blue-600 dark:text-blue-400">
                Из импорта: {dryRunResult.preview.position_hint.value}
              </span>
            ) : null}
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="grid gap-1">
              <span className="text-xs font-medium text-zinc-500">Дата приёма</span>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              />
            </label>
            <label className="grid gap-1">
              <span className="text-xs font-medium text-zinc-500">Ставка</span>
              <input
                type="number"
                min="0.01"
                max="2"
                step="0.01"
                value={employmentRate}
                onChange={(e) => setEmploymentRate(e.target.value)}
                className="rounded-lg border border-zinc-300 px-3 py-2 dark:border-zinc-700 dark:bg-zinc-950"
              />
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => setStep(1)} className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700">
              Назад
            </button>
            <button
              type="button"
              onClick={() => setStep(3)}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              Далее
            </button>
          </div>
        </div>
      ) : null}

      {step === 3 ? (
        <div className="space-y-3 text-sm">
          <div className="rounded-lg border border-zinc-200 bg-white/80 p-3 dark:border-zinc-800 dark:bg-zinc-950">
            <div className="font-medium">{fullName}</div>
            <div className="mt-1 text-xs text-zinc-600 dark:text-zinc-400">
              ИИН {iin} · отделение #{orgUnitId || "—"} · должность #{positionId || "—"}
            </div>
            {dryRunResult ? (
              <div className="mt-2 text-xs text-zinc-500">
                Будет привязано записей: {dryRunResult.linked_records_count} (same batch + same IIN)
              </div>
            ) : null}
          </div>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={confirmChecked}
              onChange={(e) => setConfirmChecked(e.target.checked)}
              className="mt-1"
            />
            <span>Создать сотрудника в операционном контуре Corpsite</span>
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => setStep(2)} className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700">
              Назад
            </button>
            <button
              type="button"
              disabled={loading || !confirmChecked}
              onClick={handleExecute}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Создание…" : "Создать и привязать"}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
