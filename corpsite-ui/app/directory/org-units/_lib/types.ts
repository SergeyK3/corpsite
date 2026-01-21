// FILE: corpsite-ui/app/directory/org-units/_lib/types.ts

export type OrgUnitNodeType = "org" | "dept" | "unit";

export type OrgUnitTreeNode = {
  id: string;
  title: string;
  type: OrgUnitNodeType;
  /**
   * Backend сейчас отдает inactive_ids отдельно, но поле полезно:
   * - для будущего упрощения UI (не таскать два источника истины),
   * - для типобезопасности при возможном расширении ответа.
   * Поэтому делаем optional, чтобы не ломать текущий контракт.
   */
  is_active?: boolean;
  children?: OrgUnitTreeNode[];
};

export type OrgUnitsTreeResponse = {
  version: number;
  total: number;
  inactive_ids: string[];
  items: OrgUnitTreeNode[];
  // root_id в backend может быть числом или строкой (в зависимости от источника/миграций),
  // поэтому UI должен спокойно принять оба варианта.
  root_id: string | number | null;
};
