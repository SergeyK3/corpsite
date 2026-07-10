"use client";

import * as React from "react";

import { getEmployees, getPositions } from "@/app/directory/employees/_lib/api.client";
import { getOrgUnitsTree, type TreeNode } from "@/app/directory/org-units/_lib/api.client";

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

type NamedOption = { id: number; name: string };

function flattenOrgUnits(nodes: TreeNode[], out: NamedOption[]) {
  for (const node of nodes) {
    const unitId = Number(node.unit_id ?? node.id);
    if (Number.isFinite(unitId) && unitId > 0) {
      out.push({
        id: unitId,
        name: String(node.name ?? node.name_ru ?? `#${unitId}`).trim() || `#${unitId}`,
      });
    }
    if (Array.isArray(node.children) && node.children.length > 0) {
      flattenOrgUnits(node.children, out);
    }
  }
}

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
  const [orgUnits, setOrgUnits] = React.useState<NamedOption[]>([]);
  const [positions, setPositions] = React.useState<NamedOption[]>([]);
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    async function loadLookups() {
      try {
        const tree = await getOrgUnitsTree();
        const units: NamedOption[] = [];
        flattenOrgUnits(Array.isArray(tree?.items) ? tree.items : [], units);
        if (!cancelled) setOrgUnits(units);
      } catch {
        if (!cancelled) setOrgUnits([]);
      }
      try {
        const raw = await getPositions({ limit: 1000, offset: 0 });
        const list = Array.isArray(raw) ? raw : Array.isArray(raw?.items) ? raw.items : [];
        const mapped: NamedOption[] = [];
        for (const row of list) {
          const id = Number((row as { position_id?: number; id?: number }).position_id ?? (row as { id?: number }).id);
          if (!Number.isFinite(id) || id <= 0) continue;
          mapped.push({
            id,
            name: String((row as { name?: string }).name ?? `#${id}`).trim() || `#${id}`,
          });
        }
        if (!cancelled) setPositions(mapped);
      } catch {
        if (!cancelled) setPositions([]);
      }
    }
    void loadLookups();
    return () => {
      cancelled = true;
    };
  }, []);

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

  function resetForm(typeCode = "HIRE") {
    setEditingItemId(null);
    setItemTypeCode(typeCode);
    setEmployeeId("");
    setEmployeeQuery("");
    setEffectiveDate("");
    setPayloadDraft(emptyItemPayloadDraft());
    setError(null);
  }

  function startEdit(item: PersonnelOrderItem) {
    setEditingItemId(item.item_id);
    setItemTypeCode(item.item_type_code);
    setEmployeeId(item.employee_id ? String(item.employee_id) : "");
    setEmployeeQuery(item.employee_name || "");
    setEffectiveDate(item.effective_date || "");
    setPayloadDraft(itemPayloadDraftFromRecord(item.payload));
    setError(null);
  }

  function updatePayloadField<K extends keyof ItemPayloadDraft>(key: K, value: string) {
    setPayloadDraft((prev) => ({ ...prev, [key]: value }));
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

  const type = itemTypeCode.toUpperCase();

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
                        onClick={() => startEdit(item)}
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
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-600">Подразделение</label>
                  <select
                    value={payloadDraft.org_unit_id || ""}
                    onChange={(e) => updatePayloadField("org_unit_id", e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  >
                    <option value="">—</option>
                    {orgUnits.map((unit) => (
                      <option key={unit.id} value={unit.id}>
                        {unit.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-600">Должность</label>
                  <select
                    value={payloadDraft.position_id || ""}
                    onChange={(e) => updatePayloadField("position_id", e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  >
                    <option value="">—</option>
                    {positions.map((position) => (
                      <option key={position.id} value={position.id}>
                        {position.name}
                      </option>
                    ))}
                  </select>
                </div>
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
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-600">Новое подразделение</label>
                  <select
                    value={payloadDraft.to_org_unit_id || ""}
                    onChange={(e) => updatePayloadField("to_org_unit_id", e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  >
                    <option value="">без изменения</option>
                    {orgUnits.map((unit) => (
                      <option key={unit.id} value={unit.id}>
                        {unit.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-zinc-600">Новая должность</label>
                  <select
                    value={payloadDraft.to_position_id || ""}
                    onChange={(e) => updatePayloadField("to_position_id", e.target.value)}
                    className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
                  >
                    <option value="">—</option>
                    {positions.map((position) => (
                      <option key={position.id} value={position.id}>
                        {position.name}
                      </option>
                    ))}
                  </select>
                </div>
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
