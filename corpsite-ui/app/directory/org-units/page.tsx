// FILE: corpsite-ui/app/directory/org-units/page.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import OrgScopeFilter from "@/components/OrgScopeFilter";
import ExportExcelButton from "@/components/ExportExcelButton";
import { useCurrentUser } from "@/lib/currentUser";
import { readOrgScopeFromSearchParams } from "@/lib/orgScope";

import { nodeSearchText, type TreeNode } from "./_components/OrgUnitsTree";
import {
  activateOrgUnit,
  createOrgUnit,
  deactivateOrgUnit,
  getOrgUnitsTree,
  mapApiTreeNodesToUi,
  mapApiErrorToMessage,
  moveOrgUnit,
  renameOrgUnit,
} from "./_lib/api.client";

function findNodeById(nodes: TreeNode[], id: string): TreeNode | null {
  const target = String(id);
  const stack: TreeNode[] = [...nodes];
  while (stack.length) {
    const n = stack.pop()!;
    if (String(n.id) === target) return n;
    for (const ch of n.children ?? []) stack.push(ch);
  }
  return null;
}

function findParentId(nodes: TreeNode[], id: string): string | null {
  const target = String(id);
  const stack: Array<{ node: TreeNode; parentId: string | null }> = nodes.map((n) => ({ node: n, parentId: null }));

  while (stack.length) {
    const cur = stack.pop()!;
    if (String(cur.node.id) === target) return cur.parentId;
    for (const ch of cur.node.children ?? []) {
      stack.push({ node: ch, parentId: String(cur.node.id) });
    }
  }
  return null;
}

function flattenNodes(nodes: TreeNode[]): Array<{ id: string; title: string; type: string }> {
  const out: Array<{ id: string; title: string; type: string }> = [];
  const stack: TreeNode[] = [...nodes];
  while (stack.length) {
    const n = stack.pop()!;
    out.push({ id: String(n.id), title: n.title || "", type: n.type });
    for (const ch of n.children ?? []) stack.push(ch);
  }
  return out;
}

type OrgUnitListRow = { node: TreeNode; parentTitle: string | null };

function flattenListRows(nodes: TreeNode[]): OrgUnitListRow[] {
  const rows: OrgUnitListRow[] = [];
  const seen = new Set<string>();
  function visit(items: TreeNode[], parentTitle: string | null) {
    for (const node of items) {
      if (seen.has(String(node.id))) continue;
      seen.add(String(node.id));
      rows.push({ node, parentTitle });
      visit(node.children ?? [], node.title);
    }
  }
  visit(nodes, null);
  return rows;
}

