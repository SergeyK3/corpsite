"use client";

import * as React from "react";

import { getEmployee, getEmployees } from "@/app/directory/employees/_lib/api.client";
import OrgScopeFilter from "@/components/OrgScopeFilter";
import OrgUnitScopeFilter from "@/components/OrgUnitScopeFilter";
import {
  isOrgUnitAllowedForGroup,
  isPositionAllowedInOptions,
  type PersonnelOrderPositionSelectGroup,
} from "@/lib/taskOrgFilters";
import { useOrgUnitScopeOptions } from "@/lib/useOrgUnitScopeOptions";
import { usePersonnelOrderPositionOptions } from "@/lib/usePersonnelOrderPositionOptions";
import { HR_DOSSIER_TITLE } from "@/lib/personnelCardTerminology";

import {
  createPersonnelOrderItem,
  mapPersonnelOrdersApiError,
  updatePersonnelOrderItem,
  type PersonnelOrderDetailResponse,
  type PersonnelOrderItem,
} from "../_lib/personnelOrdersApi.client";
import {
  employeeDtoToSearchOption,
  resolveCurrentPlacementView,
  type CurrentPlacementView,
} from "../_lib/personnelOrderCurrentPlacement";
import {
  mapEmployeesResponseToSearchOptions,
  requireEmployeeIdForItemType,
  type EmployeeSearchOption,
} from "../_lib/personnelOrderEmployeeSearch";
import {
  allowsPendingNewEmployee,
  detectUiItemTypeFromRecord,
  getItemFormRegistry,
  itemFormTypeLabel,
  itemFormTypeOptionsForOrder,
  normalizeItemFormType,
  orderTypeLabelForItemHint,
  resolveDefaultItemFormTypeForOrder,
  resolveBackendItemTypeCode,
  type ItemFormSection,
  type PersonnelOrderItemFormType,
  usesActiveEmployeeSearch,
} from "../_lib/personnelOrderItemFormRegistry";
import {
  buildItemPayload,
  emptyItemPayloadDraft,
  itemPayloadDraftFromRecord,
  type ItemPayloadDraft,
} from "../_lib/personnelOrderPayload";
import {
  clearOrgDependentFields,
  clearTransferTargetFields,
  isOrgScopedItemType,
  selectedOrgUnitIdFromDraft,
  selectedPositionIdFromDraft,
  setOrgUnitAndClearPosition,
  setPositionId,
} from "../_lib/personnelOrderOrgScope";

type Props = {
  orderId: number;
  orderTypeCode?: string | null;
  items: PersonnelOrderItem[];
  disabled?: boolean;
  onChanged: (detail: PersonnelOrderDetailResponse) => void;
};

const ORG_SCOPE_BASE_PATH = "/directory/personnel/orders";

const FIELD_LABEL_CLASS = "mb-1 block text-sm font-medium text-zinc-800 dark:text-zinc-200";
const FIELD_INPUT_CLASS =
  "w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950";
const FIELD_HINT_CLASS = "mt-1 text-xs text-zinc-500 dark:text-zinc-400";

function placementValue(value: string | null | undefined): string {
  const text = String(value ?? "").trim();
  return text || "—";
}

function renderPersonnelOrderPositionOptions(
  groups: readonly PersonnelOrderPositionSelectGroup[],
) {
  if (groups.length === 0) return null;

  return groups.map((group) => (
    <optgroup key={group.key} label={group.label}>
      {group.items.map((position) => (
        <option key={position.id} value={String(position.id)}>
          {position.label}
        </option>
      ))}
    </optgroup>
  ));
}

function FormField({
  label,
  htmlFor,
  hint,
  children,
  className = "",
}: {
  label: string;
  htmlFor?: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className={FIELD_LABEL_CLASS}>
        {label}
      </label>
      {children}
      {hint ? <p className={FIELD_HINT_CLASS}>{hint}</p> : null}
    </div>
  );
}

