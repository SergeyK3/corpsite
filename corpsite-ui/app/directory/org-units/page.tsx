// FILE: corpsite-ui/app/directory/org-units/page.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import OrgUnitsTree, { type TreeNode, type TreeAction } from "./_components/OrgUnitsTree";
import { getOrgUnitsTree, mapApiErrorToMessage, renameOrgUnit, moveOrgUnit } from "./_lib/api.client";

function findNodeById(nodes: TreeNode[], id: string): TreeNode | null {
  const target = String(id);
  const stack: TreeNode[] = [...nodes];
  while (stack.length) {
    const n = stack.pop()!;
    if (String(n.id) === target) return n;
    if (n.children && n.children.length) {
      for (const ch of n.children) stack.push(ch);
    }
  }
  return null;
}

function findParentId(nodes: TreeNode[], id: string): string | null {
  const target = String(id);
  const stack: Array<{ node: TreeNode; parentId: string | null }> = nodes.map((n) => ({
    node: n,
    parentId: null,
  }));

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

export default function OrgUnitsPage() {
  const [nodes, setNodes] = useState<TreeNode[]>([]);
  const [inactiveIds, setInactiveIds] = useState<string[]>([]);
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");

  // B3.1 Rename UI
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [renameBusy, setRenameBusy] = useState(false);

  // B3.2 Move UI
  const [moveOpen, setMoveOpen] = useState(false);
  const [moveBusy, setMoveBusy] = useState(false);
  const [moveQuery, setMoveQuery] = useState("");
  const [moveTargetId, setMoveTargetId] = useState<string | null>(null);

  const inactiveSet = useMemo(() => new Set(inactiveIds.map(String)), [inactiveIds]);

  const loadTree = useCallback(async () => {
    setIsLoading(true);
    setErrorText("");

    try {
      const data = await getOrgUnitsTree({ status: "all" });

      setNodes(Array.isArray(data.items) ? data.items : []);
      setInactiveIds(Array.isArray(data.inactive_ids) ? data.inactive_ids : []);

      if (data.root_id != null) {
        setExpandedIds((prev) => (prev.length ? prev : [String(data.root_id)]));
      }
    } catch (e) {
      setErrorText(mapApiErrorToMessage(e));
      setNodes([]);
      setInactiveIds([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTree();
  }, [loadTree]);

  const handleToggle = (id: string, open: boolean) => {
    setExpandedIds((prev) => {
      if (open) {
        if (prev.includes(id)) return prev;
        return [...prev, id];
      }
      return prev.filter((x) => x !== id);
    });
  };

  const handleSelect = (id: string) => {
    setSelectedId(id);
  };

  const handleResetExpand = () => {
    setExpandedIds([]);
  };

  const selectedNode = useMemo(() => {
    if (!selectedId) return null;
    return findNodeById(nodes, selectedId);
  }, [nodes, selectedId]);

  const parentId = useMemo(() => {
    if (!selectedId) return null;
    return findParentId(nodes, selectedId);
  }, [nodes, selectedId]);

  const parentNode = useMemo(() => {
    if (!parentId) return null;
    return findNodeById(nodes, parentId);
  }, [nodes, parentId]);

  const children = selectedNode?.children ?? [];
  const isInactive = selectedId ? inactiveSet.has(String(selectedId)) : false;

  useEffect(() => {
    if (!selectedId) return;
    const exists = findNodeById(nodes, selectedId);
    if (!exists) setSelectedId(null);
  }, [nodes, selectedId]);

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
      await renameOrgUnit({ unit_id: String(selectedNode.id), name: nextName });
      closeRename();
      await loadTree();
    } catch (e) {
      setErrorText(mapApiErrorToMessage(e));
    } finally {
      setRenameBusy(false);
    }
  }, [closeRename, loadTree, renameValue, selectedNode]);

  // Move: open/close
  const openMove = useCallback(
    (id: string) => {
      const n = findNodeById(nodes, id);
      if (!n) return;

      const curParentId = findParentId(nodes, String(id));

      setSelectedId(String(id));
      setMoveTargetId(curParentId); // по умолчанию — текущий родитель (можно сменить)
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
    // нельзя перемещать в самого себя или в своих потомков
    const stack: TreeNode[] = [...(selectedNode.children ?? [])];
    disallow.add(selected);
    while (stack.length) {
      const n = stack.pop()!;
      disallow.add(String(n.id));
      for (const ch of n.children ?? []) stack.push(ch);
    }

    let list = flat.filter((x) => !disallow.has(String(x.id)));

    // опционально: не предлагать inactive как родителя
    list = list.filter((x) => !inactiveSet.has(String(x.id)));

    const q = (moveQuery || "").trim().toLowerCase();
    if (q) {
      list = list.filter((x) => {
        const t = (x.title || "").toLowerCase();
        const id = String(x.id).toLowerCase();
        return t.includes(q) || id.includes(q);
      });
    }

    // сорт: по title
    list.sort((a, b) => (a.title || "").localeCompare(b.title || "", "ru", { sensitivity: "base" }));
    return list;
  }, [nodes, selectedNode, moveQuery, inactiveSet]);

  const submitMove = useCallback(async () => {
    if (!selectedNode) return;

    const currentParentId = findParentId(nodes, String(selectedNode.id));
    const nextParentId = moveTargetId;

    // если не изменили — закрыть
    if ((currentParentId ?? null) === (nextParentId ?? null)) {
      closeMove();
      return;
    }

    setMoveBusy(true);
    setErrorText("");

    try {
      await moveOrgUnit({
        unit_id: String(selectedNode.id),
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

  // Enter/Escape в модалках
  useEffect(() => {
    if (!renameOpen && !moveOpen) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        if (renameOpen) closeRename();
        if (moveOpen) closeMove();
      }
      if (e.key === "Enter") {
        // В модалке перемещения Enter подтверждает, когда фокус не в select?
        // Здесь делаем: если открыто rename — submitRename, иначе move — submitMove.
        e.preventDefault();
        if (renameOpen) void submitRename();
        if (moveOpen) void submitMove();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [renameOpen, moveOpen, closeRename, closeMove, submitRename, submitMove]);

  return (
    <div className="h-[calc(100vh-64px)] w-full p-4">
      <div className="flex h-full w-full gap-4">
        {/* LEFT */}
        <div className="flex w-[420px] shrink-0 flex-col">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-medium">Оргструктура</div>
            <button
              type="button"
              className="rounded-lg border px-3 py-1 text-xs hover:bg-gray-50 disabled:opacity-50"
              onClick={() => void loadTree()}
              disabled={isLoading}
              title="Обновить"
            >
              Обновить
            </button>
          </div>

          {errorText ? (
            <div className="mb-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              <div className="font-medium">Ошибка</div>
              <div className="mt-1 whitespace-pre-wrap">{errorText}</div>
            </div>
          ) : null}

          {isLoading ? (
            <div className="mb-3 rounded-xl border bg-white p-3 text-sm text-gray-600">Загрузка…</div>
          ) : null}

          <div className="min-h-0 flex-1 overflow-auto">
            <OrgUnitsTree
              nodes={nodes}
              expandedIds={expandedIds}
              selectedId={selectedId}
              inactiveIds={inactiveIds}
              searchQuery={searchQuery}
              // на этом шаге: включаем move (UX), add/deactivate — позже
              can={{ add: false, rename: true, move: true, deactivate: false }}
              onSelect={handleSelect}
              onToggle={handleToggle}
              onAction={(id: string, action: TreeAction) => {
                if (action === "rename") openRename(String(id));
                if (action === "move") openMove(String(id));
              }}
              onSearch={setSearchQuery}
              onResetExpand={handleResetExpand}
              headerTitle="Подразделения"
            />
          </div>
        </div>

        {/* RIGHT */}
        <div className="min-h-0 flex-1 overflow-auto rounded-2xl border bg-white p-6 text-gray-900">
          <div className="flex items-start justify-between gap-4">
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
              ) : (
                <div className="mt-2 text-sm text-gray-800">Выберите подразделение в дереве слева.</div>
              )}
            </div>

            {selectedNode ? (
              <div className="flex shrink-0 items-center gap-2">
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

                <button type="button" className="cursor-not-allowed rounded-lg border px-3 py-2 text-sm opacity-50" disabled>
                  Добавить секцию
                </button>
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
        </div>
      </div>

      {/* Rename modal */}
      {renameOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) closeRename();
          }}
        >
          <div className="w-full max-w-[520px] rounded-2xl border bg-white p-4 shadow-lg">
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
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
          onMouseDown={(e) => {
            if (e.target === e.currentTarget) closeMove();
          }}
        >
          <div className="w-full max-w-[720px] rounded-2xl border bg-white p-4 shadow-lg">
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
