// FILE: corpsite-ui/app/directory/org-units/page.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import OrgUnitsTree, { type TreeNode, type TreeAction } from "./_components/OrgUnitsTree";
import { getOrgUnitsTree, mapApiErrorToMessage, renameOrgUnit } from "./_lib/api.client";

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

  const inactiveSet = useMemo(() => new Set(inactiveIds.map(String)), [inactiveIds]);

  const loadTree = useCallback(async () => {
    setIsLoading(true);
    setErrorText("");

    try {
      const data = await getOrgUnitsTree({ status: "all" });

      setNodes(Array.isArray(data.items) ? data.items : []);
      // types.ts уже описывает inactive_ids, поэтому каст к any не нужен
      setInactiveIds(Array.isArray(data.inactive_ids) ? data.inactive_ids : []);

      // Важно: не затирать раскрытие пользователя при каждом refresh.
      // Раскроем root_id только при первом заходе/когда раскрытия еще нет.
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

  // Если после обновления данных выбранный узел исчез (например, права/фильтр/удаление) — сбросим selection.
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

    // UX: если имя не изменилось — просто закрыть окно
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

  // Enter/Escape в модалке
  useEffect(() => {
    if (!renameOpen) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closeRename();
      }
      if (e.key === "Enter") {
        // чтобы Enter в инпуте работал как "Сохранить"
        e.preventDefault();
        void submitRename();
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [renameOpen, closeRename, submitRename]);

  return (
    <div className="h-[calc(100vh-64px)] w-full p-4">
      <div className="flex h-full w-full gap-4">
        {/* LEFT */}
        <div className="flex w-[420px] shrink-0 flex-col">
          <div className="rounded-lg border border-white/30
            px-3 py-1 text-xs
            text-white
            hover:bg-white hover:text-black
            transition-colors
            disabled:opacity-50">
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
              // B3.1: только rename, остальное read-only
              can={{ add: false, rename: true, move: false, deactivate: false }}
              onSelect={handleSelect}
              onToggle={handleToggle}
              onAction={(id: string, action: TreeAction) => {
                if (action === "rename") openRename(String(id));
              }}
              onSearch={setSearchQuery}
              onResetExpand={handleResetExpand}
              headerTitle="Подразделения"
            />
          </div>
        </div>

        {/* RIGHT */}
        <div className="min-h-0 flex-1 overflow-auto rounded-2xl border bg-white p-6">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm text-gray-500">Карточка подразделения</div>
              {selectedNode ? (
                <div className="mt-2">
                  <div className="text-xl font-medium leading-tight">{selectedNode.title}</div>
                  <div className="mt-1 text-sm text-gray-500">
                    {isInactive ? "Статус: неактивно" : "Статус: активно"}
                  </div>
                </div>
              ) : (
                <div className="mt-2 text-sm text-gray-500">Выберите подразделение в дереве слева.</div>
              )}
            </div>

            {selectedNode ? (
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
                  onClick={() => openRename(String(selectedNode.id))}
                  disabled={renameBusy}
                >
                  Переименовать
                </button>

                <button
                  type="button"
                  className="cursor-not-allowed rounded-lg border px-3 py-2 text-sm opacity-50"
                  disabled
                >
                  Переместить
                </button>

                <button
                  type="button"
                  className="cursor-not-allowed rounded-lg border px-3 py-2 text-sm opacity-50"
                  disabled
                >
                  Добавить секцию
                </button>
              </div>
            ) : null}
          </div>

          {selectedNode ? (
            <>
              <div className="mt-6 grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="rounded-xl border p-4">
                  <div className="text-xs text-gray-500">ID</div>
                  <div className="mt-1 text-sm font-medium">{selectedNode.id}</div>
                </div>

                <div className="rounded-xl border p-4">
                  <div className="text-xs text-gray-500">Тип</div>
                  <div className="mt-1 text-sm font-medium">{selectedNode.type}</div>
                </div>

                <div className="rounded-xl border p-4 md:col-span-2">
                  <div className="text-xs text-gray-500">Родитель</div>

                  {parentNode ? (
                    <button
                      type="button"
                      onClick={() => handleSelect(String(parentNode.id))}
                      className={[
                        "mt-1 w-full rounded-lg px-2 py-2 text-left text-sm font-medium",
                        "hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2",
                      ].join(" ")}
                      title="Перейти к родительскому подразделению"
                    >
                      <span className="block truncate">
                        {parentNode.title} <span className="text-gray-400">({parentNode.id})</span>
                      </span>
                    </button>
                  ) : (
                    <div className="mt-1 text-sm font-medium text-gray-500">Нет (корневой узел)</div>
                  )}
                </div>

                <div className="rounded-xl border p-4">
                  <div className="text-xs text-gray-500">Дочерних подразделений</div>
                  <div className="mt-1 text-sm font-medium">{children.length}</div>
                </div>
              </div>

              <div className="mt-6">
                <div className="text-sm font-medium">Дочерние подразделения</div>

                {children.length === 0 ? (
                  <div className="mt-2 rounded-xl border px-4 py-3 text-sm text-gray-600">
                    Нет дочерних подразделений.
                  </div>
                ) : (
                  <div className="mt-2 overflow-hidden rounded-xl border">
                    <div className="grid grid-cols-12 border-b bg-gray-50 px-4 py-2 text-xs text-gray-600">
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
                              <div className="col-span-2 text-gray-500">{ch.id}</div>
                              <div className="col-span-8 truncate">
                                <span className={chInactive ? "text-gray-500" : "text-gray-900"}>{ch.title}</span>
                              </div>
                              <div className="col-span-2 text-right text-gray-500">
                                {chInactive ? "неактивно" : "активно"}
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
            // клик по подложке закрывает окно (но не во время сохранения)
            if (e.target === e.currentTarget) closeRename();
          }}
        >
          <div className="w-full max-w-[520px] rounded-2xl border bg-white p-4 shadow-lg">
            <div className="text-sm font-medium">Переименовать подразделение</div>

            <input
              className="mt-3 w-full rounded-lg border px-3 py-2 text-sm"
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
    </div>
  );
}
