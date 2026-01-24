// FILE: corpsite-ui/app/directory/org-units/_components/OrgUnitsTree.tsx
"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

export type OrgUnitNodeType = "org" | "dept" | "unit";

export type TreeNode = {
  id: string;
  title: string;
  type: OrgUnitNodeType;
  children?: TreeNode[];
};

export type TreeCan = {
  add: boolean;
  rename: boolean;
  move: boolean;
  deactivate: boolean;
};

export type TreeAction = "add_child" | "rename" | "move" | "deactivate" | "activate";

export type OrgUnitsTreeProps = {
  nodes: TreeNode[];

  expandedIds: string[];
  selectedId: string | null;
  inactiveIds: string[];

  searchQuery: string;
  can: TreeCan;

  onSelect: (id: string) => void;
  onToggle: (id: string, open: boolean) => void;

  onAction: (id: string, action: TreeAction) => void;

  onCreateChild?: (parentId: string, name: string) => Promise<void> | void;
  onToggleActive?: (id: string, makeActive: boolean) => Promise<void> | void;

  onSearch: (q: string) => void;
  onResetExpand: () => void;

  className?: string;
  headerTitle?: string;
};

type FlatIndex = {
  byId: Map<string, TreeNode>;
  parentById: Map<string, string | null>;
  childrenById: Map<string, string[]>;
  rootIds: string[];
};

function buildIndex(nodes: TreeNode[]): FlatIndex {
  const byId = new Map<string, TreeNode>();
  const parentById = new Map<string, string | null>();
  const childrenById = new Map<string, string[]>();
  const rootIds: string[] = [];

  const walk = (arr: TreeNode[], parentId: string | null) => {
    for (const n of arr) {
      const id = String(n.id);
      byId.set(id, { ...n, id });
      parentById.set(id, parentId);
      if (parentId == null) rootIds.push(id);

      const childIds = (n.children ?? []).map((c) => String(c.id));
      childrenById.set(id, childIds);

      if (n.children && n.children.length > 0) {
        walk(
          n.children.map((c) => ({ ...c, id: String(c.id) })),
          id
        );
      }
    }
  };

  walk(nodes.map((n) => ({ ...n, id: String(n.id) })), null);
  return { byId, parentById, childrenById, rootIds };
}

function pathToRoot(parentById: Map<string, string | null>, id: string): string[] {
  const path: string[] = [];
  let cur: string | null | undefined = id;
  while (cur != null) {
    path.push(cur);
    cur = parentById.get(cur) ?? null;
  }
  return path;
}

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function TypeIcon({ type }: { type: OrgUnitNodeType }) {
  const glyph = type === "org" ? "🏢" : type === "dept" ? "🏬" : "📁";
  return (
    <span aria-hidden="true" className="mr-2 inline-flex w-5 justify-center opacity-80">
      {glyph}
    </span>
  );
}

function Chevron({ open, onClick, disabled }: { open: boolean; onClick: () => void; disabled: boolean }) {
  return (
    <button
      type="button"
      aria-label={open ? "Свернуть" : "Развернуть"}
      disabled={disabled}
      onClick={(e) => {
        e.stopPropagation();
        if (!disabled) onClick();
      }}
      className={[
        "mr-1 inline-flex h-6 w-6 items-center justify-center rounded",
        disabled ? "opacity-0 pointer-events-none" : "opacity-70 hover:opacity-100",
        "focus:outline-none focus:ring-2 focus:ring-offset-2",
      ].join(" ")}
    >
      <span aria-hidden="true" className="text-sm leading-none">
        {open ? "▼" : "▶"}
      </span>
    </button>
  );
}

