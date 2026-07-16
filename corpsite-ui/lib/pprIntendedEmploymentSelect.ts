import {
  PERSONNEL_ORDER_POSITION_GROUP_LABELS,
  flattenPersonnelOrderPositionGroups,
  type PersonnelOrderPositionSelectGroup,
} from "@/lib/taskOrgFilters";
import type { OrgUnitSelectOption } from "@/lib/orgUnitsSelect";

/** Pin a saved unit for display when async options have not loaded it yet. */
export function ensureOrgUnitInOptions(
  options: readonly OrgUnitSelectOption[],
  unitId: number | null,
  unitName: string | null | undefined,
  groupId: number | null | undefined,
): OrgUnitSelectOption[] {
  if (unitId == null) return [...options];
  if (options.some((row) => row.unit_id === unitId)) return [...options];
  const name = String(unitName ?? "").trim();
  if (!name) return [...options];
  return [
    ...options,
    {
      unit_id: unitId,
      name,
      group_id: groupId ?? null,
    },
  ];
}

/** Pin a saved position for display when async options have not loaded it yet. */
export function ensurePositionInGroups(
  groups: readonly PersonnelOrderPositionSelectGroup[],
  positionId: number | null,
  positionName: string | null | undefined,
): PersonnelOrderPositionSelectGroup[] {
  if (positionId == null) return [...groups];
  const flat = flattenPersonnelOrderPositionGroups(groups);
  if (flat.some((row) => row.id === positionId)) return [...groups];
  const label = String(positionName ?? "").trim();
  if (!label) return [...groups];

  const pinned: PersonnelOrderPositionSelectGroup = {
    key: "allowed_in_unit",
    label: PERSONNEL_ORDER_POSITION_GROUP_LABELS.allowedInUnit,
    items: [{ id: positionId, label }],
  };
  const rest = groups.filter((group) => group.key !== "allowed_in_unit");
  return [pinned, ...rest];
}
