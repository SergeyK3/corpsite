"use client";

import * as React from "react";

import { getEmployees } from "@/app/directory/employees/_lib/api.client";
import OrgScopeFilter from "@/components/OrgScopeFilter";
import OrgUnitScopeFilter from "@/components/OrgUnitScopeFilter";
import {
  loadScopedPositionOptions,
  type TaskOrgFilterOption,
} from "@/lib/taskOrgFilters";
import { resolveEmployeeOrgScopePrefill } from "@/lib/userCreateOrgScope";

import {
  PERSONNEL_ORDER_CREATE_TYPE_OPTIONS,
  createPersonnelOrderItem,
  mapPersonnelOrdersApiError,
  updatePersonnelOrderItem,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderItem,
} from "../_lib/personnelOrdersApi.client";
import {
  buildItemPayload,
  emptyItemPayloadDraft,
  itemPayloadDraftFromRecord,
  type ItemPayloadDraft,
} from "../_lib/personnelOrderPayload";
import {
  clearOrgDependentFields,
  isOrgScopedItemType,
  selectedOrgUnitIdFromDraft,
  selectedPositionIdFromDraft,
  setOrgUnitAndClearPosition,
  setPositionId,
} from "../_lib/personnelOrderOrgScope";
import {
  mapEmployeesResponseToSearchOptions,
  requireEmployeeIdForItemType,
  type EmployeeSearchOption,
} from "../_lib/personnelOrderEmployeeSearch";

type Props = {
  orderId: number;
  items: PersonnelOrderItem[];
  disabled?: boolean;
  onChanged: (detail: PersonnelOrderDetailResponse) => void;
};

const ORG_SCOPE_BASE_PATH = "/directory/personnel/orders";

