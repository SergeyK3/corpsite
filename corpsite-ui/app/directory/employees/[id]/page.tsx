// ROUTE: /directory/employees/[id]
// FILE: corpsite-ui/app/directory/employees/[id]/page.tsx

"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { getEmployee } from "../_lib/api.client";
import type { EmployeeDTO } from "../_lib/types";

type LoadState =
  | { status: "idle" | "loading" }
  | { status: "ok"; item: EmployeeDTO }
  | { status: "error"; message: string };

function fmt(v: unknown): string {
  if (v == null) return "—";
  const s = String(v).trim();
  return s ? s : "—";
}

export default function EmployeeDetailsPage() {
  const params = useParams<{ id: string }>();
  const id = useMemo(() => String(params?.id || "").trim(), [params]);

  const [state, setState] = useState<LoadState>({ status: "idle" });

  useEffect(() => {
    if (!id) return;

    let cancelled = false;
    setState({ status: "loading" });

    (async () => {
      try {
        const item = await getEmployee(id);
        if (cancelled) return;
        setState({ status: "ok", item });
      } catch (e: any) {
        if (cancelled) return;
        const msg =
          typeof e?.message === "string" && e.message
            ? e.message
            : "Не удалось загрузить сотрудника";
        setState({ status: "error", message: msg });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [id]);

  if (!id) {
    return (
      <div style={{ padding: 16 }}>
        <h1 style={{ margin: 0, fontSize: 18 }}>Сотрудник</h1>
        <p style={{ marginTop: 12 }}>Некорректный идентификатор.</p>
      </div>
    );
  }

  if (state.status === "idle" || state.status === "loading") {
    return (
      <div style={{ padding: 16 }}>
        <h1 style={{ margin: 0, fontSize: 18 }}>Сотрудник {id}</h1>
        <p style={{ marginTop: 12 }}>Загрузка…</p>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div style={{ padding: 16 }}>
        <h1 style={{ margin: 0, fontSize: 18 }}>Сотрудник {id}</h1>
        <p style={{ marginTop: 12, color: "crimson" }}>{state.message}</p>
      </div>
    );
  }

  if (state.status !== "ok") {
    return null;
  }

  const e = state.item;

  return (
    <div style={{ padding: 16, display: "grid", gap: 12 }}>
      <h1 style={{ margin: 0, fontSize: 18 }}>{fmt(e.fio)}</h1>

      <div
        style={{
          border: "1px solid #e5e7eb",
          borderRadius: 12,
          padding: 12,
          display: "grid",
          gap: 8,
        }}
      >
        <Row label="ID" value={e.id} />
        <Row label="Отдел" value={e.department?.name} />
        <Row label="Должность" value={e.position?.name} />
        <Row label="Ставка" value={e.rate} />
        <Row label="Статус" value={e.status} />
        <Row label="Дата с" value={e.date_from} />
        <Row label="Дата по" value={e.date_to} />
      </div>
    </div>
  );
}

function Row(props: { label: string; value: unknown }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: 12 }}>
      <div style={{ color: "#6b7280" }}>{props.label}</div>
      <div>{fmt(props.value)}</div>
    </div>
  );
}