function CurrentPlacementPanel({ placement }: { placement: CurrentPlacementView }) {
  return (
    <div
      className="space-y-2 rounded-lg border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900/40"
      data-testid="personnel-order-current-placement"
    >
      <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
        Текущее назначение
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <div>
          <div className="text-[11px] text-zinc-500">Группа отделений</div>
          <div data-testid="personnel-order-current-org-group">
            {placementValue(placement.org_group_name)}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-zinc-500">Подразделение</div>
          <div data-testid="personnel-order-current-org-unit">
            {placementValue(placement.org_unit_name)}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-zinc-500">Должность</div>
          <div data-testid="personnel-order-current-position">
            {placementValue(placement.position_name)}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-zinc-500">Ставка</div>
          <div data-testid="personnel-order-current-rate">{placementValue(placement.rate)}</div>
        </div>
      </div>
    </div>
  );
}

export default function PersonnelOrderItemEditor({
  orderId,
  orderTypeCode = null,
  items,
  disabled = false,
  onChanged,
}: Props) {
  const defaultItemType = resolveDefaultItemFormTypeForOrder(orderTypeCode);
  const itemTypeOptions = itemFormTypeOptionsForOrder(orderTypeCode);
  const orderTypeHint = orderTypeLabelForItemHint(orderTypeCode);

  const [editingItemId, setEditingItemId] = React.useState<number | null>(null);
  /** Saved employee_id when edit started; independent of current form fields (WP-PO-UX-001A). */
  const [editingItemSavedEmployeeId, setEditingItemSavedEmployeeId] = React.useState<number | null>(
    null,
  );
  const [itemTypeCode, setItemTypeCode] = React.useState<PersonnelOrderItemFormType>(defaultItemType);
  const [employeeId, setEmployeeId] = React.useState("");
  const [employeeQuery, setEmployeeQuery] = React.useState("");
  const [pendingNewEmployee, setPendingNewEmployee] = React.useState(false);
  const [employeeOptions, setEmployeeOptions] = React.useState<EmployeeSearchOption[]>([]);
  const [currentPlacement, setCurrentPlacement] = React.useState<CurrentPlacementView | null>(null);
  const [effectiveDate, setEffectiveDate] = React.useState("");
  const [payloadDraft, setPayloadDraft] = React.useState<ItemPayloadDraft>(emptyItemPayloadDraft());
  const [targetOrgGroupId, setTargetOrgGroupId] = React.useState<number | null>(null);
  const [hireOrgGroupId, setHireOrgGroupId] = React.useState<number | null>(null);
  const [saving, setSaving] = React.useState(false);
  const [employeeSearchError, setEmployeeSearchError] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const formConfig = getItemFormRegistry(itemTypeCode);
  const orgScoped = isOrgScopedItemType(itemTypeCode);
  const activeOrgGroupId = formConfig?.showHirePlacement ? hireOrgGroupId : targetOrgGroupId;
  const {
    options: orgUnitSelectOptions,
    catalogOptions: orgUnitCatalogOptions,
    loading: orgUnitsLoading,
    error: orgUnitsError,
  } = useOrgUnitScopeOptions(orgScoped ? activeOrgGroupId : null);
  const selectedOrgUnitId = selectedOrgUnitIdFromDraft(payloadDraft, itemTypeCode);
  const {
    positionGroups,
    allOptions: positionOptions,
    loading: positionsLoading,
  } = usePersonnelOrderPositionOptions({
    enabled: orgScoped,
    orgUnitId: selectedOrgUnitId,
    orgGroupId: activeOrgGroupId,
  });
  const effectiveDateLabel =
    itemTypeCode.toUpperCase() === "TERMINATION" ? "Дата увольнения" : "Дата вступления в силу";
  const savedEmployeeIdBlocksPendingReset =
    editingItemId != null &&
    editingItemSavedEmployeeId != null &&
    Number.isFinite(editingItemSavedEmployeeId) &&
    editingItemSavedEmployeeId > 0;
  const pendingNewEmployeeAllowed =
    allowsPendingNewEmployee(itemTypeCode) && !savedEmployeeIdBlocksPendingReset;
  const showEmployeePicker =
    formConfig?.employeePicker && !(pendingNewEmployee && pendingNewEmployeeAllowed);

  React.useEffect(() => {
    if (editingItemId != null) return;
    setItemTypeCode(defaultItemType);
  }, [defaultItemType, editingItemId]);

  React.useEffect(() => {
    if (!formConfig?.employeePicker || pendingNewEmployee) {
      setEmployeeOptions([]);
      setEmployeeSearchError(null);
      return;
    }
    const q = employeeQuery.trim();
    if (q.length < 2) {
      setEmployeeOptions([]);
      setEmployeeSearchError(null);
      return;
    }
    const activeOnly = usesActiveEmployeeSearch(itemTypeCode);
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setEmployeeSearchError(null);
      void getEmployees({
        q,
        limit: 20,
        status: activeOnly ? "active" : "all",
      })
        .then((res) => {
          if (cancelled) return;
          setEmployeeOptions(mapEmployeesResponseToSearchOptions(res, { activeOnly }));
        })
        .catch((err) => {
          if (cancelled) return;
          setEmployeeOptions([]);
          setEmployeeSearchError(
            err instanceof Error ? err.message : "Не удалось загрузить список сотрудников.",
          );
        });
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [employeeQuery, formConfig?.employeePicker, itemTypeCode, pendingNewEmployee]);

  React.useEffect(() => {
    if (!orgScoped) return;
    if (orgUnitCatalogOptions.length === 0) return;

    const unitAllowed = isOrgUnitAllowedForGroup(
      selectedOrgUnitId ?? undefined,
      activeOrgGroupId ?? undefined,
      orgUnitCatalogOptions,
    );
    if (unitAllowed) return;

    setPayloadDraft((prev) => clearOrgDependentFields(prev, itemTypeCode));
  }, [orgScoped, activeOrgGroupId, selectedOrgUnitId, orgUnitCatalogOptions, itemTypeCode]);

  React.useEffect(() => {
    if (!orgScoped) return;

    const positionId = Number(selectedPositionIdFromDraft(payloadDraft, itemTypeCode));
    if (!Number.isFinite(positionId) || positionId <= 0) return;
    if (positionsLoading) return;
    if (isPositionAllowedInOptions(positionId, positionOptions)) return;

    setPayloadDraft((prev) => setPositionId(prev, itemTypeCode, ""));
  }, [orgScoped, positionOptions, positionsLoading, payloadDraft, itemTypeCode]);

  function resetForm(typeCode: PersonnelOrderItemFormType = defaultItemType) {
    setEditingItemId(null);
    setEditingItemSavedEmployeeId(null);
    setItemTypeCode(typeCode);
    setEmployeeId("");
    setEmployeeQuery("");
    setPendingNewEmployee(false);
    setCurrentPlacement(null);
    setEffectiveDate("");
    setPayloadDraft(emptyItemPayloadDraft());
    setTargetOrgGroupId(null);
    setHireOrgGroupId(null);
    setError(null);
  }

  async function applyEmployeeSelection(option: EmployeeSearchOption) {
    setPendingNewEmployee(false);
    setEmployeeId(String(option.employee_id));
    setEmployeeQuery(option.full_name);
    setEmployeeOptions([]);

    const config = getItemFormRegistry(itemTypeCode);
    if (config?.clearTargetOnEmployeeChange) {
      setPayloadDraft((prev) => clearTransferTargetFields(prev));
      setTargetOrgGroupId(null);
    }

    if (config?.showCurrentPlacement) {
      const placement = await resolveCurrentPlacementView(option);
      setCurrentPlacement(placement);
    } else {
      setCurrentPlacement(null);
    }
  }

  async function loadCurrentPlacementByEmployeeId(id: number, fallbackName?: string | null) {
    try {
      const details = await getEmployee(String(id));
      const option = employeeDtoToSearchOption(details);
      if (!option.full_name && fallbackName) {
        option.full_name = fallbackName;
      }
      const placement = await resolveCurrentPlacementView(option);
      setCurrentPlacement(placement);
    } catch {
      setCurrentPlacement(null);
    }
  }

  async function startEdit(item: PersonnelOrderItem) {
    const uiType = detectUiItemTypeFromRecord(item);
    const normalizedUiType = normalizeItemFormType(uiType) ?? defaultItemType;
    const draft = itemPayloadDraftFromRecord(item.payload);
    const savedEmployeeId =
      item.employee_id != null && Number(item.employee_id) > 0 ? Number(item.employee_id) : null;
    setEditingItemId(item.item_id);
    setEditingItemSavedEmployeeId(savedEmployeeId);
    setItemTypeCode(normalizedUiType);
    setEmployeeId(item.employee_id ? String(item.employee_id) : "");
    setEmployeeQuery(item.employee_name || "");
    setPendingNewEmployee(
      savedEmployeeId == null && allowsPendingNewEmployee(normalizedUiType),
    );
    setEffectiveDate(item.effective_date || "");
    setPayloadDraft(draft);
    setError(null);
    setCurrentPlacement(null);

    const config = getItemFormRegistry(normalizedUiType);
    if (item.employee_id && config?.showCurrentPlacement) {
      void loadCurrentPlacementByEmployeeId(item.employee_id, item.employee_name);
    }

    const unitId = selectedOrgUnitIdFromDraft(draft, normalizedUiType);
    if (unitId == null) {
      setTargetOrgGroupId(null);
      setHireOrgGroupId(null);
      return;
    }
    try {
      const prefill = await resolveEmployeeOrgScopePrefill(unitId);
      if (config?.showHirePlacement) {
        setHireOrgGroupId(prefill.org_group_id);
      } else if (config?.showTargetPlacement) {
        setTargetOrgGroupId(prefill.org_group_id);
      }
    } catch {
      setTargetOrgGroupId(null);
      setHireOrgGroupId(null);
    }
  }

  function handleItemTypeChange(nextType: PersonnelOrderItemFormType) {
    setItemTypeCode(nextType);
    setPayloadDraft(emptyItemPayloadDraft());
    setTargetOrgGroupId(null);
    setHireOrgGroupId(null);
    setPendingNewEmployee(
      editingItemId != null &&
        editingItemSavedEmployeeId == null &&
        allowsPendingNewEmployee(nextType),
    );
    setError(null);
    if (!getItemFormRegistry(nextType)?.showCurrentPlacement) {
      setCurrentPlacement(null);
    }
  }

  function handlePendingNewEmployeeChange(checked: boolean) {
    if (savedEmployeeIdBlocksPendingReset) return;
    setPendingNewEmployee(checked);
    if (checked) {
      setEmployeeId("");
      setEmployeeQuery("");
      setEmployeeOptions([]);
      setCurrentPlacement(null);
    }
  }

  function updatePayloadField<K extends keyof ItemPayloadDraft>(key: K, value: string) {
    setPayloadDraft((prev) => ({ ...prev, [key]: value }));
  }

  function handleTargetOrgGroupChange(nextGroupId: number | null) {
    setTargetOrgGroupId(nextGroupId);
    setPayloadDraft((prev) => clearOrgDependentFields(prev, itemTypeCode));
  }

  function handleHireOrgGroupChange(nextGroupId: number | null) {
    setHireOrgGroupId(nextGroupId);
    setPayloadDraft((prev) => clearOrgDependentFields(prev, "HIRE"));
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

    const employeeRequiredMessage = requireEmployeeIdForItemType(itemTypeCode, employeeId, {
      pendingNewEmployee: pendingNewEmployee && pendingNewEmployeeAllowed,
    });
    if (employeeRequiredMessage) {
      setError(employeeRequiredMessage);
      return;
    }

    setSaving(true);
    try {
      const backendType = resolveBackendItemTypeCode(itemTypeCode);
      const employeeNumeric = Number(employeeId);
      let resolvedEmployeeId =
        Number.isFinite(employeeNumeric) && employeeNumeric > 0 ? employeeNumeric : null;
      if (savedEmployeeIdBlocksPendingReset && resolvedEmployeeId == null) {
        resolvedEmployeeId = editingItemSavedEmployeeId;
      }
      const body = {
        item_type_code: backendType,
        employee_id: resolvedEmployeeId,
        effective_date: effectiveDate || null,
        payload: buildItemPayload(backendType, payloadDraft),
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

  function renderOrgPlacementCascade(options: {
    sectionTitle: string;
    orgGroupId: number | null;
    onOrgGroupChange: (id: number | null) => void;
    unitLabel: string;
    positionLabel: string;
    unitEmptyLabel: string;
    testId?: string;
  }) {
    const cascadeType = formConfig?.showHirePlacement ? "HIRE" : itemTypeCode;
    return (
      <div className="space-y-3" data-testid={options.testId ?? "personnel-order-org-placement"}>
        <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
          {options.sectionTitle}
        </div>
        <div data-testid="personnel-order-org-scope-cascade">
          <OrgScopeFilter
            basePath={ORG_SCOPE_BASE_PATH}
            label="Группа отделений"
            value={options.orgGroupId}
            onChange={options.onOrgGroupChange}
          />
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <OrgUnitScopeFilter
              basePath={ORG_SCOPE_BASE_PATH}
              label={options.unitLabel}
              allLabel={options.unitEmptyLabel}
              orgGroupId={options.orgGroupId}
              value={selectedOrgUnitIdFromDraft(payloadDraft, cascadeType)}
              unitOptions={orgUnitSelectOptions}
              unitsLoading={orgUnitsLoading}
              unitsError={orgUnitsError}
              onChange={(unitId) => {
                if (formConfig?.showHirePlacement) {
                  setPayloadDraft((prev) => setOrgUnitAndClearPosition(prev, "HIRE", unitId));
                } else {
                  handleOrgUnitChange(unitId);
                }
              }}
            />
            <FormField label={options.positionLabel}>
              <select
                data-testid="personnel-order-position-select"
                value={selectedPositionIdFromDraft(payloadDraft, cascadeType)}
                onChange={(e) => {
                  if (formConfig?.showHirePlacement) {
                    setPayloadDraft((prev) => setPositionId(prev, "HIRE", e.target.value));
                  } else {
                    handlePositionChange(e.target.value);
                  }
                }}
                disabled={
                  selectedOrgUnitIdFromDraft(payloadDraft, cascadeType) == null ||
                  positionsLoading ||
                  positionOptions.length === 0
                }
                className={FIELD_INPUT_CLASS}
              >
                <option value="">
                  {selectedOrgUnitIdFromDraft(payloadDraft, cascadeType) == null
                    ? "Сначала выберите подразделение"
                    : positionsLoading
                      ? "Загрузка…"
                      : positionOptions.length === 0
                        ? "Нет доступных должностей"
                        : "—"}
                </option>
                {renderPersonnelOrderPositionOptions(positionGroups)}
              </select>
            </FormField>
          </div>
        </div>
      </div>
    );
  }

  function renderItemTypeSection() {
    return (
      <FormField
        label="Тип пункта"
        hint={
          orderTypeHint
            ? `Тип конкретной строки приказа. Тип приказа «${orderTypeHint}» задаётся в заголовке.`
            : "Тип конкретной строки приказа (в составных приказах пункты могут отличаться)."
        }
      >
        <select
          data-testid="personnel-order-item-type-select"
          value={itemTypeCode}
          onChange={(e) => handleItemTypeChange(e.target.value as PersonnelOrderItemFormType)}
          className={FIELD_INPUT_CLASS}
        >
          {itemTypeOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </FormField>
    );
  }

  function renderEmployeeSection() {
    if (!formConfig?.employeePicker) return null;

    const pendingAllowed = allowsPendingNewEmployee(itemTypeCode);

    return (
      <div className="space-y-3" data-testid="personnel-order-employee-section">
        {pendingAllowed ? (
          <div className="space-y-1">
            <label
              className={`flex items-start gap-2 text-sm ${
                pendingNewEmployeeAllowed
                  ? "text-zinc-700 dark:text-zinc-300"
                  : "text-zinc-500 dark:text-zinc-500"
              }`}
            >
              <input
                type="checkbox"
                checked={pendingNewEmployee}
                disabled={!pendingNewEmployeeAllowed}
                onChange={(e) => handlePendingNewEmployeeChange(e.target.checked)}
                data-testid="personnel-order-pending-new-employee"
                className="mt-0.5"
              />
              <span>
                <span className="font-medium">Новый сотрудник</span>
                <span
                  className="mt-0.5 block text-xs text-zinc-500"
                  data-testid={
                    savedEmployeeIdBlocksPendingReset
                      ? "personnel-order-pending-new-employee-reset-blocked"
                      : undefined
                  }
                >
                  {pendingNewEmployeeAllowed
                    ? `${HR_DOSSIER_TITLE} будет создана позже. Пункт сохранится без привязки к employee_id.`
                    : "Сброс сотрудника в сохранённом пункте пока не поддерживается."}
                </span>
              </span>
            </label>
          </div>
        ) : null}

        {showEmployeePicker ? (
          <FormField
            label="Сотрудник"
            hint={
              pendingAllowed && pendingNewEmployeeAllowed
                ? "Необязательно для приёма. Можно указать существующего сотрудника или оставить пустым."
                : "Выберите действующего сотрудника из результатов поиска."
            }
          >
            <div className="flex flex-wrap gap-2">
              <input
                value={employeeQuery}
                onChange={(e) => setEmployeeQuery(e.target.value)}
                placeholder="Поиск по ФИО…"
                autoComplete="off"
                data-testid="personnel-order-employee-search-input"
                className={`min-w-[12rem] flex-1 ${FIELD_INPUT_CLASS}`}
              />
              <input
                value={employeeId}
                onChange={(e) => setEmployeeId(e.target.value)}
                placeholder="ID"
                aria-label="Идентификатор сотрудника"
                data-testid="personnel-order-employee-id-input"
                className={`w-24 ${FIELD_INPUT_CLASS}`}
              />
            </div>
            {employeeSearchError ? (
              <p
                className="mt-1 text-xs text-red-600 dark:text-red-400"
                data-testid="personnel-order-employee-search-error"
              >
                {employeeSearchError}
              </p>
            ) : null}
            {employeeOptions.length > 0 ? (
              <div
                className="mt-1 max-h-32 overflow-auto rounded-lg border border-zinc-200 dark:border-zinc-800"
                data-testid="personnel-order-employee-search-results"
              >
                {employeeOptions.map((option) => (
                  <button
                    key={option.employee_id}
                    type="button"
                    className="block w-full px-3 py-1.5 text-left text-sm hover:bg-zinc-50 dark:hover:bg-zinc-900"
                    data-testid={`personnel-order-employee-option-${option.employee_id}`}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => void applyEmployeeSelection(option)}
                  >
                    {option.full_name} · #{option.employee_id}
                  </button>
                ))}
              </div>
            ) : null}
          </FormField>
        ) : pendingNewEmployee ? (
          <p
            className="rounded-lg border border-dashed border-zinc-300 px-3 py-2 text-sm text-zinc-600 dark:border-zinc-700 dark:text-zinc-400"
            data-testid="personnel-order-pending-new-employee-hint"
          >
            Сотрудник не выбран. Сохранение возможно без employee_id.
          </p>
        ) : null}
      </div>
    );
  }

  function renderEffectiveDateSection() {
    return (
      <FormField label={effectiveDateLabel}>
        <input
          type="date"
          value={effectiveDate}
          onChange={(e) => setEffectiveDate(e.target.value)}
          className={FIELD_INPUT_CLASS}
        />
      </FormField>
    );
  }

  function renderOrgPlacementSection() {
    if (formConfig?.showTargetPlacement) {
      return renderOrgPlacementCascade({
        sectionTitle: formConfig.orgPlacementSectionTitle,
        orgGroupId: targetOrgGroupId,
        onOrgGroupChange: handleTargetOrgGroupChange,
        unitLabel: "Подразделение",
        positionLabel: "Должность",
        unitEmptyLabel: "без изменения",
        testId: "personnel-order-target-placement",
      });
    }
    if (formConfig?.showHirePlacement) {
      return renderOrgPlacementCascade({
        sectionTitle: formConfig.orgPlacementSectionTitle,
        orgGroupId: hireOrgGroupId,
        onOrgGroupChange: handleHireOrgGroupChange,
        unitLabel: "Подразделение",
        positionLabel: "Должность",
        unitEmptyLabel: "Выберите подразделение",
        testId: "personnel-order-hire-legacy",
      });
    }
    return null;
  }

  function renderAdditionalSection() {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {formConfig?.showTargetRate && formConfig.showTargetPlacement ? (
          <FormField label="Новая ставка">
            <input
              data-testid="personnel-order-target-rate-input"
              value={payloadDraft.to_rate || ""}
              onChange={(e) => updatePayloadField("to_rate", e.target.value)}
              className={FIELD_INPUT_CLASS}
            />
          </FormField>
        ) : null}

        {formConfig?.showTargetRate && !formConfig.showTargetPlacement ? (
          <FormField label="Новая ставка" className="sm:col-span-2">
            <input
              data-testid="personnel-order-new-rate-input"
              value={payloadDraft.to_rate || ""}
              onChange={(e) => updatePayloadField("to_rate", e.target.value)}
              className={FIELD_INPUT_CLASS}
            />
          </FormField>
        ) : null}

        {formConfig?.showHirePlacement ? (
          <FormField label="Ставка" className="sm:col-span-2">
            <input
              data-testid="personnel-order-hire-rate-input"
              value={payloadDraft.employment_rate || ""}
              onChange={(e) => updatePayloadField("employment_rate", e.target.value)}
              className={FIELD_INPUT_CLASS}
            />
          </FormField>
        ) : null}

        {formConfig?.showTerminationReason ? (
          <FormField label="Причина увольнения" className="sm:col-span-2">
            <input
              data-testid="personnel-order-termination-reason-input"
              value={payloadDraft.termination_reason || ""}
              onChange={(e) => updatePayloadField("termination_reason", e.target.value)}
              className={FIELD_INPUT_CLASS}
            />
          </FormField>
        ) : null}

        {formConfig?.showConcurrentDutyStartFields ? (
          <>
            <FormField label="Ставка совмещения">
              <input
                value={payloadDraft.concurrent_rate || ""}
                onChange={(e) => updatePayloadField("concurrent_rate", e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </FormField>
            <FormField label="Итоговая ставка">
              <input
                value={payloadDraft.total_rate || ""}
                onChange={(e) => updatePayloadField("total_rate", e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </FormField>
          </>
        ) : null}

        {formConfig?.showConcurrentDutyEndFields ? (
          <>
            <FormField label="Остающаяся ставка">
              <input
                value={payloadDraft.remaining_rate || ""}
                onChange={(e) => updatePayloadField("remaining_rate", e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </FormField>
            <FormField label="Снимаемая ставка">
              <input
                value={payloadDraft.concurrent_rate || ""}
                onChange={(e) => updatePayloadField("concurrent_rate", e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </FormField>
          </>
        ) : null}
      </div>
    );
  }

  function renderFormSection(section: ItemFormSection) {
    switch (section) {
      case "item_type":
        return <React.Fragment key={section}>{renderItemTypeSection()}</React.Fragment>;
      case "employee":
        return <React.Fragment key={section}>{renderEmployeeSection()}</React.Fragment>;
      case "current_placement":
        return formConfig?.showCurrentPlacement && currentPlacement ? (
          <CurrentPlacementPanel key={section} placement={currentPlacement} />
        ) : null;
      case "org_placement":
        return <React.Fragment key={section}>{renderOrgPlacementSection()}</React.Fragment>;
      case "effective_date":
        return <React.Fragment key={section}>{renderEffectiveDateSection()}</React.Fragment>;
      case "additional": {
        const additional = renderAdditionalSection();
        return additional ? <React.Fragment key={section}>{additional}</React.Fragment> : null;
      }
      default:
        return null;
    }
  }

  const sectionOrder = formConfig?.fieldSectionOrder ?? [];

  return (
    <div className="space-y-4" data-testid="personnel-order-item-editor">
      <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-50 dark:bg-zinc-900/50">
            <tr>
              {["№", "Тип пункта", "Сотрудник", "Дата", "Статус", ""].map((h) => (
                <th
                  key={h || "actions"}
                  className="px-3 py-2 text-left text-[11px] font-semibold uppercase text-zinc-500"
                >
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
                  <td className="px-3 py-2">
                    {itemFormTypeLabel(detectUiItemTypeFromRecord(item))}
                  </td>
                  <td className="px-3 py-2">
                    {item.employee_name ||
                      (item.employee_id ? `#${item.employee_id}` : "Новый сотрудник")}
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
        <form
          className="space-y-4 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800"
          onSubmit={handleSubmit}
        >
          <div>
            <div className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              {editingItemId != null ? `Редактирование пункта #${editingItemId}` : "Добавить пункт"}
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              Заполните поля пункта в указанном порядке. Тип пункта не заменяет тип приказа.
            </p>
          </div>

          <div className="space-y-4">
            {sectionOrder.map((section) => renderFormSection(section))}
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
                onClick={() => resetForm(defaultItemType)}
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
