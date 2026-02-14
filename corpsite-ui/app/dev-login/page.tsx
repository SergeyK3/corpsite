"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

const STORAGE_KEY = "user_id";

function toUserId(v: string, fallback = 1) {
  const n = Number(String(v ?? "").trim());
  if (!Number.isFinite(n)) return fallback;
  const i = Math.trunc(n);
  return i > 0 ? i : fallback;
}

export default function DevLoginPage() {
  const router = useRouter();

  const [input, setInput] = useState("1");
  const [current, setCurrent] = useState(1);

  // При загрузке страницы — читаем sessionStorage и синхронизируем UI
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      const uid = toUserId(raw ?? "1", 1);
      setCurrent(uid);
      setInput(String(uid));
    } catch {
      // ignore
    }
  }, []);

  const apply = () => {
    const uid = toUserId(input, 1);
    try {
      sessionStorage.setItem(STORAGE_KEY, String(uid)); // <-- КРИТИЧНО
    } catch {
      // ignore
    }
    setCurrent(uid);
    setInput(String(uid));
  };

  const reset = () => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
    setCurrent(1);
    setInput("1");
  };

  const goTasksThisWindow = () => {
    apply();
    router.push("/tasks");
  };

  const openTasksNewWindow = () => {
    apply();
    window.open("/tasks", "_blank", "noopener,noreferrer");
  };

  const quick = useMemo(() => [1, 2, 4, 5], []);

  const openWorkplace = (uid: number) => {
    const w = window.open("/dev-login", "_blank", "noopener,noreferrer");
    if (!w) return;

    const started = Date.now();
    const timer = window.setInterval(() => {
      try {
        if (Date.now() - started > 5000) {
          window.clearInterval(timer);
          return;
        }
        w.sessionStorage.setItem(STORAGE_KEY, String(uid));
        w.location.href = "/tasks";
        window.clearInterval(timer);
      } catch {
        // окно ещё не готово — пробуем снова
      }
    }, 80);
  };

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 16px" }}>
      <h1 style={{ fontSize: 34, fontWeight: 700, marginBottom: 10 }}>
        Dev Login (рабочие места)
      </h1>

      <div style={{ marginBottom: 10 }}>
        Текущий user_id для этого окна: <b>{current}</b>
      </div>

      <div style={{ marginBottom: 18, color: "#555" }}>
        Используется <b>sessionStorage</b>, поэтому разные окна/вкладки могут быть под разными ролями.
      </div>

      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 14 }}>
        <label style={{ minWidth: 70 }}>user_id:</label>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          inputMode="numeric"
          style={{ width: 120, padding: "8px 10px", border: "1px solid #ccc", borderRadius: 6 }}
        />

        <button type="button" onClick={apply} style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #ccc", background: "#fff" }}>
          Применить
        </button>

        <button type="button" onClick={reset} style={{ padding: "8px 14px", borderRadius: 8, border: "1px solid #ccc", background: "#fff" }}>
          Сбросить
        </button>
      </div>

      <div style={{ display: "flex", gap: 22, marginBottom: 18 }}>
        <button type="button" onClick={goTasksThisWindow} style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}>
          Перейти в /tasks (в этом окне)
        </button>

        <button type="button" onClick={openTasksNewWindow} style={{ padding: "10px 14px", borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}>
          Открыть /tasks (в новом окне)
        </button>
      </div>

      <hr style={{ border: "none", borderTop: "1px solid #eee", margin: "18px 0" }} />

      <div style={{ marginBottom: 10, fontWeight: 700 }}>
        Быстрые “рабочие места” (открывают новое окно):
      </div>

      <div style={{ display: "flex", gap: 18, flexWrap: "wrap", marginBottom: 18 }}>
        {quick.map((uid) => (
          <button
            key={uid}
            type="button"
            onClick={() => openWorkplace(uid)}
            style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #ccc", background: "#fff" }}
          >
            user_id={uid}
          </button>
        ))}
      </div>
    </div>
  );
}
