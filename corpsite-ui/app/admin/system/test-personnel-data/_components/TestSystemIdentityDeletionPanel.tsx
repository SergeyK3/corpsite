"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { MeInfo } from "@/lib/types";
import {
  previewSystemIdentities,
  probeSystemIdentityDeletionAccess,
  searchSystemIdentities,
  type SystemIdentityObjectType,
  type SystemIdentityPreviewResponse,
  type SystemIdentitySearchField,
  type SystemIdentitySearchItem,
  type SystemIdentityTarget,
} from "@/lib/testSystemIdentityDeletion";

const BUTTON = "rounded-lg bg-blue-700 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50";
const TYPE_LABELS: Record<SystemIdentityObjectType, string> = { USER: "Пользователи", ROLE: "Роли" };
const FIELDS: Record<SystemIdentityObjectType, Array<{ value: SystemIdentitySearchField; label: string }>> = {
  USER: [{ value: "full_name", label: "Имя" }, { value: "login", label: "Логин" }],
  ROLE: [{ value: "name", label: "Название" }, { value: "code", label: "Код" }],
};

const BLOCKING_LABELS: Record<string, string> = {
  TEST_SYSTEM_IDENTITY_PROVENANCE_REQUIRED: "Нет подтверждённого тестового provenance",
  HISTORICAL_AUTHORSHIP_PROTECTED: "Защищённая техническая учётная запись HISTORICAL_AUTHORSHIP",
  EMPLOYEE_LINK_PRESENT: "Пользователь связан с Employee",
  PERSON_LINK_PRESENT: "Пользователь связан с Person",
  CANONICAL_ROLE_PROTECTED: "Каноническая роль защищена",
  ACTIVE_ROLE_PROTECTED: "Активная роль защищена",
  ROLE_USED_BY_USERS: "Роль используется пользователями",
};

const CLASS_LABELS: Record<string, string> = {
  BLOCKING: "Блокирующая",
  PRESERVE: "Сохраняемая",
  REBIND_HISTORICAL_AUTHORSHIP: "Будущая перепривязка к HISTORICAL_AUTHORSHIP",
  DELETE_ALLOWLIST: "Будущий точный DELETE allowlist",
};

function targetKey(target: SystemIdentityTarget): string {
  return `${target.object_type}:${target.object_id}`;
}

function errorStatus(error: unknown): number | undefined {
  return typeof error === "object" && error !== null && "status" in error
    ? Number((error as { status?: unknown }).status)
    : undefined;
}

