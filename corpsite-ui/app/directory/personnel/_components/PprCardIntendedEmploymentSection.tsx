"use client";

import * as React from "react";

import OrgScopeFilter from "@/components/OrgScopeFilter";
import OrgUnitScopeFilter from "@/components/OrgUnitScopeFilter";
import {
  isOrgUnitAllowedForGroup,
  isPositionAllowedInOptions,
  type PersonnelOrderPositionSelectGroup,
} from "@/lib/taskOrgFilters";
import { useOrgUnitScopeOptions } from "@/lib/useOrgUnitScopeOptions";
import { usePersonnelOrderPositionOptions } from "@/lib/usePersonnelOrderPositionOptions";
import { findOrgGroupIdForUnit } from "@/lib/userCreateOrgScope";
import { getOrgUnitsTree } from "@/app/directory/org-units/_lib/api.client";

import {
  patchPprIntendedEmployment,
  type PprIntendedEmploymentUpdateBody,
} from "../_lib/pprQueryApi.client";
import type { PprIntendedEmploymentResponse } from "../_lib/pprQueryTypes";

const ORG_SCOPE_BASE_PATH = "/directory/personnel/employees";

type Props = {
  personId: number;
  initial: PprIntendedEmploymentResponse | null;
  editable?: boolean;
  onSaved?: (value: PprIntendedEmploymentResponse) => void;
};

function renderPositionOptions(groups: readonly PersonnelOrderPositionSelectGroup[]) {
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

export default function PprCardIntendedEmploymentSection({
  personId,
  initial,
  editable = true,
  onSaved,
}: Props) {
  const [orgGroupId, setOrgGroupId] = React.useState<number | null>(initial?.org_group_id ?? null);
  const [orgUnitId, setOrgUnitId] = React.useState<number | null>(initial?.org_unit_id ?? null);
  const [positionId, setPositionId] = React.useState<number | null>(initial?.position_id ?? null);
  const [employmentRate, setEmploymentRate] = React.useState(
    initial?.employment_rate != null ? String(initial.employment_rate) : "1",
  );
  const [saving, setSaving] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [savedSnapshot, setSavedSnapshot] = React.useState<PprIntendedEmploymentResponse | null>(initial);

  const {
    options: orgUnitSelectOptions,
    catalogOptions: orgUnitCatalogOptions,
    loading: orgUnitsLoading,
  } = useOrgUnitScopeOptions(orgGroupId);

  const { positionGroups, scopedOptions, loading: positionsLoading } = usePersonnelOrderPositionOptions({
    enabled: true,
    orgUnitId,
    orgGroupId,
  });

  React.useEffect(() => {
    setSavedSnapshot(initial);
    setOrgGroupId(initial?.org_group_id ?? null);
    setOrgUnitId(initial?.org_unit_id ?? null);
    setPositionId(initial?.position_id ?? null);
    setEmploymentRate(initial?.employment_rate != null ? String(initial.employment_rate) : "1");
  }, [initial]);

  React.useEffect(() => {
    if (orgGroupId != null || orgUnitId == null) return;
    let cancelled = false;
    void getOrgUnitsTree()
      .then((tree) => {
        if (cancelled) return;
        const groupId = findOrgGroupIdForUnit(tree.items ?? [], orgUnitId);
        if (groupId != null) setOrgGroupId(groupId);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [orgUnitId, orgGroupId]);

  async function handleSave() {
    if (!editable) return;
    setError(null);
    const rateNum = Number(String(employmentRate).replace(",", "."));
    if (!Number.isFinite(rateNum) || rateNum <= 0 || rateNum > 2) {
      setError("Укажите ставку от 0 до 2.");
      return;
    }
    if (orgUnitId == null || positionId == null) {
      setError("Выберите подразделение и должность.");
      return;
    }
    if (orgGroupId != null && !isOrgUnitAllowedForGroup(orgUnitId, orgGroupId, orgUnitCatalogOptions)) {
      setError("Подразделение не входит в выбранную группу.");
      return;
    }
    if (!isPositionAllowedInOptions(positionId, scopedOptions)) {
      setError("Выберите должность из списка для выбранного подразделения.");
      return;
    }

    const body: PprIntendedEmploymentUpdateBody = {
      org_group_id: orgGroupId,
      org_unit_id: orgUnitId,
      position_id: positionId,
      employment_rate: rateNum,
    };

    setSaving(true);
    try {
      const saved = await patchPprIntendedEmployment(personId, body);
      setSavedSnapshot(saved);
      onSaved?.(saved);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить.");
    } finally {
      setSaving(false);
    }
  }

  if (!editable && savedSnapshot) {
    return (
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-zinc-500">Группа подразделений</dt>
          <dd>{savedSnapshot.org_group_name ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Подразделение</dt>
          <dd>{savedSnapshot.org_unit_name ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Должность</dt>
          <dd>{savedSnapshot.position_name ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-zinc-500">Размер ставки</dt>
          <dd>{savedSnapshot.employment_rate ?? "—"}</dd>
        </div>
      </dl>
    );
  }

  return (
    <div className="space-y-4" data-testid="ppr-intended-employment-section">
      <OrgScopeFilter
        basePath={ORG_SCOPE_BASE_PATH}
        label="Группа подразделений"
        value={orgGroupId}
        onChange={(next) => {
          setOrgGroupId(next);
          setOrgUnitId(null);
          setPositionId(null);
        }}
      />

      <div className="grid gap-3 sm:grid-cols-2">
        <OrgUnitScopeFilter
          basePath={ORG_SCOPE_BASE_PATH}
          label="Подразделение"
          orgGroupId={orgGroupId}
          value={orgUnitId}
          unitOptions={orgUnitSelectOptions}
          unitsLoading={orgUnitsLoading}
          onChange={(next) => {
            setOrgUnitId(next);
            setPositionId(null);
          }}
        />

        <div>
          <label htmlFor="ppr-intended-position" className="mb-1 block text-sm font-medium">
            Должность
          </label>
          <select
            id="ppr-intended-position"
            className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
            value={positionId != null ? String(positionId) : ""}
            disabled={orgUnitId == null || positionsLoading}
            onChange={(e) => {
              const raw = e.target.value.trim();
              setPositionId(raw ? Number(raw) : null);
            }}
          >
            <option value="">{orgUnitId == null ? "Сначала выберите подразделение" : "Выберите должность"}</option>
            {renderPositionOptions(positionGroups)}
          </select>
        </div>
      </div>

      <div className="max-w-xs">
        <label htmlFor="ppr-intended-rate" className="mb-1 block text-sm font-medium">
          Размер ставки
        </label>
        <input
          id="ppr-intended-rate"
          type="text"
          inputMode="decimal"
          className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-950"
          value={employmentRate}
          onChange={(e) => setEmploymentRate(e.target.value)}
        />
      </div>

      {error ? <p className="text-sm text-red-600 dark:text-red-300">{error}</p> : null}

      {editable ? (
        <button
          type="button"
          disabled={saving}
          onClick={() => void handleSave()}
          className="rounded-lg border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 disabled:opacity-50"
        >
          {saving ? "Сохранение…" : "Сохранить предполагаемое трудоустройство"}
        </button>
      ) : null}
    </div>
  );
}
