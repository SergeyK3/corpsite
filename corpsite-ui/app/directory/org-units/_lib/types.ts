// FILE: corpsite-ui/app/directory/org-units/_lib/types.ts

export type OrgUnitTreeNode = {
  id: string;
  title: string;
  type: "unit";
  is_active: boolean;
  children?: OrgUnitTreeNode[];
};

export type OrgUnitsTreeResponse = {
  version: number;
  total: number;
  inactive_ids: string[];
  items: OrgUnitTreeNode[];
  root_id: number | null;
};