function errorMessage(error: unknown): string {
  if (typeof error === "object" && error !== null) {
    const details = (error as { details?: { detail?: { message?: unknown } } }).details;
    const backendMessage = details?.detail?.message;
    if (backendMessage === "Mask length must be between 3 and 100.") {
      return "Маска должна содержать от 3 до 100 символов";
    }
    if (typeof backendMessage === "string" && backendMessage.trim()) return backendMessage;
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return "Не удалось выполнить безопасную предварительную проверку.";
}

function shortHash(value: string): string {
  return value.length > 18 ? `${value.slice(0, 10)}…${value.slice(-8)}` : value;
}

export default function TestSystemIdentityDeletionPanel({ me }: { me: MeInfo | null }) {
  const explicitCapability = me?.can_request_test_system_identity_deletion;
  const [access, setAccess] = useState<"checking" | "allowed" | "denied">(
    me?.role_code === "HR_HEAD" ? "denied" : explicitCapability === true ? "allowed" : "checking",
  );
  const [objectType, setObjectType] = useState<SystemIdentityObjectType>("USER");
  const [field, setField] = useState<SystemIdentitySearchField>("full_name");
  const [selector, setSelector] = useState("");
  const [results, setResults] = useState<SystemIdentitySearchItem[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [preview, setPreview] = useState<SystemIdentityPreviewResponse | null>(null);
  const [searchComplete, setSearchComplete] = useState(false);
  const [busy, setBusy] = useState<"search" | "preview" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const accessSequence = useRef(0);

  useEffect(() => {
    const sequence = ++accessSequence.current;
    if (me?.role_code === "HR_HEAD" || explicitCapability === false) {
      setAccess("denied");
      return;
    }
    if (explicitCapability === true) {
      setAccess("allowed");
      return;
    }
    if (!me || me.can_request_test_personnel_deletion !== true) {
      setAccess("denied");
      return;
    }
    setAccess("checking");
    void probeSystemIdentityDeletionAccess()
      .then(() => { if (sequence === accessSequence.current) setAccess("allowed"); })
      .catch((caught) => {
        if (sequence !== accessSequence.current) return;
        setAccess([401, 403].includes(errorStatus(caught) ?? 0) ? "denied" : "allowed");
      });
  }, [explicitCapability, me]);

  const selectedTargets = useMemo(
    () => results
      .filter((item) => selected.has(targetKey(item)))
      .map(({ object_type, object_id }) => ({ object_type, object_id })),
    [results, selected],
  );

  if (access !== "allowed") return null;

  function chooseType(nextType: SystemIdentityObjectType) {
    setObjectType(nextType);
    setField(FIELDS[nextType][0].value);
    setSelector("");
    setResults([]);
    setSelected(new Set());
    setPreview(null);
    setSearchComplete(false);
    setError(null);
  }

  async function runSearch() {
    const value = selector.trim();
    if (!value || busy) return;
    setBusy("search");
    setError(null);
    setPreview(null);
    try {
      const response = await searchSystemIdentities({ objectType, field, selector: value });
      setResults(response.items);
      setSelected(new Set());
      setSearchComplete(true);
    } catch (caught) {
      setResults([]);
      setSelected(new Set());
      setSearchComplete(false);
      setError(errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  async function runPreview() {
    if (!selectedTargets.length || busy) return;
    setBusy("preview");
    setError(null);
    try {
      setPreview(await previewSystemIdentities(selectedTargets));
    } catch (caught) {
      setPreview(null);
      setError(errorMessage(caught));
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="space-y-4 border-t border-zinc-200 pt-6 dark:border-zinc-800" aria-labelledby="system-identities-title" data-testid="system-identity-deletion-panel">
      <header>
        <h2 id="system-identities-title" className="text-xl font-semibold">Системные пользователи и роли</h2>
        <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
          Только поиск и предварительная проверка. Маска не переносится в точный список и не изменяет данные.
        </p>
      </header>

      <div className="inline-flex rounded-lg border border-zinc-300 p-1 dark:border-zinc-700" role="group" aria-label="Тип системной записи">
        {(["USER", "ROLE"] as const).map((type) => (
          <button
            key={type}
            type="button"
            aria-pressed={objectType === type}
            onClick={() => chooseType(type)}
            className={`rounded-md px-3 py-1.5 text-sm font-semibold ${objectType === type ? "bg-blue-700 text-white" : "hover:bg-zinc-100 dark:hover:bg-zinc-900"}`}
          >
            {TYPE_LABELS[type]}
          </button>
        ))}
      </div>

      <form className="flex flex-wrap items-start gap-2" onSubmit={(event) => { event.preventDefault(); void runSearch(); }}>
        <label className="text-sm">
          Поле поиска
          <select value={field} onChange={(event) => setField(event.target.value as SystemIdentitySearchField)} className="mt-1 block rounded-lg border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700">
            {FIELDS[objectType].map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        <div className="min-w-72 flex-1 text-sm">
          <label htmlFor="system-identity-selector">Маска */? или точный технический ID</label>
          <input id="system-identity-selector" value={selector} onChange={(event) => setSelector(event.target.value)} required aria-describedby="system-identity-mask-hint" className="mt-1 w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700" placeholder={objectType === "USER" ? "Например: test* или 104" : "Например: TEST_* или 27"} />
          <span id="system-identity-mask-hint" className="mt-1 block text-xs text-zinc-600 dark:text-zinc-400">Введите от 3 до 100 символов. Поддерживаются маски * и ?</span>
        </div>
        <button type="submit" className={`${BUTTON} mt-6`} disabled={!selector.trim() || busy !== null}>{busy === "search" ? "Поиск…" : "Найти"}</button>
      </form>

      {error ? <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-900">{error}</p> : null}

      {results.length ? (
        <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-zinc-50 dark:bg-zinc-900"><tr><th className="p-3">Выбор</th><th className="p-3">Технический ID</th><th className="p-3">Запись</th><th className="p-3">Логин / код</th></tr></thead>
            <tbody>{results.map((item) => {
              const key = targetKey(item);
              return <tr key={key} className="border-t border-zinc-200 dark:border-zinc-800">
                <td className="p-3"><input type="checkbox" aria-label={`Выбрать ${item.label}, ${item.object_type} #${item.object_id}`} checked={selected.has(key)} onChange={() => setSelected((current) => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); setPreview(null); return next; })} /></td>
                <td className="p-3 font-mono">{item.object_type} #{item.object_id}</td>
                <td className="p-3 font-medium">{item.label}</td>
                <td className="p-3">{item.secondary_label ?? "—"}</td>
              </tr>;
            })}</tbody>
          </table>
        </div>
      ) : searchComplete ? <p className="rounded-lg border border-dashed p-4 text-sm">Подтверждённые тестовые записи не найдены.</p> : <p className="text-sm text-zinc-600">Найдите записи и выберите точные технические ID.</p>}

      <div className="flex flex-wrap items-center gap-3">
        <button type="button" className={BUTTON} disabled={!selectedTargets.length || busy !== null} onClick={() => void runPreview()}>{busy === "preview" ? "Проверка…" : "Предварительная проверка"}</button>
        <span className="text-sm text-zinc-600">Выбрано: {selectedTargets.length}</span>
      </div>

      {preview ? (
        <section className="space-y-3" aria-labelledby="system-preview-results-title">
          <h3 id="system-preview-results-title" className="text-lg font-semibold">Результат предварительной проверки</h3>
          <p className="text-xs text-zinc-600">Точный список: <code>{shortHash(preview.target_list_hash)}</code>; fingerprint связей: <code>{shortHash(preview.relationship_fingerprint)}</code></p>
          <div className="grid gap-3">
            {preview.items.map((item) => (
              <article key={targetKey(item)} className="space-y-3 rounded-xl border border-zinc-200 p-4 dark:border-zinc-800">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div><h4 className="font-semibold">{item.label}</h4><p className="font-mono text-sm">{item.object_type} #{item.object_id}{item.secondary_label ? ` · ${item.secondary_label}` : ""}</p></div>
                  <p role="status" className="font-semibold" aria-label={item.ready_for_deletion ? "Статус: можно включить в запрос" : "Статус: удаление заблокировано"}>
                    <span aria-hidden="true">{item.ready_for_deletion ? "✓" : "⛔"}</span>{" "}{item.ready_for_deletion ? "Можно включить в запрос" : "Удаление заблокировано"}
                  </p>
                </div>
                <p className="text-sm"><span className="font-semibold">Provenance:</span> {item.has_test_provenance ? "подтверждено" : "отсутствует"}</p>
                {item.blocking_codes.length ? <div><p className="text-sm font-semibold">Причины блокировки</p><ul className="list-disc pl-5 text-sm">{item.blocking_codes.map((code) => <li key={code}>{BLOCKING_LABELS[code] ?? code}</li>)}</ul></div> : null}
                <div>
                  <p className="text-sm font-semibold">Связанные данные</p>
                  {item.relationships.length ? <ul className="mt-1 space-y-1 text-sm">{item.relationships.map((relation) => <li key={relation.relation_code}><span className="font-medium">{CLASS_LABELS[relation.classification] ?? relation.classification}:</span> {relation.table}.{relation.columns.join(", ")} — строк: {relation.count}</li>)}</ul> : <p className="text-sm text-zinc-600">Связи не найдены.</p>}
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </section>
  );
}
