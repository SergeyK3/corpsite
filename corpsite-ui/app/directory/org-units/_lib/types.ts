// FILE: corpsite-ui/app/directory/org-units/_lib/types.ts

/**
 * Типы UI для Directory / Org Units.
 * Контракт выровнен под backend: GET /directory/org-units/tree
 *
 * Пример ответа (по вашим логам):
 * {
 *   "version": 1,
 *   "total": 1,
 *   "inactive_ids": [],
 *   "items": [{ "id":"44","title":"Администрация","type":"unit","is_active":true,"children":[] }],
 *   "root_id": 44
 * }
 *
 * ВАЖНО ДЛЯ UI:
 * - TreeNode.id в UI — string, поэтому здесь id тоже строго string.
 * - type должен совпадать с OrgUnitNodeType из OrgUnitsTree.tsx: "org" | "dept" | "unit".
 * - children в TreeNode объявлен как optional, поэтому делаем так же (совместимость типов).
 * - root_id / inactive_ids — string, чтобы корректно сравнивать с node.id.
 */

import type { OrgUnitNodeType } from "../_components/OrgUnitsTree";

export type OrgUnitTreeNode = {
  id: string;
  title: string;
  type: OrgUnitNodeType; // FIX: было "unit" | "group"
  children?: OrgUnitTreeNode[]; // FIX: было обязательным
  is_active?: boolean; // FIX: делаем совместимым (в TreeNode этого поля нет)
};

export type OrgUnitsTreeResponse = {
  version: number;
  total: number;
  inactive_ids: string[];
  items: OrgUnitTreeNode[];
  root_id: string | null;
};

/**
 * Ответы мутаций (rename/move/activate/deactivate/create) — backend сейчас возвращает item
 * в "плоском" виде. UI после операции делает reload tree, поэтому эти типы не обязаны
 * совпадать с OrgUnitTreeNode.
 */
export type OrgUnitMutationItem = {
  id: string | number;
  parent_id: number | null;
  name: string;
  code: string | null;
  is_active: boolean;
};

export type OrgUnitMutationResponse = {
  item: OrgUnitMutationItem;
};