export default function PersonnelOrderItemEditor({
  orderId,
  items,
  disabled = false,
  onChanged,
}: Props) {
  const [editingItemId, setEditingItemId] = React.useState<number | null>(null);
  const [itemTypeCode, setItemTypeCode] = React.useState("HIRE");
  const [employeeId, setEmployeeId] = React.useState("");
  const [employeeQuery, setEmployeeQuery] = React.useState("");
  const [employeeOptions, setEmployeeOptions] = React.useState<EmployeeSearchOption[]>([]);
  const [effectiveDate, setEffectiveDate] = React.useState("");
  const [payloadDraft, setPayloadDraft] = React.useState<ItemPayloadDraft>(emptyItemPayloadDraft());
  const [orgGroupId, setOrgGroupId] = React.useState<number | null>(null);
  const [positions, setPositions] = React.useState<TaskOrgFilterOption[]>([]);
  const [positionsLoading, setPositionsLoading] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const type = itemTypeCode.toUpperCase();
  const orgScoped = isOrgScopedItemType(itemTypeCode);
  const selectedOrgUnitId = selectedOrgUnitIdFromDraft(payloadDraft, itemTypeCode);
  const selectedPositionValue = selectedPositionIdFromDraft(payloadDraft, itemTypeCode);

  React.useEffect(() => {
    const q = employeeQuery.trim();
    if (q.length < 2) {
      setEmployeeOptions([]);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void getEmployees({ q, limit: 20, status: "all" })
        .then((res) => {
          if (cancelled) return;
          setEmployeeOptions(mapEmployeesResponseToSearchOptions(res));
        })
        .catch(() => {
          if (!cancelled) setEmployeeOptions([]);
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [employeeQuery]);

  React.useEffect(() => {
    if (!orgScoped || selectedOrgUnitId == null) {
      setPositions([]);
      setPositionsLoading(false);
      return;
    }

    let cancelled = false;
    setPositionsLoading(true);
    void loadScopedPositionOptions({
      org_group_id: orgGroupId ?? undefined,
      org_unit_id: selectedOrgUnitId,
    })
      .then((options) => {
        if (!cancelled) setPositions(options);
      })
      .catch(() => {
        if (!cancelled) setPositions([]);
      })
      .finally(() => {
        if (!cancelled) setPositionsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [orgScoped, orgGroupId, selectedOrgUnitId]);

  function resetForm(typeCode = "HIRE") {
    setEditingItemId(null);
    setItemTypeCode(typeCode);
    setEmployeeId("");
    setEmployeeQuery("");
    setEffectiveDate("");
    setPayloadDraft(emptyItemPayloadDraft());
    setOrgGroupId(null);
    setPositions([]);
    setError(null);
  }

  async function startEdit(item: PersonnelOrderItem) {
    const draft = itemPayloadDraftFromRecord(item.payload);
    setEditingItemId(item.item_id);
    setItemTypeCode(item.item_type_code);
    setEmployeeId(item.employee_id ? String(item.employee_id) : "");
    setEmployeeQuery(item.employee_name || "");
    setEffectiveDate(item.effective_date || "");
    setPayloadDraft(draft);
    setError(null);

    const unitId = selectedOrgUnitIdFromDraft(draft, item.item_type_code);
    if (unitId == null) {
      setOrgGroupId(null);
      return;
    }
    try {
      const prefill = await resolveEmployeeOrgScopePrefill(unitId);
      setOrgGroupId(prefill.org_group_id);
    } catch {
      setOrgGroupId(null);
    }
  }

  function updatePayloadField<K extends keyof ItemPayloadDraft>(key: K, value: string) {
    setPayloadDraft((prev) => ({ ...prev, [key]: value }));
  }

  function handleOrgGroupChange(nextGroupId: number | null) {
    setOrgGroupId(nextGroupId);
    setPayloadDraft((prev) => clearOrgDependentFields(prev, itemTypeCode));
  }

  function handleOrgUnitChange(nextUnitId: number | null) {
    setPayloadDraft((prev) => setOrgUnitAndClearPosition(prev, itemTypeCode, nextUnitId));
  }

  function handlePositionChange(nextPositionId: string) {
    setPayloadDraft((prev) => setPositionId(prev, itemTypeCode, nextPositionId));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (disabled) return;
    setError(null);

    const employeeRequiredMessage = requireEmployeeIdForItemType(itemTypeCode, employeeId);
    if (employeeRequiredMessage) {
      setError(employeeRequiredMessage);
      return;
    }

    setSaving(true);
    try {
      const employeeNumeric = Number(employeeId);
      const body = {
        item_type_code: itemTypeCode,
        employee_id: Number.isFinite(employeeNumeric) && employeeNumeric > 0 ? employeeNumeric : null,
        effective_date: effectiveDate || null,
        payload: buildItemPayload(itemTypeCode, payloadDraft),
      };
      const detail =
        editingItemId != null
          ? await updatePersonnelOrderItem(orderId, editingItemId, body)
          : await createPersonnelOrderItem(orderId, body);
      onChanged(detail);
      resetForm(itemTypeCode);
    } catch (err) {
      setError(mapPersonnelOrdersApiError(err, "Не удалось сохранить пункт."));
    } finally {
      setSaving(false);
    }
  }

  function renderOrgScopeCascade(labels: { unit: string; position: string; unitEmpty: string }) {
    return (
      <div className="sm:col-span-2 space-y-3" data-testid="personnel-order-org-scope-cascade">
        <OrgScopeFilter
          basePath={ORG_SCOPE_BASE_PATH}
          label="Группа отделений"
          value={orgGroupId}
          onChange={handleOrgGroupChange}
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <OrgUnitScopeFilter
            basePath={ORG_SCOPE_BASE_PATH}
            label={labels.unit}
            allLabel={labels.unitEmpty}
            orgGroupId={orgGroupId}
            value={selectedOrgUnitId}
            onChange={handleOrgUnitChange}
          />
          <div>
            <label className="mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200">
              {labels.position}
            </label>
            <select
              data-testid="personnel-order-position-select"
              value={selectedPositionValue}
              onChange={(e) => handlePositionChange(e.target.value)}
              disabled={selectedOrgUnitId == null || positionsLoading}
              className="w-full rounded-md border border-zinc-200 bg-zinc-100 px-3 py-2 text-sm text-zinc-900 outline-none disabled:opacity-60 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-50"
            >
              <option value="">
                {selectedOrgUnitId == null
                  ? "Сначала выберите подразделение"
                  : positionsLoading
                    ? "Загрузка…"
                    : "—"}
              </option>
              {positions.map((position) => (
                <option key={position.id} value={String(position.id)}>
                  {position.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="personnel-order-item-editor">
      <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900/50">
            <tr>
              {["№", "Тип", "Сотрудник", "Дата", "Статус", ""].map((h) => (
                <th key={h || "actions"} className="px-3 py-2 text-left text-[11px] font-semibold uppercase text-zinc-500">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-3 text-sm text-zinc-500">
                  Пункты отсутствуют.
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.item_id}>
                  <td className="px-3 py-2">{item.item_number}</td>
                  <td className="px-3 py-2">{item.item_type_code}</td>
                  <td className="px-3 py-2">
                    {item.employee_name || (item.employee_id ? `#${item.employee_id}` : "—")}
                  </td>
                  <td className="px-3 py-2">{item.effective_date || "—"}</td>
                  <td className="px-3 py-2">{item.item_status}</td>
                  <td className="px-3 py-2">
                    {!disabled && item.item_status === "ACTIVE" ? (
                      <button
                        type="button"
                        className="text-xs font-medium text-blue-700 hover:underline dark:text-blue-300"
                        onClick={() => void startEdit(item)}
                      >
                        Изменить
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {!disabled ? (
        <form className="space-y-3 rounded-xl border border-zinc-200 p-3 dark:border-zinc-800" onSubmit={handleSubmit}>
          <div className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
            {editingItemId != null ? `Редактирование пункта #${editingItemId}` : "Добавить пункт"}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600">Тип пункта</label>
              <select
                value={itemTypeCode}
                onChange={(e) => setItemTypeCode(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              >
                {PERSONNEL_ORDER_CREATE_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600">Дата вступления</label>
              <input
                type="date"
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
              />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-zinc-600">Сотрудник</label>
              <div className="flex flex-wrap gap-2">
                <input
                  value={employeeQuery}
                  onChange={(e) => setEmployeeQuery(e.target.value)}
                  placeholder="Поиск ФИО…"
                  className="min-w-[12rem] flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                />
                <input
                  value={employeeId}
                  onChange={(e) => setEmployeeId(e.target.value)}
                  placeholder="employee_id"
                  className="w-28 rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                />
              </div>
              {employeeOptions.length > 0 ? (
                <div
                  className="mt-1 max-h-32 overflow-auto rounded border border-zinc-200 dark:border-zinc-800"
                  data-testid="personnel-order-employee-search-results"
                >
                  {employeeOptions.map((option) => (
                    <button
                      key={option.employee_id}
                      type="button"
                      className="block w-full px-3 py-1.5 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-900"
                      data-testid={`personnel-order-employee-option-${option.employee_id}`}
                      onClick={() => {
                        setEmployeeId(String(option.employee_id));
                        setEmployeeQuery(option.full_name);
                        setEmployeeOptions([]);
                      }}
                    >
                      {option.full_name} · #{option.employee_id}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            {type === "HIRE" ? (
              <>
                {renderOrgScopeCascade({
                  unit: "Подразделение",
                  position: "Должность",
                  unitEmpty: "Выберите подразделение",
                })}
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-600">Ставка</label>
                  <input
                    value={payloadDraft.employment_rate || ""}
                    onChange={(e) => updatePayloadField("employment_rate", e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  />
                </div>
              </>
            ) : null}

            {type === "TRANSFER" ? (
              <>
                {renderOrgScopeCascade({
                  unit: "Новое подразделение",
                  position: "Новая должность",
                  unitEmpty: "без изменения",
                })}
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-600">Новая ставка</label>
                  <input
                    value={payloadDraft.to_rate || ""}
                    onChange={(e) => updatePayloadField("to_rate", e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  />
                </div>
              </>
            ) : null}

            {type === "TERMINATION" ? (
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-zinc-600">Причина увольнения</label>
                <input
                  value={payloadDraft.termination_reason || ""}
                  onChange={(e) => updatePayloadField("termination_reason", e.target.value)}
                  className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                />
              </div>
            ) : null}

            {type === "CONCURRENT_DUTY_START" ? (
              <>
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-600">Ставка совмещения</label>
                  <input
                    value={payloadDraft.concurrent_rate || ""}
                    onChange={(e) => updatePayloadField("concurrent_rate", e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-600">Итоговая ставка</label>
                  <input
                    value={payloadDraft.total_rate || ""}
                    onChange={(e) => updatePayloadField("total_rate", e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  />
                </div>
              </>
            ) : null}

            {type === "CONCURRENT_DUTY_END" ? (
              <>
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-600">Остающаяся ставка</label>
                  <input
                    value={payloadDraft.remaining_rate || ""}
                    onChange={(e) => updatePayloadField("remaining_rate", e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-600">Снимаемая ставка</label>
                  <input
                    value={payloadDraft.concurrent_rate || ""}
                    onChange={(e) => updatePayloadField("concurrent_rate", e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  />
                </div>
              </>
            ) : null}
          </div>

          {error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-200">
              {error}
            </div>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-lg bg-zinc-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-60 dark:bg-zinc-100 dark:text-zinc-900"
            >
              {saving ? "Сохранение…" : editingItemId != null ? "Сохранить пункт" : "Добавить пункт"}
            </button>
            {editingItemId != null ? (
              <button
                type="button"
                onClick={() => resetForm(itemTypeCode)}
                className="rounded-lg border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700"
              >
                Отмена
              </button>
            ) : null}
          </div>
        </form>
      ) : null}
    </div>
  );
}