function KebabButton({
  visible,
  enabled,
  onClick,
}: {
  visible: boolean;
  enabled: boolean;
  onClick: (e: React.MouseEvent) => void;
}) {
  return (
    <button
      type="button"
      aria-label="Действия"
      onClick={onClick}
      disabled={!enabled}
      className={[
        "ml-auto inline-flex h-8 w-8 items-center justify-center rounded",
        enabled
          ? visible
            ? "opacity-80 hover:opacity-100"
            : "opacity-0 pointer-events-none"
          : "opacity-0 pointer-events-none",
        "focus:outline-none focus:ring-2 focus:ring-offset-2",
      ].join(" ")}
    >
      <span aria-hidden="true" className="text-lg leading-none">
        ⋯
      </span>
    </button>
  );
}

function ContextMenu({
  anchorRect,
  onClose,
  onPick,
  can,
  isInactive,
}: {
  anchorRect: DOMRect;
  onClose: () => void;
  onPick: (action: TreeAction) => void;
  can: TreeCan;
  isInactive: boolean;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      const el = ref.current;
      if (!el) return;
      if (e.target instanceof Node && !el.contains(e.target)) onClose();
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onEsc);
    };
  }, [onClose]);

  const toggleItem = isInactive
    ? { key: "activate" as const, label: "Активировать", enabled: can.deactivate }
    : { key: "deactivate" as const, label: "Деактивировать", enabled: can.deactivate };

  const items: Array<{ key: TreeAction; label: string; enabled: boolean }> = [
    { key: "add_child", label: "Добавить дочерний", enabled: can.add },
    { key: "rename", label: "Переименовать", enabled: can.rename },
    { key: "move", label: "Переместить", enabled: can.move },
    toggleItem,
  ];

  const style: React.CSSProperties = {
    position: "fixed",
    top: Math.min(window.innerHeight - 10, anchorRect.bottom + 6),
    left: Math.min(window.innerWidth - 10, anchorRect.right - 240),
    width: 240,
    zIndex: 50,
  };

  return (
    <div ref={ref} style={style} className="rounded-xl border bg-white text-gray-900 shadow-lg">
      <div className="py-1">
        {items.slice(0, 3).map((it) => (
          <button
            key={it.key}
            type="button"
            disabled={!it.enabled}
            onClick={() => it.enabled && onPick(it.key)}
            className={[
              "w-full px-3 py-2 text-left text-sm",
              it.enabled ? "text-gray-900 hover:bg-gray-50" : "text-gray-400 cursor-not-allowed",
            ].join(" ")}
          >
            {it.label}
          </button>
        ))}
        <div className="my-1 border-t" />
        <button
          type="button"
          disabled={!items[3].enabled}
          onClick={() => items[3].enabled && onPick(items[3].key)}
          className={[
            "w-full px-3 py-2 text-left text-sm",
            items[3].enabled ? "text-gray-900 hover:bg-gray-50" : "text-gray-400 cursor-not-allowed",
          ].join(" ")}
        >
          {items[3].label}
        </button>
      </div>
    </div>
  );
}

function filterTreeForSearch(opts: {
  nodes: TreeNode[];
  q: string;
  inactiveSet: Set<string>;
  showInactive: boolean;
}): { nodes: TreeNode[]; matchIds: Set<string> } {
  const { nodes, q, inactiveSet, showInactive } = opts;
  const query = (q || "").trim();

  if (!query) {
    if (showInactive) return { nodes, matchIds: new Set() };

    const pruneInactive = (arr: TreeNode[]): TreeNode[] => {
      const out: TreeNode[] = [];
      for (const n of arr) {
        const ch = pruneInactive(n.children ?? []);
        const id = String(n.id);
        const isInactive = inactiveSet.has(id);

        if (isInactive && ch.length === 0) continue;

        out.push({ ...n, id, children: ch.length ? ch : [] });
      }
      return out;
    };

    return { nodes: pruneInactive(nodes), matchIds: new Set() };
  }

  let qRe: RegExp;
  try {
    qRe = new RegExp(escapeRegExp(query), "i");
  } catch {
    return { nodes, matchIds: new Set() };
  }

  const matchIds = new Set<string>();

  const prune = (n: TreeNode): TreeNode | null => {
    const id = String(n.id);
    const title = n.title || "";
    const titleMatch = qRe.test(title);
    if (titleMatch) matchIds.add(id);

    const childOut: TreeNode[] = [];
    for (const c of n.children ?? []) {
      const kept = prune(c);
      if (kept) childOut.push(kept);
    }

    const keep = titleMatch || childOut.length > 0;
    if (!keep) return null;

    const isInactive = inactiveSet.has(id);
    if (!showInactive) {
      if (isInactive && childOut.length === 0 && titleMatch) {
        return null;
      }
    }

    return { ...n, id, children: childOut };
  };

  const out: TreeNode[] = [];
  for (const n of nodes) {
    const kept = prune(n);
    if (kept) out.push(kept);
  }

  return { nodes: out, matchIds };
}

