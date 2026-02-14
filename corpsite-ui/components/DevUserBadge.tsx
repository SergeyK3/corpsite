// FILE: corpsite-ui/components/DevUserBadge.tsx
"use client";

import { useEffect, useState } from "react";
import { getDevUserId } from "../lib/dev_user";

export default function DevUserBadge() {
  const [uid, setUid] = useState<number>(0);

  useEffect(() => {
    const read = () => setUid(getDevUserId(1));
    read();

    // обновлять при возврате во вкладку
    window.addEventListener("focus", read);

    // обновлять при смене ключа в sessionStorage (в пределах текущей вкладки это событие не стреляет,
    // но пусть будет на случай иных сценариев)
    window.addEventListener("storage", read);

    return () => {
      window.removeEventListener("focus", read);
      window.removeEventListener("storage", read);
    };
  }, []);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div
        title="Текущий user_id (sessionStorage, per-окно)"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 10px",
          borderRadius: 999,
          border: "1px solid rgba(0,0,0,0.15)",
          background: "rgba(0,0,0,0.03)",
          fontSize: 13,
          lineHeight: "16px",
          whiteSpace: "nowrap",
        }}
      >
        <span style={{ opacity: 0.75 }}>user_id</span>
        <b>{uid || 1}</b>
      </div>

      <a
        href="/dev-login"
        style={{
          fontSize: 13,
          textDecoration: "underline",
          opacity: 0.85,
          whiteSpace: "nowrap",
        }}
        title="Сменить user_id в этом окне"
      >
        сменить
      </a>
    </div>
  );
}
