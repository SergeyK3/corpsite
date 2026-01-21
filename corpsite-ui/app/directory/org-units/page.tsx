// FILE: corpsite-ui/app/directory/org-units/page.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import OrgUnitsTree, { type TreeNode } from "./_components/OrgUnitsTree";
import { getOrgUnitsTree, mapApiErrorToMessage } from "./_lib/api.client";

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

  const inactiveSet = useMemo(() => new Set(inactiveIds.map(String)), [inactiveIds]);

  const loadTree = useCallback(async () => {
    setIsLoading(true);
    setErrorText("");

    try {
      const data = await getOrgUnitsTree({ status: "all" });

      setNodes(Array.isArray(data.items) ? data.items : []);
      setInactiveIds(Array.isArray((data as any).inactive_ids) ? (data as any).inactive_ids : []);

      if ((data as any).root_id != null) {
        setExpandedIds([String((data as any).root_id)]);
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
              <div className="font-medium">Ошибка загрузки дерева</div>
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
              // B1/B2: read-only
              can={{ add: false, rename: false, move: false, deactivate: false }}
              onSelect={handleSelect}
              onToggle={handleToggle}
              onAction={() => {
                /* read-only */
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
                  <div className="mt-1 text-sm text-gray-500">{isInactive ? "Статус: неактивно" : "Статус: активно"}</div>
                </div>
              ) : (
                <div className="mt-2 text-sm text-gray-500">Выберите подразделение в дереве слева.</div>
              )}
            </div>

            {/* B1/B2: read-only — кнопки действий отключены */}
            {selectedNode ? (
              <div className="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  className="cursor-not-allowed rounded-lg border px-3 py-2 text-sm opacity-50"
                  disabled
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
                  <div className="mt-2 rounded-xl border px-4 py-3 text-sm text-gray-600">Нет дочерних подразделений.</div>
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
                              <div className="col-span-2 text-right text-gray-500">{chInactive ? "неактивно" : "активно"}</div>
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
    </div>
  );
}
