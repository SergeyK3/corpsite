// FILE: corpsite-ui/components/TenantTitle.tsx
"use client";

import { useEffect, useState } from "react";

type TenantCfg = { orgName?: string };

export default function TenantTitle() {
  const [orgName, setOrgName] = useState<string>("");

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch("/tenant.json", { cache: "no-store" });
        if (!res.ok) return;
        const json = (await res.json()) as TenantCfg;
        const name = String(json?.orgName ?? "").trim();
        if (!cancelled) setOrgName(name);
      } catch {
        // ignore
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return <span>{"Система личных кабинетов" + (orgName ? ` ${orgName}` : "")}</span>;
}
