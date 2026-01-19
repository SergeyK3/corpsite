// corpsite-ui/app/directory/org/page.tsx

"use client";

import React, { useEffect, useMemo, useState } from "react";

/**
 * IMPORTANT:
 * In your project, there is no app/api layer.
 * Directory API lives under: app/directory/employees/_lib/
 *
 * If your real file name differs, adjust ONLY this import path.
 */
import { getOrgTree, OrgTreeNode, OrgTreeResponse } from "../employees/_lib/directory";

function flatten(nodes: OrgTreeNode[], out: OrgTreeNode[] = []): OrgTreeNode[] {
  for (const n of nodes) {
    out.push(n);
    if (n.children?.length) flatten(n.children, out);
  }
  return out;
}

function TreeNode({
  node,
  level,
  selectedId,
  onSelect,
}: {
  node: OrgTreeNode;
  level: number;
  selectedId: number | null;
  onSelect: (n: OrgTreeNode) => void;
}) {
  const [open, setOpen] = useState<boolean>(true);
  const hasChildren = (node.children?.length || 0) > 0;
  const isSelected = selectedId === node.id;

  return (
    <div style={{ marginLeft: level * 12 }}>
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "center",
          padding: "6px 8px",
          borderRadius: 8,
          cursor: "pointer",
          background: isSelected ? "rgba(0,0,0,0.06)" : "transparent",
        }}
        onClick={() => onSelect(node)}
      >
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            if (hasChildren) setOpen((v) => !v);
          }}
          style={{
            width: 22,
            height: 22,
            borderRadius: 6,
            border: "1px solid rgba(0,0,0,0.15)",
            background: "white",
            cursor: hasChildren ? "pointer" : "default",
            opacity: hasChildren ? 1 : 0.35,
          }}
          aria-label={open ? "Collapse" : "Expand"}
          title={open ? "Collapse" : "Expand"}
        >
          {hasChildren ? (open ? "−" : "+") : "•"}
        </button>

        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontWeight: 600 }}>{node.name}</div>
          <div style={{ fontSize: 12, opacity: 0.7 }}>
            id={node.id}
            {node.code ? ` · code=${node.code}` : ""}
          </div>
        </div>
      </div>

      {hasChildren && open && (
        <div style={{ marginTop: 2 }}>
          {node.children!.map((ch) => (
            <TreeNode
              key={ch.id}
              node={ch}
              level={level + 1}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function OrgPage() {
  const [data, setData] = useState<OrgTreeResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [err, setErr] = useState<string>("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;

    (async () => {
      setLoading(true);
      setErr("");
      try {
        const res = await getOrgTree();
        if (!alive) return;
        setData(res);

        const all = flatten(res.items);
        if (all.length) setSelectedId(all[0].id);
      } catch (e: any) {
        if (!alive) return;
        setErr(e?.message || String(e));
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    })();

    return () => {
      alive = false;
    };
  }, []);

  const flat = useMemo(() => (data ? flatten(data.items, []) : []), [data]);

  const selectedInfo = useMemo(() => {
    if (!data || selectedId === null) return null;
    return flat.find((x) => x.id === selectedId) || null;
  }, [data, selectedId, flat]);

  return (
    <div style={{ padding: 16, display: "grid", gridTemplateColumns: "420px 1fr", gap: 16 }}>
      <div style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 12 }}>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 10 }}>Оргструктура</div>

        {loading && <div>Загрузка…</div>}

        {err && (
          <div style={{ color: "crimson", whiteSpace: "pre-wrap" }}>
            Ошибка: {err}
          </div>
        )}

        {!loading && !err && data && (
          <div>
            {data.items.map((n) => (
              <TreeNode
                key={n.id}
                node={n}
                level={0}
                selectedId={selectedId}
                onSelect={(node) => setSelectedId(node.id)}
              />
            ))}
          </div>
        )}
      </div>

      <div style={{ border: "1px solid rgba(0,0,0,0.12)", borderRadius: 12, padding: 12 }}>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 10 }}>Сводка</div>

        {!selectedInfo ? (
          <div style={{ opacity: 0.7 }}>Выберите подразделение в дереве.</div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            <div>
              <div style={{ fontSize: 12, opacity: 0.7 }}>Подразделение</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{selectedInfo.name}</div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div style={{ border: "1px solid rgba(0,0,0,0.10)", borderRadius: 10, padding: 10 }}>
                <div style={{ fontSize: 12, opacity: 0.7 }}>unit_id</div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{selectedInfo.id}</div>
              </div>
              <div style={{ border: "1px solid rgba(0,0,0,0.10)", borderRadius: 10, padding: 10 }}>
                <div style={{ fontSize: 12, opacity: 0.7 }}>code</div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{selectedInfo.code || "—"}</div>
              </div>
            </div>

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <a
                href={`/directory/employees?org_unit_id=${encodeURIComponent(String(selectedInfo.id))}&include_children=true&status=all`}
                style={{
                  display: "inline-block",
                  padding: "10px 12px",
                  borderRadius: 10,
                  border: "1px solid rgba(0,0,0,0.15)",
                  textDecoration: "none",
                  fontWeight: 600,
                }}
              >
                Сотрудники (с подотделами)
              </a>

              <a
                href={`/directory/employees?org_unit_id=${encodeURIComponent(String(selectedInfo.id))}&include_children=false&status=all`}
                style={{
                  display: "inline-block",
                  padding: "10px 12px",
                  borderRadius: 10,
                  border: "1px solid rgba(0,0,0,0.15)",
                  textDecoration: "none",
                  fontWeight: 600,
                }}
              >
                Сотрудники (только узел)
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