function Modal({
  open,
  title,
  children,
  onClose,
}: {
  open: boolean;
  title: string;
  children: React.ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;

    const onClick = (e: MouseEvent) => {
      const el = ref.current;
      if (!el) return;
      if (e.target instanceof Node && !el.contains(e.target)) onClose();
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/30 p-4">
      <div ref={ref} className="w-full max-w-lg rounded-2xl border bg-white shadow-xl">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <div className="text-sm font-medium">{title}</div>
          <button type="button" onClick={onClose} className="rounded-lg border px-2 py-1 text-sm hover:bg-gray-50">
            Закрыть
          </button>
        </div>
        <div className="px-4 py-4">{children}</div>
      </div>
    </div>
  );
}

export default function OrgUnitsTree(props: OrgUnitsTreeProps) {
  const {
    nodes,
    expandedIds,
    selectedId,
    inactiveIds,
    searchQuery,
    can,
    onSelect,
    onToggle,
    onAction,
    onCreateChild,
    onToggleActive,
    onSearch,
    onResetExpand,
    className,
    headerTitle = "Структура",
  } = props;

  const inactiveSet = useMemo(() => new Set(inactiveIds.map(String)), [inactiveIds]);
  const [showInactive, setShowInactive] = useState<boolean>(false);

  const fullIdx = useMemo(() => buildIndex(nodes), [nodes]);

  const { viewNodes, matchIds } = useMemo(() => {
    const r = filterTreeForSearch({
      nodes,
      q: searchQuery,
      inactiveSet,
      showInactive,
    });
    return { viewNodes: r.nodes, matchIds: r.matchIds };
  }, [nodes, searchQuery, inactiveSet, showInactive]);

  const viewIdx = useMemo(() => buildIndex(viewNodes), [viewNodes]);
  const expandedSnapshotRef = useRef<string[] | null>(null);

  useEffect(() => {
    const q = (searchQuery || "").trim();

    if (!q) {
      if (expandedSnapshotRef.current) {
        const snap = expandedSnapshotRef.current;
        expandedSnapshotRef.current = null;

        const cur = new Set(expandedIds);
        const target = new Set(snap);

        for (const id of cur) {
          if (!target.has(id)) onToggle(id, false);
        }
        for (const id of target) {
          if (!cur.has(id)) onToggle(id, true);
        }
      }
      return;
    }

    if (!expandedSnapshotRef.current) {
      expandedSnapshotRef.current = [...expandedIds];
    }

    let qRe: RegExp | null = null;
    try {
      qRe = new RegExp(escapeRegExp(q), "i");
    } catch {
      qRe = null;
    }
    if (!qRe) return;

    const needOpen = new Set<string>();
    for (const [id, node] of fullIdx.byId.entries()) {
      if (qRe.test(node.title || "")) {
        const path = pathToRoot(fullIdx.parentById, id);
        for (let i = 1; i < path.length; i++) needOpen.add(path[i]);
      }
    }

    const expandedNow = new Set(expandedIds);
    for (const id of needOpen) {
      if (!expandedNow.has(id)) onToggle(id, true);
    }
  }, [searchQuery, fullIdx.byId, fullIdx.parentById, expandedIds, onToggle]);

  useEffect(() => {
    const q = (searchQuery || "").trim();
    if (!q) return;

    const stack: string[] = [...viewIdx.rootIds].reverse();
    let firstMatchId: string | null = null;

    while (stack.length) {
      const id = stack.pop()!;
      if (matchIds.has(id)) {
        firstMatchId = id;
        break;
      }
      const ch = viewIdx.childrenById.get(id) ?? [];
      for (let i = ch.length - 1; i >= 0; i--) stack.push(ch[i]);
    }

    if (!firstMatchId) return;

    const t = window.setTimeout(() => {
      const el = document.querySelector<HTMLElement>(`[data-tree-node-id="${CSS.escape(firstMatchId!)}"]`);
      if (el) el.scrollIntoView({ block: "center" });
    }, 0);

    return () => window.clearTimeout(t);
  }, [searchQuery, viewIdx.rootIds, viewIdx.childrenById, matchIds]);

  const [menu, setMenu] = useState<{ nodeId: string; rect: DOMRect } | null>(null);

  useEffect(() => {
    setMenu(null);
  }, [selectedId, searchQuery, showInactive]);

  const q = (searchQuery || "").trim();
  const highlightRe = useMemo(() => {
    if (!q) return null;
    try {
      return new RegExp(escapeRegExp(q), "ig");
    } catch {
      return null;
    }
  }, [q]);

  const renderTitle = useCallback(
    (title: string) => {
      if (!highlightRe) return <span>{title}</span>;

      const parts: React.ReactNode[] = [];
      let lastIndex = 0;
      const s = title || "";

      for (const m of s.matchAll(highlightRe)) {
        const start = m.index ?? 0;
        const end = start + m[0].length;

        if (start > lastIndex) {
          parts.push(<span key={`t-${lastIndex}`}>{s.slice(lastIndex, start)}</span>);
        }
        parts.push(
          <mark key={`m-${start}`} className="rounded bg-yellow-200 px-1">
            {s.slice(start, end)}
          </mark>
        );
        lastIndex = end;
      }

      if (lastIndex < s.length) {
        parts.push(<span key={`t-${lastIndex}`}>{s.slice(lastIndex)}</span>);
      }

      return <span>{parts}</span>;
    },
    [highlightRe]
  );

  const sortChildren = useCallback(
    (ids: string[]) => {
      const enriched = ids
        .map((id) => ({ id, node: viewIdx.byId.get(id) }))
        .filter((x): x is { id: string; node: TreeNode } => !!x.node);

      enriched.sort((a, b) => {
        const aInactive = inactiveSet.has(a.id);
        const bInactive = inactiveSet.has(b.id);
        if (aInactive !== bInactive) return aInactive ? 1 : -1;
        return (a.node.title || "").localeCompare(b.node.title || "", "ru", { sensitivity: "base" });
      });

      return enriched.map((x) => x.id);
    },
    [inactiveSet, viewIdx.byId]
  );

  const expandedSet = useMemo(() => new Set(expandedIds), [expandedIds]);

  const hasAnyActions = useMemo(() => {
    return !!(can.add || can.rename || can.move || can.deactivate);
  }, [can.add, can.rename, can.move, can.deactivate]);

  const [createModal, setCreateModal] = useState<{ open: boolean; parentId: string | null }>({ open: false, parentId: null });
  const [createName, setCreateName] = useState<string>("");
  const [createBusy, setCreateBusy] = useState<boolean>(false);
  const [createErr, setCreateErr] = useState<string | null>(null);

  const openCreate = useCallback((parentId: string) => {
    setCreateErr(null);
    setCreateName("");
    setCreateModal({ open: true, parentId });
  }, []);

  const closeCreate = useCallback(() => {
    if (createBusy) return;
    setCreateModal({ open: false, parentId: null });
    setCreateErr(null);
  }, [createBusy]);

  const submitCreate = useCallback(async () => {
    if (!createModal.parentId) return;
    const name = (createName || "").trim();

    if (!name) {
      setCreateErr("Название обязательно.");
      return;
    }

    if (!onCreateChild) {
      onAction(createModal.parentId, "add_child");
      setCreateModal({ open: false, parentId: null });
      return;
    }

    setCreateBusy(true);
    setCreateErr(null);
    try {
      await onCreateChild(createModal.parentId, name);
      setCreateModal({ open: false, parentId: null });
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e ?? "Ошибка");
      setCreateErr(msg || "Ошибка");
    } finally {
      setCreateBusy(false);
    }
  }, [createModal.parentId, createName, onCreateChild, onAction]);

  const runToggleActive = useCallback(
    async (id: string, makeActive: boolean) => {
      if (!onToggleActive) {
        onAction(id, makeActive ? "activate" : "deactivate");
        return;
      }

      if (!makeActive) {
        const ok = window.confirm("Деактивировать подразделение? Оно исчезнет из списка активных.");
        if (!ok) return;
      }

      try {
        await onToggleActive(id, makeActive);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e ?? "Ошибка");
        window.alert(msg || "Ошибка");
      }
    },
    [onToggleActive, onAction]
  );

  const Row = ({ nodeId, depth }: { nodeId: string; depth: number }) => {
    const node = viewIdx.byId.get(nodeId);
    if (!node) return null;

    const childrenIdsRaw = viewIdx.childrenById.get(nodeId) ?? [];
    const childrenIds = sortChildren(childrenIdsRaw);

    const hasChildren = childrenIds.length > 0;

    const isOpen = expandedSet.has(nodeId);
    const isSelected = nodeId === selectedId;
    const isInactive = inactiveSet.has(nodeId);

    const [hover, setHover] = useState(false);

    return (
      <div>
        <div
          data-tree-node-id={nodeId}
          role="treeitem"
          aria-selected={isSelected}
          aria-expanded={hasChildren ? isOpen : undefined}
          tabIndex={0}
          onMouseEnter={() => setHover(true)}
          onMouseLeave={() => setHover(false)}
          onClick={() => onSelect(nodeId)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSelect(nodeId);

            if (e.key === "ArrowRight" && hasChildren && !isOpen) onToggle(nodeId, true);
            if (e.key === "ArrowLeft" && hasChildren && isOpen) onToggle(nodeId, false);

            if (e.key === "Escape" && menu) setMenu(null);
          }}
          className={[
            "group flex items-center rounded-lg px-2 py-1.5 text-sm",
            isSelected ? "bg-gray-100 ring-1 ring-gray-200" : "hover:bg-gray-50",
            "focus:outline-none focus:ring-2 focus:ring-offset-2",
            isInactive ? "text-gray-700" : "text-gray-900",
          ].join(" ")}
          style={{ paddingLeft: 8 + depth * 16 }}
        >
          <Chevron open={isOpen} disabled={!hasChildren} onClick={() => onToggle(nodeId, !isOpen)} />
          <TypeIcon type={node.type} />
          <div className="min-w-0 flex-1 truncate">
            <span>{renderTitle(node.title)}</span>
            {isInactive ? <span className="ml-2 text-xs text-gray-600">(неактивно)</span> : null}
          </div>

          <KebabButton
            visible={hover}
            enabled={hasAnyActions}
            onClick={(e) => {
              e.stopPropagation();
              if (!hasAnyActions) return;
              const rect = (e.currentTarget as HTMLButtonElement).getBoundingClientRect();
              setMenu({ nodeId, rect });
            }}
          />
        </div>

        {hasChildren && isOpen ? (
          <div role="group" className="mt-1">
            {childrenIds.map((cid) => (
              <Row key={cid} nodeId={cid} depth={depth + 1} />
            ))}
          </div>
        ) : null}
      </div>
    );
  };

  const onClickReset = () => {
    onResetExpand();
    onSearch("");
  };

  return (
    <div className={["w-full rounded-2xl border bg-white", className ?? ""].join(" ")}>
      <div className="flex items-center gap-2 border-b px-3 py-3">
        <div className="text-sm font-medium">{headerTitle}</div>

        <div className="ml-auto flex items-center gap-2">
          <button type="button" onClick={onClickReset} className="rounded-lg border px-2.5 py-1.5 text-sm hover:bg-gray-50">
            Свернуть всё
          </button>
        </div>
      </div>

      <div className="px-3 py-3">
        <div className="flex items-center gap-2">
          <input
            value={searchQuery}
            onChange={(e) => onSearch(e.target.value)}
            placeholder="Поиск по структуре"
            className="w-full rounded-xl border bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-500 outline-none focus:ring-2 focus:ring-offset-2"
          />

          {searchQuery ? (
            <button
              type="button"
              onClick={() => onSearch("")}
              className="rounded-xl border px-3 py-2 text-sm hover:bg-gray-50"
              aria-label="Очистить поиск"
              title="Очистить поиск"
            >
              ✕
            </button>
          ) : null}
        </div>

        <div className="mt-2 flex items-center justify-between">
          <label className="inline-flex select-none items-center gap-2 text-xs text-gray-700">
            <input
              type="checkbox"
              checked={showInactive}
              onChange={(e) => setShowInactive(e.target.checked)}
              className="h-4 w-4 rounded border"
            />
            Показывать неактивные
          </label>

          {searchQuery ? <div className="text-xs text-gray-600">Найдено: {matchIds.size}</div> : null}
        </div>

        <div role="tree" className="mt-3 space-y-1">
          {viewIdx.rootIds.length === 0 ? (
            <div className="rounded-xl border px-3 py-3 text-sm text-gray-700">
              {searchQuery ? "Нет совпадений." : "Нет данных для отображения."}
            </div>
          ) : (
            sortChildren(viewIdx.rootIds).map((rid) => <Row key={rid} nodeId={rid} depth={0} />)
          )}
        </div>
      </div>

      {menu ? (
        <ContextMenu
          anchorRect={menu.rect}
          can={can}
          isInactive={inactiveSet.has(menu.nodeId)}
          onClose={() => setMenu(null)}
          onPick={(action) => {
            const nodeId = menu.nodeId;
            setMenu(null);

            if (action === "add_child") {
              openCreate(nodeId);
              return;
            }

            if (action === "deactivate") {
              void runToggleActive(nodeId, false);
              return;
            }

            if (action === "activate") {
              void runToggleActive(nodeId, true);
              return;
            }

            onAction(nodeId, action);
          }}
        />
      ) : null}

      <Modal open={createModal.open} title="Добавить подразделение" onClose={closeCreate}>
        <div className="space-y-3">
          <div className="text-xs text-gray-600">
            Родитель: <span className="font-medium">{createModal.parentId ?? "-"}</span>
          </div>

          <div className="space-y-1">
            <label className="block text-xs text-gray-700">Название *</label>
            <input
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              className="w-full rounded-xl border bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-offset-2"
              placeholder="Например: Секция внутреннего обучения"
              disabled={createBusy}
            />
          </div>

          {createErr ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{createErr}</div>
          ) : null}

          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={closeCreate}
              disabled={createBusy}
              className="rounded-xl border px-3 py-2 text-sm hover:bg-gray-50 disabled:opacity-50"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => void submitCreate()}
              disabled={createBusy}
              className="rounded-xl border bg-gray-900 px-3 py-2 text-sm text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {createBusy ? "Создание..." : "Создать"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