export default function OrgUnitsPage() {
  const canManage = useCurrentUser()?.is_sysadmin_assistant !== true;
  const router = useRouter();
  const sp = useSearchParams();
  const orgScope = useMemo(() => readOrgScopeFromSearchParams(sp), [sp]);

  const [nodes, setNodes] = useState<TreeNode[]>([]);
  const [inactiveIds, setInactiveIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showInactive, setShowInactive] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState("");

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");

  // Rename modal
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [renameBusy, setRenameBusy] = useState(false);

  // Move modal
  const [moveOpen, setMoveOpen] = useState(false);
  const [moveBusy, setMoveBusy] = useState(false);
  const [moveQuery, setMoveQuery] = useState("");
  const [moveTargetId, setMoveTargetId] = useState<string | null>(null);

  const inactiveSet = useMemo(() => new Set(inactiveIds.map(String)), [inactiveIds]);

  const loadTree = useCallback(async () => {
    setIsLoading(true);
    setErrorText("");

    try {
      const data = await getOrgUnitsTree({
        include_inactive: true,
        org_group_id: orgScope.org_group_id ?? null,
      });

      setNodes(mapApiTreeNodesToUi(data.items));
      setInactiveIds(data.inactive_ids);
    } catch (e) {
      setErrorText(mapApiErrorToMessage(e));
      setNodes([]);
      setInactiveIds([]);
    } finally {
      setIsLoading(false);
    }
  }, [orgScope.org_group_id]);

  useEffect(() => {
    setNodes([]);
    setInactiveIds([]);
    setSelectedId(null);
    void loadTree();
  }, [loadTree]);

  const handleSelect = (id: string) => setSelectedId(id);
  const selectedFilterId = orgScope.org_unit_id ? String(orgScope.org_unit_id) : "";
  const listRows = useMemo(() => flattenListRows(nodes), [nodes]);
  const filteredRows = useMemo(() => {
    const query = searchQuery.trim().toLocaleLowerCase("ru").replaceAll("ё", "е");
    return listRows.filter(({ node }) => {
      if (selectedFilterId && String(node.id) !== selectedFilterId) return false;
      if (!showInactive && !selectedFilterId && inactiveSet.has(String(node.id))) return false;
      return !query || nodeSearchText(node).toLocaleLowerCase("ru").replaceAll("ё", "е").includes(query);
    });
  }, [listRows, selectedFilterId, showInactive, inactiveSet, searchQuery]);

  function updateUnitFilter(id: string) {
    const params = new URLSearchParams(sp.toString());
    if (id) params.set("org_unit_id", id);
    else params.delete("org_unit_id");
    setSearchQuery("");
    setSelectedId(null);
    const query = params.toString();
    router.replace(query ? `/directory/org-units?${query}` : "/directory/org-units");
  }

  const selectedNode = useMemo(() => (selectedId ? findNodeById(nodes, selectedId) : null), [nodes, selectedId]);
  const parentId = useMemo(() => (selectedId ? findParentId(nodes, selectedId) : null), [nodes, selectedId]);
  const parentNode = useMemo(() => (parentId ? findNodeById(nodes, parentId) : null), [nodes, parentId]);

  const children = selectedNode?.children ?? [];
  const isInactive = selectedId ? inactiveSet.has(String(selectedId)) : false;

  // if selected disappears after reload — reset
  useEffect(() => {
    if (!selectedId) return;
    const exists = findNodeById(nodes, selectedId);
    if (!exists) setSelectedId(null);
  }, [nodes, selectedId]);

  // ---------------------------
  // Rename
  // ---------------------------
  const openRename = useCallback(
    (id: string) => {
      const n = findNodeById(nodes, id);
      if (!n) return;
      setSelectedId(String(id));
      setRenameValue(n.title || "");
      setRenameOpen(true);
      setErrorText("");
    },
    [nodes]
  );

  const closeRename = useCallback(() => {
    if (renameBusy) return;
    setRenameOpen(false);
    setRenameValue("");
  }, [renameBusy]);

  const submitRename = useCallback(async () => {
    if (!selectedNode) return;

    const nextName = renameValue.trim();
    if (!nextName) return;

    if ((selectedNode.title || "").trim() === nextName) {
      closeRename();
      return;
    }

    setRenameBusy(true);
    setErrorText("");

    try {
      await renameOrgUnit(selectedNode.id, { name: nextName });
      closeRename();
      await loadTree();
    } catch (e) {
      setErrorText(mapApiErrorToMessage(e));
    } finally {
      setRenameBusy(false);
    }
  }, [closeRename, loadTree, renameValue, selectedNode]);

  // ---------------------------
  // Move
  // ---------------------------
  const openMove = useCallback(
    (id: string) => {
      const n = findNodeById(nodes, id);
      if (!n) return;

      const curParentId = findParentId(nodes, String(id));
      setSelectedId(String(id));
      setMoveTargetId(curParentId);
      setMoveQuery("");
      setMoveOpen(true);
      setErrorText("");
    },
    [nodes]
  );

  const closeMove = useCallback(() => {
    if (moveBusy) return;
    setMoveOpen(false);
    setMoveQuery("");
    setMoveTargetId(null);
  }, [moveBusy]);

  const moveCandidates = useMemo(() => {
    if (!selectedNode) return [];
    const flat = flattenNodes(nodes);

    const selected = String(selectedNode.id);
    const disallow = new Set<string>();
    disallow.add(selected);

    const stack: TreeNode[] = [...(selectedNode.children ?? [])];
    while (stack.length) {
      const n = stack.pop()!;
      disallow.add(String(n.id));
      for (const ch of n.children ?? []) stack.push(ch);
    }

    let list = flat.filter((x) => !disallow.has(String(x.id)));
    list = list.filter((x) => !inactiveSet.has(String(x.id)));

    const q = (moveQuery || "").trim().toLowerCase();
    if (q) {
      list = list.filter((x) => {
        const t = (x.title || "").toLowerCase();
        const id = String(x.id).toLowerCase();
        return t.includes(q) || id.includes(q);
      });
    }

    list.sort((a, b) => (a.title || "").localeCompare(b.title || "", "ru", { sensitivity: "base" }));
    return list;
  }, [nodes, selectedNode, moveQuery, inactiveSet]);

  const submitMove = useCallback(async () => {
    if (!selectedNode) return;

    const currentParentId = findParentId(nodes, String(selectedNode.id));
    const nextParentId = moveTargetId;

    if ((currentParentId ?? null) === (nextParentId ?? null)) {
      closeMove();
      return;
    }

    setMoveBusy(true);
    setErrorText("");

    try {
      await moveOrgUnit(selectedNode.id, {
        parent_unit_id: nextParentId ? Number(nextParentId) : null,
      });
      closeMove();
      await loadTree();
    } catch (e) {
      setErrorText(mapApiErrorToMessage(e));
    } finally {
      setMoveBusy(false);
    }
  }, [closeMove, loadTree, moveTargetId, nodes, selectedNode]);

  // ---------------------------
  // Create and activation actions remain available from the selected card.
  // ---------------------------
  const handleCreateChild = useCallback(
    async (parentId: string, name: string) => {
      const pid = String(parentId);
      const nm = String(name ?? "").trim();
      if (!pid || !nm) return;

      setErrorText("");
      try {
        await createOrgUnit({
          name: nm,
          parent_unit_id: Number(pid),
          is_active: true,
        });

        await loadTree();

      } catch (e) {
        setErrorText(mapApiErrorToMessage(e));
        throw e;
      }
    },
    [loadTree]
  );

  const handleToggleActive = useCallback(
    async (id: string, makeActive: boolean) => {
      const sid = String(id);
      if (!sid) return;

      setErrorText("");
      try {
        if (makeActive) {
          if (!inactiveSet.has(sid)) return;
          await activateOrgUnit(sid);
        } else {
          if (inactiveSet.has(sid)) return;
          await deactivateOrgUnit(sid);
        }
        await loadTree();
      } catch (e) {
        setErrorText(mapApiErrorToMessage(e));
        throw e;
      }
    },
    [inactiveSet, loadTree]
  );

  // ---------------------------
  // Keyboard in modals (rename/move)
  // ---------------------------
  useEffect(() => {
    if (!renameOpen && !moveOpen) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        if (renameOpen) closeRename();
        if (moveOpen) closeMove();
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (renameOpen) void submitRename();
        if (moveOpen) void submitMove();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [renameOpen, moveOpen, closeRename, closeMove, submitRename, submitMove]);

  return (
    <div className="mx-auto w-full max-w-[1440px] px-4 py-3">
      <div className="rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        <div className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <h1 className="text-xl font-semibold">Отделения</h1>
        </div>
        <div className="space-y-4 p-4">
          <div className="flex flex-wrap items-end gap-3 rounded-xl border border-zinc-200 p-3 dark:border-zinc-800">
            <OrgScopeFilter basePath="/directory/org-units" className="min-w-[210px] flex-1" resetParamsOnChange={["org_unit_id"]} />
            <div className="min-w-[210px] flex-1 text-sm font-medium text-zinc-800 dark:text-zinc-200">
              <label htmlFor="org-unit-filter">Отделение</label>
              <select id="org-unit-filter" value={selectedFilterId} disabled={isLoading}
                onChange={(event) => updateUnitFilter(event.target.value)}
                className="mt-1 w-full rounded-md border border-zinc-200 bg-zinc-100 px-3 py-2 text-sm dark:border-zinc-800 dark:bg-zinc-900">
                <option value="">Все</option>
                {listRows.map(({ node }) => <option key={node.id} value={node.id}>{node.title} (ID {node.id})</option>)}
              </select>
            </div>
            <label className="min-w-[240px] flex-[2] text-sm font-medium text-zinc-800 dark:text-zinc-200">
              Поиск по названию, коду или ID
              <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Поиск по названию, коду или ID"
                className="mt-1 w-full rounded-md border border-zinc-200 bg-zinc-100 px-3 py-2 text-sm dark:border-zinc-800 dark:bg-zinc-900" />
            </label>
            <label className="flex items-center gap-2 pb-2 text-sm text-zinc-700 dark:text-zinc-300">
              <input type="checkbox" checked={showInactive} onChange={(event) => setShowInactive(event.target.checked)} />
              Показывать неактивные
            </label>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">Всего: {filteredRows.length}</p>
            <div className="flex items-center gap-2">
              <ExportExcelButton filename="Отделения.xlsx" disabled={isLoading || !!errorText}
                load={async () => ({
                  headers: ["ID", "Название", "Код", "Родитель", "Статус"],
                  rows: filteredRows.map(({ node, parentTitle }) => [node.id, node.title, node.code ?? null,
                    parentTitle, inactiveSet.has(String(node.id)) ? "Неактивно" : "Активно"]),
                })} />
              <button type="button" onClick={() => void loadTree()} disabled={isLoading}
                className="rounded-lg border border-zinc-200 px-3 py-2 text-sm hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-800 dark:hover:bg-zinc-900">
                Обновить
              </button>
            </div>
          </div>

          {errorText ? <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/55 dark:bg-red-950/35 dark:text-red-300">Ошибка: {errorText}</div> : null}

          <div className="flex min-w-0 flex-col gap-4 lg:flex-row">
            <div className="min-w-0 flex-1 overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
              <table className="w-full text-sm" data-testid="org-units-list">
                <thead className="bg-zinc-50 text-left dark:bg-zinc-900"><tr>
                  <th className="px-3 py-2 font-semibold">ID</th>
                  <th className="px-3 py-2 font-semibold">Отделение</th>
                  <th className="px-3 py-2 font-semibold">Код</th>
                  <th className="px-3 py-2 font-semibold">Родитель</th>
                  <th className="px-3 py-2 font-semibold">Статус</th>
                </tr></thead>
                <tbody>
                  {filteredRows.map(({ node, parentTitle }) => <tr key={node.id} data-testid="org-unit-row"
                    tabIndex={0} aria-selected={selectedId === String(node.id)}
                    onClick={() => handleSelect(String(node.id))}
                    onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); handleSelect(String(node.id)); } }}
                    className="cursor-pointer border-t border-zinc-200 hover:bg-zinc-50 focus:bg-zinc-50 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-zinc-800 dark:hover:bg-zinc-900 dark:focus:bg-zinc-900">
                    <td className="px-3 py-2">{node.id}</td>
                    <td className="px-3 py-2 font-medium">{node.title}</td>
                    <td className="px-3 py-2">{node.code || "—"}</td>
                    <td className="px-3 py-2">{parentTitle || "—"}</td>
                    <td className="px-3 py-2">{inactiveSet.has(String(node.id)) ? "Неактивно" : "Активно"}</td>
                  </tr>)}
                  {!isLoading && filteredRows.length === 0 ? <tr><td colSpan={5} className="px-3 py-5 text-center text-zinc-500">Отделения не найдены.</td></tr> : null}
                  {isLoading ? <tr><td colSpan={5} className="px-3 py-5 text-center text-zinc-500">Загрузка…</td></tr> : null}
                </tbody>
              </table>
            </div>

            {selectedNode ? <div className="min-w-0 rounded-xl border border-zinc-200 bg-white p-4 text-gray-900 dark:border-zinc-800 dark:bg-zinc-950 lg:w-[440px] lg:shrink-0">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="text-sm text-gray-800">Карточка подразделения</div>
              {selectedNode ? (
                <div className="mt-2">
                  <div className="text-xl font-medium leading-tight text-gray-900">{selectedNode.title}</div>
                  <div className="mt-1 text-sm">
                    <span className="text-gray-800">Статус: </span>
                    <span className={isInactive ? "text-rose-700" : "text-emerald-700"}>
                      {isInactive ? "неактивно" : "активно"}
                    </span>
                  </div>
                </div>
              ) : null}
            </div>

            {selectedNode ? (
              <div className="flex flex-wrap items-center gap-2">
                {canManage ? <>
                <button type="button" onClick={() => { setCreateName(""); setCreateError(""); setCreateOpen(true); }}
                  className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50">Добавить дочерний</button>
                <button
                  type="button"
                  className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                  onClick={() => openRename(String(selectedNode.id))}
                  disabled={renameBusy || moveBusy}
                >
                  Переименовать
                </button>

                <button
                  type="button"
                  className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                  onClick={() => openMove(String(selectedNode.id))}
                  disabled={renameBusy || moveBusy || isInactive}
                  title={isInactive ? "Нельзя перемещать неактивное подразделение" : "Переместить"}
                >
                  Переместить
                </button>

                {isInactive ? (
                  <button
                    type="button"
                    className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                    onClick={() => void handleToggleActive(String(selectedNode.id), true)}
                    disabled={renameBusy || moveBusy || isLoading}
                    title="Активировать"
                  >
                    Активировать
                  </button>
                ) : (
                  <button
                    type="button"
                    className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                    onClick={() => void handleToggleActive(String(selectedNode.id), false)}
                    disabled={renameBusy || moveBusy || isLoading}
                    title="Деактивировать"
                  >
                    Деактивировать
                  </button>
                )}
                </> : null}
                <button type="button" onClick={() => setSelectedId(null)}
                  className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50">Закрыть</button>
              </div>
            ) : null}
          </div>

          {selectedNode ? (
            <>
              <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="rounded-xl border p-4">
                  <div className="text-xs text-gray-800">ID</div>
                  <div className="mt-1 text-sm font-medium text-gray-900">{selectedNode.id}</div>
                </div>

                <div className="rounded-xl border p-4">
                  <div className="text-xs text-gray-800">Тип</div>
                  <div className="mt-1 text-sm font-medium text-gray-900">{selectedNode.type}</div>
                </div>

                <div className="rounded-xl border p-4 md:col-span-2">
                  <div className="text-xs text-gray-800">Родитель</div>

                  {parentNode ? (
                    <button
                      type="button"
                      onClick={() => handleSelect(String(parentNode.id))}
                      className={[
                        "mt-1 w-full rounded-lg px-2 py-2 text-left text-sm font-medium text-gray-900",
                        "hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2",
                      ].join(" ")}
                      title="Перейти к родительскому подразделению"
                    >
                      <span className="block truncate">
                        {parentNode.title} <span className="text-gray-600">({parentNode.id})</span>
                      </span>
                    </button>
                  ) : (
                    <div className="mt-1 text-sm font-medium text-gray-800">Нет (корневой узел)</div>
                  )}
                </div>

                <div className="rounded-xl border p-4">
                  <div className="text-xs text-gray-800">Дочерних подразделений</div>
                  <div className="mt-1 text-sm font-medium text-gray-900">{children.length}</div>
                </div>
              </div>

              <div className="mt-6">
                <div className="text-sm font-medium text-gray-900">Дочерние подразделения</div>

                {children.length === 0 ? (
                  <div className="mt-2 rounded-xl border px-4 py-3 text-sm text-gray-800">Нет дочерних подразделений.</div>
                ) : (
                  <div className="mt-2 overflow-hidden rounded-xl border">
                    <div className="grid grid-cols-12 border-b bg-gray-50 px-4 py-2 text-xs text-gray-800">
                      <div className="col-span-2">ID</div>
                      <div className="col-span-8">Название</div>
                      <div className="col-span-2 text-right">Статус</div>
                    </div>

                    <div className="divide-y">
                      {children
                        .slice()
                        .sort((a, b) => (a.title || "").localeCompare(b.title || "", "ru", { sensitivity: "base" }))
                        .map((ch) => {
                          const chInactive = inactiveSet.has(String(ch.id));
                          return (
                            <button
                              key={ch.id}
                              type="button"
                              className="grid w-full grid-cols-12 px-4 py-3 text-left text-sm hover:bg-gray-50"
                              onClick={() => handleSelect(String(ch.id))}
                              title="Открыть карточку"
                            >
                              <div className="col-span-2 text-gray-800">{ch.id}</div>
                              <div className="col-span-8 truncate">
                                <span className={chInactive ? "text-gray-700" : "text-gray-900"}>{ch.title}</span>
                              </div>
                              <div className="col-span-2 text-right">
                                <span className={chInactive ? "text-rose-700" : "text-emerald-700"}>
                                  {chInactive ? "неактивно" : "активно"}
                                </span>
                              </div>
                            </button>
                          );
                        })}
                    </div>
                  </div>
                )}
              </div>
            </>
          ) : null}
            </div> : null}
          </div>
        </div>
      </div>

      {createOpen && selectedNode ? <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 dark:bg-black/55">
        <form className="w-full max-w-[520px] rounded-2xl border bg-white p-4 shadow-lg dark:bg-zinc-950"
          onSubmit={async (event) => {
            event.preventDefault();
            if (!createName.trim()) { setCreateError("Название обязательно."); return; }
            setCreateBusy(true);
            setCreateError("");
            try {
              await handleCreateChild(String(selectedNode.id), createName);
              setCreateOpen(false);
            } catch (error) {
              setCreateError(mapApiErrorToMessage(error));
            } finally {
              setCreateBusy(false);
            }
          }}>
          <h2 className="text-sm font-medium">Добавить дочернее подразделение</h2>
          <p className="mt-1 text-xs text-zinc-600">Родитель: {selectedNode.title}</p>
          <label className="mt-3 block text-sm">Название
            <input value={createName} onChange={(event) => setCreateName(event.target.value)} autoFocus
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm" disabled={createBusy} />
          </label>
          {createError ? <p role="alert" className="mt-2 text-sm text-red-700">{createError}</p> : null}
          <div className="mt-4 flex justify-end gap-2">
            <button type="button" onClick={() => setCreateOpen(false)} disabled={createBusy} className="rounded-lg border px-3 py-2 text-sm">Отмена</button>
            <button type="submit" disabled={createBusy || !createName.trim()} className="rounded-lg border bg-black px-3 py-2 text-sm text-white disabled:opacity-50">Создать</button>
          </div>
        </form>
      </div> : null}

      {/* Rename modal */}
      {renameOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 dark:bg-black/55 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) closeRename();
          }}
        >
          <div className="w-full max-w-[520px] rounded-2xl border bg-white dark:bg-zinc-950 p-4 shadow-lg">
            <div className="text-sm font-medium text-gray-900">Переименовать подразделение</div>

            <input
              className="mt-3 w-full rounded-lg border px-3 py-2 text-sm text-gray-900"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              disabled={renameBusy}
              autoFocus
            />

            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                onClick={closeRename}
                disabled={renameBusy}
              >
                Отмена
              </button>
              <button
                type="button"
                className="rounded-lg border bg-black px-3 py-2 text-sm text-white disabled:opacity-50"
                onClick={() => void submitRename()}
                disabled={renameBusy || !renameValue.trim()}
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {/* Move modal */}
      {moveOpen && selectedNode ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 dark:bg-black/55 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) closeMove();
          }}
        >
          <div className="w-full max-w-[720px] rounded-2xl border bg-white dark:bg-zinc-950 p-4 shadow-lg">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-gray-900">Переместить подразделение</div>
                <div className="mt-1 text-sm text-gray-700">
                  <span className="font-medium text-gray-900">{selectedNode.title}</span>{" "}
                  <span className="text-gray-500">({String(selectedNode.id)})</span>
                </div>
              </div>
              <button
                type="button"
                className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                onClick={closeMove}
                disabled={moveBusy}
                title="Закрыть"
              >
                Закрыть
              </button>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="rounded-xl border p-3">
                <div className="text-xs font-medium text-gray-800">Поиск родителя</div>
                <input
                  className="mt-2 w-full rounded-lg border px-3 py-2 text-sm text-gray-900 placeholder:text-gray-500"
                  value={moveQuery}
                  onChange={(e) => setMoveQuery(e.target.value)}
                  placeholder="Введите часть названия или ID…"
                  disabled={moveBusy}
                  autoFocus
                />
                <div className="mt-2 text-xs text-gray-600">
                  Доступно вариантов: <span className="font-medium text-gray-900">{moveCandidates.length}</span>
                </div>
              </div>

              <div className="rounded-xl border p-3">
                <div className="text-xs font-medium text-gray-800">Новый родитель</div>
                <select
                  className="mt-2 w-full rounded-lg border px-3 py-2 text-sm text-gray-900"
                  value={moveTargetId ?? ""}
                  onChange={(e) => setMoveTargetId(e.target.value ? e.target.value : null)}
                  disabled={moveBusy}
                >
                  <option value="">(сделать корневым)</option>
                  {moveCandidates.map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.title} ({x.id})
                    </option>
                  ))}
                </select>

                <div className="mt-2 text-xs text-gray-600">
                  Текущий родитель:{" "}
                  <span className="font-medium text-gray-900">
                    {parentNode ? `${parentNode.title} (${parentNode.id})` : "нет"}
                  </span>
                </div>
              </div>
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                onClick={closeMove}
                disabled={moveBusy}
              >
                Отмена
              </button>
              <button
                type="button"
                className="rounded-lg border bg-black px-3 py-2 text-sm text-white disabled:opacity-50"
                onClick={() => void submitMove()}
                disabled={moveBusy}
              >
                Переместить
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
