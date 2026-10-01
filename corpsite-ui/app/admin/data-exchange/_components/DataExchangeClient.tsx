"use client";

import { ChangeEvent, useEffect, useState } from "react";
import { buildHeaders, readJsonSafe, toApiError } from "@/lib/api";
import { resolveApiUrl } from "@/lib/apiBase";

type Scenario = {
  code: string;
  schema_version: string;
  label: string;
  accepted_suffixes: string[];
  max_bytes: number;
  atomic_apply: boolean;
  available?: boolean;
  export_only?: boolean;
  reason?: string;
};

type Package = {
  package_id: number;
  status: string;
  content_sha256: string;
  schema_version: string;
  dry_run_target_fingerprint?: string | null;
  counters?: Record<string, number>;
};

function headers(): HeadersInit {
  return buildHeaders({ Accept: "application/json" });
}

async function read<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(resolveApiUrl(path), { cache: "no-store", ...init });
  const body = await readJsonSafe(response);
  if (!response.ok) throw toApiError(response.status, body);
  return body as T;
}

export default function DataExchangeClient() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenario, setScenario] = useState("");
  const [packageInfo, setPackageInfo] = useState<Package | null>(null);
  const [message, setMessage] = useState("Выберите зарегистрированный сценарий и файл.");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void read<{ items: Scenario[] }>("/directory/personnel/data-exchange/scenarios", { headers: headers() })
      .then((result) => { setScenarios(result.items); setScenario(result.items.find((item) => item.available !== false && !item.export_only)?.code ?? ""); })
      .catch(() => setMessage("Нет разрешения на просмотр сценариев импорта и экспорта."));
  }, []);

  async function upload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !scenario) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(resolveApiUrl(`/directory/personnel/data-exchange/packages?scenario_code=${encodeURIComponent(scenario)}`), {
        method: "POST", headers: headers(), body: form,
      });
      const body = await readJsonSafe(response);
      if (!response.ok) throw toApiError(response.status, body);
      const result = body as { duplicate: boolean; package: Package };
      setPackageInfo(result.package);
      setMessage(result.duplicate ? "Этот файл уже зарегистрирован; используйте существующий пакет." : "Файл зарегистрирован. Запустите предпросмотр.");
    } catch {
      setMessage("Не удалось безопасно зарегистрировать файл.");
    } finally { setBusy(false); }
  }

  async function transition(action: "preview" | "dry-run" | "confirm" | "apply") {
    if (!packageInfo) return;
    setBusy(true);
    try {
      const body = action === "confirm" ? JSON.stringify({
        expected_sha256: packageInfo.content_sha256,
        expected_schema_version: packageInfo.schema_version,
        expected_target_fingerprint: packageInfo.dry_run_target_fingerprint,
      }) : undefined;
      const result = await read<Package | { package: Package }>(`/directory/personnel/data-exchange/packages/${packageInfo.package_id}/${action}`, {
        method: "POST", headers: body ? buildHeaders({ "Content-Type": "application/json", Accept: "application/json" }) : headers(), body,
      });
      const next = "package" in result ? result.package : result;
      setPackageInfo(next);
      setMessage(`Операция выполнена: ${next.status}.`);
    } catch { setMessage("Операция заблокирована. Проверьте статус и предпросмотр пакета."); }
    finally { setBusy(false); }
  }

  async function downloadReference() {
    try {
      const response = await fetch(resolveApiUrl("/directory/personnel/data-exchange/employee-reference"), { headers: headers() });
      if (!response.ok) throw new Error("blocked");
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = "corpsite_employee_reference.xlsx"; anchor.click(); URL.revokeObjectURL(url);
    } catch { setMessage("Экспорт эталона недоступен для текущего пользователя."); }
  }

  return <main className="mx-auto max-w-5xl space-y-5 p-6">
    <h1 className="text-xl font-semibold">Импорт и экспорт данных</h1>
    <p className="text-sm text-slate-600">Только зарегистрированные сценарии. Загрузка и проверка не изменяют кадровые данные.</p>
    <section className="rounded border p-4 space-y-3" aria-label="Зарегистрированные сценарии">
      <label className="block text-sm font-medium">Сценарий
        <select className="mt-1 block w-full rounded border p-2" value={scenario} onChange={(event) => setScenario(event.target.value)} disabled={busy}>
          {scenarios.map((item) => <option key={item.code} value={item.code} disabled={item.available === false || item.export_only}>{item.label} — {item.schema_version}{item.available === false ? " (пока недоступно)" : ""}</option>)}
        </select>
      </label>
      <label className="block text-sm font-medium">Файл
        <input aria-label="Файл импорта" className="mt-1 block w-full" type="file" accept=".xlsx" onChange={upload} disabled={busy || !scenario} />
      </label>
      <button type="button" onClick={downloadReference} className="rounded border px-3 py-2 text-sm">Экспорт эталонного списка сотрудников</button>
    </section>
    <section className="rounded border p-4 space-y-3" aria-live="polite">
      <p>{message}</p>
      {packageInfo && <>
        <p className="text-sm">Пакет #{packageInfo.package_id}; SHA-256: <code>{packageInfo.content_sha256}</code>; статус: {packageInfo.status}</p>
        {packageInfo.counters && <p className="text-sm">Строк: {packageInfo.counters.total ?? 0}; заблокировано: {packageInfo.counters.blocked ?? 0}</p>}
        <div className="flex flex-wrap gap-2">
          <button type="button" className="rounded border px-3 py-2" onClick={() => transition("preview")} disabled={busy}>Предпросмотр</button>
          <button type="button" className="rounded border px-3 py-2" onClick={() => transition("dry-run")} disabled={busy}>Dry-run</button>
          <button type="button" className="rounded border px-3 py-2" onClick={() => transition("confirm")} disabled={busy}>Подтвердить</button>
          <button type="button" className="rounded bg-slate-800 px-3 py-2 text-white" onClick={() => transition("apply")} disabled={busy}>Применить</button>
        </div>
      </>}
    </section>
  </main>;
}
