// corpsite-ui/app/org-units/page.tsx
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import OrgUnitsTree, {
  type TreeNode,
  type TreeAction,
} from "./_components/OrgUnitsTree";

type OrgUnitsTreeResponse = {
  version: number;
  total: number;
  inactive_ids: string[];
  items: TreeNode[];
  root_id?: number | null;
};

function _apiBase(): string {
  const v = (process.env.NEXT_PUBLIC_API_BASE_URL || "").trim();
  return v || "http://127.0.0.1:8000";
}

function _devUserId(): string {
  const v = (process.env.NEXT_PUBLIC_DEV_X_USER_ID || "").trim();
  return v || "34";
}

export default function OrgUnitsPage() {
  const apiBase = useMemo(() => _apiBase(), []);
  const devUserId = useMemo(() => _devUserId(), []);

  const [nodes, setNodes] = useState<TreeNode[]>([]);
  const [inactiveIds, setInactiveIds] = useState<string[]>([]);
  const [expandedIds, setExpandedIds] = useState<string[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorText, setErrorText] = useState<string>("");

  const loadTree = useCallback(async () => {
    setIsLoading(true);
    setErrorText("");

    try {
      const url = `${apiBase}/directory/org-units/tree?include_inactive=true`;
      const res = await fetch(url, {
        method: "GET",
        headers: {
          "X-User-Id": devUserId,
        },
        cache: "no-store",
      });

      if (!res.ok) {
        const t = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status}: ${t || res.statusText}`);
      }

      const data = (await res.json()) as OrgUnitsTreeResponse;

      setNodes(Array.isArray(data.items) ? data.items : []);
      setInactiveIds(Array.isArray(data.inactive_ids) ? data.inactive_ids : []);

      if (data.root_id != null) {
        setExpandedIds([String(data.root_id)]);
      }
    } catch (e: any) {
      setErrorText(e?.message ? String(e.message) : "Failed to load org units tree.");
      setNodes([]);
      setInactiveIds([]);
    } finally {
      setIsLoading(false);
    }
  }, [apiBase, devUserId]);

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

  const handleAction = (id: string, action: TreeAction) => {
    // eslint-disable-next-line no-console
    console.log("org-units tree action:", { id, action });
  };

  const handleResetExpand = () => {
    setExpandedIds([]);
  };

  const selectedNodeLabel = useMemo(() => {
    if (!selectedId) return null;

    const stack: TreeNode[] = [...nodes];
    while (stack.length) {
      const n = stack.pop()!;
      if (String(n.id) === String(selectedId)) return n.title || selectedId;
      if (n.children && n.children.length) {
        for (const ch of n.children) stack.push(ch);
      }
    }
    return selectedId;
  }, [nodes, selectedId]);

  return (
    <div className="h-[calc(100vh-64px)] w-full p-4">
      <div className="flex h-full w-full gap-4">
        {/* LEFT: fixed width, own scroll */}
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
            <div className="mb-3 rounded-xl border bg-white p-3 text-sm text-gray-600">
              Загрузка…
            </div>
          ) : null}

          {/* Scroll area for tree */}
          <div className="min-h-0 flex-1 overflow-auto">
            <OrgUnitsTree
              nodes={nodes}
              expandedIds={expandedIds}
              selectedId={selectedId}
              inactiveIds={inactiveIds}
              searchQuery={searchQuery}
              can={{
                add: true,
                rename: true,
                move: true,
                deactivate: true,
              }}
              onSelect={handleSelect}
              onToggle={handleToggle}
              onAction={handleAction}
              onSearch={setSearchQuery}
              onResetExpand={handleResetExpand}
              headerTitle="Подразделения"
            />
          </div>
        </div>

        {/* RIGHT: flex-1, own scroll */}
        <div className="min-h-0 flex-1 overflow-auto rounded-2xl border bg-white p-6">
          <div className="text-sm text-gray-500">Выбранный узел</div>

          {selectedId ? (
            <>
              <div className="mt-2 text-lg font-medium">{selectedNodeLabel}</div>
              <div className="mt-2 text-sm text-gray-600">
                <div>
                  <span className="text-gray-500">ID:</span> {selectedId}
                </div>
                <div className="mt-3 text-gray-500">
                  Здесь следующим шагом будет карточка подразделения и управление (B2/B3).
                </div>
              </div>
            </>
          ) : (
            <div className="mt-2 text-sm text-gray-500">
              Выберите подразделение в дереве слева.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
